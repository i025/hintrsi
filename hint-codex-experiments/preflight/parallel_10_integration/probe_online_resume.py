"""Round-trip batched tools through the candidate SSE, LiteLLM, and real SDK offline."""

import ast
import io
import json
import os
import tarfile
import time
from pathlib import Path

import docker
import pyarrow.parquet as pq

ROOT = Path('/srv/lab-disks/disk2/users/xymo/hint-codex-experiments')
OUT = ROOT / 'preflight/parallel_10_integration/online_resume'
SOURCE = ROOT / 'source_parallel_10'
CANDIDATE = SOURCE / 'codex_cli_bridge.py'
PYTHON = '/opt/python3.12-tmp/bin/python3'

GUEST = (ROOT / 'preflight/parallel_10_integration/online_guest.py').read_text()


def put(container, path, data):
    data = data.encode() if isinstance(data, str) else data
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        item = tarfile.TarInfo(Path(path).name)
        item.size = len(data)
        archive.addfile(item, io.BytesIO(data))
    container.put_archive(str(Path(path).parent), stream.getvalue())


def selected_function(path, name):
    tree = ast.parse(path.read_text())
    node = next(node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name)
    return ast.unparse(node) + '\n'


def main():
    OUT.mkdir()
    client = docker.DockerClient(base_url='unix://' + str(ROOT / 'vm-lane1/docker.sock'), timeout=1300)
    row = next(row for row in pq.read_table(ROOT.parent / 'hint-baseline-run/data/deep_swe_tasks.parquet').to_pylist() if 'igel' in row['instance_id'].lower())
    image = client.images.get(row['image_name'])
    env = {value.split('=', 1)[0]: 'offline-fixture' for value in image.attrs['Config'].get('Env', []) if any(word in value.split('=', 1)[0].upper() for word in ('KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'ANTHROPIC', 'OPENAI', 'OFOX', 'HUBROUTER'))}
    env.update(ANTHROPIC_BASE_URL='http://127.0.0.1:8768', ANTHROPIC_AUTH_TOKEN='offline-fixture', ANTHROPIC_MODEL='gpt-6.1-terra', ANTHROPIC_SMALL_FAST_MODEL='gpt-6.1-terra', CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1', IS_SANDBOX='1', API_TIMEOUT_MS='60000', PYTHONDONTWRITEBYTECODE='1', SYSTEM_PROMPT_FILE='', HTTP_PROXY='', HTTPS_PROXY='', ALL_PROXY='', http_proxy='', https_proxy='', all_proxy='', NO_PROXY='*', BUN_JSC_useJIT='0', LITELLM_LOCAL_MODEL_COST_MAP='True', LITELLM_TELEMETRY='False')
    container = client.containers.run(image.id, name='codex-production10-online-resume-offline', entrypoint='', command=['tail', '-f', '/dev/null'], detach=True, mem_limit='128g', nano_cpus=8_000_000_000, privileged=True, network_mode='none', environment=env, labels={'hint.experiment_name': 'preflight_parallel10_online_resume'}, volumes={'/opt/hint-codex-runtime/python': {'bind': '/opt/python3.12-tmp', 'mode': 'ro'}})
    record = {'started_at_unix': time.time(), 'real_model_calls': 0, 'network': 'none', 'container': container.id, 'candidate': str(CANDIDATE), 'sdk_source': str(SOURCE / 'run_cc_sdk.py')}
    try:
        code, output = container.exec_run(['bash', '-c', 'rm -rf /app /root/.claude; mkdir -p /app /tmp/production'])
        assert code == 0, output
        for path, target in [(SOURCE / 'run_cc_sdk.py', '/tmp/sdk_script.py'), (SOURCE / 'logging_utils.py', '/tmp/logging_utils.py'), (SOURCE / 'litellm_proxy/claude_code_proxy.py', '/tmp/litellm_call_backs.py'), (SOURCE / 'litellm_proxy/streaming_fix.py', '/tmp/streaming_fix.py')]:
            put(container, target, path.read_bytes())
        scope = {}
        exec(selected_function(SOURCE / 'constant_zhy.py', 'render_proxy_config'), scope)
        config = scope['render_proxy_config']('openai', 'gpt-6.1-terra', 'offline-fixture', 'http://127.0.0.1:8767/sessions/offline-online-hint/student/solve/v1')
        put(container, '/tmp/config.yaml', config)
        put(container, '/tmp/production/codex_cli_bridge.py', CANDIDATE.read_bytes())
        put(container, '/tmp/fake_exec.py', (ROOT / 'preflight/parallel_10_integration/online_fake_exec.py').read_bytes())
        put(container, '/tmp/probe_multitool.py', GUEST)
        started = time.monotonic()
        code, output = container.exec_run(['timeout', '--signal=INT', '--kill-after=20', '1200', PYTHON, '/tmp/probe_multitool.py'], workdir='/app')
        (OUT / 'stdout.log').write_bytes(output)
        chunks, _ = container.get_archive('/tmp/transport_audit_out')
        with tarfile.open(fileobj=io.BytesIO(b''.join(chunks))) as archive:
            for item in archive.getmembers():
                if item.isfile():
                    target = OUT / Path(item.name).relative_to('transport_audit_out')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.extractfile(item).read())
        result = json.loads((OUT / 'result.json').read_text())
        record.update(exit_code=code, passed=code == 0 and result['passed'], host_exec_seconds=time.monotonic() - started)
    finally:
        container.remove(force=True)
        client.close()
        record.update(container_removed=True, finished_at_unix=time.time())
        (OUT / 'host_result.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record), flush=True)
    return 0 if record.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
