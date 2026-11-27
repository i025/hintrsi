"""Own all processes for one SDK run, including its model-only CLI backend."""
import argparse
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import urllib.request

from isolation import ROOT, prepare, command

PYTHON = '/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'


def process_resources():
    processes = {}
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            fields = path.read_text().rsplit(')', 1)[1].split()
            processes[int(path.parent.name)] = (int(fields[1]), int(fields[11]) + int(fields[12]), int(fields[21]))
        except (OSError, ValueError, IndexError):
            continue  # Processes may exit while /proc is being sampled.
    owned = {os.getpid()}
    while True:
        children = {pid for pid, values in processes.items() if values[0] in owned}
        expanded = owned | children
        if expanded == owned:
            break
        owned = expanded
    return {'live_processes': len(owned),
            'rss_sum_mib': sum(processes[pid][2] for pid in owned if pid in processes) * os.sysconf('SC_PAGE_SIZE') / 1024**2,
            'live_cpu_seconds': sum(processes[pid][1] for pid in owned if pid in processes) / os.sysconf('SC_CLK_TCK')}


def execute(directory, image, prompt, seconds=1500, calls=120, cpus=None, port=18865):
    directory = prepare(directory, image, prompt)
    (directory / 'proxy').mkdir(exist_ok=True)
    (directory / 'claude_code_proxy.py').symlink_to(ROOT / 'sdk/litellm_proxy/claude_code_proxy.py')
    backend_home = directory / 'backend_home'
    backend_home.mkdir(exist_ok=True)
    shutil.copyfile(Path.home() / '.codex/auth.json', backend_home / 'auth.json')
    (backend_home / 'auth.json').chmod(0o600)
    services = []
    socket_directory = Path(tempfile.mkdtemp(prefix='scene-rsi-'))
    proxy_socket = socket_directory / 'proxy.sock'
    api_base = 'http://127.0.0.1:' + str(port) + '/sessions/' + directory.name + '/student/solve/v1'
    config = {'model_list': [{'model_name': 'default_model', 'litellm_params': {
        'model': 'openai/gpt-6.1-terra', 'api_base': api_base, 'api_key': 'local-scene'}}],
        'litellm_settings': {'callbacks': ['claude_code_proxy.proxy_handler_instance'],
                             'drop_params': True, 'request_timeout': 240, 'num_retries': 0},
        'router_settings': {'num_retries': 0, 'timeout': 240}}
    import yaml
    (directory / 'proxy.yaml').write_text(yaml.safe_dump(config))
    environment = dict(os.environ, PYTHONPATH=str(ROOT / 'sdk') + ':' + str(ROOT / 'sdk/litellm_proxy'),
                       PYTHONDONTWRITEBYTECODE='1', CODEX_HOME=str(backend_home))
    proxy_environment = dict(environment)
    for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
        proxy_environment.pop(key, None)
    proxy_environment.update(CONFIG_FILE_PATH=str(directory / 'proxy.yaml'),
                             SCENE_PROXY_SOCKET=str(proxy_socket), SCENE_PROXY_LOG_DIR=str(directory / 'proxy'),
                             LITELLM_TELEMETRY='False', LITELLM_LOCAL_MODEL_COST_MAP='True')
    started = time.time()
    state = {'status': 'starting', 'model': 'gpt-6.1-terra', 'reasoning_effort': 'low',
             'agent_loop': 'Claude Agent SDK', 'started_at': started,
             'seconds_limit': seconds, 'model_call_limit': calls, 'cpu_affinity': cpus,
             'hint_enabled': False, 'persistent_capability_enabled': False, 'teacher_enabled': False}

    def save():
        (directory / 'status.json').write_text(json.dumps(state, indent=2))

    def spawn(argv, name, env):
        with (directory / (name + '.log')).open('wb') as output:
            process = subprocess.Popen(argv, stdout=output, stderr=subprocess.STDOUT,
                                       env=env, start_new_session=True)
        services.append(process)
        return process

    save()
    student = None
    def interrupted(signum, frame):
        raise InterruptedError('Supervisor received signal ' + str(signum))
    signal.signal(signal.SIGTERM, interrupted)
    try:
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1', port)) == 0:
                raise RuntimeError('Selected experiment bridge port is already occupied')
        bridge = spawn([PYTHON, '-u', str(ROOT / 'harness/bridge_server.py'), '--directory', str(directory / 'bridge'),
                        '--port', str(port), '--limit', str(calls)], 'bridge_server', environment)
        proxy = spawn([PYTHON, '-u', str(ROOT / 'harness/proxy_server.py')], 'proxy_server', proxy_environment)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for _ in range(120):
            if bridge.poll() is not None or proxy.poll() is not None:
                raise RuntimeError('Model service exited during startup; inspect server logs')
            if proxy_socket.exists():
                try:
                    with opener.open('http://127.0.0.1:' + str(port) + '/health', timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
            time.sleep(.5)
        else:
            raise TimeoutError('Model services did not become ready')
        argv = command(directory, proxy_socket, calls)
        (directory / 'sdk_command.json').write_text(json.dumps(argv, indent=2))

        def limits():
            os.nice(15)
            if cpus:
                os.sched_setaffinity(0, cpus)
            resource.setrlimit(resource.RLIMIT_AS, (32 * 1024 ** 3, 32 * 1024 ** 3))

        with (directory / 'sdk_stdout.log').open('wb') as output:
            student = subprocess.Popen(argv, stdout=output, stderr=subprocess.STDOUT,
                                       start_new_session=True, preexec_fn=limits)
            state.update(status='running', student_pid=student.pid, student_started_at=time.time())
            save()
            while student.poll() is None:
                elapsed = time.time() - state['student_started_at']
                state.update(student_seconds=elapsed,
                             blender_executions=len(list((directory / 'capture').glob('blender_*'))),
                             rendered_images=len(list((directory / 'workspace').rglob('*.png'))))
                resources = process_resources()
                state['peak_sampled_rss_sum_mib'] = max(state.get('peak_sampled_rss_sum_mib', 0), resources['rss_sum_mib'])
                with (directory / 'resources.jsonl').open('a') as output:
                    output.write(json.dumps({'timestamp': time.time(), **resources}) + '\n')
                save()
                if elapsed >= seconds:
                    state['stop_reason'] = 'wall_time_limit'
                    os.killpg(student.pid, signal.SIGTERM)
                    break
                time.sleep(2)
            try:
                student.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(student.pid, signal.SIGKILL)
                student.wait()
        state.update(status='completed' if student.returncode == 0 else 'incomplete', exit_code=student.returncode,
                     stop_reason=state.get('stop_reason', 'sdk_exit'))
        if (directory / 'capture/trajs.json').exists():
            metadata = json.loads((directory / 'capture/trajs.json').read_text())['metadata']
            state['sdk_status'] = metadata['status']
            if metadata['status'] != 'completed':
                state['status'] = 'incomplete'
    except BaseException as error:
        state.update(status='engineering_failure', error=str(error))
        raise
    finally:
        if student and student.poll() is None:
            os.killpg(student.pid, signal.SIGKILL)
            student.wait()
        for process in reversed(services):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        state.update(finished_at=time.time(), total_seconds=time.time() - started, owned_processes_stopped=True)
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        state.update(child_user_cpu_seconds=usage.ru_utime, child_system_cpu_seconds=usage.ru_stime,
                     largest_child_rss_mib=usage.ru_maxrss / 1024)
        (backend_home / 'auth.json').unlink(missing_ok=True)
        save()
        print(json.dumps(state), flush=True)
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--prompt', required=True)
    parser.add_argument('--seconds', type=int, default=1500)
    parser.add_argument('--calls', type=int, default=120)
    parser.add_argument('--port', type=int, default=18865)
    parser.add_argument('--cpus', default='32,33,34,35,36,37,38,39')
    args = parser.parse_args()
    execute(args.directory, args.image, Path(args.prompt).read_text(), args.seconds, args.calls,
            [int(x) for x in args.cpus.split(',')], args.port)
