"""One bounded same-patch evaluation; no new student or answer modification."""
import json
import os
import shutil
import sys
import time
from pathlib import Path

OUT = Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
OLD = OUT.parent / 'trajectory_capability_20261126_020200'
sys.path.insert(0, str(OUT / 'source/benchmark/deepswe'))
from eval_deep_swe import evaluate_task

name = 'capability_followup_known_good_control_01'
task = 'claude-code-by-agents-recursive-delegation'
state_path = OUT / 'runs' / (name + '_state.json')
if state_path.exists():
    raise FileExistsError(state_path)
source = OLD / f'runs/capability_hint_development_{task}_Error_r1/infer_logs/{task}/turn_1/patch.diff'
directory = OUT / 'runs' / name
patch_dir = directory / 'fixed_patch_input' / task
patch_dir.mkdir(parents=True)
shutil.copy2(source, patch_dir / 'patch.diff')
assert source.read_bytes() == (patch_dir / 'patch.diff').read_bytes()
lane = next(r for r in json.loads((OUT / 'config/runtime_resume.json').read_text())['lanes'] if r['lane'] == 0)
os.environ.update(DOCKER_HOST=lane['docker_host'], HINT_EXPERIMENT_NAME=name,
    HINT_VERIFIER_TIMEOUT_SEC='900')
state = {'task': task, 'stage': 'same_patch_diagnostic', 'pid': os.getpid(),
    'status': 'running', 'started_at': time.time(), 'new_student_attempts': 0,
    'model_calls': 0, 'original_patch': str(source), 'patch_bytes': source.stat().st_size,
    'same_patch_direct_content': True, 'verifier_seconds': 900,
    'condition_difference': 'Known previously successful Development Error-guided patch used once as an evaluator environment control after reproducible NoHint timeout. Same 900s exec bound, grader, tests, memory and VM; no student retry or patch changes.',
    'attempts': [{'run_name': name, 'group': 'Known_good_Error_patch', 'status': 'running', 'started_at': time.time()}]}
def save():
    state_path.write_text(json.dumps(state, indent=2) + '\n')
save()
try:
    result = evaluate_task(Path('/srv/lab-disks/disk2/users/xymo/hint-baseline-run/data/tasks') / task,
        task, patch_dir.parent, directory / 'eval_output')
    state.update(status='complete' if result.get('reward') is not None else 'evaluation_incomplete', result=result)
    state['attempts'][0].update(status=state['status'], finished_at=time.time(), result=result)
finally:
    state['finished_at'] = time.time()
    save()
print(json.dumps({'state': str(state_path), 'status': state['status']}), flush=True)
