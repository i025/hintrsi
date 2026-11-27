"""Supplement historical comparisons after freeze, with no learner feedback."""
import csv
import gzip
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pyarrow.parquet as pq

OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
PYTHON='/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
if not (OUT/'config/knowledge_freeze.json').exists():raise RuntimeError('Post-freeze audit only')
inventory=list(csv.DictReader((OUT/'trajectory_inventory.csv').open()))
description=next(r['problem_statement'] for r in pq.read_table(
    '/srv/lab-disks/disk2/users/xymo/hint-baseline-run/data/deep_swe_tasks.parquet',
    columns=['instance_id','problem_statement']).to_pylist() if r['instance_id']=='claude-code-by-agents-recursive-delegation')
selections=[('E03','08','B','1'),('E04','08','H','1'),('E05','08','I','1'),
    ('E06','12','H','2'),('E07','12','B','2'),('E08','12','B','3'),('E09','12','M','3')]
def clip(value):
    if isinstance(value,str):return value if len(value)<=1800 else value[:1800]+f'\n[TRUNCATED {len(value)-1800}characters; original retained]'
    if isinstance(value,list):return [clip(x) for x in value]
    if isinstance(value,dict):return {k:clip(x) for k,x in value.items()}
    return value
records=[]
for audit_id,batch,group,round_num in selections:
    marker=f'codex_parallel_{batch}_lane0_{group}_r{round_num}/'
    row=next(r for r in inventory if r['project']=='hintrsi' and r['kind']=='student'
        and r['task']=='claude-code-by-agents-recursive-delegation' and marker in r['path'])
    path=Path(row['path']);raw=json.loads(gzip.open(path,'rt').read() if path.suffix=='.gz' else path.read_text())
    events=[]
    for agent,trace in raw['trajectories'].items():
        trace=[json.loads(line) for line in trace.splitlines()] if isinstance(trace,str) else trace
        events.extend(dict(agent=agent,event=i,record=clip(event)) for i,event in enumerate(trace,1))
    packet=dict(audit_id=audit_id,scope='Post-freeze historical audit; never knowledge generation/selection/student input.',
        original_public_description=description,inventory=row,metadata=raw.get('metadata',{}),events=events,
        final_student_patch=Path(row['patch_path']).read_text() if row['patch_path'] else None,
        formal_evaluation=json.loads(Path(row['eval_path']).read_text()) if row['eval_path'] else None,
        actual_captured_materials={})
    for name in ['system_prompt_actual.json','system_prompt_config.json','online_teacher_events.json','online_teacher_state.json']:
        p=path.parent/name
        if p.exists():packet['actual_captured_materials'][str(p)]=json.loads(p.read_text())
    prompt='''Read-only historical comparison audit in English, at most1000words. Cite exact original paths and one-based agent/event numbers. All event IDs supplied; individual event strings clipped1800chars, disclose that. Captured initial system prompt/online events and finalpatch/formalevaluation supplied separately without that event-field clipping. Identify actual task work, changed behavior, local versus formal checks, teacher knowledge actually received, executable adoption versus selfclaim, independent exploration, stop reason and technical versus algorithmic failure/empty patch. Archive Hint availability is not receipt; after-round review is not input. This historical batch may differ from batch12/source13 in model, runtime, budgets or tool settings: report recorded conditions and unknowns, no causal group comparison or invented equivalence. Particularly assess a no-Hint full pass if present; do not assume I2 is the only historical success or that teacher is necessary. A later failed round may be a fresh patch, not an edit atop a prior patch; inspect evidence before claiming regression. Unknown historical cost is not zero; SDK estimates are not actual CLI billing. Distinguish actual finite officialgrade from full public-contract proof. Candidate transferable lessons are hypotheses, not measured transfer; no source ablation ranks learning value. No code fixes, library updates or feedback to current students.\nEVIDENCE:\n'''+json.dumps(packet,ensure_ascii=False,separators=(',',':'))
    if len(prompt)>700000:raise RuntimeError('Historical audit exceeds input cap')
    p=OUT/'config'/f'audit_{audit_id}_prompt.txt';p.write_text(prompt)
    records.append(dict(audit_id=audit_id,trajectory_path=str(path),events=len(events),all_event_ids_included=True,
        per_string_characters_max=1800,prompt_characters=len(prompt),prompt_path=str(p),knowledge_input=False))
(OUT/'audit/historical_comparison_sources.json').write_text(json.dumps(records,indent=2)+'\n')
def run(record):
    output=OUT/'audit'/('audit_'+record['audit_id']+'.md')
    if output.exists():return 0
    return subprocess.run([PYTHON,'-u','-B','work/model_job.py','capability-audit-'+record['audit_id'],
        record['prompt_path'],str(output)],check=False).returncode
with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,records))
print(json.dumps({'audits':len(records),'events':sum(r['events'] for r in records),'failed':sum(bool(x) for x in results)}),flush=True)
