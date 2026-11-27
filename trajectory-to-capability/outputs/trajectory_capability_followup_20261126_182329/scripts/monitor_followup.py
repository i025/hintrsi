"""Observe only this continuation's named queues, containers and CLI ledgers."""
import json
import os
import time
import urllib.request
from pathlib import Path

import docker

OUT = Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
(OUT / 'config/monitor_process.json').write_text(json.dumps({'pid': os.getpid(), 'started_at': time.time()}) + '\n')
while not (OUT / 'config/monitor_stop').exists():
    snapshot = {'timestamp': time.time(), 'loadavg': list(os.getloadavg()), 'queues': [], 'containers': [], 'audits': {}}
    try:
        snapshot['bridge'] = json.load(opener.open('http://127.0.0.1:8765/status', timeout=5))
    except Exception as error:
        snapshot['bridge_error'] = str(error)
    names = set()
    for path in (OUT / 'runs').glob('*_state.json'):
        try:
            state = json.loads(path.read_text())
            snapshot['queues'].append({'file': str(path), 'status': state.get('status'),
                'task': state.get('task'), 'attempts': [{k: a.get(k) for k in ('group', 'status', 'started_at', 'finished_at')}
                    for a in state.get('attempts', [])]})
            names.update(a['run_name'] for a in state.get('attempts', []))
        except Exception as error:
            snapshot.setdefault('state_errors', []).append(str(error))
    runtime_path = OUT / 'config/runtime_resume.json'
    lanes = json.loads(runtime_path.read_text()).get('lanes', []) if runtime_path.exists() else []
    for lane in lanes:
        if not lane.get('docker_host'):
            continue
        client = None
        try:
            client = docker.DockerClient(base_url=lane['docker_host'], timeout=10)
            for container in client.containers.list():
                label = container.labels.get('hint.experiment_name', '')
                if label in names:
                    stat = container.stats(stream=False)
                    snapshot['containers'].append({'lane': lane['lane'], 'name': container.name,
                        'experiment': label, 'status': container.status,
                        'memory_bytes': stat.get('memory_stats', {}).get('usage'),
                        'cpu_total_ns': stat.get('cpu_stats', {}).get('cpu_usage', {}).get('total_usage')})
        except Exception as error:
            snapshot.setdefault('docker_errors', []).append({'lane': lane['lane'], 'error': str(error)})
        finally:
            if client:
                client.close()
    for project in ('hintrsi', 'scene'):
        path = OUT / 'config' / (project + '_full_audit_manifest.json')
        if path.exists():
            data = json.loads(path.read_text())
            snapshot['audits'][project] = {k: data.get(k) for k in ('status', 'complete_files', 'completed_chunks')}
    (OUT / 'logs/monitor_latest.json').write_text(json.dumps(snapshot, indent=2) + '\n')
    with (OUT / 'logs/monitor.jsonl').open('a') as stream:
        stream.write(json.dumps(snapshot) + '\n')
    time.sleep(30)
