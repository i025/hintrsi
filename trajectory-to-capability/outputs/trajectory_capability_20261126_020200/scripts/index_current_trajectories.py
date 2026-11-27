"""Extend the file inventory with new student trajectories, preserving historical rows."""
import csv
import json
from collections import Counter
from pathlib import Path

OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
usage=json.loads((OUT/'results/actual_usage_summary.json').read_text())['by_session']
path=OUT/'trajectory_inventory.csv';rows=list(csv.DictReader(path.open()))
rows=[r for r in rows if r['project']!='trajectory_capability'];fields=list(rows[0])
if 'stage' not in fields:fields.append('stage')
attempts=json.loads((OUT/'results/attempt_metrics.json').read_text())
for r in csv.DictReader((OUT/'extra_attempt_metrics.csv').open()):
    run=OUT/'runs'/(r['run_name']+'_r1')
    attempts.append(dict(r,trajectory_path=str(run/'infer_logs'/r['task']/'turn_1/trajs.json'),
        eval_path=str(run/'eval_output'/r['task']/'eval_result.json'),outcome=r['classification']))
hint=OUT/'hint_attempt_metrics.csv'
if hint.exists():attempts.extend(csv.DictReader(hint.open()))
for name,group,session in [('injection_preflight','capability_append_fixture','capability-injection-preflight'),('empty_append_preflight','empty_append_fixture','capability-empty-append-preflight')]:
    directory=OUT/'evidence'/name/'attempt_01'
    if (directory/'student/trajs.json').exists():
        passed=json.loads((directory/'host_result.json').read_text()).get('passed')
        attempts.append({'trajectory_path':str(directory/'student/trajs.json'),'patch_path':str(directory/'final_patch.diff'),
            'eval_path':str(directory/'result.json'),'kind':'preflight','task':'window-report-inclusive-boundary',
            'group':group,'session':session,'stage':'engineering_preflight','run_name':session,
            'outcome':'engineering_preflight_passed' if passed else 'engineering_preflight_not_passed',
            'loaded_knowledge_path':str(directory.parent/'capability.md') if name=='injection_preflight' else ''})
new=[]
for r in attempts:
    p=Path(r.get('trajectory_path') or '')
    if not p.is_file():continue
    d=json.loads(p.read_text());events=[];calls=set()
    for trace in d['trajectories'].values():
        trace=[json.loads(line) for line in trace.splitlines()] if isinstance(trace,str) else trace
        events.extend(trace)
        for e in trace:
            blocks=e.get('message',{}).get('content',[])
            if isinstance(blocks,list):calls.update(b['id'] for b in blocks if isinstance(b,dict) and b.get('name') and b.get('id'))
    patch=Path(r.get('patch_path') or str(p.parent/'patch.diff'));ev=Path(r.get('eval_path') or '')
    stage=r.get('stage','hint_exploration');group=r['group'];task=r['task']
    prefix='posthoc_selection_matched_' if 'matched_prompt' in r['run_name'] else 'posthoc_'+stage+'_'
    if stage=='selection_superseded_before_common_prompt_fix':prefix='posthoc_selection_'
    audit=OUT/'audit'/(prefix+task+'_'+group+'.md')
    row={'project':'trajectory_capability','kind':r.get('kind','student'),'path':str(p),'bytes':p.stat().st_size,
        'task':task,'group':group,'round':1,'stage':stage,'events':len(events),'tools':len(calls),
        'patch_path':str(patch) if patch.exists() else '','patch_bytes':patch.stat().st_size if patch.exists() else '',
        'eval_path':str(ev) if ev.is_file() else '','status':r.get('outcome',r.get('status','')),
        'teacher_materials':json.dumps({'loaded_capabilities':r.get('loaded_knowledge_path') or (str(p.parent/'loaded_capabilities.md') if (p.parent/'loaded_capabilities.md').exists() else ''),
            'model_requests':str(OUT/'logs/bridge/model_requests.jsonl'),
            'model_responses':str(OUT/'logs/bridge/model_responses.jsonl'),
            'session':r.get('session',r['run_name']+'-r1'),
            'online_teacher_events':str(p.parent/'online_teacher_events.json') if (p.parent/'online_teacher_events.json').exists() else ''}),
        'audit_depth':'posthoc_all_event_ids_long_fields_clipped_1800' if audit.exists() else 'parsed_event_counts',
        'audit_report':str(audit) if audit.exists() else '','knowledge_extraction_cohort':False,
        'recorded_terminal_reason':d.get('metadata',{}).get('terminal_reason','')}
    for key in ['f2p_passed','f2p_total','p2p_passed','p2p_total']:row[key]=r.get(key,'')
    session=r.get('session',r['run_name']+'-r1');u=usage.get(session,{})
    row['student_cli_session']=session
    for key in ['model_calls_with_usage','input_tokens','output_tokens','cached_input_tokens']:row['actual_'+key]=u.get(key,'')
    new.append(row)
with path.open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows+new)
(OUT/'audit/current_inventory_summary.json').write_text(json.dumps({'new_student_files':sum(r['kind']=='student' for r in new),
    'new_preflight_files':sum(r['kind']=='preflight' for r in new),'total_inventory_rows':len(rows)+len(new),
    'counts_by_project_kind':{project+'/'+kind:count for (project,kind),count in Counter((r['project'],r['kind']) for r in rows+new).items()},
    'scope':'File-backed new student and neutral preflight trajectories. Historical117student/104teacher/36preflight denominators are unchanged. Planned or pre-model launches without a trajectory remain in attempt_metrics/extra_attempt_metrics, not invented as files.'},indent=2)+'\n')
print(json.dumps({'new_trajectory_files_indexed':len(new),'preserved_other_rows':len(rows)}))
