import csv
import difflib
import json
from collections import Counter,defaultdict
from pathlib import Path

HOME=Path('/srv/lab-disks/disk2/users/xymo')
OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
original=HOME/'hint-codex-experiments/source_parallel_13'
public=HOME/'hintrsi/hint-codex-experiments/source_parallel_13'
changed=[];missing=[];compared=0
for p in original.rglob('*'):
    if not p.is_file() or '__pycache__' in p.parts:continue
    q=public/p.relative_to(original)
    if not q.exists():missing.append(str(p.relative_to(original)));continue
    compared+=1
    if p.read_bytes()!=q.read_bytes():changed.append(str(p.relative_to(original)))
diff=[]
for p in sorted((OUT/'source').rglob('*')):
    if not p.is_file() or '__pycache__' in p.parts:continue
    q=original/p.relative_to(OUT/'source')
    try:
        old=q.read_text().splitlines(keepends=True) if q.exists() else []
        new=p.read_text().splitlines(keepends=True)
    except UnicodeError:continue
    diff.extend(difflib.unified_diff(old,new,fromfile='source_parallel_13/'+str(p.relative_to(OUT/'source')),tofile='source/'+str(p.relative_to(OUT/'source'))))
(OUT/'results/source_changes.diff').write_text(''.join(diff))
(OUT/'audit/source_comparison.json').write_text(json.dumps({'original_source':str(original),'public_checkout_source':str(public),'files_compared_by_direct_content':compared,'different_files':changed,'absent_public_files':missing,'hintrsi_local_public_and_remote_main':'c0132d7e381ff660354d7a4403e29ee6107354f9','scene_local_latest_audited_branch':'d29db8ddb223dfe2899fb7a158c7fcbb1bfda690','scene_remote_main':'355930a79d1d7ceecaddd8b549fa7a88121e97bd','scene_remote_stagewise_branch':'d29db8ddb223dfe2899fb7a158c7fcbb1bfda690','no_download_or_hash_verification':True},indent=2)+'\n')
p=OUT/'audit/source_comparison.json';comparison=json.loads(p.read_text())
comparison.update(scene_main_is_ancestor_of_stagewise=True,scene_stagewise_commits_ahead_of_main=40)
p.write_text(json.dumps(comparison,indent=2)+'\n')

# State files import some older attempts. Link by original trajectory path; do not count imported rows twice.
attempts={}
for p in sorted((HOME/'hint-codex-experiments/runs').rglob('experiment_state.json')):
    d=json.loads(p.read_text())
    for row in d.get('attempts',[]):
        key=row.get('trajs_path') or '|'.join([row.get('origin_experiment') or d.get('experiment','')]+[str(row.get(k,'')) for k in ('task','group','round')])
        value=dict(row, state_path=str(p),parent_status=d.get('status'))
        if value.get('status')=='running' and d.get('status')=='stopped':value['classification']='interrupted_by_batch_stop'
        elif value.get('status')=='solved':value['classification']='formal_success'
        elif value.get('status')=='not_solved':value['classification']='formally_not_solved_requires_patch_review'
        else:value['classification']=value.get('status','unknown')
        # Preserve all references to the same physical attempt.
        if key in attempts:
            value['state_references']=attempts[key].get('state_references',[])+[str(p)]
            if attempts[key]['classification']=='interrupted_by_batch_stop':value['classification']='interrupted_by_batch_stop'
        else:value['state_references']=[str(p)]
        attempts[key]=value
fields=['task','group','round','classification','status','parent_status','trajs_path','eval_path','elapsed_seconds','started_at','finished_at','state_path','state_references']
with (OUT/'audit/attempt_inventory.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(attempts.values())

usage=defaultdict(lambda:defaultdict(int));sources=defaultdict(list)
for base in [HOME/'hint-codex-experiments/logs/codex_parallel_12/bridge',HOME/'hint-codex-experiments/preflight/parallel_13_fixes/sdk_bridge']:
    p=base/'token_usage.jsonl'
    for line in p.open():
        d=json.loads(line);key=(str(base),d['session'],d['role'],d['phase']);usage[key]['model_calls_with_usage']+=1
        for name,value in d['usage'].items():
            if isinstance(value,(float,int)):usage[key][name]+=value
fields=['ledger','session','role','phase','model_calls_with_usage','input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens']
with (OUT/'audit/historical_cli_usage.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader()
    for key,value in usage.items():w.writerow(dict(zip(fields[:4],key),**value))
summary={'attempt_state_rows_after_path_linking':len(attempts),'classifications':dict(Counter(x['classification'] for x in attempts.values())),
    'usage_note':'Sum actual Codex CLI usage only. SDK metadata costs and usage are retained as raw historical fields but are not added or treated as actual dollars. Cached input is a subset of input tokens.'}
(OUT/'audit/historical_metrics_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
baseline_path=HOME/'hint-baseline-run/baseline_state.json'
baseline=json.loads(baseline_path.read_text());baseline_rows=[]
for number,job in enumerate(baseline['jobs'],1):
    task=job['instance_id'];run=HOME/'hint-baseline-run/runs'/(job['run_name']+'_r1')
    infer=run/'infer_logs'/task/'turn_1';ev=run/'eval_output'/task/'eval_result.json'
    baseline_rows.append({'launch_record':number,'task':task,'run_name':job['run_name'],
        'group':'B','independent_attempt':job.get('independent_attempt'),
        'model':job.get('model') or baseline['model'],'model_attempt_counted':job.get('model_attempt_counted'),
        'status':job.get('status'),'reward_recorded':job.get('reward'),
        'trajectory_path':str(infer/'trajs.json') if (infer/'trajs.json').exists() else '',
        'patch_path':str(infer/'patch.diff') if (infer/'patch.diff').exists() else '',
        'eval_path':str(ev) if ev.exists() else '',
        'log_path':job.get('log_file') or job.get('log'),'state_path':str(baseline_path),
        'classification_reason':job.get('classification_reason','')})
with (OUT/'audit/baseline_attempt_inventory.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(baseline_rows[0]));w.writeheader();w.writerows(baseline_rows)
print(json.dumps(summary));print('source differences',changed,'public missing',missing)
