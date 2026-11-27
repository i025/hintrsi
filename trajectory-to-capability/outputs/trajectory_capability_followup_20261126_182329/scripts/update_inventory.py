"""Update file-backed provenance and review coverage; never invent pending traces."""
import csv
import json
from pathlib import Path

OUT=Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
OLD=OUT.parent/'trajectory_capability_20261126_020200'
with (OLD/'trajectory_inventory.csv').open() as stream:
    reader=csv.DictReader(stream);fields=reader.fieldnames;rows=list(reader)
fields=fields+['experiment_phase','full_reviewed_chunks','full_total_chunks','full_audit_reports',
    'archive_member','canonical_trajectory','loaded_knowledge_path','sdk_session_id','followup_learning_role',
    'cli_usage_ledger','historical_cost_coverage','student_wall_seconds','student_sdk_seconds','teacher_wait_seconds','cli_turn_seconds']
lookup={row['path']:row for row in rows}
cost_path=OUT/'audit/historical_attempt_costs.csv'
if cost_path.exists():
    for cost in csv.DictReader(cost_path.open()):
        target=lookup.get(cost['trajectory_path'])
        if target is None:continue
        target.update(cli_usage_ledger=cost['cli_usage_ledger'],historical_cost_coverage=cost['coverage'],
            student_wall_seconds=cost['student_wall_seconds'],student_sdk_seconds=cost['student_sdk_seconds'],
            teacher_wait_seconds=cost['teacher_wait_seconds'],cli_turn_seconds=cost['cli_turn_seconds'])
        if cost['cli_usage_ledger']:
            target.update(student_cli_session=cost['cli_session'],actual_model_calls_with_usage=cost['cli_calls_with_usage'],
                actual_input_tokens=cost['cli_input_tokens'],actual_output_tokens=cost['cli_output_tokens'],actual_cached_input_tokens=cost['cli_cached_input_tokens'])
for project in ['hintrsi','scene']:
    manifest=json.loads((OUT/'config'/f'{project}_full_audit_manifest.json').read_text())
    for source in manifest['files']:
        target=lookup.get(source['original_file'])
        if target is None:continue
        completed=sum(c['status']=='complete' for c in source['chunks']);total=len(source['chunks'])
        target.update(audit_depth='full_decoded_content_CLI_review_complete' if completed==total else 'full_chunk_CLI_review_in_progress',
            full_reviewed_chunks=completed,full_total_chunks=total,
            full_audit_reports=json.dumps([c['report'] for c in source['chunks'] if c['status']=='complete']))
hint_sources={}
for variant in ['NoHint','Error','Strategy','Exploration']:
    source=json.loads((OUT/'evidence'/f'HT_{variant}_development_input.json').read_text())
    hint_sources[source['source_trajectory']]='HT_'+variant+'_source'
for row in rows:
    row['experiment_phase']='original_historical' if row['project']!='trajectory_capability' else 'original_six_hour'
    row['followup_learning_role']=hint_sources.get(row['path'],
        'original_V1_Development_memory' if str(row.get('knowledge_extraction_cohort')).lower()=='true' else '')
for row in json.loads((OUT/'results/attempt_metrics.json').read_text()):
    path=row['trajectory_path']
    if not path:continue
    rows.append({'project':'trajectory_capability_followup','kind':'student','path':path,
        'bytes':Path(path).stat().st_size,'task':row['task'],'group':row['group'],'round':1,
        'patch_path':str(Path(path).parent/'patch.diff'),'patch_bytes':row['patch_bytes'],
        'eval_path':row['eval_path'],'status':row['outcome'],'f2p_passed':row['f2p_passed'],
        'f2p_total':row['f2p_total'],'p2p_passed':row['p2p_passed'],'p2p_total':row['p2p_total'],
        'student_cli_session':row['session'],'sdk_session_id':row['sdk_session_id'],
        'actual_model_calls_with_usage':row['model_calls_with_usage'],
        'actual_input_tokens':row['input_tokens'],'actual_output_tokens':row['output_tokens'],
        'actual_cached_input_tokens':row['cached_input_tokens'],'stage':row['stage'],
        'experiment_phase':'followup','audit_depth':'new_actual_attempt_trace',
        'knowledge_extraction_cohort':row['stage']=='development',
        'followup_learning_role':row['group'][:2]+'_V2_on_policy_Development' if row['stage']=='development' else '',
        'loaded_knowledge_path':row['loaded_knowledge_path'],
        'teacher_materials':json.dumps({'persistent_capability':row['loaded_knowledge_path'] or None,
            'online_teacher':False,'initial_teacher_hint':None}),
        'recorded_terminal_reason':row['stop_reason']})
for alias in json.loads((OUT/'config/scene_archive_trajectory_links.json').read_text())['records']:
    canonical=lookup.get(alias['expanded_file'],{})
    rows.append({'project':'scene','kind':'archived_student_trajectory_alias','path':alias['archive'],
        'bytes':alias['archive_payload_bytes'],'archive_member':alias['member'],
        'canonical_trajectory':alias['expanded_file'],'experiment_phase':'original_archive_copy',
        'audit_depth':canonical.get('audit_depth','indexed'),
        'full_reviewed_chunks':canonical.get('full_reviewed_chunks',''),
        'full_total_chunks':canonical.get('full_total_chunks',''),
        'full_audit_reports':canonical.get('full_audit_reports',''),
        'status':'same_observations_after_original_archive_path_and_account_redaction'
            if alias.get('same_after_existing_archive_public_path_rules') else 'unexplained_archive_difference'})
additional_path=OUT/'config/scene_additional_full_audit_manifest.json'
additional={}
if additional_path.exists():
    for source in json.loads(additional_path.read_text())['files']:
        n=sum(c['status']=='complete' for c in source['chunks'])
        additional[source['original_file']]={'audit_depth':'full_decoded_content_CLI_review_complete' if n==len(source['chunks']) else 'full_chunk_CLI_review_in_progress',
            'full_reviewed_chunks':n,'full_total_chunks':len(source['chunks']),
            'full_audit_reports':json.dumps([c['report'] for c in source['chunks'] if c['status']=='complete'])}
work_path=OUT/'audit/scene_work_archive_inventory.csv'
if work_path.exists():
    with work_path.open() as stream:
        reader=csv.DictReader(stream);work_fields=reader.fieldnames;work_rows=list(reader)
    for work in work_rows:
        evidence=lookup.get(work['canonical_trajectory'],{}) if work['canonical_trajectory'] else additional.get(work['path'],{})
        work['audit_depth']=evidence.get('audit_depth',work['audit_depth'])
        rows.append({'project':'scene','kind':'work_archive_trajectory','path':work['path'],'bytes':work['bytes'],
            'canonical_trajectory':work['canonical_trajectory'],'experiment_phase':'original_work_archive',
            'audit_depth':work['audit_depth'],'full_reviewed_chunks':evidence.get('full_reviewed_chunks',''),
            'full_total_chunks':evidence.get('full_total_chunks',''),
            'full_audit_reports':evidence.get('full_audit_reports',''),'status':work['relation']})
    with work_path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=work_fields);writer.writeheader();writer.writerows(work_rows)
# Directly reviewed execution/event sidecars have their own file-level coverage.
sidecars={}
for name in ['scene_execution_audit_manifest.json','scene_stage_event_audit_manifest.json']:
    path=OUT/'config'/name
    if not path.exists():continue
    for chunk in json.loads(path.read_text())['chunks']:
        if chunk['status']!='complete':continue
        for source in chunk['sources']:
            file=source.get('file',source.get('path'))
            sidecars.setdefault(file,[]).append(chunk['report'])
for row in rows:
    if row['path'] in sidecars:
        reports=list(dict.fromkeys(sidecars[row['path']]))
        row.update(audit_depth='complete_numbered_text_CLI_sidecar_review',full_reviewed_chunks=len(reports),
            full_total_chunks=len(reports),full_audit_reports=json.dumps(reports))
with (OUT/'trajectory_inventory.csv').open('w',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
print(json.dumps({'file_rows':len(rows),'new_actual_student_files':sum(r['project']=='trajectory_capability_followup' for r in rows),
    'archive_alias_rows':161}),flush=True)
with (OLD/'audit/scene_artifact_inventory.csv').open() as stream:
    reader=csv.DictReader(stream);artifact_fields=reader.fieldnames;artifacts=list(reader)
visual=set()
for path,key in [(OUT/'config/scene_visual_expansion_manifest.json','images')]:
    for case in json.loads(path.read_text())['cases']:visual.update(case[key])
for row in artifacts:
    if row['path'] in sidecars:row['audit_depth']='complete_numbered_text_CLI_sidecar_review'
    elif row['path'] in lookup:row['audit_depth']=lookup[row['path']]['audit_depth']
    if row['path'] in visual:row['audit_depth']='native_CLI_visual_sample_file_not_independent_trial'
with (OUT/'audit/scene_artifact_inventory.csv').open('w',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=artifact_fields);writer.writeheader();writer.writerows(artifacts)
