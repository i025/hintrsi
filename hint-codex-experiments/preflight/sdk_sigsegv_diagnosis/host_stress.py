#!/usr/bin/env python3
"""Compare the unchanged native CLI with its JIT disabled, using no models."""

import io
import json
import subprocess
import tarfile
import time
from pathlib import Path

import docker
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
NAME = 'codex-sdk-sigsegv-offline-02'
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


def collect(container, path, destination):
    destination.mkdir(parents=True, exist_ok=True)
    chunks, _ = container.get_archive(path)
    with tarfile.open(fileobj=io.BytesIO(b''.join(chunks))) as archive:
        for item in archive.getmembers():
            if item.isfile():
                (destination / Path(item.name).name).write_bytes(archive.extractfile(item).read())


def main():
    row = next(item for item in pq.read_table(ROOT.parent / 'hint-baseline-run/data/deep_swe_tasks.parquet').to_pylist()
               if item['instance_id'] == 'anko-default-function-arguments')
    prompt = (ROOT / 'source/benchmark/deepswe/prompts/deep_swe_user_prompt.md').read_text().replace('{{issue_description}}', row['problem_statement'])
    hint = (ROOT / 'runs/codex_formal_02/codex_formal_02_shared/hint_gen/anko-default-function-arguments/hint_compact_r1.md').read_text().strip()
    config = json.loads((ROOT / 'runs/codex_formal_02/codex_formal_02_H_r1/infer_logs/anko-default-function-arguments/turn_1/system_prompt_config.json').read_text())
    assert '<system-reminder>\n' + hint + '\n</system-reminder>' == config['append_text']
    assert len(config['append_text']) == 3785
    prompts = {'short': 'Complete this offline SDK tool execution fixture and report its local test result.',
               'h': prompt, 'long': prompt + '\n' + 'Preserve the local source and follow the provided evidence.\n' * 600}
    hints = {'short': '', 'h': hint, 'long': hint + '\n' + 'Review the local behavior before editing any source.\n' * 250}
    cases = [{'name': f'native_{number:02d}_{mode}', 'mode': mode, 'jit_off': False,
              'hook': number == 3, 'resume': number == 0} for number, mode in enumerate(['short', 'h', 'long'] * 2)]
    cases += [{'name': f'nojit_{number:02d}_{mode}', 'mode': mode, 'jit_off': True,
               'hook': number in [3, 12, 19], 'resume': number in [0, 9, 19]}
              for number, mode in enumerate((['short', 'h', 'long'] * 7)[:20])]
    (OUT / 'stress_plan.json').write_text(json.dumps({'cases': cases, 'real_model_calls': 0,
        'prompt_chars': {key: len(value) for key, value in prompts.items()},
        'hint_wrapped_chars': {key: len('<system-reminder>\n' + value + '\n</system-reminder>') if value else 0 for key, value in hints.items()},
        'controlled_difference': 'BUN_JSC_useJIT=0; tools, model label, SDK/CLI, CPU/RAM and fake API are shared',
        'exact_h_append_matches_archived_config': True}, indent=2))
    client = docker.DockerClient(base_url='unix://' + str(ROOT / 'vm/docker.sock'), timeout=420)
    image = client.images.get(row['image_name'])
    env = {item.split('=', 1)[0]: 'offline-fixture' for item in image.attrs['Config'].get('Env', [])
           if any(word in item.split('=', 1)[0].upper() for word in
                  ('KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'ANTHROPIC', 'OPENAI', 'OFOX', 'HUBROUTER'))}
    env.update({'ANTHROPIC_BASE_URL': 'http://127.0.0.1:8767', 'ANTHROPIC_AUTH_TOKEN': 'offline-fixture',
                'ANTHROPIC_MODEL': 'gpt-6.1-terra', 'ANTHROPIC_SMALL_FAST_MODEL': 'gpt-6.1-terra',
                'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1', 'IS_SANDBOX': '1',
                'API_TIMEOUT_MS': '60000', 'PYTHONDONTWRITEBYTECODE': '1',
                'HTTP_PROXY': '', 'HTTPS_PROXY': '', 'ALL_PROXY': '', 'http_proxy': '',
                'https_proxy': '', 'all_proxy': '', 'NO_PROXY': '*', 'SYSTEM_PROMPT_FILE': ''})
    container = client.containers.run(image.id, name=NAME, entrypoint='', command=['tail', '-f', '/dev/null'],
        detach=True, mem_limit='128g', nano_cpus=8_000_000_000, privileged=True,
        network_mode='none', environment=env,
        volumes={'/opt/hint-codex-runtime/python': {'bind': '/opt/python3.12-tmp', 'mode': 'ro'}})
    result = {'container': container.id, 'name': NAME, 'image': image.id, 'started_at_unix': time.time(),
              'real_model_calls': 0, 'synthetic_usage_excluded': True, 'cpus': 8, 'memory': '128g',
              'network': 'none', 'runtime_mount': 'ro', 'status': 'running', 'cases': []}
    def save():
        (OUT / 'stress_result.json').write_text(json.dumps(result, indent=2) + '\n')
    save()
    try:
        code, output = container.exec_run(['bash', '-c', 'rm -rf /app /root/.claude; mkdir -p /app /tmp/stress_out /tmp/prompts /tmp/cases'])
        assert code == 0, output.decode()
        for local, remote in [(ROOT / 'source/run_cc_sdk.py', '/tmp/sdk_script.py'),
                              (ROOT / 'source/logging_utils.py', '/tmp/logging_utils.py'),
                              (ROOT / 'preflight/sdk_hook_fixture/probe.py', '/tmp/hook_fixture.py'),
                              (OUT / 'guest_stress.py', '/tmp/guest_stress.py')]:
            put_file(container, remote, local.read_bytes())
        for mode in prompts:
            put_file(container, '/tmp/prompts/' + mode + '.txt', prompts[mode])
            put_file(container, '/tmp/prompts/' + mode + '_hint.txt', hints[mode])
        code, output = container.exec_run([PYTHON, '-c', "import json,platform; from pathlib import Path; from importlib.metadata import version; print(json.dumps({'kernel':platform.release(),'sdk':version('claude-agent-sdk'),'litellm':version('litellm'),'cpu_max':Path('/sys/fs/cgroup/cpu.max').read_text().strip(),'memory_max':Path('/sys/fs/cgroup/memory.max').read_text().strip(),'cpu_flags':next(l for l in Path('/proc/cpuinfo').read_text().splitlines() if l.startswith('flags'))}))"])
        assert code == 0, output.decode()
        result['runtime'] = json.loads(output)
        for label, overrides in [('native', {'BUN_JSC_dumpOptions': '2'}),
                                  ('nojit', {'BUN_JSC_dumpOptions': '2', 'BUN_JSC_useJIT': '0'})]:
            code, output = container.exec_run(['timeout', '90', CLI, '--version'], environment=overrides)
            (OUT / ('option_ack_' + label + '.log')).write_bytes(output)
            result['option_ack_' + label] = {'exit_code': code, 'useJIT_lines':
                [line for line in output.decode(errors='replace').splitlines() if 'useJIT' in line]}
        save()
        for case in cases:
            put_file(container, '/tmp/cases/' + case['name'] + '.json', json.dumps(case))
            started = time.monotonic()
            code, output = container.exec_run(['timeout', '--signal=INT', '--kill-after=20', '230', PYTHON,
                '/tmp/guest_stress.py', '/tmp/cases/' + case['name'] + '.json'], workdir='/app',
                environment={'APPEND_SYSTEM_PROMPT_FILE': '/tmp/prompts/' + case['mode'] + '_hint.txt' if hints[case['mode']] else ''})
            destination = OUT / 'cases' / case['name']
            collect(container, '/tmp/stress_out/' + case['name'], destination)
            (destination / 'stdout.log').write_bytes(output)
            row_result = json.loads((destination / 'result.json').read_text())
            summary = {'case': case, 'passed': row_result['passed'], 'exit_code': code,
                       'host_exec_seconds': time.monotonic() - started,
                       'fake_http_requests': row_result['fake_http_requests'], 'error': row_result.get('error')}
            result['cases'].append(summary)
            save()
            print(json.dumps(summary), flush=True)
            if case['jit_off'] and not row_result['passed']:
                result['status'] = 'candidate_failed'
                break
        else:
            result['status'] = 'candidate_passed_20_fresh_sessions'
    except BaseException as exc:
        result.update({'status': 'incomplete', 'error': str(exc) or type(exc).__name__})
        raise
    finally:
        result['finished_at_unix'] = time.time()
        container.stop(timeout=10)
        container.reload()
        result['container_running_after_cleanup'] = container.attrs['State']['Running']
        save()
        client.close()
        print(json.dumps({'status': result['status'], 'cases': len(result['cases']),
                          'container_stopped': not result['container_running_after_cleanup']}), flush=True)


if __name__ == '__main__':
    main()
