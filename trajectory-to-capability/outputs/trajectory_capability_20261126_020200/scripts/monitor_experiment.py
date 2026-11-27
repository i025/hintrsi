"""Read existing experiment ledgers and stop only this run at its six-hour deadline."""
import json
import os
import signal
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

import docker

OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
DEADLINE=1795651320.0
OLD=Path('/srv/lab-disks/disk2/users/xymo/hint-codex-experiments')
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
offset=0;totals=defaultdict(int);sessions=defaultdict(lambda:defaultdict(int))

def own(name):
    if name=='trajectory_capability_preflight':return True
    for p in (OUT/'runs').glob('*_state.json'):
        try:state=json.loads(p.read_text())
        except ValueError:continue
        if any(a.get('run_name')==name for a in state.get('attempts',[])):return True
    return False

def snapshot():
    global offset
    ledger=OUT/'logs/bridge/token_usage.jsonl'
    if ledger.exists():
        with ledger.open() as f:
            f.seek(offset)
            for line in f:
                row=json.loads(line);usage=row['usage'];session=row['session']
                totals['model_calls_with_usage']+=1;sessions[session]['model_calls_with_usage']+=1
                for key,value in usage.items():
                    if isinstance(value,(int,float)):
                        totals[key]+=value;sessions[session][key]+=value
            offset=f.tell()
    record={'timestamp':time.time(),'remaining_seconds':max(0,DEADLINE-time.time()),'loadavg':list(os.getloadavg()),'usage':dict(totals),'sessions':dict(sessions),'queues':[],'containers':[]}
    try:record['bridge']=json.load(opener.open('http://127.0.0.1:8765/status',timeout=5))
    except Exception as e:record['bridge_error']=str(e)
    for p in sorted((OUT/'runs').glob('*_state.json')):
        try:
            state=json.loads(p.read_text());record['queues'].append({'file':str(p),'status':state['status'],'task':state['task'],'attempts':[{'group':a['group'],'status':a['status'],'started_at':a['started_at']} for a in state['attempts']]})
        except (ValueError,KeyError):pass
    for lane in range(6):
        directory=OLD/('vm' if lane==0 else f'vm-lane{lane}')
        client=docker.DockerClient(base_url='unix://'+str(directory/'docker.sock'),timeout=10)
        try:
            for c in client.containers.list():
                label=c.labels.get('hint.experiment_name','')
                if own(label):
                    row={'lane':lane,'name':c.name,'experiment':label,'status':c.status}
                    try:
                        s=c.stats(stream=False);row['memory_bytes']=s.get('memory_stats',{}).get('usage');row['cpu_total_ns']=s.get('cpu_stats',{}).get('cpu_usage',{}).get('total_usage')
                    except Exception as e:row['stats_error']=str(e)
                    record['containers'].append(row)
        except Exception as e:record.setdefault('docker_errors',[]).append({'lane':lane,'error':str(e)})
        finally:client.close()
    (OUT/'logs/monitor_latest.json').write_text(json.dumps(record,indent=2)+'\n')
    with (OUT/'logs/monitor.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
    return record

def cutoff(reason='Six-hour wall-clock deadline'):
    result={'timestamp':time.time(),'reason':reason,'signals':[],'containers':[]}
    for p in (OUT/'runs').glob('*_state.json'):
        state=json.loads(p.read_text());pid=state.get('pid')
        try:
            cmd=Path(f'/proc/{pid}/cmdline').read_bytes()
            if OUT.name.encode() in cmd and (b'run_capability_experiments.py' in cmd or b'run_hint_exploration.py' in cmd):
                os.kill(pid,signal.SIGINT);result['signals'].append(pid)
        except (FileNotFoundError,ProcessLookupError):pass
    request=urllib.request.Request('http://127.0.0.1:8765/stop',data=json.dumps({'reason':result['reason']}).encode(),headers={'Content-Type':'application/json'})
    try:result['bridge']=json.load(opener.open(request,timeout=10))
    except Exception as e:result['bridge_error']=str(e)
    time.sleep(10)
    for lane in range(6):
        directory=OLD/('vm' if lane==0 else f'vm-lane{lane}')
        client=docker.DockerClient(base_url='unix://'+str(directory/'docker.sock'),timeout=20)
        try:
            for c in client.containers.list():
                if own(c.labels.get('hint.experiment_name','')):
                    c.stop(timeout=10);result['containers'].append({'lane':lane,'name':c.name,'stopped':True})
        finally:client.close()
    for service in json.loads((OUT/'config/services.json').read_text()):
        pid=service['pid']
        try:
            if str(OUT).encode() in Path(f'/proc/{pid}/cmdline').read_bytes():os.kill(pid,signal.SIGTERM)
        except (FileNotFoundError,ProcessLookupError):pass
    (OUT/'logs/deadline_cleanup.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':
    (OUT/'config/monitor_process.json').write_text(json.dumps({'pid':os.getpid(),'deadline_utc':'2026-11-26T00:02:00Z','started_at':time.time()})+'\n')
    while time.time()<DEADLINE:
        try:snapshot()
        except Exception as e:
            with (OUT/'logs/monitor_errors.jsonl').open('a') as f:f.write(json.dumps({'timestamp':time.time(),'error':str(e)})+'\n')
        time.sleep(min(30,max(0,DEADLINE-time.time())))
    cutoff()
    snapshot()
