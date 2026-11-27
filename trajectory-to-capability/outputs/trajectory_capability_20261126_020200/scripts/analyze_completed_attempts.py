"""Post-hoc analysis only: never alters knowledge or student workspaces."""
import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
PYTHON='/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
p=argparse.ArgumentParser();p.add_argument('--stage',choices=['selection','test'],required=True);args=p.parse_args()
rows=json.loads((OUT/'results/attempt_metrics.json').read_text())
if args.stage=='test':
    import pyarrow.parquet as pq
    descriptions={r['instance_id']:r['problem_statement'] for r in pq.read_table(
        '/srv/lab-disks/disk2/users/xymo/hint-baseline-run/data/deep_swe_tasks.parquet',
        columns=['instance_id','problem_statement']).to_pylist()}
jobs=[]
def short(value,limit):
    if isinstance(value,str):return value if len(value)<=limit else value[:limit]+f'\n[TRUNCATED {len(value)-limit} remaining characters; original file retained]'
    if isinstance(value,list):return [short(x,limit) for x in value]
    if isinstance(value,dict):return {k:short(v,limit) for k,v in value.items()}
    return value
for row in rows:
    if row['stage']!=args.stage or row['status']!='complete' or not row['trajectory_path']:continue
    name='posthoc_'+row['stage']+'_'+row['task']+'_'+row['group']
    if 'matched_prompt' in row['run_name']:name=name.replace('posthoc_selection_','posthoc_selection_matched_',1)
    output=OUT/'audit'/f'{name}.md'
    if output.exists():continue
    path=Path(row['trajectory_path']);d=json.loads(path.read_text());events=[]
    for agent,trace in d['trajectories'].items():
        trace=[json.loads(line) for line in trace.splitlines()] if isinstance(trace,str) else trace
        for i,e in enumerate(trace,1):
            events.append({'agent':agent,'event':i,'type':e.get('type'),'content':short(e.get('message',{}).get('content',[]),1800)})
    cap=Path(row['loaded_knowledge_path']).read_text() if row['loaded_knowledge_path'] else None
    data={'actual_attempt_metrics':row,'trajectory_source':str(path),'events':events,
        'student_final_metadata':d.get('metadata',{}),'actual_loaded_capabilities':cap,
        'final_student_patch':short((path.parent/'patch.diff').read_text(),30000),
        'formal_evaluation':json.loads(Path(row['eval_path']).read_text()) if row['eval_path'] else None}
    if args.stage=='test':data['original_public_task_description']=descriptions[row['task']]
    text=json.dumps(data,ensure_ascii=False,separators=(',',':'))
    if len(text)>680000:
        data['events']=short(events,650);text=json.dumps(data,ensure_ascii=False,separators=(',',':'))
    if len(text)>680000:raise RuntimeError('Posthoc packet still exceeds declared cap; inspect rather than silently dropping events')
    prompt='''Post-hoc observational audit only. Output English, at most 1300 words. The student run is over; no output will be returned to it or used to update the frozen capability libraries. Cite exact agent/event IDs and source paths. Describe task exploration, actual program changes and validation. For each relevant loaded capability, distinguish (a) direct executable behavior consistent with it, (b) a mere student claim, (c) absent or contrary behavior, and (d) unassessable truncation. A matching behavior is not proof that the library caused it, especially when an ordinary base student could do the same. For B0 there was no library: report baseline behaviors without attributing knowledge adoption. Explicitly examine extra or unnecessary work, regressions and costs. Distinguish local checks from official F2P/P2P and full success, and a budget/technical stop from normal completion. Do not infer the causes of unseen failures or fill unknown metrics with zero. SDK total_cost_usd is a proxy estimate, not actual CLI billing; report no actual dollar fee. Do not propose a new task solution, write code, update a skill, or claim long-term generality. End with a concise evidence table of capability/theme, observed action, event IDs, and inference limits.\n'''+text
    file=OUT/'config'/f'{name}_prompt.txt';file.write_text(prompt)
    jobs.append((name,file,output))
def run(job):
    name,file,output=job
    return subprocess.run([PYTHON,'-u','-B','work/model_job.py','capability-'+name,str(file),str(output)],check=False).returncode
with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,jobs))
print(json.dumps({'stage':args.stage,'new_audits':len(jobs),'failed':sum(bool(x) for x in results)}),flush=True)
