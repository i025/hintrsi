"""Index scientific files for later sync; runtime homes and credentials are excluded."""
from pathlib import Path
import datetime
import json

ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'experiments/experiment_01_natural_trajectories'
excluded_parts={'.git','.codex','.agents','.aws','__pycache__','home','backend_home','tmp'}
rows=[]
for path in sorted(ROOT.rglob('*')):
 relative=path.relative_to(ROOT)
 if any(part in excluded_parts for part in relative.parts) or path.is_symlink() or not path.is_file():continue
 if path.name in {'file_index.json','sync_manifest.json','auth.json'} or path.suffix=='.pyc':continue
 stat=path.stat()
 rows.append({'path':str(relative),'bytes':stat.st_size,'modified_utc':datetime.datetime.fromtimestamp(stat.st_mtime,datetime.timezone.utc).isoformat(),
              'keep_local_large_file':stat.st_size>=10*1024**2})
index={'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'root':str(ROOT),'files':rows,
       'bytes':sum(row['bytes'] for row in rows),'file_count':len(rows),'hash_or_checksum_system':False,
       'excluded':'Runtime homes, credentials, session keys, temporary process files, bytecode, protected metadata roots, and absolute runtime symlinks.'}
(EXP/'file_index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2))
manifest={'repository_not_published_by_this_task':True,'source_and_scientific_files':[row['path'] for row in rows if not row['keep_local_large_file']],
          'large_local_files':[{'path':row['path'],'bytes':row['bytes']} for row in rows if row['keep_local_large_file']],
          'policy':'Large assets remain local and indexed. A later authorized GitHub sync may use LFS or release storage; no credentials or runtime homes should be synced.',
          'data_license':'IDEAL-Scenes CC BY 4.0; see data/README.md and configs/scenes.json'}
(EXP/'sync_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print(index['file_count'],'scientific files;',round(index['bytes']/1024**2,1),'MiB;',len(manifest['large_local_files']),'large local files')
