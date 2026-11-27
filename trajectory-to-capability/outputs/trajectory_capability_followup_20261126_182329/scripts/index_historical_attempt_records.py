"""Index existing attempt/summary tables, including records without trajectories."""
import csv
import json
import subprocess
from collections import Counter,defaultdict
from pathlib import Path

OUT=Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
roots=['/srv/lab-disks/disk2/users/xymo/hint-codex-experiments','/srv/lab-disks/disk2/users/xymo/hint-baseline-run']
files=subprocess.check_output(['rg','--files','-g','*.csv','-g','!**/env/**','-g','!**/data/**',*roots],text=True).splitlines()
allowed={'attempt_metrics.csv','excluded_prior_attempt_metrics.csv','baseline_results.csv','driver_results_original_after_stop.csv','results.csv'}
source_ids={x['original_file']:x['source_id'] for x in json.loads((OUT/'config/hintrsi_full_audit_manifest.json').read_text())['files']}
rows=[];source_files=[]
for name in sorted(files):
    path=Path(name)
    if path.name not in allowed:continue
    with path.open(encoding='utf-8-sig') as stream:
        reader=csv.DictReader(stream)
        if not reader.fieldnames or not any(k in reader.fieldnames for k in ['task','instance_id']):continue
        values=list(reader)
    source_files.append(str(path))
    for number,record in enumerate(values,2):
        declared=record.get('trajs_path') or record.get('trajectory_path') or ''
        actual=[]
        if declared:
            candidates=[Path(declared),Path(declared+'.gz')]
            actual=[str(p) for p in candidates if p.is_file()]
        reference=record.get('result_run','')
        if not actual and reference:
            actual=[p for p in source_ids if reference in Path(p).parts or reference+'_r1' in Path(p).parts]
        kind='attempt_record' if 'attempt_metrics' in path.name else 'task_summary' if path.name=='baseline_results.csv' else 'group_or_driver_summary'
        rows.append({'source_csv':str(path),'source_row':number,'record_kind':kind,
            'task':record.get('task') or record.get('instance_id',''),'group':record.get('group',''),
            'round':record.get('round',''),'status':record.get('status') or record.get('supplemental_nohint_status',''),
            'session':record.get('session',''),'stage':record.get('stage',''),'origin_experiment':record.get('origin_experiment',''),
            'declared_trajectory':declared,'existing_trajectory_paths':json.dumps(actual),
            'full_text_audit_source_ids':json.dumps([source_ids[p] for p in actual if p in source_ids]),
            'eval_path':record.get('eval_path',''),'run_reference':reference,
            'raw_record':json.dumps(record,ensure_ascii=False),
            'scope':'Metadata record, not a unique independent trial. Aggregate tables, shared-first aliases, snapshots and planned/not-started entries can overlap.'})
output=OUT/'audit/historical_attempt_records.csv'
with output.open('w',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
summary={'source_csv_files':len(source_files),'metadata_rows':len(rows),'record_kinds':dict(Counter(r['record_kind'] for r in rows)),
    'rows_with_existing_trajectory_reference':sum(r['existing_trajectory_paths']!='[]' for r in rows),
    'rows_with_declared_but_missing_trajectory':sum(bool(r['declared_trajectory']) and r['existing_trajectory_paths']=='[]' for r in rows),
    'table':str(output),'source_files':source_files,
    'limit':'These records complement the 117 student trajectory files. They include repeated references, summaries and unstarted entries, so cannot be counted as independent student attempts or deep-audited trajectories. Missing raw trajectories/ratings are not invented; the original record remains visible.'}
(OUT/'config/historical_attempt_record_inventory.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='source_files'}))
