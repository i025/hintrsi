"""Apply the pre-saved Selection rule and freeze every experimental candidate."""
import datetime
import json
import shutil
from pathlib import Path

OUT=Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
path=OUT/'config/knowledge_freeze.json'
if path.exists():raise FileExistsError(path)
rows=[r for r in json.loads((OUT/'results/attempt_metrics.json').read_text()) if r['stage']=='selection']
if len(rows)!=7 or any(r['status'] in ('not_started','running') for r in rows):
    raise RuntimeError('Finish all seven pre-saved Selection attempts before freezing')
review=OUT/'audit/library_review_v2.md'
if not review.is_file():raise RuntimeError('Complete the Development-only V2 library content review first')
for row in rows:
    if row['group']!='B0' and (row['capability_in_actual_prompt'] is not True or row['capability_in_first_bridge_request'] is not True):
        raise RuntimeError('Actual capability delivery not established for '+row['group'])
choices={}
for arm in ['K0','K1','K2']:
    v1=next(r for r in rows if r['group']==arm+'_v1')
    v2=next(r for r in rows if r['group']==arm+'_v2')
    known=all(r['status']=='complete' for r in [v1,v2]) and all(isinstance(r[k],int) for r in [v1,v2] for k in
        ['formal_success','f2p_passed','f2p_total','p2p_passed','p2p_total'])
    totals_match=known and v1['f2p_total']==v2['f2p_total'] and v1['p2p_total']==v2['p2p_total']
    if not totals_match:
        selected=arm+'_v1';reason='Inconclusive/missing or mismatched complete grades: retain V1 by pre-saved rule'
    elif v2['formal_success']>v1['formal_success']:
        selected=arm+'_v2';reason='V2 improves formal full success on Selection'
    elif v2['formal_success']==v1['formal_success'] and v2['f2p_passed']>=v1['f2p_passed'] and v2['p2p_passed']>=v1['p2p_passed']:
        selected=arm+'_v2';reason='Equal formal success; neither F2P nor P2P count regresses'
    else:
        selected=arm+'_v1';reason='V2 does not meet the pre-saved non-regression rule'
    choices[arm]={'selected':selected,'reason':reason,'V1':v1,'V2':v2}
directory=OUT/'knowledge/frozen_v2_comparison'
directory.mkdir()
libraries={}
for name in [f'{arm}_v{version}' for arm in ['K0','K1','K2'] for version in [1,2]]:
    source=OUT/'knowledge'/(name+'.md');destination=directory/source.name
    content=source.read_text()
    if len(content.split())>700:raise RuntimeError('Library exceeds shared word cap: '+name)
    shutil.copy2(source,destination)
    libraries[name]={'path':str(destination),'source':str(source),'text':content,'words':len(content.split()),
        'selected_for_deployment':choices[name[:2]]['selected']==name}
record={'frozen_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'model':'gpt-6.1-terra','reasoning_effort':'low','libraries':libraries,
    'selection_choices':choices,'selection_results':rows,'content_review':str(review),
    'hint_libraries_separately_frozen':str(OUT/'config/knowledge_freeze_hint.json'),
    'rule':'Use only pre-saved Selection rule; new Test results never change books or selected deployment. Test both versions regardless of retention to report all candidates. Original six-hour frozen books remain unchanged.'}
path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
manifest_path=OUT/'config/run_manifest.json';manifest=json.loads(manifest_path.read_text());manifest.update(status='all_libraries_frozen_test_ready',knowledge_freeze=str(path));manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'freeze':str(path),'selected':{k:v['selected'] for k,v in choices.items()},
    'words':{k:v['words'] for k,v in libraries.items()}}),flush=True)
