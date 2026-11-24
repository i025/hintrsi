"""Replay captured real SDK requests through the actual adapter and an offline bridge."""
import asyncio
import copy
import json
import os
import sys
from pathlib import Path

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "source"), str(ROOT / "source" / "litellm_proxy"), str(ROOT / "tests")]
import streaming_fix
streaming_fix.apply()
from litellm.llms.anthropic.experimental_pass_through.adapters.transformation import LiteLLMAnthropicMessagesAdapter
from codex_cli_bridge import CodexBridge, _text
from test_codex_cli_bridge import FakeRPC

MARKER = "TEACHER_HINT_MARKER_7B93"

async def main():
    captured = json.loads((HERE / "captured_requests.json").read_text())
    raw = [entry["body"] for entry in captured]
    adapter = LiteLLMAnthropicMessagesAdapter()
    requests = [adapter.translate_anthropic_to_openai(copy.deepcopy(body))[0] for body in raw]
    tool_uses = [block for message in raw[1]["messages"] if message["role"] == "assistant"
                 for block in message["content"] if block["type"] == "tool_use"]
    expected = {message["tool_call_id"]: _text(message["content"])
                for message in requests[1]["messages"] if message["role"] == "tool"}
    rpc = FakeRPC()
    bridge = CodexBridge(str(HERE / "bridge_replay_logs"), rpc=rpc)
    route = {"session": "preflight-hook-replay", "role": "student", "phase": "solve"}
    def start(current):
        for index, tool in enumerate(tool_uses):
            current.tool(call_id=tool["id"], request_id=100+index, arguments=tool["input"])
    rpc.on_turn = start
    first = await bridge.chat(requests[0], route=route)
    assert len(first["choices"][0]["message"]["tool_calls"]) == 20
    def responded(current, request_id):
        if len(current.responses) == 20:
            current.finish("Offline hook replay completed")
    rpc.on_response = responded
    await bridge.chat(requests[1], route=route)
    before_replay = json.dumps(rpc.calls) + json.dumps(rpc.responses)
    assert before_replay.count(MARKER) == 1, "Guidance was lost or duplicated"
    id_to_call = {100+index: tool["id"] for index, tool in enumerate(tool_uses)}
    actual = {id_to_call[request_id]: result["contentItems"][0]["text"]
              for request_id, result in rpc.responses}
    assert actual == expected, "Original tool result content changed"
    assert len(actual) == 20
    assert all(result["success"] for _, result in rpc.responses)
    await bridge.chat(requests[1], route=route)
    after_replay = json.dumps(rpc.calls) + json.dumps(rpc.responses)
    assert after_replay.count(MARKER) == 1, "Historical replay delivered guidance again"
    assert len(rpc.responses) == 20, "Historical replay repeated tool responses"
    thread_starts = sum(method == "thread/start" for method, _ in rpc.calls)
    turn_starts = sum(method == "turn/start" for method, _ in rpc.calls)
    steering = [params for method, params in rpc.calls if method == "turn/steer"]
    assert thread_starts == turn_starts == len(steering) == 1
    assert requests[0]["messages"][0]["role"] == "system"
    assert requests[0]["messages"][0]["content"] == requests[1]["messages"][0]["content"]
    result = {
        "kind": "offline_actual_sdk_wire_bridge_replay", "passed": True,
        "real_model_calls": 0, "synthetic_model_usage": True,
        "captured_sdk_requests": len(raw), "raw_roles": [[m["role"] for m in b["messages"]] for b in raw],
        "translated_roles": [[m["role"] for m in b["messages"]] for b in requests],
        "top_level_system_preserved": True, "inline_system_preserved_as_user_in_place": True,
        "original_tool_results_preserved": len(actual), "thread_starts": thread_starts,
        "turn_starts": turn_starts, "guidance_steers": len(steering),
        "guidance_delivery_count": after_replay.count(MARKER),
        "historical_replay_duplicate_results": len(rpc.responses)-20,
    }
    await bridge.close()
    (HERE / "bridge_replay_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    sdk = json.loads((HERE / "result.json").read_text())
    sdk["sdk_hook_passed"] = sdk.get("sdk_hook_passed", sdk["passed"])
    sdk["bridge_replay_passed"] = result["passed"]
    sdk["passed"] = sdk["sdk_hook_passed"] and sdk["bridge_replay_passed"]
    (HERE / "result.json").write_text(json.dumps(sdk, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
