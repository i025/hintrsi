"""One diagnostic evaluation of the existing K2 patch; no new student/model call."""
import json
import os
import shutil
import sys
import time
from pathlib import Path

OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
sys.path.insert(0,str(OUT/'source/benchmark/deepswe'))
from eval_deep_swe import evaluate_task,find_patch_file

name='capability_eval_diagnostic_selection_K2_02';task='superjson-error-stack-serialization'
state_path=OUT/'runs/evaluation_diagnostic_02_state.json'
if state_path.exists():raise FileExistsError(state_path)
directory=OUT/'runs'/name
patch=OUT/'runs/capability_v1_matched_prompt_selection_superjson-error-stack-serialization_K2_r1/infer_logs'/task/'turn_1/patch.diff'
if not patch.is_file():raise FileNotFoundError(patch)
source=directory/'fixed_patch_input'
(source/task).mkdir(parents=True)
shutil.copy2(patch,source/task/'patch.diff')
os.environ.update(DOCKER_HOST='unix:///srv/lab-disks/disk2/users/xymo/hint-codex-experiments/vm-lane1/docker.sock',HINT_EXPERIMENT_NAME=name)
state={'stage':'evaluation_diagnostic','task':task,'pid':os.getpid(),'status':'running','started_at':time.time(),
    'new_student_attempts':0,'model_calls':0,'original_patch':str(patch),
    'purpose':'One same-patch evaluation under unchanged evaluator environment, with full raw stdout/stderr retention. Original grade is preserved.',
    'attempts':[{'run_name':name,'group':'K2_fixed_patch_diagnostic','status':'running','started_at':time.time()}]}
def save():state_path.write_text(json.dumps(state,indent=2)+'\n')
save()
try:
    result=evaluate_task(Path('/srv/lab-disks/disk2/users/xymo/hint-baseline-run/data/tasks')/task,task,source,directory/'eval_output')
    state['attempts'][0].update(status='complete',finished_at=time.time(),result=result)
    state['status']='complete'
finally:
    state['finished_at']=time.time();save()
print(json.dumps(state),flush=True)
