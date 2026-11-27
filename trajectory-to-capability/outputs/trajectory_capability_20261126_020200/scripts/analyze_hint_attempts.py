"""CLI post-hoc audit of completed optional attempts; never feedback to a student."""
import json
import subprocess
from pathlib import Path

import pyarrow.parquet as pq

OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
PYTHON='/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
rows=json.loads((OUT/'results/hint_attempt_metrics.json').read_text())
descriptions={r['instance_id']:r['problem_statement'] for r in pq.read_table(
    '/srv/lab-disks/disk2/users/xymo/hint-baseline-run/data/deep_swe_tasks.parquet',
    columns=['instance_id','problem_statement']).to_pylist()}
progress=OUT/'logs/hint_progress/progress.jsonl'
checks=[json.loads(line) for line in progress.open()] if progress.exists() else []
def short(value,limit):
    if isinstance(value,str):return value if len(value)<=limit else value[:limit]+f'\n[TRUNCATED {len(value)-limit} characters; original retained]'
    if isinstance(value,list):return [short(x,limit) for x in value]
    if isinstance(value,dict):return {k:short(v,limit) for k,v in value.items()}
    return value
jobs=[]
for row in rows:
    if not row.get('student_and_evaluation_finished') or not row['trajectory_path']:continue
    name='posthoc_hint_exploration_'+row['task']+'_'+row['group'];output=OUT/'audit'/(name+'.md')
    if output.exists():continue
    trajectory=Path(row['trajectory_path']);d=json.loads(trajectory.read_text());events=[]
    for agent,trace in d['trajectories'].items():
        trace=[json.loads(line) for line in trace.splitlines()] if isinstance(trace,str) else trace
        for i,event in enumerate(trace,1):events.append(dict(agent=agent,event=i,type=event.get('type'),content=short(event.get('message',{}).get('content',[]),1800)))
    data=dict(metrics=row,trajectory_source=str(trajectory),events=events,metadata=d.get('metadata',{}),
        public_problem=descriptions[row['task']],final_patch=short((trajectory.parent/'patch.diff').read_text(),30000),
        evaluation=json.loads(Path(row['eval_path']).read_text()) if row['eval_path'] else None,
        teacher_checks=[c for c in checks if c['session']==row['session']])
    validation=json.loads((OUT/'results/hint_condition_validation.json').read_text())
    data['actual_initial_request_comparison']=[x for x in validation['initial_requests'] if x['group']==row['group']]
    data['actual_delivered_hint_request_entry']=[x for x in validation['delivered_hint_actual_request_entry'] if x['group']==row['group']]
    data['initial_hint_note']='Guided arms deliberately have empty initial Hint files. The original initial-system-Hint checker may warn missing Hint; this is not evidence that the later online Hint was absent. Actual later request entry is checked separately above.'
    online=trajectory.parent/'online_teacher_events.json'
    if online.exists():data['online_teacher_events']=json.loads(online.read_text())
    prompt='''Read-only post-hoc observational audit in English, at most1200 words. This is an optional Development Hint trial, not a fresh transfer test. Cite exact source paths and agent/event numbers. Describe actual state transitions, code changes, local validation, official F2P/P2P and full success separately. Distinguish SDK callbacks, actual teacher checks, candidate/screen model calls, screened/delivered Hint, and actual next-request entry/action adoption. Inspect the actual feedback against the requested Error/Strategy/Exploration style; a named variant may deliver no Hint or mixed guidance. Do not label a treatment delivered merely because a model was called. Use before/after executable evidence for student response, not only student self-claims; temporal order is not causal proof. NoHint had no online teacher. All attempts start from common initial code with fresh contexts, no restoration of a shared intermediate state; trajectories are stochastic, not strict counterfactual replay. There is no independent Hint-to-knowledge transfer evaluation. Different final grades alone do not measure learning value. Distinguish environment/technical failures from algorithmic failures, and local tests from hidden formal tests. Do not propose task code fixes, generate a library, or return feedback to a student. End with observations, candidate transferable lessons and unverified hypotheses, clearly separated.\nEVIDENCE:\n'''+json.dumps(data,ensure_ascii=False,separators=(',',':'))
    if len(prompt)>680000:raise RuntimeError('Optional audit exceeds input budget')
    path=OUT/'config'/(name+'_prompt.txt');path.write_text(prompt)
    result=subprocess.run([PYTHON,'-u','-B','work/model_job.py','capability-'+name,str(path),str(output)],check=False)
    jobs.append(dict(name=name,returncode=result.returncode))
print(json.dumps({'new_audits':jobs}),flush=True)
