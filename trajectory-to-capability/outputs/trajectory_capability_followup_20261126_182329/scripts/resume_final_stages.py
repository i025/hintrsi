"""Observe existing queues after engineering recovery; never launch a student."""
import json
import os
import subprocess
import time
from pathlib import Path

ROOT=Path.cwd()
OUT=Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
PYTHON='/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
state_path=OUT/'config/final_stages_process.json'
record=json.loads(state_path.read_text())
def alive(pid):
    try:return b'\nState:\tZ' not in Path(f'/proc/{pid}/status').read_bytes()
    except FileNotFoundError:return False
if alive(record['pid']):raise RuntimeError('Original controller is still active')
record.setdefault('resumptions',[]).append({'previous_pid':record['pid'],'pid':os.getpid(),'at':time.time(),
    'reason':'Observe preserved queues after the first evaluation of a student-deadline patch; no student restart'})
record.update(pid=os.getpid(),status='test_running')
def save():state_path.write_text(json.dumps(record,indent=2)+'\n')
def helper(name,*args):subprocess.run([PYTHON,'-u','-B',str(ROOT/'work_followup'/name),*args],check=True)
save()
try:
    tasks=json.loads((OUT/'config/task_split.json').read_text())['test']
    while True:
        queues=[json.loads((OUT/'runs'/f'capability_followup_v2_test_{task}_state.json').read_text()) for task in tasks]
        if all(q['status']=='complete' for q in queues):break
        for queue in queues:
            if queue['status']=='complete':continue
            if queue['status'] in ('needs_engineering_review','interrupted'):
                raise RuntimeError('A queue requires engineering inspection; preserve it without implicit retry')
            if not any(alive(queue.get(key,0)) for key in ['pid','recovery_pid'] if queue.get(key)):
                raise RuntimeError('Queue and recovery process stopped before completion')
        time.sleep(30)
    record['queues_finished_at']=time.time();save()
    for name in ['collect_attempt_metrics.py','validate_model_conditions.py','update_inventory.py']:helper(name)
    record['status']='posthoc_running';save()
    for stage in ['selection','test','hint_transfer']:helper('analyze_completed_attempts.py','--stage',stage)
    helper('collect_attempt_metrics.py')
    record['status']='experiment_queues_complete_reports_pending'
except BaseException as error:
    record.update(status='needs_engineering_review',error=str(error));raise
finally:
    record['finished_at']=time.time();save()
