"""Read optional student/teacher records without changing an attempt or a library."""
import csv
import json
from collections import defaultdict
from pathlib import Path

OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
state_path=OUT/'runs/hint_exploration_state.json'
if not state_path.exists():raise SystemExit('Optional experiment not launched')
state=json.loads(state_path.read_text());attempts={a['group']:a for a in state['attempts']}
requests=defaultdict(list);usage=defaultdict(list)
for name,target in [('model_requests.jsonl',requests),('token_usage.jsonl',usage)]:
    for line in (OUT/'logs/bridge'/name).open():
        record=json.loads(line);target[record['session']].append(record)
progress_path=OUT/'logs/hint_progress/progress.jsonl'
progress=[json.loads(line) for line in progress_path.open()] if progress_path.exists() else []
rows=[]
for order,group in enumerate(state['planned_groups'],1):
    name='capability_hint_development_'+state['task']+'_'+group;session=name+'-r1'
    a=attempts.get(group,{});run=OUT/'runs'/(name+'_r1')
    trajectory=run/'infer_logs'/state['task']/'turn_1/trajs.json'
    if not trajectory.exists() and (trajectory.parent.parent/'trajs.json').exists():trajectory=trajectory.parent.parent/'trajs.json'
    infer=trajectory.parent
    evaluation=run/'eval_output'/state['task']/'eval_result.json'
    row=dict(stage='hint_exploration',task=state['task'],group=group,planned_order=order,
        run_name=name,session=session,status=a.get('status','not_started'),student_and_evaluation_finished=bool(a.get('finished_at')),
        model='gpt-6.1-terra',reasoning_effort='low',
        formal_success='',observed_verifier_reward='',evaluation_exit_code='',evaluation_timed_out=False,evaluation_heap_oom_observed=False,
        f2p_passed='',f2p_total='',p2p_passed='',p2p_total='',
        patch_bytes='',tool_calls_requested='',tool_returns='',model_requests=len(requests[session]) if a else '',
        model_calls_with_usage=len(usage[session]) if a else '',
        usage_unreported_requests=len({x['request_id'] for x in requests[session]}-{x['request_id'] for x in usage[session]}) if a else '',
        input_tokens='',output_tokens='',cached_input_tokens='',
        sdk_seconds='',wall_seconds=round(a['finished_at']-a['started_at'],3) if a.get('finished_at') else '',
        stop_reason='',sdk_session_id='',sdk_is_error=False,sdk_teacher_callbacks=0,server_teacher_checks=0,delivered_hints=0,
        teacher_model_requests=0,teacher_calls_with_usage=0,teacher_input_tokens=0,teacher_output_tokens=0,
        teacher_cached_input_tokens=0,teacher_usage_unreported_requests=0,teacher_wait_seconds=0,
        sdk_teacher_wait_seconds=0,server_teacher_wait_seconds=0,
        trajectory_path=str(trajectory) if trajectory.exists() else '',eval_path=str(evaluation) if evaluation.exists() else '',
        loaded_knowledge_path='',actual_hint_records=str(progress_path),outcome='not_started' if not a else 'running',
        notes='Common initial code/fresh sessions; no common intermediate-state replay; no independent Hint transfer test.')
    if usage[session]:
        for key in ['input_tokens','output_tokens','cached_input_tokens']:row[key]=sum(r['usage'].get(key,0) for r in usage[session])
    if trajectory.exists():
        d=json.loads(trajectory.read_text());calls=set();returns=set()
        for trace in d.get('trajectories',{}).values():
            events=[json.loads(line) for line in trace.splitlines()] if isinstance(trace,str) else trace
            for event in events:
                blocks=event.get('message',{}).get('content',[])
                if not isinstance(blocks,list):continue
                for block in blocks:
                    if isinstance(block,dict):
                        if block.get('name') and block.get('id'):calls.add(block['id'])
                        if block.get('tool_use_id'):returns.add(block['tool_use_id'])
        meta=d.get('metadata',{});result=meta.get('ResultMessage',{})
        row.update(tool_calls_requested=len(calls),tool_returns=len(returns),sdk_session_id=result.get('session_id',''),
            stop_reason=meta.get('terminal_reason') or result.get('stop_reason',''),
            sdk_seconds=round(result['duration_ms']/1000,3) if result.get('duration_ms') is not None else '',
            sdk_teacher_callbacks=meta.get('teacher_checks',0),teacher_wait_seconds=meta.get('teacher_wait_seconds',0),
            sdk_teacher_wait_seconds=meta.get('teacher_wait_seconds',0))
        row['sdk_is_error']=bool(result.get('is_error'))
        if result.get('is_error'):row['notes']+=' SDK reported is_error; inspect terminal reason independently of observed grade.'
    online=infer/'online_teacher_state.json'
    if online.exists():
        d=json.loads(online.read_text());row['sdk_teacher_callbacks']=d.get('checks',row['sdk_teacher_callbacks'])
    patch=infer/'patch.diff'
    if patch.exists():row['patch_bytes']=patch.stat().st_size
    if evaluation.exists():
        v=json.loads(evaluation.read_text());reward=v.get('reward')
        if isinstance(reward,dict):v={**v,**reward};reward=reward.get('reward')
        row.update(observed_verifier_reward=reward,evaluation_exit_code=v.get('exit_code',''),evaluation_timed_out=bool(v.get('verifier_timed_out')))
        row['formal_success']=1 if reward==1 else 0 if reward==0 else ''
        for key in ['f2p_passed','f2p_total','p2p_passed','p2p_total']:row[key]=v.get(key,'')
        row['outcome']='formal_success' if reward==1 else 'formally_unsolved' if reward==0 else 'evaluation_missing'
        stderr=evaluation.parent/'verifier_stderr.log'
        error_text=stderr.read_text() if stderr.exists() else v.get('stderr_tail','')
        if 'heap out of memory' in error_text.lower():
            row['evaluation_heap_oom_observed']=True
            row['notes']+=' Verifier stderr contains a Node heap-out-of-memory signal. Preserve complete official grade separately; no root cause or extra assertion coverage inferred.'
    checks=[r for r in progress if r['session']==session]
    row['server_teacher_checks']=len(checks);row['delivered_hints']=sum(bool(r.get('hint')) for r in checks)
    for teacher_session in requests.keys()|usage.keys():
        if not teacher_session.startswith(session+'_progress_'):continue
        row['teacher_model_requests']+=len(requests[teacher_session]);row['teacher_calls_with_usage']+=len(usage[teacher_session])
        row['teacher_usage_unreported_requests']+=len({x['request_id'] for x in requests[teacher_session]}-{x['request_id'] for x in usage[teacher_session]})
        for key in ['input_tokens','output_tokens','cached_input_tokens']:
            row['teacher_'+key]+=sum(r['usage'].get(key,0) for r in usage[teacher_session])
    row['server_teacher_wait_seconds']=sum(c.get('duration_seconds',0) for c in checks)
    if row['teacher_model_requests'] and not row['teacher_calls_with_usage']:
        for key in ['teacher_input_tokens','teacher_output_tokens','teacher_cached_input_tokens']:row[key]=''
    if row['sdk_is_error']:
        if 'timeout' in row['stop_reason'].lower() and row['formal_success']!='':row['outcome']='budget_exhausted_with_formal_grade'
        else:row.update(status='technical_incomplete',outcome='technical_interruption_with_or_without_observed_grade')
    if a.get('status')=='technical_incomplete':row['outcome']='technical_incomplete_with_or_without_grade'
    manual_timeout=OUT/'logs'/('optional_evaluation_timeout_'+group+'.json')
    if manual_timeout.exists() and json.loads(manual_timeout.read_text()).get('status')=='evaluation_timeout_stopped':row['evaluation_timed_out']=True
    if row['evaluation_timed_out']:
        row.update(status='evaluation_timeout',formal_success='',f2p_passed='',f2p_total='',p2p_passed='',p2p_total='',outcome='evaluation_timeout_incomplete_report')
        row['notes']+=' Bounded optional evaluation ended without complete report; raw observed reward/exit retained, no ordinary success/failure assigned. Root cause unknown; no same-patch retry.'
    elif a.get('status')=='complete' and row['formal_success']=='':
        row.update(status='evaluation_missing',outcome='incomplete_evaluation_no_binary_grade')
    rows.append(row)
with (OUT/'hint_attempt_metrics.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
(OUT/'results/hint_attempt_metrics.json').write_text(json.dumps(rows,indent=2)+'\n')
base_session=rows[0]['session'];base=requests[base_session][0]['request'] if requests[base_session] else None
def strings(value):
    if isinstance(value,str):return [value]
    if isinstance(value,list):return [s for v in value for s in strings(v)]
    if isinstance(value,dict):return [s for v in value.values() for s in strings(v)]
    return []
comparisons=[];hint_entry=[]
for row in rows:
    recorded=requests[row['session']]
    item=dict(group=row['group'],first_request_available=bool(recorded))
    if recorded:
        request=recorded[0]['request']
        item.update(first_request_id=recorded[0]['request_id'],
            persistent_capability_marker_present=any('<persistent_capabilities>' in s for s in strings(request['messages'])))
        if base:
            item.update(system_messages_equal_NoHint=[m for m in request['messages'] if m['role']=='system']==[m for m in base['messages'] if m['role']=='system'],
                non_system_messages_equal_NoHint=[m for m in request['messages'] if m['role']!='system']==[m for m in base['messages'] if m['role']!='system'],
                tool_definitions_equal_NoHint=request.get('tools')==base.get('tools'))
    comparisons.append(item)
    for check in [p for p in progress if p['session']==row['session'] and p.get('hint')]:
        hint_file=OUT/'hints'/(row['group']+'_r1.md')
        hint_file.parent.mkdir(exist_ok=True)
        hint_file.write_text(check['hint']+'\n')
        appearances=[dict(request_id=r['request_id'],request_index=i) for i,r in enumerate(recorded,1)
            if any(check['hint'] in s for s in strings(r['request']['messages']))]
        hint_entry.append(dict(group=row['group'],check=check['check'],tool_count=check.get('tool_count'),
            hint=check['hint'],literal_hint_path=str(hint_file),words=len(check['hint'].split()),first_actual_student_request=appearances[0] if appearances else None,
            requests_containing_hint=len(appearances)))
(OUT/'results/hint_condition_validation.json').write_text(json.dumps(dict(initial_requests=comparisons,
    delivered_hint_actual_request_entry=hint_entry,scope='Actual logged text and tool comparisons; no common intermediate state or causal attribution.'),indent=2)+'\n')
print(json.dumps({'planned':len(rows),'attempted':len(attempts),'completed':sum(r['status']=='complete' for r in rows),
    'actual_teacher_checks':sum(r['server_teacher_checks'] for r in rows),'actual_delivered_hints':sum(r['delivered_hints'] for r in rows)}))
