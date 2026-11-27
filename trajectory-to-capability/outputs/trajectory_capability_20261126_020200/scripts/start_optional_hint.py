"""Conditional one-time activation; preserve the original bridge and shared VMs."""
import json
import os
import shutil
import signal
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

import docker

WORK=Path.cwd();OUT=WORK/'outputs/trajectory_capability_20261126_020200'
PYTHON='/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
rows=json.loads((OUT/'results/attempt_metrics.json').read_text())
if len(rows)!=12 or any(r['status']!='complete' or r['formal_success']=='' for r in rows):
    raise RuntimeError('All12 core attempts must finish first')
if time.time()>1795651320-9000:raise RuntimeError('The pre-saved150minute launch gate has closed')
record_path=OUT/'config/optional_activation.json'
if record_path.exists():raise FileExistsError(record_path)
client=docker.DockerClient(base_url='unix:///srv/lab-disks/disk2/users/xymo/hint-codex-experiments/vm/docker.sock',timeout=10)
active=[c.name for c in client.containers.list()];client.close()
if active:raise RuntimeError('VM0 is busy; preserve its active containers: '+str(active))
record={'started_at':time.time(),'VM0_active_before':active,'status':'activating'}
record_path.write_text(json.dumps(record,indent=2)+'\n')
shutil.copy2(WORK/'work/run_hint_exploration.py',OUT/'source/run_hint_exploration.py')

monitor=WORK/'work/monitor_experiment.py';text=monitor.read_text()
text=text.replace("b'run_capability_experiments.py' in cmd", "(b'run_capability_experiments.py' in cmd or b'run_hint_exploration.py' in cmd)")
monitor.write_text(text)
old=json.loads((OUT/'config/monitor_process.json').read_text())
(OUT/'logs/monitor_process_before_optional.json').write_text(json.dumps(old,indent=2)+'\n')
pid=old['pid'];command=Path(f'/proc/{pid}/cmdline').read_bytes()
if b'monitor_experiment.py' not in command or Path(f'/proc/{pid}/cwd').resolve()!=WORK:raise RuntimeError('Monitor PID does not match this experiment')
os.kill(pid,signal.SIGTERM)
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
for key in ['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy']:env.pop(key,None)
with (OUT/'logs/monitor_process.log').open('ab') as stream:
    process=subprocess.Popen([PYTHON,'-u','-B',str(monitor)],cwd=WORK,env=env,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
record['new_monitor_pid']=process.pid

services_path=OUT/'config/services.json';services=json.loads(services_path.read_text())
(OUT/'logs/services_before_optional.json').write_text(json.dumps(services,indent=2)+'\n')
progress=next(r for r in services if r['name']=='progress');pid=progress['pid']
command=Path(f'/proc/{pid}/cmdline').read_bytes()
if str(OUT).encode() not in command or b'teacher_progress.py' not in command:raise RuntimeError('Progress PID does not match this experiment')
os.kill(pid,signal.SIGTERM)
for _ in range(50):
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1',8766))!=0:break
    time.sleep(0.1)
else:raise RuntimeError('Own old progress service has not released its port')
cmd=[PYTHON,'-u','-B',str(OUT/'source/run_hint_exploration.py'),'service']
with (OUT/'logs/hint_progress_service.log').open('xb') as stream:
    process=subprocess.Popen(cmd,cwd=OUT/'source',env=env,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
progress.update(pid=process.pid,command=cmd,started_at=time.time(),mode='optional_hint_max_one_check')
services_path.write_text(json.dumps(services,indent=2)+'\n')
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
for _ in range(50):
    try:
        with opener.open('http://127.0.0.1:8766/experiment/status?session=optional-startup-check',timeout=2) as response:record['progress_health']=json.load(response)
        break
    except OSError:time.sleep(0.1)
else:raise RuntimeError('Optional progress service did not start')
cmd=[PYTHON,'-u','-B',str(OUT/'source/run_hint_exploration.py'),'run']
with (OUT/'logs/hint_exploration.log').open('xb') as stream:
    process=subprocess.Popen(cmd,cwd=WORK,env=env,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
record.update(queue_pid=process.pid,queue_command=cmd,status='launched',finished_at=time.time())
record_path.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
