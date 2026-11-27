"""Finish the saved queues through existing runners, freezing before any Test."""
import json
import os
import subprocess
import time
from pathlib import Path

ROOT=Path.cwd()
OUT=Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
PYTHON='/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
state_path=OUT/'config/final_stages_process.json'
if state_path.exists():raise FileExistsError(state_path)
record={'pid':os.getpid(),'started_at':time.time(),'status':'waiting_for_selection','test_processes':[]}
def save():state_path.write_text(json.dumps(record,indent=2)+'\n')
def helper(name,*args):
    subprocess.run([PYTHON,'-u','-B',str(ROOT/'work_followup'/name),*args],check=True)
def alive(pid):
    try:return b'\nState:\tZ' not in Path(f'/proc/{pid}/status').read_bytes()
    except FileNotFoundError:return False
save()
try:
    selection=OUT/'runs/capability_followup_v2_selection_mashumaro-flattened-dataclass-fields_state.json'
    while True:
        current=json.loads(selection.read_text())
        if current['status']=='complete':break
        diagnostic=OUT/'runs/capability_followup_selection_same_patch_01_state.json'
        parent=json.loads(diagnostic.read_text()) if diagnostic.exists() else {}
        if current['status'] in ('needs_engineering_review','interrupted') or not any(alive(p) for p in [current['pid'],parent.get('pid',0)] if p):
            raise RuntimeError('Selection stopped before completion; inspect preserved state rather than rerun')
        time.sleep(30)
    helper('collect_attempt_metrics.py')
    helper('validate_model_conditions.py')
    validation=json.loads((OUT/'results/model_condition_validation.json').read_text())
    if validation['condition_mismatches']:raise RuntimeError('Actual model/effort mismatch; inspect before Test')
    helper('freeze_libraries.py')
    record['status']='test_running';save()
    split=json.loads((OUT/'config/task_split.json').read_text())
    processes=[]
    for task in split['test']:
        command=[PYTHON,'-u','-B',str(OUT/'source/run_capability_experiments.py'),
            '--stage','test','--task',task,'--run_tag','capability_followup_v2']
        if task==split['hint_transfer_test']:command.append('--interleave_hint_transfer')
        log=OUT/'logs'/f'final_test_queue_{task}.log'
        with log.open('xb') as stream:
            process=subprocess.Popen(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        processes.append(process)
        record['test_processes'].append({'task':task,'pid':process.pid,'command':command,'log':str(log),'started_at':time.time()});save()
    while any(p.poll() is None for p in processes):time.sleep(30)
    for task in split['test']:
        final=json.loads((OUT/'runs'/f'capability_followup_v2_test_{task}_state.json').read_text())
        if final['status']!='complete':raise RuntimeError('A Test queue stopped; preserve it for engineering review')
    helper('collect_attempt_metrics.py')
    helper('validate_model_conditions.py')
    helper('update_inventory.py')
    record['status']='posthoc_running';save()
    for stage in ['selection','test','hint_transfer']:helper('analyze_completed_attempts.py','--stage',stage)
    helper('collect_attempt_metrics.py')
    record['status']='experiment_queues_complete_reports_pending'
except BaseException as error:
    record.update(status='needs_engineering_review',error=str(error));raise
finally:
    record['finished_at']=time.time();save()
