"""Prepare incremental arm-specific updates from the fixed new Development cohort."""
import json
from pathlib import Path

OUT = Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
OLD = OUT.parent / 'trajectory_capability_20261126_020200'
split = json.loads((OUT / 'config/task_split.json').read_text())
metrics = json.loads((OUT / 'results/attempt_metrics.json').read_text())
development = [r for r in metrics if r['stage'] == 'development']
if len(development) != 4 or any(r['status'] not in ('complete', 'evaluation_timeout', 'technical_incomplete')
        or not r['trajectory_path'] for r in development):
    raise RuntimeError('All four new Development attempts must finish with preserved trajectories before updating')

def clip(value):
    if isinstance(value, str) and len(value) > 1800:
        return value[:1800] + f'\n[TRUNCATED {len(value)-1800} original characters; source retained]'
    if isinstance(value, list):
        return [clip(v) for v in value]
    if isinstance(value, dict):
        return {k: clip(v) for k, v in value.items()}
    return value

metadata = {r['instance_id']: r for r in json.loads((OUT / 'config/new_task_public_metadata.json').read_text())}
records = []
for arm in ('K1', 'K2'):
    evidence = {'arm': arm, 'previous_library': (OUT / 'knowledge' / (arm + '_v1.md')).read_text(),
        'prior_development_analysis': (OLD / 'knowledge' / (arm + '_analysis_v1.md')).read_text(),
        'prior_analysis_provenance': 'Fixed original D01-D08 Development cohort, no Selection/Test feedback; used as incremental memory rather than rereading old raw evidence.',
        'new_own_development_attempts': []}
    for task in split['development']:
        row = next(r for r in development if r['task'] == task and r['group'] == arm + '_v1')
        trace = Path(row['trajectory_path'])
        data = json.loads(trace.read_text())
        events = []
        for agent, value in data['trajectories'].items():
            values = [json.loads(line) for line in value.splitlines()] if isinstance(value, str) else value
            for number, event in enumerate(values, 1):
                events.append({'agent': agent, 'event': number, 'record': clip(event)})
        patch = (trace.parent / 'patch.diff').read_text()
        evidence['new_own_development_attempts'].append({'task': task, 'source': str(trace),
            'public_description': metadata[task]['problem_statement'], 'events': events,
            'final_patch': patch[:30000] + (f'\n[TRUNCATED {len(patch)-30000} characters]' if len(patch)>30000 else ''),
            'actual_loaded_capability': Path(row['loaded_knowledge_path']).read_text() if row['loaded_knowledge_path'] else None,
            'formal_outcome': {k: row[k] for k in ['status', 'formal_success', 'f2p_passed', 'f2p_total', 'p2p_passed', 'p2p_total', 'stop_reason', 'outcome']},
            'cost': {k: row[k] for k in ['model_requests', 'input_tokens', 'output_tokens', 'cached_input_tokens', 'wall_seconds', 'tool_calls_requested']}})
    raw = json.dumps(evidence, ensure_ascii=False, separators=(',', ':'))
    common = '''Incremental V2 capability update using Development evidence only. Output English at most 2200 words. No Selection/Test task, scores, hints, GT or hidden tests are supplied. You may keep, add, revise, delete or merge V1 knowledge; knowledge count need not grow. Cite old source IDs and exact new task/agent/event IDs. Distinguish observed code/tool/test facts from inferred semantic labels, and algorithm failures from setup errors, empty patches, budget stops and missing evaluations. Never present a clipped observation as full verification. Do not output a solution, patch or benchmark-specific answer for future tasks. The two arms intentionally generated their own on-policy new trajectories; do not claim identical raw evidence or isolate state alignment causally in this recursive update.\n'''
    instruction = ('Ordinary chronological trajectory-distillation baseline: read each new attempt in sequence, summarize transferable experience, teacher-prior use, effective repairs, failures, applicability and caveats. Do not construct explicit state-alignment units or cross-trajectory functional-state tables.\n' if arm == 'K1' else
        'State-aligned update: first produce explicit evidence-grounded state transition units with inferred semantic subgoal, observed program state, operation and affected behavior/module, tool return, visible failure/test, any actually received guidance, subsequent repair and verification. Align old/new and successful/failed evidence by functional goal, behavioral constraint and test class, never equal event number. Label inferences. Include a compact alignment table; distinguish shared implementation-independent constraints, effective repair knowledge, applicability/complementarity and incidental actions. Do not replace this with ordinary full-text summarization.\n')
    prompt = common + instruction + raw
    if len(prompt)>700000:
        raise RuntimeError(f'{arm} input exceeds the common cap; preserve and inspect before any extraction')
    name = arm + '_v2'
    packet = OUT / 'evidence' / (name + '_development_input.json')
    packet.write_text(raw + '\n')
    (OUT / 'config' / (name + '_analysis_prompt.txt')).write_text(prompt)
    records.append({'arm': arm, 'input_characters': len(prompt), 'raw_input_characters': len(raw),
        'new_attempts': 2, 'per_field_characters_max': 1800, 'patch_characters_max': 30000,
        'old_representation': 'previous frozen V1 plus original Development intermediate analysis',
        'packet': str(packet), 'model_calls_budget': 2})
(OUT / 'config/v2_extraction_inputs.json').write_text(json.dumps(records, indent=2) + '\n')
print(json.dumps(records), flush=True)
