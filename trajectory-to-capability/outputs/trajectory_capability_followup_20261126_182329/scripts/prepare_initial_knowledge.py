"""Prepare teacher-only and Hint-trajectory transfer inputs without new Test data."""
import json
from pathlib import Path
import pyarrow.parquet as pq

OUT = Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
OLD = OUT.parent / 'trajectory_capability_20261126_020200'
split = json.loads((OUT / 'config/task_split.json').read_text())
old_split = json.loads((OLD / 'config/task_split.json').read_text())
descriptions = pq.read_table('/srv/lab-disks/disk2/users/xymo/hint-baseline-run/data/deep_swe_tasks.parquet',
    columns=['instance_id', 'problem_statement']).to_pylist()
development = old_split['development'] + split['development']
teacher_input = [r for r in descriptions if r['instance_id'] in development]
(OUT / 'config/K0_v2_analysis_prompt.txt').write_text('''Teacher-knowledge-only condition. Output English, at most 2200 words. You see only five Development descriptions and may use general programming knowledge. You have no student trajectories, observed solutions, patches, GT, Selection or Test information. Do not guess empirical outcomes or solve the tasks. Propose general reusable capabilities with applicability, behavior constraints, candidate methods, verification, limits and source descriptions. Label these as teacher prior knowledge, not learned evidence.\n''' + json.dumps(teacher_input, ensure_ascii=False))

def clip(value):
    if isinstance(value, str) and len(value) > 1800:
        return value[:1800] + f'\n[TRUNCATED {len(value)-1800} original characters; full source retained]'
    if isinstance(value, list):
        return [clip(v) for v in value]
    if isinstance(value, dict):
        return {k: clip(v) for k, v in value.items()}
    return value

task = 'claude-code-by-agents-recursive-delegation'
metrics = json.loads((OLD / 'results/hint_attempt_metrics.json').read_text())
for variant in ['NoHint', 'Error', 'Strategy', 'Exploration']:
    row = next(r for r in metrics if r['group'] == variant)
    trajectory = Path(row['trajectory_path'])
    data = json.loads(trajectory.read_text())
    events = []
    for agent, trace in data['trajectories'].items():
        records = [json.loads(line) for line in trace.splitlines()] if isinstance(trace, str) else trace
        for number, event in enumerate(records, 1):
            events.append({'agent': agent, 'event': number, 'record': clip(event)})
    hint_file = OLD / f'hints/{variant}_r1.md'
    evidence = {'condition': variant, 'task': task, 'source_trajectory': str(trajectory),
        'public_development_description': next(r['problem_statement'] for r in descriptions if r['instance_id'] == task),
        'actual_delivered_hint': hint_file.read_text() if hint_file.exists() else None,
        'student_events': events, 'final_patch': (trajectory.parent / 'patch.diff').read_text(),
        'formal_outcome': {k: row.get(k) for k in ['status', 'formal_success', 'f2p_passed', 'f2p_total', 'p2p_passed', 'p2p_total', 'evaluation_timed_out']},
        'source_limit': 'NoHint original evaluation is missing after timeout, never a normal zero. No follow-up diagnostic or hidden-test source is supplied. Actual Hint exposure was verified in the original request ledger. Single source trajectory; its patch is Development evidence only, not a reusable answer.'}
    name = 'HT_' + variant
    raw = json.dumps(evidence, ensure_ascii=False, separators=(',', ':'))
    prompt = '''Independent Hint-to-knowledge transfer extraction, chronological distillation. Output English, at most 2200 words. Only this fixed historical Development trajectory, public description, actual delivered Hint and observed results are available. You receive no new Selection/Test task information. Extract reusable programming knowledge, effective autonomous and teacher-consistent behavior, failed or incomplete approaches, applicability and limitations. Cite exact source event IDs. Do not copy the solution, patch, task-specific API names, provider-specific implementation, hidden-test recipe or answer code into reusable knowledge. A formal pass is not proof of learning and a timeout is not an algorithmic zero. Mere Hint exposure or temporal consistency does not establish causation. No state-alignment advantage is added to any variant; use ordinary chronological distillation for every condition.\n''' + raw
    assert len(prompt) <= 700000
    (OUT / 'config' / (name + '_analysis_prompt.txt')).write_text(prompt)
    (OUT / 'evidence' / (name + '_development_input.json')).write_text(raw + '\n')
    print(name, len(raw))

# Document the incremental representation before V2 extraction or any new scores.
path = OUT / 'config/protocol.json'
protocol = json.loads(path.read_text())
protocol['V2_training'] = 'Each arm independently solves the same two new Development tasks using its unchanged V1. The update receives its own V1, the original arm-specific Development intermediate analysis (provenance: fixed D01-D08 cohort), and its own two new trajectories with identical per-field clipping and input caps. Original old raw evidence remains archived; it is represented by the prior analysis during incremental update. No Selection/Test information enters extraction. On-policy new data differ intentionally; V2 comparison is not an identical-evidence alignment ablation.'
path.write_text(json.dumps(protocol, indent=2) + '\n')
