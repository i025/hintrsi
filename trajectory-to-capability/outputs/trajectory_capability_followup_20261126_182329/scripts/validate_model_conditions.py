"""Summarize actual logged model settings and knowledge entry, without fingerprints."""
import datetime
import json
from collections import Counter
from pathlib import Path

OUT=Path.cwd()/'outputs/trajectory_capability_followup_20261126_182329'
counts=Counter();mismatches=[];first={}
for path in (OUT/'logs').glob('*/model_requests.jsonl'):
    for line in path.open():
        d=json.loads(line)
        first.setdefault(d['session'],d)
        model=d.get('actual_model',d.get('model'))
        effort=d.get('reasoning_effort')
        counts[(model,effort)]+=1
        if (model,effort)!=('gpt-6.1-terra','low'):
            mismatches.append({'ledger':str(path),'request_id':d.get('request_id'),'session':d.get('session'),'model':model,'effort':effort})
rows=json.loads((OUT/'results/attempt_metrics.json').read_text())
checks=[{k:r[k] for k in ['stage','task','group','status','model_requests','capability_in_actual_prompt','capability_in_first_bridge_request','notes']} for r in rows]
def system_text(request):
    blocks=[]
    for message in request['messages']:
        if message['role']!='system':continue
        content=message['content']
        if isinstance(content,str):blocks.append(content)
        else:blocks.extend(b['text'] for b in content if b.get('type')=='text')
    return '\n'.join(blocks)
matched=[]
for stage,task in sorted({(r['stage'],r['task']) for r in rows}):
    task_rows=[r for r in rows if r['stage']==stage and r['task']==task]
    base_row=next((r for r in task_rows if r['group']=='B0'),None) or next((r for r in rows if r['stage']=='test' and r['task']==task and r['group']=='B0'),None) or task_rows[0]
    base=first.get(base_row['session'],{}).get('request')
    comparisons=[]
    for r in task_rows:
        logged=first.get(r['session']);request=logged.get('request') if logged else None
        entry={'group':r['group'],'session':r['session'],'first_request_id':logged.get('request_id') if logged else None}
        if request:
            names=[t.get('function',{}).get('name') for t in request.get('tools',[])]
            entry['tool_names']=names;entry['native_sdk_Skill_in_tools']='Skill' in names
        if base and request:
            text=system_text(request)
            if r['group']!='B0':text=text.replace((OUT/'knowledge'/f"{r['group']}.md").read_text().strip(),'')
            entry.update(system_text_excluding_exact_capability_equals_B0=text.strip()==(system_text(base).replace((OUT/'knowledge'/f"{base_row['group']}.md").read_text().strip(),'') if base_row['group']!='B0' else system_text(base)).strip(),
                exact_tool_definitions_equal_B0=request.get('tools')==base.get('tools'),
                exact_non_system_messages_equal_B0=[m for m in request['messages'] if m['role']!='system']==[m for m in base['messages'] if m['role']!='system'])
        comparisons.append(entry)
    matched.append({'stage':stage,'task':task,'reference_group':base_row['group'],'reference_stage':base_row['stage'],'reference_first_request_available':bool(base),'comparisons':comparisons})
sdk_ids=[r['sdk_session_id'] for r in rows if r.get('sdk_session_id')]
record={'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'logged_request_conditions':[{'model':m,'effort':e,'requests':n} for (m,e),n in counts.items()],
    'condition_mismatches':mismatches,'actual_prompt_checks':checks,'matched_first_request_comparisons':matched,
    'core_SDK_session_IDs':sdk_ids,'repeated_core_SDK_session_IDs':{v:sdk_ids.count(v) for v in set(sdk_ids) if sdk_ids.count(v)>1},
    'scope':'Recorded primary bridge and native visual audit requests; missing fields are reported, not inferred. Content checks compare actual plain text directly; no hash/signature system.'}
path=OUT/'results/model_condition_validation.json'
path.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'request_conditions':record['logged_request_conditions'],'mismatches':len(mismatches)}))
