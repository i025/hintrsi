"""Check the integrated backend; launch the fixed cohort only with --launch."""
import argparse
import concurrent.futures
import json
import os
import shlex
import subprocess
import time
import urllib.request
from pathlib import Path

import docker

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT.parent / 'hint-baseline-run/env/bin/python'
SOURCE = ROOT / 'source_parallel_10'
NAME = 'codex_parallel_10'
OUT = ROOT / 'preflight/parallel_10_integration'
LOGS = ROOT / 'logs' / NAME
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def read_api(url):
    with OPENER.open(url, timeout=10) as response:
        return json.load(response)


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def local_environment():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    for name in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
        env.pop(name, None)
    return env


def health(lane):
    directory = ROOT / ('vm' if lane['lane'] == 0 else f"vm-lane{lane['lane']}")
    client = docker.DockerClient(base_url=lane['docker_host'], timeout=30)
    try:
        info = client.info()
        assert info['NCPU'] == 8 and info['ContainersRunning'] == 0
        for image in lane['assigned_images']:
            client.images.get(image['original_alias'])
    finally:
        client.close()
    args = ['ssh', '-F', '/dev/null', '-S', str(directory/'ssh-control.sock'),
            '-p', str(lane['ssh_port']), '-i', str(ROOT.parent/'hint-baseline-run/vm/ssh_key'),
            '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
            '-o', 'UserKnownHostsFile='+str(directory/'known_hosts'),
            '-o', 'StrictHostKeyChecking=yes', 'experiment@127.0.0.1']
    program = "import json,urllib.request; print(json.dumps([json.load(urllib.request.urlopen('http://172.17.0.1:8765/status',timeout=10)),json.load(urllib.request.urlopen('http://172.17.0.1:8766/experiment/status?session=prelaunch10',timeout=10))]))"
    result = subprocess.run(args + ['python3 -c ' + shlex.quote(program)], check=True,
                            capture_output=True, text=True, timeout=40)
    gateway = json.loads(result.stdout)
    assert all(not value['stopped'] for value in gateway)
    assert gateway[0]['backend'] == 'stateless_exec_action'
    return {'lane':lane['lane'], 'cpus':info['NCPU'], 'memory':info['MemTotal'],
            'running_containers':info['ContainersRunning'], 'gateways_ready':True,
            'assigned_images_ready':True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launch', action='store_true')
    args = parser.parse_args()
    if args.launch:
        readiness = json.loads((ROOT/'reports/parallel_10_readiness.json').read_text())
        assert readiness['status'] == 'ready_for_explicit_launch'
        assert not (ROOT/'runs'/NAME).exists()
    OUT.mkdir(exist_ok=True)
    directory = LOGS if args.launch else OUT/'service_check'
    directory.mkdir(parents=True, exist_ok=True)
    services = []
    launched = False
    try:
        for name, script, port in [('bridge','codex_cli_bridge.py','8765'),
                                   ('progress','teacher_progress.py','8766')]:
            command = [str(PYTHON), '-u', '-B', str(SOURCE/script),
                       '--run_dir', str(directory/name), '--port', port]
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1') if name == 'bridge' else local_environment()
            with (directory/(name+'.log')).open('ab') as stream:
                process = subprocess.Popen(command, cwd=SOURCE, env=env, stdin=subprocess.DEVNULL,
                                           stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            services.append({'name':name, 'pid':process.pid, 'command':command, 'process':process})
        for attempt in range(30):
            assert all(s['process'].poll() is None for s in services), 'A local service exited; see its log'
            try:
                status = read_api('http://127.0.0.1:8765/status')
                progress = read_api('http://127.0.0.1:8766/experiment/status?session=prelaunch10')
                if not status['stopped'] and not progress['stopped']:
                    break
            except OSError:
                pass
            time.sleep(1)
        else:
            raise RuntimeError('Integrated services did not become ready')
        assert status['backend'] == 'stateless_exec_action' and not status['active_requests']
        lanes = json.loads((ROOT/'preflight/parallel_runtime/runtime_manifest.json').read_text())['lanes']
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            health_rows = list(pool.map(health, lanes))
        save(directory/'health.json', {'at_unix':time.time(), 'lanes':health_rows,
             'source':str(SOURCE), 'real_model_calls':0})
        if not args.launch:
            print(json.dumps({'status':'service_and_six_lane_check_passed', 'real_model_calls':0,
                              'health':str(directory/'health.json')}), flush=True)
            return
        command = [str(PYTHON), '-u', '-B', str(SOURCE/'run_parallel_experiments.py'),
                   '--experiment_name',NAME, '--prior_state',str(ROOT/'runs/codex_formal_04/experiment_state.json'),
                   '--runtime_manifest',str(ROOT/'preflight/parallel_runtime/runtime_manifest.json'),
                   '--bridge_dir',str(directory/'bridge'), '--progress_dir',str(directory/'progress')]
        with (directory/'experiment.log').open('xb') as stream:
            process = subprocess.Popen(command, cwd=SOURCE, env=local_environment(), stdin=subprocess.DEVNULL,
                                       stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        record = {'pid':process.pid, 'started_at_unix':time.time(), 'command':command,
                  'cwd':str(SOURCE), 'configuration':str(ROOT/'reports/parallel_10_config.json'),
                  'source_snapshot':str(ROOT/'reports/parallel_10_source.tar.gz'),
                  'log':str(directory/'experiment.log')}
        save(directory/'experiment_process.json',record)
        launched = True
        print(json.dumps(record),flush=True)
    finally:
        if not launched:
            for service in services:
                if service['process'].poll() is None:
                    service['process'].terminate()
            for service in services:
                service['process'].wait(timeout=30)
        save(directory/'services.json',{'status':'running' if launched else 'stopped',
             'at_unix':time.time(), 'source':str(SOURCE),
             'services':[{k:v for k,v in service.items() if k!='process'} for service in services]})


if __name__ == '__main__':
    main()
