"""Index scientific assets for later publication; omit credentials and runtime homes."""
import datetime
import difflib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'experiments/experiment_02_teacher_guided_exploration'
EXCLUDED={'.git','.codex','.agents','.aws','__pycache__','home','backend_home','tmp'}


def source_snapshot():
    initial=json.loads((EXP/'source_origin.json').read_text())
    initial_changes={r['file']:r['kind'] for r in initial['changes']}
    records=[];patch=[]
    for folder in ('sdk','harness','analysis','configs'):
        for path in sorted((ROOT/folder).rglob('*')):
            relative=path.relative_to(ROOT)
            if path.is_symlink() or not path.is_file() or EXCLUDED.intersection(relative.parts):continue
            if path.suffix not in ('.py','.json','.yaml','.yml','.md','.txt') or path.name=='auth.json':continue
            target=EXP/'final_source_snapshot'/relative
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
            before=EXP/'source_at_formal_run'/relative
            old=before.read_text() if before.exists() else ''
            current=path.read_text()
            changed=old!=current
            records.append({'file':str(relative),'initial_increment':initial_changes.get(str(relative),'reused' if before.exists() else 'added_after_formal_start'),
                            'present_at_formal_start':before.exists(),'changed_after_formal_start':changed})
            if changed:patch.extend(difflib.unified_diff(old.splitlines(keepends=True),current.splitlines(keepends=True),
                fromfile='source_at_formal_run/'+str(relative),tofile='final_source/'+str(relative)))
    for name in ('README.md','.gitignore'):
        shutil.copy2(ROOT/name,EXP/'final_source_snapshot'/name)
    patch.extend(difflib.unified_diff((EXP/'shared_README_before.md').read_text().splitlines(keepends=True),
        (ROOT/'README.md').read_text().splitlines(keepends=True),fromfile='before_experiment_02/README.md',tofile='final_source/README.md'))
    (EXP/'post_formal_source_changes.diff').write_text(''.join(patch))
    origin={'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':records,
        'initial_increment':'source_origin.json and source_changes.diff preserve the pre-formal increment.',
        'documentation_changes':'Shared README adds the Experiment 02 index; its original text is preserved in shared_README_before.md. Existing .gitignore is reused unchanged.',
        'runtime_versions':'Students retain source_at_formal_run/source_at_repeat_start; subsequent analysis and the post-student Bridge fix do not resample or repair student outputs.',
        'scene_logic':'New checkpoint branch preparation, fixed hint protocol and independent evaluation; no SceneEvolve reconstruction strategy.',
        'model_backend':'sdk/run_cc_sdk.py remains the original hintrsi SDK loop. Codex Bridge receives the documented post-student agent-disable settings only after all students ended.',
        'environment':'Existing Python, Blender and data reused in place; no replacement installations or dataset download.'}
    (EXP/'final_source_origin.json').write_text(json.dumps(origin,ensure_ascii=False,indent=2)+'\n')


def main():
    source_snapshot()
    paths=[ROOT/'README.md',ROOT/'.gitignore']
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
