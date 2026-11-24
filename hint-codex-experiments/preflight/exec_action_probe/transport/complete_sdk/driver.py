"""Run the isolated B preexperiment after the host bridge is explicitly ready."""
import argparse
import ast
import io
import json
import shlex
import subprocess
import tarfile
import time
from pathlib import Path

import docker
import pyarrow.parquet as pq

ROOT = Path('/srv/lab-disks/disk2/users/xymo/hint-codex-experiments')
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / 'source_parallel_09_checked'
PYTHON = '/opt/python3.12-tmp/bin/python3'


def put(container, path, data):
    data = data.encode() if isinstance(data, str) else data
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        item = tarfile.TarInfo(Path(path).name)
        item.size = len(data)
        archive.addfile(item, io.BytesIO(data))
    container.put_archive(str(Path(path).parent), stream.getvalue())


def proxy_config(backend):
    tree = ast.parse((SOURCE / 'constant_zhy.py').read_text())
    node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'render_proxy_config')
    scope = {}
    exec(ast.unparse(node), scope)
    return scope['render_proxy_config']('openai', 'gpt-6.1-terra', 'local-exec-bridge', backend, max_tokens=65536)


def create_container(client, image, name, experiment):
    env = {value.split('=', 1)[0]: 'unused-local-fixture' for value in image.attrs['Config'].get('Env', []) if any(word in value.split('=', 1)[0].upper() for word in ('KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'ANTHROPIC', 'OPENAI', 'OFOX', 'HUBROUTER'))}
    env.update(ANTHROPIC_BASE_URL='http://127.0.0.1:8768', ANTHROPIC_AUTH_TOKEN='local-exec-bridge', ANTHROPIC_MODEL='gpt-6.1-terra[1m]', ANTHROPIC_SMALL_FAST_MODEL='gpt-6.1-terra[1m]', CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1', IS_SANDBOX='1', API_TIMEOUT_MS='600000', PYTHONDONTWRITEBYTECODE='1', SYSTEM_PROMPT_FILE='', HTTP_PROXY='', HTTPS_PROXY='', ALL_PROXY='', http_proxy='', https_proxy='', all_proxy='', NO_PROXY='127.0.0.1,localhost,172.17.0.1', BUN_JSC_useJIT='0', LITELLM_LOCAL_MODEL_COST_MAP='True', LITELLM_TELEMETRY='False')
    container = client.containers.run(image.id, name=name, entrypoint='', command=['tail', '-f', '/dev/null'], detach=True, mem_limit='128g', nano_cpus=8_000_000_000, privileged=True, network_mode='bridge', environment=env, labels={'hint.experiment_name': experiment}, volumes={'/opt/hint-codex-runtime/python': {'bind': '/opt/python3.12-tmp', 'mode': 'ro'}})
    return container


def install_sdk_files(container):
    for path, target in [(SOURCE / 'run_cc_sdk.py', '/tmp/sdk_script.py'), (SOURCE / 'logging_utils.py', '/tmp/logging_utils.py'), (SOURCE / 'litellm_proxy/claude_code_proxy.py', '/tmp/litellm_call_backs.py'), (SOURCE / 'litellm_proxy/streaming_fix.py', '/tmp/streaming_fix.py')]:
        put(container, target, path.read_bytes())


def collect_output(container, source, destination):
    chunks, _ = container.get_archive(source)
    with tarfile.open(fileobj=io.BytesIO(b''.join(chunks))) as archive:
        for item in archive.getmembers():
            if item.isfile():
                target = destination / Path(item.name).relative_to(Path(source).name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(item).read())


def restrict_network(container, lane=5, ports=(8765,)):
    container.reload()
    pid = container.attrs['State']['Pid']
    directory = ROOT / ('vm-lane' + str(lane))
    ssh = ['ssh', '-F', '/dev/null', '-S', str(directory / 'ssh-control.sock'),
           '-p', str(22230 + lane), '-i', str(ROOT.parent / 'hint-baseline-run/vm/ssh_key'),
           '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
           '-o', 'UserKnownHostsFile=' + str(directory / 'known_hosts'),
           '-o', 'StrictHostKeyChecking=yes', 'experiment@127.0.0.1']
    rules = [['-F', 'OUTPUT'], ['-A', 'OUTPUT', '-o', 'lo', '-j', 'ACCEPT'],
             ['-A', 'OUTPUT', '-m', 'conntrack', '--ctstate', 'ESTABLISHED,RELATED', '-j', 'ACCEPT']]
    rules += [['-A', 'OUTPUT', '-d', '172.17.0.1', '-p', 'tcp', '--dport', str(port), '-j', 'ACCEPT'] for port in ports]
    rules += [['-P', 'OUTPUT', 'DROP']]
    program = """import json,os,subprocess
pid=PID
host_ns=os.readlink('/proc/self/ns/net')
container_ns=os.readlink('/proc/'+str(pid)+'/ns/net')
assert host_ns != container_ns
before=subprocess.check_output(['iptables','-S','OUTPUT'])
prefix=['nsenter','--target',str(pid),'--net','--','iptables']
for rule in RULES: subprocess.run(prefix+rule,check=True)
after=subprocess.check_output(['iptables','-S','OUTPUT'])
assert before == after
print(json.dumps({'container_pid':pid,'host_netns':host_ns,'container_netns':container_ns,'host_output_rules_unchanged':True,'rules':subprocess.check_output(prefix+['-S','OUTPUT'],text=True)}))
""".replace('PID', str(pid)).replace('RULES', repr(rules))
    completed = subprocess.run(ssh + ['sudo python3 -c ' + shlex.quote(program)], check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', default='attempt_01')
    parser.add_argument('--precheck', action='store_true', help='Start the proxy and inspect SDK entrypoints without a model request')
    parser.add_argument('--session', default='exec-preexperiment-b')
    parser.add_argument('--backend', default='http://172.17.0.1:8765')
    args = parser.parse_args()
    out = HERE / args.attempt
    out.mkdir()
    config = {'backend': args.backend, 'session': args.session, 'role': 'student', 'phase': 'B1', 'model': 'gpt-6.1-terra[1m]', 'sdk_source': str(SOURCE / 'run_cc_sdk.py'), 'fixture_data_shards': 20, 'precheck': args.precheck}
    (out / 'probe_config.json').write_text(json.dumps(config, indent=2))
    client = docker.DockerClient(base_url='unix://' + str(ROOT / 'vm-lane5/docker.sock'), timeout=1700)
    row = next(row for row in pq.read_table(ROOT.parent / 'hint-baseline-run/data/deep_swe_tasks.parquet').to_pylist() if row['instance_id'] == 'sqlfmt-create-table-ddl-formatting')
    image = client.images.get(row['image_name'])
    container = create_container(client, image, 'codex-exec-complete-sdk-b', 'preflight_exec_complete_sdk_b')
    record = {'passed': False, 'started_at_unix': time.time(), 'ofox_calls': 0, 'container': container.id, 'image': image.id, 'cpu_count': 8, 'memory_gib': 128, 'network': 'bridge; OUTPUT permits only loopback and gateway TCP 8765', 'readonly_runtime': True, 'config': config}
    (out / 'container.json').write_text(json.dumps(record, indent=2))
    try:
        code, output = container.exec_run(['bash', '-c', 'set -e; rm -rf /app /root/.claude; mkdir -p /app/data'])
        (out / 'setup.log').write_bytes(output)
        assert code == 0, output
        (out / 'network_rules.json').write_text(json.dumps(restrict_network(container), indent=2))
        for path in (HERE / 'fixture').rglob('*'):
            if path.is_file():
                put(container, '/app/' + str(path.relative_to(HERE / 'fixture')), path.read_bytes())
        install_sdk_files(container)
        put(container, '/tmp/problem.txt', (HERE / 'problem.txt').read_bytes())
        put(container, '/tmp/complete_sdk_guest.py', (HERE / 'guest.py').read_bytes())
        endpoint = args.backend + '/sessions/' + args.session + '/student/B1/v1'
        put(container, '/tmp/config.yaml', proxy_config(endpoint))
        put(container, '/tmp/probe_config.json', json.dumps(config))
        started = time.monotonic()
        code, output = container.exec_run(['timeout', '--signal=INT', '--kill-after=20', '1600', PYTHON, '/tmp/complete_sdk_guest.py'], workdir='/app')
        (out / 'stdout.log').write_bytes(output)
        collect_output(container, '/tmp/complete_sdk_out', out)
        result = json.loads((out / 'result.json').read_text())
        record.update(exit_code=code, passed=code == 0 and result['passed'], host_exec_seconds=time.monotonic() - started)
    finally:
        container.remove(force=True)
        client.close()
        record.update(container_removed=True, finished_at_unix=time.time())
        (out / 'host_result.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record), flush=True)
    return 0 if record['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
