import csv
import json
from collections import Counter,defaultdict
from pathlib import Path

OUT=Path.cwd()/'outputs/trajectory_capability_followup_20261126_182329'
split=json.loads((OUT/'config/task_split.json').read_text())
protocol=json.loads((OUT/'config/protocol.json').read_text())
usage=defaultdict(list);requests=defaultdict(list);responses=defaultdict(list);errors=defaultdict(list)
for filename,target in [('token_usage.jsonl',usage),('model_requests.jsonl',requests),('model_responses.jsonl',responses),('model_errors.jsonl',errors)]:
    p=OUT/'logs/bridge'/filename
    if p.exists():
        for line in p.open():
            try:d=json.loads(line)
            except ValueError:continue
            target[d['session']].append(d)

rows=[]
for stage in ['development','selection','test','hint_transfer']:
    TAG=protocol.get('stage_run_tags',{}).get(stage,protocol.get('run_tag','capability_v1'))
    for task in ([split['hint_transfer_test']] if stage=='hint_transfer' else split[stage]):
        state_path=OUT/'runs'/f'{TAG}_{stage}_{task}_state.json'
        state=json.loads(state_path.read_text()) if state_path.exists() else {}
        if stage=='hint_transfer' and not state:
            shared=OUT/'runs'/f"{protocol['run_tag']}_test_{task}_state.json"
            state=json.loads(shared.read_text()) if shared.exists() else {}
        by={a['group']:a for a in state.get('attempts',[])}
        order=split['hint_transfer_order'] if stage=='hint_transfer' else split['group_orders'][task]
        for index,group in enumerate(order,1):
            name=f'{TAG}_{stage}_{task}_{group}';session=name+'-r1'
            run=OUT/'runs'/(name+'_r1');infer=run/'infer_logs'/task/'turn_1'
            a=by.get(group,{})
            row={'stage':stage,'task':task,'group':group,'planned_order':index,'actual_order_in_task_queue':next((i for i,x in enumerate(state.get('attempts',[]),1) if x['group']==group),''),'status':a.get('status','not_started'),
                'run_name':name,'session':session,'model':'gpt-6.1-terra','reasoning_effort':'low',
                'formal_success':'','observed_verifier_reward':'','initial_eval_path':'','initial_verifier_reward':'',
                'initial_wall_seconds':'','diagnostic_evaluation_seconds':'','uniform_evaluation_repair_seconds':'','evaluation_attempts':'',
                'student_budget_seconds':protocol['student_seconds'],'configured_final_verifier_seconds':protocol['verifier_seconds'],'observed_verifier_timeout_seconds':'','verifier_elapsed_seconds':'',
                'f2p_passed':'','f2p_total':'','p2p_passed':'','p2p_total':'',
                'patch_bytes':'','tool_calls_requested':'','tool_calls_with_returns':'','tool_returns':'',
                'sdk_session_id':'','model_requests':len(requests[session]) if a else '',
                'model_calls_with_usage':len(usage[session]) if a else '',
                'usage_missing':len({x['request_id'] for x in requests[session]}-{x['request_id'] for x in usage[session]}) if a else '',
                'input_tokens':'','output_tokens':'','cached_input_tokens':'','wall_seconds':'','end_to_end_seconds':'','sdk_seconds':'','student_execution_seconds':'',
                'knowledge_words':0 if group=='B0' else (len((OUT/'knowledge'/f'{group}.md').read_text().split()) if (OUT/'knowledge'/f'{group}.md').exists() else ''),
                'capability_requested':group!='B0','capability_in_actual_prompt':'','capability_in_first_bridge_request':'',
                'stop_reason':'','bridge_model_errors':len(errors[session]),'visible_process_segfault_returns':'','eval_path':'','trajectory_path':'',
                'loaded_knowledge_path':'','notes':''}
            if a:
                row['wall_seconds']=round(a['finished_at']-a['started_at'],3) if 'finished_at' in a else ''
                row['end_to_end_seconds']=row['wall_seconds']
            if usage[session]:
                for key in ['input_tokens','output_tokens','cached_input_tokens']:
                    row[key]=sum(x['usage'].get(key,0) for x in usage[session])
            ev=run/'eval_output'/task/'eval_result.json'
            if ev.exists():
                v=json.loads(ev.read_text());reward=v.get('reward')
                if isinstance(reward,dict):v={**v,**reward};reward=reward.get('reward')
                row.update(eval_path=str(ev),formal_success=1 if reward==1 else 0 if reward==0 else '',observed_verifier_reward=reward,evaluation_attempts=1,observed_verifier_timeout_seconds=v.get('verifier_timeout_seconds',''),verifier_elapsed_seconds=v.get('verifier_elapsed_seconds',''))
                for key in ['f2p_passed','f2p_total','p2p_passed','p2p_total']:row[key]=v.get(key,'')
                if v.get('verifier_timed_out'):
                    row.update(formal_success='',status='evaluation_timeout',outcome='evaluation_timeout_incomplete_report')
                    for key in ['f2p_passed','f2p_total','p2p_passed','p2p_total']:row[key]=''
                elif reward==1:row['outcome']='formal_success'
                elif isinstance(v.get('f2p_passed'),int) and v['f2p_passed']>0:row['outcome']='partial_correct_formally_unsolved'
                else:row['outcome']='formally_unsolved'
            else:row['outcome']='evaluation_missing' if a else 'not_started'
            p=infer/'patch.diff'
            if p.exists():
                row['patch_bytes']=p.stat().st_size
                if p.stat().st_size==0 and row['formal_success']==0:row['outcome']='empty_patch_formally_unsolved'
            p=infer/'capability_injection.json'
            if p.exists():
                proof=json.loads(p.read_text());row['capability_in_actual_prompt']=proof.get('content_present')
            cap=infer/'loaded_capabilities.md'
            if cap.exists():row['loaded_knowledge_path']=str(cap)
            if requests[session]:
                req=requests[session][0]['request'];text=json.dumps(req['messages'],ensure_ascii=False)
                if group!='B0':
                    expected=(OUT/'knowledge'/f'{group}.md').read_text().strip()
                    # Search decoded system content, avoiding JSON-escaped newlines.
                    def strings(value):
                        if isinstance(value,str):return [value]
                        if isinstance(value,list):return [s for v in value for s in strings(v)]
                        if isinstance(value,dict):return [s for v in value.values() for s in strings(v)]
                        return []
                    row['capability_in_first_bridge_request']=any(expected in s for s in strings(req['messages']))
                else:
                    row['capability_in_first_bridge_request']=False
                    if '<persistent_capabilities>' in text:row['notes']='Unexpected capability marker in B0 request; inspect.'
                configs={(x['actual_model'],x['reasoning_effort']) for x in requests[session]}
                if configs!={('gpt-6.1-terra','low')}:row['notes']+=' Model/effort mismatch: '+str(configs)
            p=infer/'trajs.json'
            if p.exists():
                row['trajectory_path']=str(p);d=json.loads(p.read_text());calls=set();returns=set();segfaults=set();observed_sessions=set()
                for data in d.get('trajectories',{}).values():
                    es=[json.loads(line) for line in data.splitlines()] if isinstance(data,str) else data
                    for event in es:
                        sid=event.get('message',{}).get('session_id')
                        if sid:observed_sessions.add(sid)
                        content=event.get('message',{}).get('content',[])
                        if not isinstance(content,list):continue
                        for b in content:
                            if isinstance(b,dict):
                                if b.get('name') and b.get('id'):calls.add(b['id'])
                                if b.get('tool_use_id'):
                                    returns.add(b['tool_use_id'])
                                    content=b.get('content','')
                                    if isinstance(content,str) and (content.startswith('Exit code 139\n') or '\nSegmentation fault (core dumped)' in content):segfaults.add(b['tool_use_id'])
                meta=d.get('metadata',{});result=meta.get('ResultMessage',{})
                row['sdk_session_id']=result.get('session_id') or (next(iter(observed_sessions)) if len(observed_sessions)==1 else '')
                row.update(tool_calls_requested=len(calls),tool_returns=len(returns),tool_calls_with_returns=len(calls&returns),
                    visible_process_segfault_returns=len(segfaults),
                    sdk_seconds=round(result['duration_ms']/1000,3) if result.get('duration_ms') is not None else '',
                    stop_reason=meta.get('terminal_reason') or result.get('stop_reason') or meta.get('status',''))
                if result.get('is_error'):
                    row['notes']+=' SDK reported is_error.'
                    if 'timeout' in str(row['stop_reason']).lower() and row['formal_success']!='':
                        row['outcome']='budget_exhausted_with_formal_grade'
                    else:
                        row['status']='technical_incomplete'
                        row['outcome']='technical_interruption_with_or_without_observed_grade'
            rounds_path=infer.parent/'rounds_meta.json'
            if rounds_path.exists():
                execution=json.loads(rounds_path.read_text()).get('rounds',[])
                seconds=[r.get('execution',{}).get('effective_seconds') for r in execution]
                if seconds and all(isinstance(s,(int,float)) for s in seconds):row['student_execution_seconds']=round(sum(seconds),3)
            deadline=run/'budget_stop_evaluation.json'
            if deadline.exists():
                recovery=json.loads(deadline.read_text())
                row['stop_reason']='student_timeout'
                row['initial_wall_seconds']=round(recovery['original_finished_at']-a['started_at'],3)
                row['notes']+=' Student stopped at the unchanged 1800s deadline. Original cancellation/technical state preserved; first formal evaluation of the identical saved deadline patch, no additional student or model call. Source: '+str(deadline)
                if recovery['status']=='running':row.update(status='running',outcome='deadline_patch_formal_evaluation_running')
                elif recovery['status']=='complete' and row['formal_success']!='':
                    row.update(status='complete',outcome='student_budget_exhausted_with_formal_grade')
                elif recovery['status']=='evaluation_timeout':
                    row.update(status='evaluation_timeout',formal_success='',outcome='student_timeout_with_incomplete_formal_evaluation')
            elif a.get('status')=='technical_incomplete':row['outcome']='technical_incomplete_with_or_without_grade'
            rows.append(row)
triage_path=OUT/'config/evaluation_triage.json'
if triage_path.exists():
    triage=json.loads(triage_path.read_text())
    for row in rows:
        if row['run_name']==triage['affected_run'] and triage['status']=='pending':
            row.update(status='evaluation_triage_pending',formal_success='',outcome='missing_test_report_cause_unresolved')
            row['notes']+=' Original scorer reward0 is retained as observed_verifier_reward; missing F2P report is under same-patch diagnostic, not yet an ordinary algorithm failure.'
        elif row['run_name']==triage['affected_run'] and triage.get('replacement_eval_path'):
            ev=Path(triage['replacement_eval_path']);v=json.loads(ev.read_text());reward=v.get('reward')
            if isinstance(reward,dict):v={**v,**reward};reward=reward['reward']
            row.update(initial_eval_path=row['eval_path'],initial_verifier_reward=row['observed_verifier_reward'],
                eval_path=str(ev),observed_verifier_reward=reward,formal_success=1 if reward==1 else 0 if reward==0 else '',
                initial_wall_seconds=round(triage['initial_wall_seconds'],3),wall_seconds=round(triage['recovered_end_to_end_seconds'],3),
                diagnostic_evaluation_seconds=round(triage['diagnostic_evaluation_seconds'],3),evaluation_attempts=2,
                outcome='formal_success_after_incomplete_evaluation_recovery' if reward==1 else 'complete_evaluation_after_incomplete_report')
            for key in ['f2p_passed','f2p_total','p2p_passed','p2p_total']:row[key]=v.get(key,'')
            row['notes']+=' Initial report missing; original grade preserved. First complete same-patch diagnostic used without student retry or code/environment change. Wall includes triage/recovery; SDK/model/tool counts unchanged.'
diagnostic_state=OUT/'runs/capability_followup_selection_same_patch_01_state.json'
if diagnostic_state.exists():
    diagnostic=json.loads(diagnostic_state.read_text())
    for row in rows:
        if row['run_name']!=diagnostic['original_run']:continue
        row['notes']+=' Original Selection evaluation timed out; one bounded identical-patch diagnostic is separately retained. No new student attempt.'
        if 'finished_at' not in diagnostic:continue
        value=diagnostic.get('result',{});reward=value.get('reward')
        if isinstance(reward,dict):value={**value,**reward};reward=reward.get('reward')
        row.update(evaluation_attempts=2,diagnostic_evaluation_seconds=round(diagnostic['finished_at']-diagnostic['started_at'],3))
        known=not value.get('verifier_timed_out') and reward in (0,1) and all(isinstance(value.get(k),int) for k in ['f2p_passed','f2p_total','p2p_passed','p2p_total'])
        if known:
            row.update(initial_eval_path=row['eval_path'],initial_verifier_reward=row['observed_verifier_reward'],
                initial_wall_seconds=row['wall_seconds'],
                eval_path=str(OUT/'runs/capability_followup_selection_same_patch_01/eval_output'/row['task']/'eval_result.json'),
                formal_success=int(reward==1),observed_verifier_reward=reward,status='complete',
                outcome='complete_evaluation_after_same_patch_diagnostic')
            for key in ['f2p_passed','f2p_total','p2p_passed','p2p_total']:row[key]=value[key]
            row['notes']+=' First complete diagnostic grade used; original student wall time retained, additional diagnostic cost separate. Account outage/wait is outside active solve time.'
        else:row['notes']+=' Diagnostic did not produce complete formal counts; outcome remains unknown.'
repair_state=OUT/'runs/capability_followup_selection_uniform_evaluation_recovery_01_state.json'
if repair_state.exists():
    repair=json.loads(repair_state.read_text())
    for row in rows:
        if row['run_name']!=repair['original_run']:continue
        row['notes']+=' One uniform 3600s evaluation repair is retained separately after the 900s attempt and diagnostic; no additional student.'
        if 'finished_at' not in repair:continue
        value=repair.get('result',{});reward=value.get('reward')
        if isinstance(reward,dict):value={**value,**reward};reward=reward.get('reward')
        row.update(evaluation_attempts=3,uniform_evaluation_repair_seconds=round(repair['finished_at']-repair['started_at'],3))
        known=not value.get('verifier_timed_out') and reward in (0,1) and all(isinstance(value.get(k),int) for k in ['f2p_passed','f2p_total','p2p_passed','p2p_total'])
        if known:
            original_state=json.loads((OUT/'runs/capability_followup_v2_selection_mashumaro-flattened-dataclass-fields_state.json').read_text())
            original_attempt=next(a for a in original_state['attempts'] if a['run_name']==repair['original_run'])
            row.update(initial_eval_path=row['initial_eval_path'] or row['eval_path'],
                initial_verifier_reward=row['initial_verifier_reward'] if row['initial_verifier_reward']!='' else row['observed_verifier_reward'],
                initial_wall_seconds=row['initial_wall_seconds'] or row['wall_seconds'],
                eval_path=str(OUT/'runs/capability_followup_selection_uniform_evaluation_recovery_01/eval_output'/row['task']/'eval_result.json'),
                formal_success=int(reward==1),observed_verifier_reward=reward,status='complete',outcome='complete_evaluation_after_uniform_budget_repair',observed_verifier_timeout_seconds=value.get('verifier_timeout_seconds',''),
                end_to_end_seconds=round(repair['finished_at']-original_attempt['started_at'],3),verifier_elapsed_seconds=value.get('verifier_elapsed_seconds',''))
            for key in ['f2p_passed','f2p_total','p2p_passed','p2p_total']:row[key]=value[key]
        else:row['notes']+=' Uniform repair also lacks a complete grade; no further repeat is authorized by the finite protocol.'
observation_path=OUT/'config/observed_attempt_notes.json'
if observation_path.exists():
    for observation in json.loads(observation_path.read_text()):
        for row in rows:
            if row['run_name']==observation['run_name']:
                row['notes']+=' '+observation['observation']+' Source: '+observation['source']
fields=list(rows[0])
with (OUT/'attempt_metrics.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
(OUT/'results/attempt_metrics.json').write_text(json.dumps(rows,indent=2)+'\n')

incident=OUT/'config/statemachine_baseline_timeout_incident.json'
if incident.exists():
    observed=[]
    for row in rows:
        if row['task']!='python-statemachine-state-data-scoping' or row['status']!='complete' or not row['eval_path']:continue
        path=Path(row['eval_path']).with_name('verifier_stdout.log')
        if not path.exists():continue
        base=path.read_text().split('===== raw suite output: new.log =====')[0]
        failed=sorted({line[7:].split(' - ',1)[0].strip() for line in base.splitlines() if line.startswith('FAILED ')})
        observed.append({'run_name':row['run_name'],'group':row['group'],'patch_bytes':row['patch_bytes'],
            'formal_success':row['formal_success'],'p2p_passed':row['p2p_passed'],'p2p_total':row['p2p_total'],
            'base_suite_failed_test_ids':failed,'timeout_60s_message_present':'Timeout (>60.0s)' in base,
            'failure_ids_match_reported_count':all(isinstance(row[k],int) for k in ['p2p_passed','p2p_total']) and len(failed)==row['p2p_total']-row['p2p_passed'],
            'source':str(path)})
    pristine=next((r for r in observed if r['group']=='K2_v2' and r['patch_bytes']==0),None)
    if pristine:
        baseline=set(pristine['base_suite_failed_test_ids'])
        for item in observed:
            item['shared_failure_ids_with_pristine']=sorted(set(item['base_suite_failed_test_ids'])&baseline)
            item['other_observed_failure_ids']=sorted(set(item['base_suite_failed_test_ids'])-baseline)
        (OUT/'results/statemachine_baseline_failure_inventory.json').write_text(json.dumps({
            'pristine_base_comparator':pristine['run_name'],'pristine_base_failure_ids':sorted(baseline),'attempts':observed,
            'scope':'Existing-suite failure IDs from completed raw stdout, not a new score or causal regression judgment. Comparator is unchanged base from an empty patch, not B0. Incomplete ID extraction is marked; no tests, deadlines or official scores change.'},indent=2)+'\n')

all_usage=[];all_requests=[];all_errors=[]
for p in (OUT/'logs').glob('*/token_usage.jsonl'):
    for line in p.open():
        d=json.loads(line);all_usage.append(dict(ledger=str(p),**d))
for filename,target in [('model_requests.jsonl',all_requests),('model_errors.jsonl',all_errors)]:
    for p in (OUT/'logs').glob('*/'+filename):
        for line in p.open():target.append(dict(ledger=str(p),**json.loads(line)))
totals=defaultdict(int);by_session=defaultdict(lambda:defaultdict(int))
for d in all_usage:
    by_session[d['session']]['model_calls_with_usage']+=1;totals['model_calls_with_usage']+=1
    for k,v in d['usage'].items():
        if isinstance(v,(int,float)):totals[k]+=v;by_session[d['session']][k]+=v
reported={d['request_id'] for d in all_usage}
missing=[{k:d.get(k) for k in ['request_id','session','role','phase','timestamp']} for d in all_requests if d['request_id'] not in reported]
cost={'actual_cli_usage':dict(totals),'by_session':dict(by_session),'recorded_bridge_or_native_cli_requests':len(all_requests),
    'usage_unreported_requests':missing,'recorded_errors':[{k:d.get(k) for k in ['session','request_id','error','code']} for d in all_errors],
    'settled_dollar_cost':None,
    'note':'Input includes cached input; cached tokens are not added a second time. SDK usage/cost estimates are not added. Visual audit native CLI ledgers are included separately from the primary HTTP bridge ledger. Pre-metadata-fix extraction and engineering preflight remain charged and separately attributable.'}
(OUT/'results/actual_usage_summary.json').write_text(json.dumps(cost,indent=2)+'\n')
extra=[]
old=OUT/'runs/selection_superjson-error-stack-serialization_state.json'
if old.exists():
    state=json.loads(old.read_text())
    for a in state['attempts']:
        session=a['run_name']+'-r1';u=by_session.get(session,{})
        grade=a.get('summary',{}).get('rounds',[{}])[0].get('eval',{})
        old_eval=OUT/'runs'/(a['run_name']+'_r1')/'eval_output'/state['task']/'eval_result.json'
        if old_eval.exists():grade={**grade,**json.loads(old_eval.read_text())}
        extra.append({'stage':'selection_superseded_before_forwarding_fix','task':state['task'],'group':a['group'],
            'run_name':a['run_name'],'classification':'completed_old_revision' if a['status']=='complete' else 'engineering_interruption_before_model',
            'formal_success':int(grade['solved']) if isinstance(grade.get('solved'),bool) else None,'f2p_passed':grade.get('f2p_passed'),'f2p_total':grade.get('f2p_total'),
            'p2p_passed':grade.get('p2p_passed'),'p2p_total':grade.get('p2p_total'),
            'model_calls_with_usage':u.get('model_calls_with_usage',0),'input_tokens':u.get('input_tokens',0),'output_tokens':u.get('output_tokens',0),
            'cached_input_tokens':u.get('cached_input_tokens',0),
            'wall_seconds':round(a['finished_at']-a['started_at'],3) if a.get('finished_at') else round(state['finished_at']-a['started_at'],3),
            'state_path':str(old),'reason':'Full cohort restarted after capability option forwarding repair; original outcomes preserved, excluded from core comparison.'})
old=OUT/'runs/capability_v1_selection_superjson-error-stack-serialization_state.json'
if protocol.get('stage_run_tags',{}).get('selection')=='capability_v1_matched_prompt' and old.exists():
    state=json.loads(old.read_text())
    for a in state['attempts']:
        session=a['run_name']+'-r1';u=by_session.get(session,{})
        ev=OUT/'runs'/(a['run_name']+'_r1')/'eval_output'/state['task']/'eval_result.json'
        grade=json.loads(ev.read_text()) if ev.exists() else {}
        extra.append({'stage':'selection_superseded_before_common_prompt_fix','task':state['task'],'group':a['group'],
            'run_name':a['run_name'],'classification':'completed_prompt_identity_confound',
            'formal_success':1 if grade.get('reward')==1 else 0 if grade.get('reward')==0 else None,
            'f2p_passed':grade.get('f2p_passed'),'f2p_total':grade.get('f2p_total'),
            'p2p_passed':grade.get('p2p_passed'),'p2p_total':grade.get('p2p_total'),
            'model_calls_with_usage':u.get('model_calls_with_usage',0),'input_tokens':u.get('input_tokens',0),'output_tokens':u.get('output_tokens',0),
            'cached_input_tokens':u.get('cached_input_tokens',0),
            'wall_seconds':round(a['finished_at']-a['started_at'],3),
            'state_path':str(old),'reason':'All four Selection cells revalidated once with common empty/nonempty append routing; libraries unchanged and no Test feedback used.'})
if extra:
    with (OUT/'extra_attempt_metrics.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(extra[0]));w.writeheader();w.writerows(extra)
diagnostics=[]
for name in ['capability_followup_nohint_same_patch_01','capability_followup_known_good_control_01']:
    path=OUT/'runs'/(name+'_state.json')
    if not path.exists():continue
    state=json.loads(path.read_text());value=state.get('result',{});reward=value.get('reward')
    if isinstance(reward,dict):value={**value,**reward};reward=reward.get('reward')
    item={'run_name':name,'status':state['status'],'new_student_attempts':state['new_student_attempts'],
        'model_calls':state['model_calls'],'wall_seconds':round(state['finished_at']-state['started_at'],3) if state.get('finished_at') else '',
        'verifier_elapsed_seconds':value.get('verifier_elapsed_seconds',''),'raw_reward':reward,
        'f2p_passed':value.get('f2p_passed',''),'f2p_total':value.get('f2p_total',''),
        'p2p_passed':value.get('p2p_passed',''),'p2p_total':value.get('p2p_total',''),'source':str(path)}
    diagnostics.append(item)
(OUT/'results/additional_evaluation_metrics.json').write_text(json.dumps(diagnostics,indent=2)+'\n')
if diagnostics:
    with (OUT/'additional_evaluation_metrics.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(diagnostics[0]));w.writeheader();w.writerows(diagnostics)
print(json.dumps({'planned':len(rows),'statuses':dict(Counter(r['status'] for r in rows)),'completed_formal':sum(r['formal_success']!='' for r in rows),'usage':dict(totals)}))
