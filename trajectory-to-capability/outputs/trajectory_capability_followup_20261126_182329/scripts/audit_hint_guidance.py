"""Review captured student guidance alongside fully reviewed historical actions."""
import csv
import json
import subprocess
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

OUT=Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
OLD=OUT.parent/'trajectory_capability_20261126_020200'
PYTHON='/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
manifest=json.loads((OUT/'config/hintrsi_full_audit_manifest.json').read_text())
sources={r['original_file']:r for r in manifest['files'] if r['kind']=='student'}
if not all(c['status']=='complete' for r in sources.values() for c in r['chunks']):
    raise RuntimeError('Finish all historical student text chunks before guidance/action synthesis')
directory=OUT/'audit/hint_guidance'
directory.mkdir(exist_ok=True)
packets=OUT/'evidence/hint_guidance'
packets.mkdir(exist_ok=True)
groups=defaultdict(list)
inventory=[]
for row in csv.DictReader((OLD/'trajectory_inventory.csv').open()):
    if row['project']!='hintrsi' or row['kind']!='student':continue
    source=sources[row['path']]
    links=json.loads(row['teacher_materials'] or '{}')
    record={'source_id':source['source_id'],'student_index':row,'captured_files':[],
        'available_archive_texts':[],'full_action_audits':[{'report':c['report'],'text':Path(c['report']).read_text()} for c in source['chunks']]}
    for name in ['system_prompt_actual.json','system_prompt_config.json','online_teacher_events.json','online_teacher_state.json']:
        path=Path(row['path']).parent/name
        if path.is_file():
            record['captured_files'].append({'path':str(path),'kind':name,'text':path.read_text(),
                'scope':'Actual captured student system prompt' if name=='system_prompt_actual.json' else 'Configuration/server delivery state; interpret its fields, not automatically proof of receipt/adoption'})
    for key,value in links.items():
        values=value if isinstance(value,list) else [value]
        for item in values:
            if not isinstance(item,str):continue
            path=Path(item)
            if key.startswith('available_') and path.suffix=='.md' and path.is_file():
                record['available_archive_texts'].append({'label':key,'path':str(path),'text':path.read_text(),
                    'scope':'Available text only, not proof of student receipt; after-round review is not input to that round'})
    inventory.append({'source_id':source['source_id'],'trajectory':row['path'],'task':row['task'],
        'captured_files':[{'path':f['path'],'kind':f['kind'],'characters':len(f['text'])} for f in record['captured_files']],
        'available_texts':[{'path':f['path'],'label':f['label'],'characters':len(f['text'])} for f in record['available_archive_texts']]})
    groups[row['task']].append(record)
(OUT/'config/hint_guidance_sources.json').write_text(json.dumps(inventory,indent=2)+'\n')
jobs=[]
for task,records in sorted(groups.items()):
    batches=[];current='';labels=[]
    for record in records:
        text=json.dumps(record,ensure_ascii=False,separators=(',',':'))
        if len(text)>580000:raise RuntimeError('One guidance record needs explicit chunking: '+record['source_id'])
        if current and len(current)+len(text)>580000:
            batches.append((labels,current));current='';labels=[]
        current+='\nATTEMPT\n'+text+'\n';labels.append(record['source_id'])
    if current:batches.append((labels,current))
    for i,(labels,content) in enumerate(batches,1):
        name=task+f'_part{i:02d}'
        packet=packets/(name+'.txt');report=directory/(name+'.md')
        if report.exists():continue
        packet.write_text('''Historical guidance-to-action audit, English at most 1800 words. Inputs include complete captured prompt/config/online-state files, available Hint/review Markdown archives, and already completed full student-action audit reports. No source string is prefix-clipped. Distinguish actual received guidance, an available archive, server candidate/state and later review. Do not claim current-round receipt of an after-round review. For each student source ID in this packet, link teacher knowledge actually received to concrete later code/tool/test events, autonomous exploration and final formal/partial/technical/empty-patch/budget outcome. Availability, agent self-report and temporal sequence alone do not prove adoption or causation. Quote only a few words when needed; cite original file and exact event/key IDs. Record evidence gaps explicitly, especially the one missing actual prompt. Separate reusable constraints from task-specific answers and unsupported learning hypotheses. Explain source-round guidance changes only where directly recorded. Never generate new solutions, modify skills, access new Test data or send feedback to students. Include a per-attempt evidence matrix rather than only selected successes.\n''' + json.dumps({'task':task,'batch':i,'batches':len(batches),'student_source_ids':labels})+'\n'+content)
        jobs.append({'name':name,'packet':str(packet),'report':str(report),'student_source_ids':labels,'status':'pending'})
state={'started_at':time.time(),'student_files':len(inventory),'jobs':jobs}
state_path=OUT/'config/hint_guidance_audit_manifest.json'
state_path.write_text(json.dumps(state,indent=2)+'\n')
print(json.dumps({'student_files':len(inventory),'new_jobs':len(jobs)}),flush=True)
def run(job):
    result=subprocess.run([PYTHON,'-u','-B',str(Path(__file__).with_name('model_job.py')),
        'followup-guidance-'+job['name'],job['packet'],job['report']],stdout=subprocess.DEVNULL,check=False)
    return job,result.returncode
with ThreadPoolExecutor(max_workers=2) as pool:
    for job,code in pool.map(run,jobs):
        job.update(status='complete' if code==0 else 'failed',exit_code=code,completed_at=time.time())
        state_path.write_text(json.dumps(state,indent=2)+'\n')
        print(json.dumps({'job':job['name'],'exit_code':code}),flush=True)
state.update(finished_at=time.time(),status='complete' if all(j['status']=='complete' for j in jobs) else 'some_jobs_failed')
state_path.write_text(json.dumps(state,indent=2)+'\n')
