"""Replay real SDK compacted requests through the actual converter/session router."""
import asyncio,copy,json,os,sys,tempfile
from pathlib import Path
os.environ['LITELLM_LOCAL_MODEL_COST_MAP']='True'
os.environ['TELEMETRY']='False'
ROOT=Path('/srv/lab-disks/disk2/users/xymo/hint-codex-experiments')
OUT=ROOT/'preflight/parallel_09_compaction_audit'
sys.path.insert(0,str(ROOT/'source_parallel_09'));sys.path.insert(0,str(ROOT/'source_parallel_09/litellm_proxy'))
import streaming_fix
streaming_fix.apply()
from litellm.llms.anthropic.experimental_pass_through.adapters.transformation import LiteLLMAnthropicMessagesAdapter
from codex_cli_bridge import CodexBridge,CodexBridgeError,_input
rows=json.loads((OUT/'attempt_02/requests.json').read_text())
initial=LiteLLMAnthropicMessagesAdapter().translate_anthropic_to_openai(copy.deepcopy(rows[0]['body']))[0]
compacted=LiteLLMAnthropicMessagesAdapter().translate_anthropic_to_openai(copy.deepcopy(rows[-1]['body']))[0]
results=[]
async def main():
 for role,phase in [('student','solve'),('teacher','generate'),('teacher','review_r1')]:
  with tempfile.TemporaryDirectory() as directory:
   bridge=CodexBridge(directory)
   route={'session':'same-sdk','role':role,'phase':'solve' if role=='student' else 'generate'}
   state=bridge.resolve_session(initial,{},route)
   state.user_inputs=[_input(m.get('content')) for m in initial['messages'] if m['role']=='user']
   state.thread_id='original-native-thread';state.tool_specs=initial['tools']
   route['phase']=phase
   row={'role':role,'continued_phase':phase,'real_model_calls':0,'network_calls':0}
   try:
    next_state=bridge.resolve_session(compacted,{},route)
    row.update(same_native_state=next_state is state,new_state_thread_id=next_state.thread_id,session_count=len(bridge.sessions))
   except CodexBridgeError as exc:row.update(error=str(exc),error_code=exc.code)
   row['global_stop']=bridge.stopped;results.append(row)
 result={'real_model_calls':0,'network_calls':0,'actual_sdk_session_unchanged':True,'initial_wire_messages':len(initial['messages']),'compacted_wire_messages':len(compacted['messages']),'tool_specs_equal':initial['tools']==compacted['tools'],'cases':results,'trigger_tested':'manual SDK /compact, not an observed automatic production compact'}
 (OUT/'bridge_replay.json').write_text(json.dumps(result,indent=2)+'\n')
 (OUT/'compacted_wire.json').write_text(json.dumps(compacted,indent=2)+'\n')
 print(json.dumps(result,indent=2))
asyncio.run(main())
