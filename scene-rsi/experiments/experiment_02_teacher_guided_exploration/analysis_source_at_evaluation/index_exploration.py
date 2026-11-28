"""Index scientific assets for later publication; omit credentials and runtime homes."""
import datetime
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'experiments/experiment_02_teacher_guided_exploration'
EXCLUDED={'.git','.codex','.agents','.aws','__pycache__','home','backend_home','tmp'}


def main():
    paths=[]
    for folder in ('sdk','harness','analysis','configs'):
        paths.extend((ROOT/folder).rglob('*'))
    paths.extend(EXP.rglob('*'))
    rows=[]
    for path in sorted(paths):
        relative=path.relative_to(ROOT)
        if path.is_symlink() or not path.is_file() or EXCLUDED.intersection(relative.parts):continue
        if path.suffix=='.pyc' or path.name in ('auth.json','file_index.json','sync_manifest.json'):continue
        stat=path.stat()
        rows.append({'path':str(relative),'bytes':stat.st_size,
                     'modified_utc':datetime.datetime.fromtimestamp(stat.st_mtime,datetime.timezone.utc).isoformat(),
                     'large_local_asset':stat.st_size>=10*1024**2})
    reused=[]
    for scene in json.loads((ROOT/'configs/scenes.json').read_text())['scenes']:
        reused.append({'scene':scene['id'],'original_gt_directory':scene['evaluation_directory'],
                       'dataset_source':scene['source_url'],'license':scene['license'],
                       'storage':'Reused in place from Experiment 01; not downloaded or duplicated.'})
    index={'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'root':str(ROOT),'files':rows,'file_count':len(rows),'bytes':sum(row['bytes'] for row in rows),
           'reused_ground_truth':reused,'hash_or_checksum_system':False}
    (EXP/'file_index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
    manifest={'scope':'Current source plus complete Experiment 02 scientific record; Experiment 01 originals stay separate.',
              'source_and_scientific_files':[r['path'] for r in rows if not r['large_local_asset']],
              'large_local_assets':[{'path':r['path'],'bytes':r['bytes']} for r in rows if r['large_local_asset']],
              'excluded':'Authentication, runtime homes/session-key stores, temporary files, bytecode and symlinks to installed environments.',
              'publication_status':'Local results and index only; no new GitHub upload is performed by this experiment task.',
              'existing_repository':'https://github.com/i025/hintrsi/tree/main/scene-rsi'}
    (EXP/'sync_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(len(rows),'files;',round(index['bytes']/1024**2,1),'MiB;',len(manifest['large_local_assets']),'large local assets')


if __name__=='__main__':main()
