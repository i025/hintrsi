import csv
import gzip
import json
import re
from collections import Counter
from pathlib import Path

HOME = Path('/srv/lab-disks/disk2/users/xymo')
OUT = Path.cwd() / 'outputs/trajectory_capability_20261126_020200'
ROOTS = [HOME / n for n in ('hint-experiment-handoff', 'hint-baseline-run/runs', 'hint-baseline-run/preflight',
    'hint-codex-experiments/runs', 'hint-codex-experiments/preflight')]
fields = ['project','kind','path','bytes','task','group','round','events','tools',
          'patch_path','patch_bytes','eval_path','status','f2p_passed','f2p_total','p2p_passed','p2p_total',
          'teacher_materials','audit_depth','error']
rows = []
TASK_NAMES = {p.name for p in (HOME/'hint-baseline-run/data/tasks').iterdir() if p.is_dir()}
def load(p):
    with (gzip.open(p, 'rt') if p.suffix == '.gz' else p.open()) as f:
        return json.load(f)

def events(d):
    result = []
    for agent, data in d.get('trajectories', {}).items():
        if isinstance(data, str):
            for i, line in enumerate(data.splitlines(), 1):
                try: e = json.loads(line)
                except ValueError: continue
                result.append({'agent':agent, 'event':i, 'record':e})
        elif isinstance(data, list):
            result.extend({'agent':agent, 'event':i, 'record':e} for i,e in enumerate(data,1))
    return result

for root in ROOTS:
    for p in sorted(root.rglob('trajs.json*')):
        if p.name not in ('trajs.json', 'trajs.json.gz'): continue
        s = str(p)
        kind = 'student' if '/infer_logs/' in s else 'teacher' if '/teacher/' in s or '/hint_gen/' in s else 'preflight'
        row = dict.fromkeys(fields, '')
        row.update(project='hintrsi', kind=kind, path=s, bytes=p.stat().st_size, audit_depth='indexed')
        m = re.search(r'/infer_logs/([^/]+)/',s)
        if m: row['task'] = m[1]
        else: row['task'] = next((part for part in p.parts if part in TASK_NAMES), '')
        m = re.search(r'_([BHMI])_r(\d+)(?:/|_)',s)
        if m: row.update(group=m[1],round=m[2])
        elif kind=='teacher':
            match=re.search(r'_([HMI])/',s)
            if match:row['group']=match[1]
            match=re.search(r'/round_(\d+)/',s)
            if match:row['round']=match[1]
        try:
            d=load(p); es=events(d)
            row['events']=len(es)
            row['tools']=sum(1 for e in es for b in e['record'].get('message',{}).get('content',[]) if isinstance(b,dict) and b.get('name'))
            if kind=='student':
                parent=p.parent.parent
                patch=parent/'patch.diff'
                if not patch.exists(): patch=p.parent/'patch.diff'
                row.update(patch_path=str(patch) if patch.exists() else '',patch_bytes=patch.stat().st_size if patch.exists() else '')
                run=parent.parent.parent
                ev=run/'eval_output'/str(row['task'])/'eval_result.json'
                if ev.exists():
                    v=load(ev); row['eval_path']=str(ev)
                    reward=v.get('reward') or {}
                    if not isinstance(reward,dict):reward={'reward':reward}
                    row.update(status='solved' if reward.get('reward')==1 else 'not_solved',f2p_passed=v.get('f2p_passed',reward.get('f2p_passed','')),f2p_total=v.get('f2p_total',reward.get('f2p_total','')),p2p_passed=v.get('p2p_passed',reward.get('p2p_passed','')),p2p_total=v.get('p2p_total',reward.get('p2p_total','')))
                    if row['status']!='solved' and isinstance(row['f2p_passed'],int) and row['f2p_passed']>0:row['status']='partial_correct_formally_not_solved'
                    elif row['status']!='solved' and row['patch_bytes']==0:row['status']='empty_patch_formally_not_solved'
                else: row['status']='evaluation_missing'
                row['teacher_materials']=json.dumps({name:str(p.parent/name) for name in ['system_prompt_actual.json','online_teacher_events.json','online_teacher_state.json'] if (p.parent/name).is_file()})
            row['audit_depth']='parsed_event_counts'
        except Exception as e:row['error']=str(e)
        rows.append(row)

with (OUT/'trajectory_inventory.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
summary={'rows':len(rows),'kinds':dict(Counter(r['kind'] for r in rows)),
    'student_tasks':dict(Counter(r['task'] for r in rows if r['kind']=='student')),
    'deeply_audited':0,'scope':'Original handoff, original baseline runs, all original Codex runs and preflights. Publication copy hintrsi is indexed as an alias, not counted as new attempts.'}
(OUT/'audit/inventory_summary.json').write_text(json.dumps(summary,indent=2)+'\n')

# Fixed evidence cohort: the same event sequence is given to K1 and K2.
selected=[]
spec=[('claude-code-by-agents-recursive-delegation',g,r) for g,r in [('B','1'),('H','1'),('M','2'),('I','1'),('I','2')]]
spec += [('igel-persist-feature-schema','B','3'),('igel-persist-feature-schema','H','1')]
for task,g,r in spec:
    candidates=[x for x in rows if '/runs/codex_parallel_12/' in x['path'] and x['kind']=='student' and x['task']==task and x['group']==g and x['round']==r]
    selected.append(candidates[0])
selected += [x for x in rows if '/parallel_13_fixes/real_sqlfmt/' in x['path'] and x['kind']=='student']
source=[]
for i,row in enumerate(selected,1):
    p=Path(row['path']);d=load(p);es=events(d)
    # Keep exact events; the limit is shared and established before generation.
    material={'source_id':f'D{i:02}', 'index':row,'metadata':d.get('metadata',{}),'events':es}
    patch=Path(row['patch_path']) if row['patch_path'] else None
    material['student_patch']=patch.read_text() if patch and patch.exists() else None
    if row['eval_path']: material['formal_evaluation']=load(Path(row['eval_path']))
    lane=p
    while lane.parent!=lane and not (lane/'experiment_state.json').exists():lane=lane.parent
    if (lane/'experiment_state.json').exists():
        state=load(lane/'experiment_state.json')
        material['shared_teacher_materials']=state.get('shared',{}).get(row['task'],{})
        material['available_hint_archive']={}
        for k in ('full_hint','first_hint'):
            hp=Path(material['shared_teacher_materials'].get(k,''))
            if hp.is_file():material['available_hint_archive'][k]={'path':str(hp),'text':hp.read_text()}
        if row['group']!='B':
            for hp in sorted(lane.rglob('*.md')):
                if row['task'] in str(hp) and any(s in hp.name for s in ('hint_compact','review_hint')):
                    material['available_hint_archive'][str(hp)]={'path':str(hp),'text':hp.read_text()}
    target=OUT/'evidence'/f'D{i:02}_{row["task"]}_{row["group"]}{row["round"]}.json'
    target.write_text(json.dumps(material,ensure_ascii=False,indent=2)+'\n')
    source.append({'source_id':f'D{i:02}','file':str(target),'task':row['task'],'group':row['group'],'round':row['round'],'events':len(es)})
(OUT/'config/development_sources.json').write_text(json.dumps(source,indent=2)+'\n')
print(json.dumps(summary));print('selected',len(source))
