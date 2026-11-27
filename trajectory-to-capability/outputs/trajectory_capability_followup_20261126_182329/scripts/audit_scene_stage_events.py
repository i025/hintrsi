"""Read every indexed Blender-stage event/call record in complete numbered chunks."""
import csv
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

OUT=Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
OLD=OUT.parent/'trajectory_capability_20261126_020200'
PYTHON='/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
rows=[r for r in csv.DictReader((OLD/'audit/scene_artifact_inventory.csv').open())
    if r['kind'] in ['stage_events','model_calls'] and r['scope_root']!='/srv/lab-disks/disk2/users/xymo/rsi']
directory=OUT/'evidence/scene_stage_event_chunks';directory.mkdir(exist_ok=True)
reports=OUT/'audit/scene_stage_events';reports.mkdir(exist_ok=True)
chunks=[];content='';labels=[]
for i,row in enumerate(rows,1):
    raw=Path(row['path']).read_text()
    label={'source_id':f'SE{i:04d}','path':row['path'],'kind':row['kind'],'characters':len(raw),'complete':True}
    numbered='\n'.join(f'{n:05d}: {line}' for n,line in enumerate(raw.splitlines(),1))
    addition='\nSOURCE '+json.dumps(label)+'\n'+numbered+'\n'
    if content and len(content)+len(addition)>420000:
        chunks.append((labels,content));labels=[];content=''
    content+=addition;labels.append(label)
if content:chunks.append((labels,content))
manifest={'created_at':time.time(),'source_files':len(rows),'scope':'All indexed stage_events.jsonl and calls.json in original Blender outputs/publication trees; excludes unrelated grid-domain rsi call files. Copies remain file records, not independent trials. Complete numbered text, no clipping.','chunks':[]}
for i,(labels,content) in enumerate(chunks,1):
    name=f'SE_chunk{i:02d}';packet=directory/(name+'.txt');report=reports/(name+'.md')
    packet.write_text('''Historical Blender stage/call evidence audit, English at most 1200 words. These are complete selected event/call files, not image or full geometry attachments. Cite source IDs, exact original paths and one-based lines. Distinguish actual recorded build/patch/render/validation transitions, failed commands and merely proposed actions; teacher advice, student execution, acceptance and quality are separate. Identify material evidence and counterexamples regarding stage ordering, object/part relations, pose/camera/lighting/material checks, rerenders, failures, H/M or mechanism updates and acceptance decisions. Do not equate an ok flag, render completion or AABB bounds with visual fidelity/physical contact. Inputs include original/publication copies; do not count them as independent trials or generalize all scenes. This audit never feeds code students or capability updates. No new solution or code.\n''' + content)
    manifest['chunks'].append({'name':name,'packet':str(packet),'report':str(report),'sources':labels,'status':'pending'})
path=OUT/'config/scene_stage_event_audit_manifest.json'
if path.exists():raise FileExistsError(path)
path.write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'files':len(rows),'chunks':len(chunks)}),flush=True)
def run(job):
    code=subprocess.run([PYTHON,'-u','-B',str(Path(__file__).with_name('model_job.py')),
        'followup-scene-stage-events-'+job['name'],job['packet'],job['report']],stdout=subprocess.DEVNULL,check=False).returncode
    return job,code
with ThreadPoolExecutor(max_workers=2) as pool:
    for job,code in pool.map(run,manifest['chunks']):
        job.update(status='complete' if code==0 else 'failed',exit_code=code,finished_at=time.time())
        path.write_text(json.dumps(manifest,indent=2)+'\n')
        print(json.dumps({'chunk':job['name'],'exit_code':code}),flush=True)
manifest.update(status='complete' if all(j['status']=='complete' for j in manifest['chunks']) else 'some_chunks_failed',finished_at=time.time())
path.write_text(json.dumps(manifest,indent=2)+'\n')
