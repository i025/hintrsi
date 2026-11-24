#!/usr/bin/env python3
"""Run one local fake-API SDK read/edit/test probe in a new VM lane."""

import io
import json
import tarfile
import time
from pathlib import Path

import docker
import pyarrow.parquet as pq

ROOT = Path('/srv/lab-disks/disk2/users/xymo/hint-codex-experiments')
OUT = ROOT / 'preflight/parallel_runtime/lane1_sdk_gate'
PYTHON = '/opt/python3.12-tmp/bin/python3'
CLI = '/opt/python3.12-tmp/lib/python3.12/site-packages/claude_agent_sdk/_bundled/claude'


def put_file(container, target, content):
    content = content.encode() if isinstance(content, str) else content
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        item = tarfile.TarInfo(Path(target).name)
        item.size = len(content)
        archive.addfile(item, io.BytesIO(content))
    container.put_archive(str(Path(target).parent), stream.getvalue())


def collect(container, path):
    chunks, _ = container.get_archive(path)
    with tarfile.open(fileobj=io.BytesIO(b''.join(chunks))) as archive:
        for item in archive.getmembers():
            if item.isfile():
                (OUT / Path(item.name).name).write_bytes(archive.extractfile(item).read())


def main():
    OUT.mkdir()
    client = docker.DockerClient(base_url='unix://' + str(ROOT / 'vm-lane1/docker.sock'), timeout=420)
    row = next(row for row in pq.read_table(ROOT.parent / 'hint-baseline-run/data/deep_swe_tasks.parquet').to_pylist()
               if row['instance_id'] == 'obsidian-linter-auto-table-of-contents')
    image = client.images.get(row['image_name'])
    env = {item.split('=', 1)[0]: 'offline-fixture' for item in image.attrs['Config'].get('Env', [])
           if any(word in item.split('=', 1)[0].upper() for word in
                  ('KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'ANTHROPIC', 'OPENAI', 'OFOX', 'HUBROUTER'))}
    env.update({'ANTHROPIC_BASE_URL':'http://127.0.0.1:8767', 'ANTHROPIC_AUTH_TOKEN':'offline-fixture',
        'ANTHROPIC_MODEL':'gpt-6.1-terra', 'ANTHROPIC_SMALL_FAST_MODEL':'gpt-6.1-terra',
        'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC':'1', 'IS_SANDBOX':'1',
        'API_TIMEOUT_MS':'60000', 'PYTHONDONTWRITEBYTECODE':'1', 'SYSTEM_PROMPT_FILE':'',
        'HTTP_PROXY':'', 'HTTPS_PROXY':'', 'ALL_PROXY':'', 'http_proxy':'',
        'https_proxy':'', 'all_proxy':'', 'NO_PROXY':'*'})
    container = client.containers.run(image.id, name='codex-parallel-lane1-offline',
        entrypoint='', command=['tail','-f','/dev/null'], detach=True,
        mem_limit='128g', nano_cpus=8_000_000_000, privileged=True, network_mode='none',
        environment=env, volumes={'/opt/hint-codex-runtime/python':{'bind':'/opt/python3.12-tmp','mode':'ro'}})
    record = {'container':container.id, 'started_at_unix':time.time(), 'real_model_calls':0,
              'synthetic_usage_excluded':True, 'network':'none', 'cpus':8, 'memory':'128g'}
    try:
        code, output = container.exec_run(['bash','-c','rm -rf /app /root/.claude; mkdir -p /app /tmp/stress_out /tmp/prompts /tmp/cases'])
        assert code == 0, output.decode()
        for local, remote in [(ROOT/'source/run_cc_sdk.py','/tmp/sdk_script.py'),
            (ROOT/'source/logging_utils.py','/tmp/logging_utils.py'),
            (ROOT/'preflight/sdk_hook_fixture/probe.py','/tmp/hook_fixture.py'),
            (ROOT/'preflight/sdk_sigsegv_diagnosis/guest_stress.py','/tmp/guest_stress.py')]:
            put_file(container, remote, local.read_bytes())
        case = {'name':'preflight-parallel-lane1','mode':'short','jit_off':True,'hook':False,'resume':True}
        put_file(container,'/tmp/cases/probe.json',json.dumps(case))
        put_file(container,'/tmp/prompts/short.txt','Complete the offline local SDK tool fixture and report its local test result.')
        code, output = container.exec_run([PYTHON,'-c',
            "import json,platform;from pathlib import Path;from importlib.metadata import version;print(json.dumps({'python':platform.python_version(),'sdk':version('claude-agent-sdk'),'litellm':version('litellm'),'kernel':platform.release(),'cpu_max':Path('/sys/fs/cgroup/cpu.max').read_text().strip(),'memory_max':Path('/sys/fs/cgroup/memory.max').read_text().strip()}))"])
        assert code == 0, output.decode()
        record['runtime'] = json.loads(output)
        code, output = container.exec_run(['timeout','90',CLI,'--version'])
        assert code == 0, output.decode()
        record['cli_version'] = output.decode().strip()
        started = time.monotonic()
        code, output = container.exec_run(['timeout','--signal=INT','--kill-after=20','230',PYTHON,
            '/tmp/guest_stress.py','/tmp/cases/probe.json'],workdir='/app')
        (OUT/'stdout.log').write_bytes(output)
        collect(container,'/tmp/stress_out/preflight-parallel-lane1')
        result = json.loads((OUT/'result.json').read_text())
        assert code == 0 and result['passed'], result
        messages = json.loads((OUT/'sdk_messages.json').read_text())
        for phase in ['initial','resume']:
            tools = [block for row in messages if row['phase'] == phase
                for block in row['message'].get('content',[]) if isinstance(block,dict) and block.get('tool_use_id')]
            assert {block['tool_use_id'] for block in tools} == {phase+'-read-0',phase+'-edit',phase+'-test'}
            assert all(not block.get('is_error') for block in tools)
            assert 'LOCAL_TEST_PASSED' in next(block['content'] for block in tools if block['tool_use_id']==phase+'-test')
        record.update(passed=True,host_exec_seconds=time.monotonic()-started,
                      same_sdk_session=result['sessions'][0] == result['sessions'][1],
                      actual_successful_tools=6)
    finally:
        container.remove(force=True)
        client.close()
        record['container_removed'] = True
        record['finished_at_unix'] = time.time()
        (OUT/'host_result.json').write_text(json.dumps(record,indent=2)+'\n')
        print(json.dumps(record),flush=True)


if __name__ == '__main__':
    main()
