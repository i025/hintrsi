"""Complete the first evaluation of a saved deadline patch, then resume the queue."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

OUT=Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
PYTHON='/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
sys.path.insert(0,str(OUT/'source'))
from run_capability_experiments import evaluate_budget_stop

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--task',default='adaptix-name-mapping-aliases')
p.add_argument('--group',default='B0')
args=p.parse_args()
task=args.task
state_path=OUT/'runs'/f'capability_followup_v2_test_{task}_state.json'
state=json.loads(state_path.read_text())
attempt=state['attempts'][-1]
if attempt['group']!=args.group:raise RuntimeError('Only inspect and recover the last stopped queue entry')
if state['status']!='needs_engineering_review' or attempt['status']!='technical_incomplete':
    raise RuntimeError('Inspect the original queue before recovery')
image=json.loads((OUT/'config'/f'image_{task}.json').read_text())
protocol=json.loads((OUT/'config/protocol.json').read_text())
os.environ.update(DOCKER_HOST=image['docker_host'],HINT_EXPERIMENT_NAME=attempt['run_name'])
for name in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):os.environ.pop(name,None)
state.update(status='deadline_evaluation_recovery',recovery_pid=os.getpid(),recovery_started_at=time.time())
state_path.write_text(json.dumps(state,indent=2)+'\n')
code=evaluate_budget_stop(task,attempt,protocol['verifier_seconds'])
state.update(status='recovered_ready_to_resume' if code in (0,1) else 'needs_engineering_review',recovery_finished_at=time.time())
state_path.write_text(json.dumps(state,indent=2)+'\n')
if code not in (0,1):raise RuntimeError('First deadline-patch evaluation incomplete; inspect without repeating')
command=[PYTHON,'-u','-B',str(OUT/'source/run_capability_experiments.py'),'--stage','test','--task',task,
    '--run_tag','capability_followup_v2','--resume']
split=json.loads((OUT/'config/task_split.json').read_text())
if task==split['hint_transfer_test']:command.append('--interleave_hint_transfer')
raise SystemExit(subprocess.run(command,check=False).returncode)
