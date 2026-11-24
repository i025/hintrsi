"""Resume completed saved teacher threads without starting an inference turn."""
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT=Path('/srv/lab-disks/disk2/users/xymo/hint-codex-experiments')
OUT=ROOT/'preflight/parallel_08_teacher_native_resume_verified'
sys.path.insert(0,str(ROOT/'source_parallel_08'))
from codex_cli_bridge import CodexRPCClient, MODEL

async def main():
    OUT.mkdir()
    saved=json.loads((ROOT/'logs/bridge/bridge_recovery.json').read_text())
    (OUT/'original_bridge_recovery.json').write_text(json.dumps(saved,indent=2)+'\n')
    events=[]
    rpc=CodexRPCClient(event_callback=events.append,stderr_path=OUT/'stderr.log',cwd=ROOT/'logs/bridge')
    sent_methods=[]
    original_request=rpc.request
    async def record_request(method, params=None):
        sent_methods.append(method)
        return await original_request(method,params)
    rpc.request=record_request
    result={'started_at_unix':time.time(),'real_model_calls':0,'threads':[],'passed':False}
    try:
        await asyncio.wait_for(rpc.start(),30)
        for row in saved:
            state=row['state']
            assert state['role']=='teacher' and not state['active']
            assert all(item['completed'] for item in state['pending'])
            value=await asyncio.wait_for(rpc.request('thread/resume',{'threadId':state['thread_id'],'excludeTurns':True}),30)
            assert value['thread']['id']==state['thread_id']
            assert value['model']==MODEL and value['reasoningEffort']=='low'
            turns=await asyncio.wait_for(rpc.request('thread/turns/list',{'threadId':state['thread_id'],'limit':1,'sortDirection':'desc'}),30)
            latest=turns['data'][0]
            assert latest['status']=='completed',latest['status']
            result['threads'].append({'session':state['session_id'],'thread_id':state['thread_id'],'same_native_thread':True,'model':value['model'],'reasoning_effort':value['reasoningEffort'],'latest_turn_status':latest['status'],'latest_turn_id':latest['id'],'saved_turn_id':state['turn_id'],'path':value['thread'].get('path'),'sdk_tools':len(state['tool_specs'])})
        assert 'turn/start' not in sent_methods
        assert not any(x.get('method')=='turn/started' for x in events)
        saved_usage={row['state']['thread_id']:row['state']['usage_total'] for row in saved}
        historical=[x['params'] for x in events if x.get('method')=='thread/tokenUsage/updated']
        for event in historical:
            assert event['tokenUsage']['total']==saved_usage[event['threadId']]
        result['historical_usage_snapshots']=len(historical)
        result['historical_usage_unchanged']=True
        result['passed']=True
    finally:
        await rpc.close()
        result['finished_at_unix']=time.time()
        result['sent_rpc_methods']=sent_methods
        result['event_methods']=sorted({x.get('method','') for x in events})
        (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)

if __name__=='__main__':asyncio.run(main())
