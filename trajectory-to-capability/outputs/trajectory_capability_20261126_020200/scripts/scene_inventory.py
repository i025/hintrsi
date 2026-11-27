import csv
import json
import os
from collections import Counter
from pathlib import Path

HOME=Path('/srv/lab-disks/disk2/users/xymo')
OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
PROJECT=HOME/'Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender'
roots=[HOME/'rsi',PROJECT/'outputs',PROJECT/'archive/scene/experiments']
names={'session.json':'model_session','messages.json':'model_messages','request.json':'model_request',
    'build.py':'student_program','patch.py':'student_program','final.png':'render','scene_structure.json':'geometry',
    'judgment.json':'judgment','proposal_result.json':'meta_proposal','changes.diff':'update_patch',
    'selected.json':'candidate_selection','regression.json':'candidate_regression','stage_events.jsonl':'stage_events',
    'observations.json':'observations','evaluation.json':'evaluation','scores.json':'scores','calls.json':'model_calls',
    'trajectory.jsonl':'student_trajectory','events.jsonl':'model_events','teacher.py':'teacher_program','policy.py':'policy','meta.py':'meta_program',
    'state.json':'run_state','record.json':'record'}
counts=Counter();by_root={};rows=[];all_files=0
for root in roots:
    total=0
    for directory,dirs,files in os.walk(root):
        dirs[:]=[d for d in dirs if d not in ('.git','__pycache__','node_modules','site-packages','home','cache')]
        for name in files:
            total+=1
            p=Path(directory)/name
            kind=names.get(name)
            if kind is None and name.endswith('.jsonl'):kind='other_jsonl'
            if kind:
                try:size=p.stat().st_size
                except OSError:continue
                row={'project':'scene','kind':kind,'path':str(p),'bytes':size,'scope_root':str(root),'audit_depth':'indexed'}
                rows.append(row);counts[kind]+=1
    by_root[str(root)]=total;all_files+=total
with (OUT/'audit/scene_artifact_inventory.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['project','kind','path','bytes','scope_root','audit_depth']);w.writeheader();w.writerows(rows)
with (OUT/'trajectory_inventory.csv').open(newline='') as f:
    reader=csv.DictReader(f);fields=reader.fieldnames;old=[r for r in reader if r['project']!='scene']
with (OUT/'trajectory_inventory.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(old)
    for row in rows:
        if row['kind'] in ('model_session','stage_events','model_calls','student_trajectory','model_events'):
            w.writerow({k:v for k,v in row.items() if k in fields})
bundles=PROJECT/'work/scene_archive/bundles'
bundle_rows=[{'path':str(p),'bytes':p.stat().st_size,'content_indexed':False,'note':'Local expanded original and publication trees indexed separately; no repeat extraction'} for p in sorted(bundles.glob('*.tar.gz'))]
with (OUT/'audit/scene_bundles.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['path','bytes','content_indexed','note']);w.writeheader();w.writerows(bundle_rows)
summary={'files_walked':all_files,'files_by_root':by_root,'selected_artifact_rows':len(rows),'counts':dict(counts),
    'bundle_files_found':len(bundle_rows),'bundles_contents_deeply_audited':0,
    'warning':'Original outputs and public archive may contain copies of the same experiment. Counts are file counts, not unique independent attempts. No hash or content-based deduplication. Home/cache/env excluded. No image-wide visual audit claimed.'}
(OUT/'audit/scene_inventory_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary))
