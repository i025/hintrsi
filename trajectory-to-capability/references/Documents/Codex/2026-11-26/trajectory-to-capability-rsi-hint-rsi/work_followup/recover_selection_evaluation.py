"""One bounded same-patch diagnostic, followed by the untouched remaining queue."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

OUT=Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
PYTHON='/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
sys.path.insert(0,str(OUT/'source/benchmark/deepswe'))
from eval_deep_swe import evaluate_task

task='mashumaro-flattened-dataclass-fields'
name='capability_followup_selection_same_patch_01'
state_path=OUT/'runs'/(name+'_state.json')
if state_path.exists():raise FileExistsError(state_path)
original_run=f'capability_followup_v2_selection_{task}_K1_v1'
source=OUT/'runs'/(original_run+'_r1')/'infer_logs'/task/'turn_1/patch.diff'
directory=OUT/'runs'/name
patch_dir=directory/'fixed_patch_input'/task
patch_dir.mkdir(parents=True)
shutil.copy2(source,patch_dir/'patch.diff')
assert source.read_bytes()==(patch_dir/'patch.diff').read_bytes()
lane=next(r for r in json.loads((OUT/'config/runtime_resume.json').read_text())['lanes'] if r['lane']==1)
os.environ.update(DOCKER_HOST=lane['docker_host'],HINT_EXPERIMENT_NAME=name,HINT_VERIFIER_TIMEOUT_SEC='900')
state={'task':task,'stage':'same_patch_diagnostic','pid':os.getpid(),'status':'running','started_at':time.time(),
    'new_student_attempts':0,'model_calls':0,'original_run':original_run,'original_patch':str(source),
    'patch_bytes':source.stat().st_size,'same_patch_direct_content':True,'verifier_seconds':900,
    'condition_difference':'None in patch, grader, tests or timeout. One repeat diagnoses the missing official report, never reruns the student.',
    'attempts':[{'run_name':name,'group':'Selection_K1_v1_same_patch','status':'running','started_at':time.time()}]}
def save():state_path.write_text(json.dumps(state,indent=2)+'\n')
save()
try:
    result=evaluate_task(Path('/srv/lab-disks/disk2/users/xymo/hint-baseline-run/data/tasks')/task,
        task,patch_dir.parent,directory/'eval_output')
    state.update(status='evaluation_timeout' if result.get('verifier_timed_out') else 'complete' if result.get('reward') is not None else 'evaluation_incomplete',result=result)
    state['attempts'][0].update(status=state['status'],finished_at=time.time(),result=result)
finally:
    state['finished_at']=time.time();save()
print(json.dumps({'diagnostic_state':str(state_path),'status':state['status']}),flush=True)
command=[PYTHON,'-u','-B',str(OUT/'source/run_capability_experiments.py'),'--stage','selection','--task',task,
    '--run_tag','capability_followup_v2','--resume']
raise SystemExit(subprocess.run(command,check=False).returncode)
