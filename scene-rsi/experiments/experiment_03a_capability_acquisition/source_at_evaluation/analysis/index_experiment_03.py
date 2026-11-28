"""Index the two new scientific records for a later authorized GitHub sync."""
import datetime
import difflib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
NAMES=['experiment_03a_capability_acquisition','experiment_03b_teacher_alignment']
EXCLUDED={'.git','.codex','.agents','.aws','__pycache__','home','backend_home','tmp'}
SELF_FILES={'file_index.json','sync_manifest.json','auth.json','.env'}
TEXT={'.py','.json','.jsonl','.yaml','.yml','.md','.txt','.html','.css','.js'}


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def scientific(path):
    return path.is_file() and not path.is_symlink() and not EXCLUDED.intersection(path.relative_to(ROOT).parts) and path.name not in SELF_FILES and path.suffix!='.pyc'


def source_snapshot(exp):
    previous=ROOT/'experiments/experiment_02_teacher_guided_exploration/final_source_snapshot'
    changes=[];patch=[]
    for folder in ['sdk','harness','analysis','configs']:
        for path in sorted((ROOT/folder).rglob('*')):
            if not scientific(path) or path.suffix not in TEXT:continue
            relative=path.relative_to(ROOT);target=exp/'final_source_snapshot'/relative
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
            old=previous/relative
            before=old.read_text() if old.exists() else ''
            after=path.read_text()
            kind='reused_unchanged' if old.exists() and before==after else ('modified' if old.exists() else 'new')
            changes.append({'path':str(relative),'kind':kind,'compared_to':str(old.relative_to(ROOT)) if old.exists() else None})
            if before!=after:
                patch.extend(difflib.unified_diff(before.splitlines(keepends=True),after.splitlines(keepends=True),fromfile='experiment02_final/'+str(relative),tofile='experiment03_final/'+str(relative)))
    for name in ['README.md','.gitignore']:
        shutil.copy2(ROOT/name,exp/'final_source_snapshot'/name)
    (exp/'source_changes.diff').write_text(''.join(patch))
    write(exp/'source_origin.json',{'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':changes,
          'runtime_versions':'Actual acquisition and formal-test source snapshots plus infrastructure/shared_v2.diff preserve which runtime each role used.',
          'sdk':'Existing hintrsi Claude Agent SDK and latest model-only Codex CLI bridge reused; shared optional image/read-only library fields and runtime-file exposure changes are documented separately.',
          'environment':'Existing SDK Python, analysis Python and Blender reused without installation; new public dataset files are separately indexed.',
          'scene_logic':'New source-specific capability acquisition, frozen-library transfer, posthoc evaluation and teacher alignment materials; no SceneEvolve modeling strategy.'})


def main():
    manifests=[]
    for name in NAMES:
        exp=ROOT/'experiments'/name;source_snapshot(exp)
        paths={ROOT/'README.md',ROOT/'.gitignore'}
        for folder in ['sdk','harness','analysis','configs']:
            paths.update((ROOT/folder).rglob('*'))
        paths.update(exp.rglob('*'))
        paths.update((ROOT/'data/experiment_03').rglob('*'))
        rows=[]
        for path in sorted(paths):
            if not scientific(path):continue
            stat=path.stat()
            rows.append({'path':str(path.relative_to(ROOT)),'bytes':stat.st_size,'modified_utc':datetime.datetime.fromtimestamp(stat.st_mtime,datetime.timezone.utc).isoformat(),'large_local_asset':stat.st_size>=10*1024**2})
        index={'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'root':str(ROOT),'files':rows,'file_count':len(rows),'bytes':sum(row['bytes'] for row in rows),'reused_development_gt':'Existing data/evaluation_gt referenced in the frozen data split; originals remain in place.','data_license':'IDEAL-Scenes CC-BY-4.0; see frozen data split/source records.'}
        write(exp/'file_index.json',index)
        manifest={'scope':name+' plus current common source and new Experiment03 data; earlier experiment originals stay separate.',
                  'source_and_scientific_files':[row['path'] for row in rows if not row['large_local_asset']],
                  'large_local_assets':[{'path':row['path'],'bytes':row['bytes']} for row in rows if row['large_local_asset']],
                  'excluded':'Credentials, runtime homes, temporary files, bytecode, protected metadata roots and environment symlinks.',
                  'publication_status':'Local synchronization list only; Experiment03 is not uploaded by this task.',
                  'target_repository':'https://github.com/i025/hintrsi/tree/main/scene-rsi'}
        write(exp/'sync_manifest.json',manifest)
        manifests.append({'experiment':name,'manifest':str((exp/'sync_manifest.json').relative_to(ROOT)),'files':len(rows),'bytes':index['bytes']})
        print(name,len(rows),'files',round(index['bytes']/1024**2,1),'MiB')
    write(ROOT/'experiments/experiment_03_sync_index.json',{'experiments':manifests,'publication_status':'Prepared locally; no upload performed.'})


if __name__=='__main__':main()
