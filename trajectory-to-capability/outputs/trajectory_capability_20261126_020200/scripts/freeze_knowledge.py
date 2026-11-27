import datetime
import json
import shutil
from pathlib import Path

OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
rows=[r for r in json.loads((OUT/'results/attempt_metrics.json').read_text()) if r['stage']=='selection']
if len(rows)!=4 or any(r['status']!='complete' or r['formal_success']=='' for r in rows):
    raise RuntimeError('Complete all four Selection attempts before freezing')
for row in rows:
    if row['group']!='B0' and (row['capability_in_actual_prompt'] is not True or row['capability_in_first_bridge_request'] is not True):
        raise RuntimeError('Actual knowledge injection is unverified: '+row['group'])
path=OUT/'config/knowledge_freeze.json'
if path.exists():raise FileExistsError(path)
directory=OUT/'knowledge/frozen_v1';directory.mkdir()
libraries={}
for group in ['K0','K1','K2']:
    source=OUT/'knowledge'/f'{group}_v1.md';destination=directory/source.name
    shutil.copy2(source,destination);content=destination.read_text()
    libraries[group]={'path':str(destination),'source':str(source),'words':len(content.split()),
        'text':content,'version':'v1','retained':True}
record={'frozen_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'model':'gpt-6.1-terra','reasoning_effort':'low','libraries':libraries,'selection_results':rows,
    'retention_rule':'One candidate per arm. Injection verified; read-only library review found no answer/GT/test-code leakage or invalid format. Selection alone does not establish a causal regression or improvement; preserve inconclusive candidates rather than tune them. No Test feedback used.',
    'candidate_review':str(OUT/'audit/library_review.md'),
    'test_policy':'Read only these frozen copies, fresh student sessions/code, same budgets/tools, no teacher/GT/history. Never update from Test results.'}
path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
p=OUT/'config/run_manifest.json';data=json.loads(p.read_text());data.update(status='test_ready',knowledge_freeze=str(path));p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'freeze':str(path),'words':{k:v['words'] for k,v in libraries.items()}}))
