"""Launch the authorized nine-task cohort on the existing six runtimes."""
import concurrent.futures
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import docker

ROOT = Path('/srv/lab-disks/disk2/users/xymo/hint-codex-experiments')
PYTHON = ROOT.parent / 'hint-baseline-run/env/bin/python'
SOURCE = ROOT / 'source_parallel_07'
NAME = 'codex_parallel_07'
OUT = ROOT / 'preflight/parallel_07_launch'
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def read_api(url):
    with OPENER.open(url, timeout=10) as response:
        return json.load(response)


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


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
    program = "import json,urllib.request; print(json.dumps([json.load(urllib.request.urlopen('http://172.17.0.1:8765/status',timeout=10)),json.load(urllib.request.urlopen('http://172.17.0.1:8766/experiment/status?session=prelaunch07',timeout=10))]))"
    result = subprocess.run(args + ['python3 -c ' + shlex.quote(program)], check=True,
                            capture_output=True, text=True, timeout=40)
    gateway = json.loads(result.stdout)
    assert all(not value['stopped'] for value in gateway)
    return {'lane':lane['lane'], 'cpus':info['NCPU'], 'memory':info['MemTotal'],
            'running_containers':info['ContainersRunning'], 'gateways_ready':True,
            'assigned_images_ready':True}


def main():
    OUT.mkdir(exist_ok=True)
    assert json.loads((ROOT/'preflight/parallel_07_session_gate/host_result.json').read_text())['passed']
    dry = json.loads((ROOT/'preflight/dryruns/codex_parallel_07_dryrun/experiment_state.json').read_text())
    assert dry['status']=='complete' and dry['parallelism']==6
    assert not (ROOT/'runs'/NAME).exists()
    quota = json.loads((ROOT/'preflight/parallel_07_quota.json').read_text())
    assert quota['ordinaryUsageAllowed'] and not quota['rateLimits']['spendControlReached']
    if '--services_ready' not in sys.argv:
        previous = json.loads((ROOT/'logs/services.json').read_text())
        status = read_api('http://127.0.0.1:8765/status')
        assert status['stopped'] and not any(s['active'] for s in status['sessions'])
        save(OUT/'previous_services.json', previous)
        save(OUT/'previous_bridge_status.json', status)
        for name in ('bridge_state.json','bridge_recovery.json'):
            path=ROOT/'logs/bridge'/name
            if path.exists():shutil.copy2(path, OUT/('previous_'+name))
        for service in previous['services']:
            pid=service['pid']
            process=Path(f'/proc/{pid}/cmdline')
            if process.exists():
                command=process.read_bytes().split(b'\0')
                assert str(ROOT).encode() in b' '.join(command) and service['command'][2].encode() in command
                os.kill(pid,signal.SIGTERM)
        deadline=time.monotonic()+30
        while any(Path(f"/proc/{s['pid']}").exists() and ') Z ' not in Path(f"/proc/{s['pid']}/stat").read_text() for s in previous['services']):
            if time.monotonic()>deadline:raise RuntimeError('Previous service did not shut down')
            time.sleep(0.5)
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
        env.pop('ALL_PROXY',None)
        env.pop('all_proxy',None)
        services=[]
        for name,script,port in [('bridge','codex_cli_bridge.py','8765'),('progress','teacher_progress.py','8766')]:
            command=[str(PYTHON),'-u','-B',str(SOURCE/script),'--run_dir',str(ROOT/'logs'/name),'--port',port]
            with (ROOT/'logs'/(name+'.log')).open('ab') as stream:
                process=subprocess.Popen(command,cwd=SOURCE,env=env,stdin=subprocess.DEVNULL,
                                         stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            services.append({'name':name,'pid':process.pid,'command':command})
        save(ROOT/'logs/services.json',{'started_at':time.time(),'services':services,
              'reason':'User-authorized fresh nine-task cohort after the interrupted parallel05 batch',
              'previous_services_record':str(OUT/'previous_services.json')})
    else:
        services = json.loads((ROOT/'logs/services.json').read_text())['services']
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        env.pop('ALL_PROXY', None)
        env.pop('all_proxy', None)
    for attempt in range(30):
        try:
            status=read_api('http://127.0.0.1:8765/status')
            progress=read_api('http://127.0.0.1:8766/experiment/status?session=prelaunch07')
            if not status['stopped'] and not progress['stopped']:break
        except OSError:pass
        time.sleep(1)
    else:raise RuntimeError('New services did not become ready')
    assert not status['sessions']
    lanes=json.loads((ROOT/'preflight/parallel_runtime/runtime_manifest.json').read_text())['lanes']
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        health_rows=list(pool.map(health,lanes))
    save(OUT/'health.json',{'at_unix':time.time(),'services':services,'lanes':health_rows,'real_model_calls':0})
    command=[str(PYTHON),'-u','-B',str(SOURCE/'run_parallel_experiments.py'),
             '--experiment_name',NAME,'--prior_state',str(ROOT/'runs/codex_formal_04/experiment_state.json'),
             '--runtime_manifest',str(ROOT/'preflight/parallel_runtime/runtime_manifest.json')]
    with (ROOT/'logs'/(NAME+'.log')).open('xb') as stream:
        process=subprocess.Popen(command,cwd=SOURCE,env=env,stdin=subprocess.DEVNULL,
                                 stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    record={'pid':process.pid,'started_at_unix':time.time(),'command':command,'cwd':str(SOURCE),
            'configuration':str(ROOT/'reports/parallel_07_config.json'),
            'source_snapshot':str(ROOT/'reports/parallel_07_snapshot.json'),
            'separate_interrupted_batch':str(ROOT/'runs/codex_parallel_05/experiment_state.json'),
            'reason':'All nine tasks start as a new cohort; Anko retained without rerun. Prior six-task partial results and usage are preserved separately.',
            'log':str(ROOT/'logs'/(NAME+'.log'))}
    save(ROOT/'logs'/(NAME+'_process.json'),record)
    print(json.dumps(record),flush=True)


if __name__=='__main__':
    main()
