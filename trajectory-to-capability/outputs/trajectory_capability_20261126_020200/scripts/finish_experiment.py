"""Reuse the existing scoped shutdown in the final90 seconds, then record evidence."""
import datetime
import json
import os
import signal
import subprocess
import time
from pathlib import Path

import docker
import monitor_experiment as monitor

OUT=monitor.OUT
if time.time()<monitor.DEADLINE-90:raise RuntimeError('Keep monitoring until the final90 seconds')
pid=json.loads((OUT/'config/monitor_process.json').read_text())['pid']
try:
    command=Path(f'/proc/{pid}/cmdline').read_bytes()
    cwd=Path(f'/proc/{pid}/cwd').resolve()
    if b'monitor_experiment.py' in command and cwd==Path.cwd():os.kill(pid,signal.SIGTERM)
except (FileNotFoundError,ProcessLookupError):pass
monitor.cutoff('Final90-second shutdown within the six-hour wall-clock budget')
time.sleep(2)
containers=[];errors=[]
for lane in range(6):
    directory=monitor.OLD/('vm' if lane==0 else f'vm-lane{lane}')
    client=docker.DockerClient(base_url='unix://'+str(directory/'docker.sock'),timeout=10)
    try:
        for container in client.containers.list():containers.append(dict(lane=lane,name=container.name,
            experiment=container.labels.get('hint.experiment_name',''),owned=monitor.own(container.labels.get('hint.experiment_name',''))))
    except Exception as exc:errors.append(dict(lane=lane,error=str(exc)))
    finally:client.close()
services=[]
for item in json.loads((OUT/'config/services.json').read_text()):
    try:command=Path(f"/proc/{item['pid']}/cmdline").read_bytes()
    except FileNotFoundError:command=b''
    services.append(dict(pid=item['pid'],experiment_command_still_present=str(OUT).encode() in command))
try:monitor_command=Path(f'/proc/{pid}/cmdline').read_bytes()
except FileNotFoundError:monitor_command=b''
queue_processes=[]
for path in (OUT/'runs').glob('*_state.json'):
    state=json.loads(path.read_text());queue_pid=state.get('pid')
    try:command=Path(f'/proc/{queue_pid}/cmdline').read_bytes()
    except FileNotFoundError:continue
    if str(OUT).encode() in command and (b'run_capability_experiments.py' in command or b'run_hint_exploration.py' in command):queue_processes.append(queue_pid)
record=dict(verified_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    before_deadline=time.time()<=monitor.DEADLINE,remaining_seconds=monitor.DEADLINE-time.time(),
    active_containers=containers,docker_errors=errors,services=services,
    own_monitor_command_still_present=b'monitor_experiment.py' in monitor_command,
    own_queue_processes_still_present=queue_processes,
    own_active_container_count=sum(c['owned'] for c in containers),
    original_VM_and_image_policy='Original VMs and base task images retained; final shutdown issues no VM/image deletion. Temporary verifier images follow the original evaluator lifecycle.',
    scope='Existing monitor exact experiment-label cleanup only; no other-user process/container stop.')
(OUT/'results/final_verification.json').write_text(json.dumps(record,indent=2)+'\n')
for script in ['collect_attempt_metrics.py','collect_hint_metrics.py','cost_breakdown.py','resource_summary.py',
               'index_current_trajectories.py','export_helpers.py','finalize_report.py']:
    subprocess.run(['/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python','-B','work/'+script],check=True)
manifest=OUT/'config/run_manifest.json';data=json.loads(manifest.read_text())
data.update(status='complete',finished_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    final_verification=str(OUT/'results/final_verification.json'))
manifest.write_text(json.dumps(data,indent=2)+'\n')
p=OUT/'README.md';text=p.read_text().replace('额外Hint探索与截止监控仍在进行','额外Hint探索及截止清理已结束').replace('额外Hint探索已结束，截止监控仍在进行','额外Hint探索及截止清理已结束')
text+='\n实际结束时间（UTC）：'+data['finished_at_utc']+'。截止清理与最终运行核验见 `logs/deadline_cleanup.json`、`results/final_verification.json`。\n'
p.write_text(text)
print(json.dumps(record),flush=True)
