import csv
import json
from pathlib import Path

OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
audits={}
development=json.loads((OUT/'config/development_sources.json').read_text())
for item in development:
    d=json.loads(Path(item['file']).read_text())
    audits[d['index']['path']]={'report':str(OUT/'audit'/f"audit_{item['source_id']}.md"),
        'depth':'deep_full_parsed_event_sequence','events':item['events'],'knowledge_input':True}
supplemental=json.loads((OUT/'audit/baseline_addendum_sources.json').read_text())
comparison=OUT/'audit/historical_comparison_sources.json'
if comparison.exists():supplemental+=json.loads(comparison.read_text())
for item in supplemental:
    report=OUT/'audit'/f"audit_{item['audit_id']}.md"
    if not report.exists() or not json.loads(report.with_suffix('.md.job.json').read_text())['completed']:raise RuntimeError('Supplemental audit incomplete')
    audits[item['trajectory_path']]={'report':str(report),'depth':'deep_all_event_ids_long_fields_clipped_1800',
        'events':item['events'],'knowledge_input':False}
p=OUT/'config/audit_teacher_chain_reduced_prompt.txt';s=p.read_text();packet=json.loads(s[s.index('{'):])
for item in packet['teacher_chain']:
    if Path(item['source']).name not in ['trajs.json','trajs.json.gz']:continue
    audits[item['source']]={'report':str(OUT/'audit/audit_teacher_chain_reduced.md'),
        'depth':'deep_full_teacher_event_sequence','knowledge_input':False}
path=OUT/'trajectory_inventory.csv';rows=list(csv.DictReader(path.open()));fields=list(rows[0])
for key in ['audit_report','knowledge_extraction_cohort']:
    if key not in fields:fields.append(key)
for row in rows:
    if row['path'] in audits:
        audit=audits[row['path']];row['audit_depth']=audit['depth'];row['audit_report']=audit['report']
        row['knowledge_extraction_cohort']=audit['knowledge_input']
with path.open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
p=OUT/'audit/inventory_summary.json';summary=json.loads(p.read_text())
deep_files=len(development)+len(supplemental)
dev_events=sum(item['events'] for item in development);supplemental_events=sum(item['events'] for item in supplemental)
summary.update(deeply_audited_students=deep_files,deeply_audited_student_events=dev_events+supplemental_events,
    development_knowledge_cohort_students=len(development),development_knowledge_cohort_events=dev_events,
    postfreeze_audit_only_students=len(supplemental),postfreeze_audit_only_events=supplemental_events,
    postfreeze_audit_field_scope='Every supplementary event ID included; long event fields clipped to1800characters. Separate captured prompts, patches and evaluations supplied; original raw trajectories retained.',
    not_deeply_audited_student_files=117-deep_files)
p.write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({'deep_student_files':deep_files,'parsed_events':dev_events+supplemental_events,'teacher_rows_linked':sum(v['depth']=='deep_full_teacher_event_sequence' for v in audits.values())}))
