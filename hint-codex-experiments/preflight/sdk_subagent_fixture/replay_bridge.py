"""Replay the actual SDK subagent conversation without invoking a model."""
import asyncio
import copy
import json
import os
import sys
from pathlib import Path
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"]="True"
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
DATA=HERE/sys.argv[1] if len(sys.argv)>1 else HERE
sys.path[:0]=[str(ROOT/"source"),str(ROOT/"source/litellm_proxy"),str(ROOT/"tests")]
import streaming_fix
streaming_fix.apply()
from litellm.llms.anthropic.experimental_pass_through.adapters.transformation import LiteLLMAnthropicMessagesAdapter
from codex_cli_bridge import CodexBridge, DISABLED_FEATURES, default_command, _text
from test_codex_cli_bridge import FakeRPC

async def main():
    raw=[row["body"] for row in json.loads((DATA/"captured_requests.json").read_text())]
    adapter=LiteLLMAnthropicMessagesAdapter()
    requests=[adapter.translate_anthropic_to_openai(copy.deepcopy(body))[0] for body in raw]
    rpc=FakeRPC()
    bridge=CodexBridge(str(DATA/"bridge_replay_logs"),rpc=rpc)
    route={"session":"preflight-subagent-replay","role":"student","phase":"solve"}
    def tool(current,call_id,request_id,name):
        current.emit("item/tool/call",{"threadId":current.thread,"turnId":current.turn,
            "callId":call_id,"tool":name,"arguments":{"file_path":"/app/fixture_child.txt"}},request_id)
    def start(current):
        if current.thread=="thread-1":
            tool(current,"fixture-parent-read",100,"Read")
        else:
            tool(current,"fixture-child-read",102,"Read")
    rpc.on_turn=start
    def response(current,request_id):
        if request_id==100:
            tool(current,"fixture-parent-agent",101,"Agent")
        elif request_id==101:
            if sum(method=="thread/start" for method,_ in current.calls)==1:
                tool(current,"fixture-child-read",102,"Read")
            else:
                old_thread,old_turn=current.thread,current.turn
                current.thread,current.turn="thread-1","turn-1"
                current.finish("PARENT_FINAL_MARKER")
                current.thread,current.turn=old_thread,old_turn
        elif request_id==102:
            current.finish("CHILD_SUMMARY_MARKER")
    rpc.on_response=response
    events=[]
    error=None
    parent_state=None
    child_state=None
    parent_inputs_before_child=None
    parent_unchanged_during_child=True
    agent_pending_during_child=True
    try:
        for index,request in enumerate(requests):
            answer=await asyncio.wait_for(bridge.chat(request,route=route),timeout=5)
            if index==0: parent_state=bridge.by_call["fixture-parent-read"]
            if index==2: child_state=bridge.by_call["fixture-child-read"]
            state=child_state if index in (2,3) else parent_state
            if index==1:
                parent_inputs_before_child=copy.deepcopy(parent_state.user_inputs)
            if index in (2,3):
                parent_unchanged_during_child &= parent_state.user_inputs==parent_inputs_before_child
                agent_pending_during_child &= not parent_state.pending["fixture-parent-agent"].completed
            events.append({"request":index+1,"thread":state.thread_id,
                           "finish_reason":answer["choices"][0]["finish_reason"]})
    except Exception as exc:
        error={"type":type(exc).__name__,"message":str(exc)}
    responses={str(request_id):result for request_id,result in rpc.responses}
    parent_result=responses.get("101",{})
    parent_result_text=json.dumps(parent_result)
    injected=[params for method,params in rpc.calls if method=="thread/inject_items"]
    injected_text=json.dumps(injected)
    inherited_context=("ORIGINAL_PARENT_FIXTURE_CONTENT" in injected_text
                       and "fixture-parent-read" in injected_text
                       and "fixture-parent-agent" in injected_text)
    fork_fixture=json.loads((DATA/"result.json").read_text()).get("mode")=="fork"
    native_disabled=all("features."+name+"=false" in default_command() for name in DISABLED_FEATURES)
    result={"kind":"offline_actual_sdk_subagent_bridge_replay","real_model_calls":0,
        "synthetic_model_usage":True,"sdk_fixture_passed":True,
        "parent_child_separate_states":child_state is not None and child_state is not parent_state,
        "parent_inputs_unchanged_during_child":parent_unchanged_during_child,
        "parent_agent_pending_until_real_summary":agent_pending_during_child,
        "parent_summary_delivery_count":sum(request_id==101 for request_id,_ in rpc.responses),
        "inherited_context_injected":inherited_context,
        "injected_items":injected,"native_tools_disabled":native_disabled,
        "thread_starts":sum(method=="thread/start" for method,_ in rpc.calls),
        "rpc_responses":responses,"request_outcomes":events,"error":error,
        "parent_agent_received_placeholder":"Fork started" in parent_result_text,
        "parent_agent_received_final_summary":"CHILD_SUMMARY_MARKER" in parent_result_text,
        "bridge_stopped":bridge.stopped,"bridge_stop_reason":bridge.stop_reason}
    result["passed"]=(result["parent_child_separate_states"] and result["thread_starts"]==2
        and result["parent_agent_received_final_summary"] and not result["parent_agent_received_placeholder"]
        and result["parent_inputs_unchanged_during_child"] and result["parent_agent_pending_until_real_summary"]
        and result["parent_summary_delivery_count"]==1 and (inherited_context or not fork_fixture) and native_disabled
        and len(events)==5 and not error and not bridge.stopped)
    (DATA/"bridge_replay_result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    sdk=json.loads((DATA/"result.json").read_text())
    sdk["sdk_execution_passed"]=sdk.get("sdk_execution_passed",sdk["passed"])
    sdk["bridge_replay_passed"]=result["passed"]
    sdk["passed"]=sdk["sdk_execution_passed"] and sdk["bridge_replay_passed"]
    (DATA/"result.json").write_text(json.dumps(sdk,ensure_ascii=False,indent=2)+"\n")
    await bridge.close()
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    asyncio.run(main())
