"""Post-freeze audit-only historical examples, excluded from capability extraction."""
import csv
import json
from pathlib import Path

import pyarrow.parquet as pq

OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
if not (OUT/'config/knowledge_freeze.json').exists():raise RuntimeError('Only after knowledge freeze')
descriptions={r['instance_id']:r['problem_statement'] for r in pq.read_table(
    '/srv/lab-disks/disk2/users/xymo/hint-baseline-run/data/deep_swe_tasks.parquet',
    columns=['instance_id','problem_statement']).to_pylist()}
baseline=list(csv.DictReader((OUT/'audit/baseline_attempt_inventory.csv').open()))
def clip(v):
    if isinstance(v,str):return v if len(v)<=1800 else v[:1800]+f'\n[TRUNCATED {len(v)-1800} characters; original retained]'
    if isinstance(v,list):return [clip(x) for x in v]
    if isinstance(v,dict):return {k:clip(x) for k,x in v.items()}
    return v
records=[]
for key,number in [('E01','3'),('E02','6')]:
    row=next(r for r in baseline if r['launch_record']==number)
    path=Path(row['trajectory_path']);raw=json.loads(path.read_text());events=[]
    for agent,trace in raw['trajectories'].items():
        trace=[json.loads(line) for line in trace.splitlines()] if isinstance(trace,str) else trace
        for i,event in enumerate(trace,1):events.append({'agent':agent,'event':i,'record':clip(event)})
    packet={'audit_id':key,'scope':'Post-freeze historical audit only. Never included in K0/K1/K2 extraction, Selection, Test prompts or updates.',
        'historical_launch':row,'original_public_task_description':descriptions[row['task']],
        'historical_metadata':raw.get('metadata',{}),'events':events,
        'actual_student_patch':Path(row['patch_path']).read_text(),
        'formal_evaluation':json.loads(Path(row['eval_path']).read_text()),
        'comparison_development_audit':(OUT/'audit'/('audit_D02.md' if key=='E01' else 'audit_D06.md')).read_text()}
    prompt='''Read-only historical Ofox baseline audit in English, at most1400 words. This supplementary audit happens after main libraries were frozen and must never change them or help current students. All new analysis is through Codex CLI Terra/low, but the historical solver is the different Ofox model recorded in metadata. Cite exact source paths and one-based agent/event IDs. Describe the task, actual operations/code changes, visible validation, formal F2P/P2P, stop reason and known/unknown costs. Determine whether any task teacher Hint was actually supplied; do not invent teacher intervention. Identify independent discovery, reusable constraints, task-specific details, failures, and unverified hypotheses. Compare cautiously with the supplied earlier audit of the same task: different model, runtime and budgets prevent causal group comparisons. Local checks are not formal success; a formally successful attempt need not teach more than a failure. No source ablation or independent transfer test ranks its learning value. Every event ID is supplied but long fields are clipped at1800characters; disclose this and do not infer missing content. Do not propose a student answer, edit code or update capabilities. SDK dollar/token estimates are historical proxy fields, not new CLI billing or actual historical paid cost unless independently established.\n'''+json.dumps(packet,ensure_ascii=False,separators=(',',':'))
    if len(prompt)>700000:raise RuntimeError('Supplementary packet too large')
    target=OUT/'config'/f'audit_{key}_prompt.txt';target.write_text(prompt)
    records.append({'audit_id':key,'trajectory_path':str(path),'events':len(events),
        'all_event_ids_included':True,'per_string_characters_max':1800,
        'prompt_characters':len(prompt),'knowledge_input':False,'prompt_path':str(target)})
(OUT/'audit/baseline_addendum_sources.json').write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps(records))
