"""Observe response-loss retry semantics without a network or model."""
import asyncio,json,sys,tempfile
from pathlib import Path
ROOT=Path('/srv/lab-disks/disk2/users/xymo/hint-codex-experiments')
OUT=ROOT/'preflight/parallel_09_concurrency_audit'
sys.path.insert(0,str(OUT))
from test_concurrency import CodexBridge,InterleavedRPC,request

async def main():
    with tempfile.TemporaryDirectory() as directory:
        rpc=InterleavedRPC();bridge=CodexBridge(directory,rpc=rpc)
        body=request('SDK request whose HTTP tool response is lost')
        route={'session':'lost-response-lane0','role':'student','phase':'solve'}
        first=await bridge.chat(body,route=route)
        original_tools=first['choices'][0]['message']['tool_calls']
        state=next(iter(bridge.sessions.values()))
        # The SDK never receives first; its retry therefore has unchanged history.
        retry=asyncio.create_task(bridge.chat(body,route=route))
        await asyncio.sleep(.05)
        observed={'limitation_reproduced':not retry.done(),'first_tool_count':len(original_tools),
            'unchanged_sdk_retry_waiting':not retry.done(),'native_turn_active':state.active,
            'ready_calls':list(state.ready),'pending_served':[vars(tool) for tool in state.pending.values()],
            'rpc_tool_results_received':len(rpc.responses),'new_native_turns':sum(method=='turn/start' for method,_ in rpc.calls),
            'bridge_stopped':bridge.stopped,'real_model_calls':0,'network_calls':0,
            'scope':'Synthetic lost HTTP response after bridge marked calls served; no production packet loss claimed.'}
        assert observed['limitation_reproduced'] and not observed['ready_calls']
        assert all(tool['served'] and not tool['completed'] for tool in observed['pending_served'])
        assert observed['rpc_tool_results_received']==0
        retry.cancel();await asyncio.gather(retry,return_exceptions=True);await bridge.close()
        (OUT/'lost_response_retry.json').write_text(json.dumps(observed,indent=2)+'\n')
        print(json.dumps(observed,indent=2))

asyncio.run(main())
