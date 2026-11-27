"""Index work archives and distinguish relocated copies from additional trajectories."""
import csv
import gzip
import json
import os
import re
import time
from collections import Counter
from pathlib import Path

OUT=Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
BASE=Path('/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender')
HOME=Path('/srv/lab-disks/disk2/users/xymo')
def read(path):
    return gzip.open(path,'rt').read() if path.suffix=='.gz' else path.read_text()
def public_paths(text,source):
    # The same literal relocation/account rules already used by the original exporter.
    changes=[(str(source),'__EXPERIMENT_ROOT__'),
        (str(BASE.parent/'files-pasted-by-the-user-sceneevolve'),'__SCENEEVOLVE_REPRO__'),
        (str(HOME/'projects/BlenderWorld'),'__BLENDERWORLD_ROOT__'),
        (str(HOME/'projects/e-harness/datasets/web_scenes'),'__COMMONS_DATA_ROOT__'),
        (str(HOME),'__SERVER_USER_ROOT__'),('/home/'+HOME.name,'__SERVER_USER_ROOT__')]
    for old,new in changes:text=text.replace(old,new)
    return re.sub(r'\b'+re.escape(HOME.name)+r'\b','SERVER_USER',text)
canonical=[]
for row in json.loads((OUT/'config/scene_full_audit_manifest.json').read_text())['files']:
    path=Path(row['original_file']);value=read(path)
    index=next((i for i,p in enumerate(path.parts) if p.startswith('scene_rsi_')),None)
    source=Path(*path.parts[:index+1]) if index is not None else path.parent
    canonical.append((row['source_id'],str(path),value,public_paths(value,source)))
records=[];additional=[];extra_values=[]
for directory,dirs,files in os.walk(BASE/'work'):
    dirs[:]=[d for d in dirs if d not in ['.git','__pycache__','node_modules','site-packages',
        'blender-4.2.10-linux-x64','python','lib','cache']]
    for name in files:
        if name not in ['trajectory.jsonl','trajs.json','trajs.json.gz']:continue
        path=Path(directory)/name;value=read(path)
        same=next((c for c in canonical if value==c[2]),None)
        method='exact_decoded_text_copy'
        if same is None:
            # Verification archives already contain public placeholders.
            normalized=public_paths(value,path.parent)
            same=next((c for c in canonical if normalized==c[3]),None)
            method='copy_after_original_export_path_account_redaction'
        row={'path':str(path),'bytes':path.stat().st_size,'family':path.relative_to(BASE/'work').parts[0],
            'kind':'work_archive_trajectory','canonical_trajectory':same[1] if same else '',
            'canonical_source_id':same[0] if same else '', 'relation':method if same else 'additional_content',
            'audit_depth':'canonical_full_chunk_review' if same else 'additional_review_pending'}
        if same is None:
            previous=next((p for text,p in extra_values if value==text),None)
            if previous:
                row.update(canonical_trajectory=previous,relation='exact_additional_archive_copy',audit_depth='additional_copy_pending')
            else:
                extra_values.append((value,str(path)))
                additional.append({'project':'scene_additional','kind':'additional_scene_archive_trace','path':str(path),
                    'bytes':path.stat().st_size,'task':'','group':'','round':'','archive_family':row['family']})
        records.append(row)
fields=list(records[0])
with (OUT/'audit/scene_work_archive_inventory.csv').open('w',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(records)
(OUT/'config/scene_additional_trace_inventory.json').write_text(json.dumps(additional,indent=2)+'\n')
summary={'at':time.time(),'work_trajectory_files':len(records),'families':dict(Counter(r['family'] for r in records)),
    'relations':dict(Counter(r['relation'] for r in records)),'additional_distinct_decoded_contents':len(additional),
    'method':'Direct decoded-content comparison and only the original exporter literal path/account redactions; no hash/checksum/signature system. File copies are not independent attempts.',
    'additional_sources':additional}
(OUT/'config/scene_work_archive_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='additional_sources'}),flush=True)
