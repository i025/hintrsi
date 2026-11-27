"""Close only this finished follow-up's containers, resumed VMs and services."""
import datetime
import json
import os
import signal
import socket
import time
import urllib.request
from pathlib import Path

import docker

ROOT=Path.cwd()
OUT=Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
rows=json.loads((OUT/'results/attempt_metrics.json').read_text())
stage=json.loads((OUT/'config/final_stages_process.json').read_text())
if len(rows)!=29 or any(r['status'] in ('running','not_started') for r in rows):
    raise RuntimeError('Finish all saved attempt cells before shutdown')
if stage['status']!='experiment_queues_complete_reports_pending':
    raise RuntimeError('Finish queues and report-only posthocs before shutdown')
if not (OUT/'audit/final_report_review.md.job.json').exists() or not json.loads((OUT/'audit/final_report_review.md.job.json').read_text())['completed']:
    raise RuntimeError('Finish final report and its CLI review before shutdown')
record={'started_at_beijing':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
    'scope':'Exact saved experiment labels and owned process command/cwd checks only. Preserve VM overlays, task images, previous outputs and all other users.',
    'containers':[],'signals':[],'VM_actions':[]}
names={r['run_name'] for r in rows}
for path in (OUT/'runs').glob('*_state.json'):
    names.update(a['run_name'] for a in json.loads(path.read_text()).get('attempts',[]))

def command(pid):
    try:return Path(f'/proc/{pid}/cmdline').read_bytes()
    except FileNotFoundError:return b''

def signal_owned(pid,marker):
    raw=command(pid)
    if not raw:return
    if marker.encode() not in raw:raise RuntimeError('Process identity changed: '+str(pid))
    os.kill(pid,signal.SIGTERM);record['signals'].append(pid)

def qmp(path,action):
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
        connection.settimeout(5);connection.connect(path)
        stream=connection.makefile('rwb',buffering=0)
        json.loads(stream.readline())
        for name in ['qmp_capabilities',action]:
            stream.write((json.dumps({'execute':name})+'\n').encode())
            while True:
                response=json.loads(stream.readline())
                if 'error' in response:raise RuntimeError(str(response))
                if 'return' in response:break

runtime=json.loads((OUT/'config/runtime_resume.json').read_text())
for lane in runtime['lanes']:
    client=docker.DockerClient(base_url=lane['docker_host'],timeout=20)
    try:
        for container in client.containers.list():
            label=container.labels.get('hint.experiment_name','')
            if label in names:
                container.stop(timeout=10)
                record['containers'].append({'lane':lane['lane'],'name':container.name,'experiment':label,'stopped':True})
        remaining=client.containers.list()
        if remaining:raise RuntimeError('VM contains an unowned running container; preserve VM and inspect')
    finally:client.close()
for lane in runtime['lanes']:
    pid=lane['vm_pid'];raw=command(pid)
    qmp_path=lane['vm_command'][lane['vm_command'].index('-qmp')+1].split(',')[0][5:]
    if raw:
        if qmp_path.encode() not in raw:raise RuntimeError('VM identity changed')
        qmp(qmp_path,'system_powerdown')
        record['VM_actions'].append({'lane':lane['lane'],'pid':pid,'action':'system_powerdown'})
time.sleep(40)
for lane in runtime['lanes']:
    pid=lane['vm_pid'];raw=command(pid)
    qmp_path=lane['vm_command'][lane['vm_command'].index('-qmp')+1].split(',')[0][5:]
    if raw:
        if qmp_path.encode() not in raw:raise RuntimeError('VM identity changed')
        qmp(qmp_path,'quit')
        record['VM_actions'].append({'lane':lane['lane'],'pid':pid,'action':'quit_after_powerdown_wait'})
    signal_owned(lane['tunnel_pid'],lane['tunnel_command'][lane['tunnel_command'].index('-S')+1])
(OUT/'config/monitor_stop').touch()
monitor=json.loads((OUT/'config/monitor_process.json').read_text())
if command(monitor['pid']):
    if Path(f"/proc/{monitor['pid']}/cwd").resolve()!=ROOT:raise RuntimeError('Monitor cwd changed')
    signal_owned(monitor['pid'],'work_followup/monitor_followup.py')
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
request=urllib.request.Request('http://127.0.0.1:8765/stop',data=json.dumps({'reason':'Saved follow-up attempts, report and review finished'}).encode(),headers={'Content-Type':'application/json'})
record['bridge_stop']=json.load(opener.open(request,timeout=10))
for service in json.loads((OUT/'config/services.json').read_text()):signal_owned(service['pid'],str(OUT))
time.sleep(2)
record['finished_at_beijing']=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
record['remaining_owned_processes']=[pid for pid in record['signals']+[l['vm_pid'] for l in runtime['lanes']] if command(pid)]
(OUT/'logs/followup_cleanup.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
if record['remaining_owned_processes']:raise RuntimeError('Inspect remaining own processes before declaring closure')
