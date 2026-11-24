"""Replay candidate SSE through the installed LiteLLM adapter without network access."""

import ast
import asyncio
import copy
import importlib.metadata
import json
import os
import socket
import sys
from pathlib import Path

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
os.environ["LITELLM_TELEMETRY"] = "False"
network_attempts = []


def no_connect(self, address):
    network_attempts.append(str(address))
    raise RuntimeError("Network disabled for offline SSE replay")


socket.socket.connect = no_connect
socket.socket.connect_ex = no_connect
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
ORIGINAL = ROOT / "source_parallel_08_static/codex_cli_bridge.py"
CANDIDATE = OUT / "codex_cli_bridge.py"
sys.path.insert(0, str(ROOT / "source_parallel_08_static/litellm_proxy"))

from litellm.types.utils import ModelResponseStream
from litellm.llms.anthropic.experimental_pass_through.adapters.streaming_iterator import AnthropicStreamWrapper
import streaming_fix

streaming_fix.apply()


def load_sse(path):
    node = next(node for node in ast.parse(path.read_text()).body
                if isinstance(node, ast.AsyncFunctionDef) and node.name == "_sse")
    namespace = {"json": json}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["_sse"]


def response(content=None, tools=(), finish=None):
    return {"id": "fixture-response", "created": 1, "model": "gpt-6.1-terra",
            "object": "chat.completion", "choices": [{"index": 0,
                "message": {"role": "assistant", "content": content, "tool_calls": list(tools)},
                "finish_reason": finish or ("tool_calls" if tools else "stop")}],
            "usage": {"prompt_tokens": 101, "completion_tokens": 7, "total_tokens": 108,
                "prompt_tokens_details": {"cached_tokens": 41},
                "completion_tokens_details": {"reasoning_tokens": 3}}}


def tool(index, name, arguments):
    return {"id": f"fixture-tool-{index}", "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)}}


async def convert(sse, value):
    chunks, packets = [], []
    async def models():
        async for packet in sse(value):
            packets.append(packet)
            for line in packet.splitlines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    chunk = json.loads(line[6:])
                    chunks.append(chunk)
                    yield ModelResponseStream(**chunk)
    events = [event async for event in AnthropicStreamWrapper(models(), model=value["model"])]
    return chunks, packets, events


def assemble(events):
    blocks = {}
    for event in events:
        kind = event["type"]
        if kind == "content_block_start":
            blocks[event["index"]] = {"block": event["content_block"], "text": "", "arguments": "", "closed": False}
        elif kind == "content_block_delta":
            item = blocks[event["index"]]
            item["text"] += event["delta"].get("text", "")
            item["arguments"] += event["delta"].get("partial_json", "")
        elif kind == "content_block_stop":
            blocks[event["index"]]["closed"] = True
    return list(blocks.values())


async def verify_case(name, value):
    before = copy.deepcopy(value)
    chunks, packets, events = await convert(load_sse(CANDIDATE), value)
    assert value == before
    assert packets[-1] == "data: [DONE]\n\n"
    message = value["choices"][0]["message"]
    calls = message["tool_calls"]
    assert chunks[0]["choices"][0]["delta"]["role"] == "assistant"
    assert "tool_calls" not in chunks[0]["choices"][0]["delta"]
    tool_chunks = [row["choices"][0]["delta"]["tool_calls"] for row in chunks
                   if "tool_calls" in row["choices"][0]["delta"]]
    assert tool_chunks == [[{"index": index, **call}] for index, call in enumerate(calls)]
    assert chunks[-1]["usage"] == value["usage"]
    assert chunks[-1]["choices"][0]["finish_reason"] == value["choices"][0]["finish_reason"]
    assert all(row["id"] == value["id"] and row["created"] == value["created"]
               and row["model"] == value["model"] for row in chunks)
    blocks = assemble(events)
    recovered = [row for row in blocks if row["block"]["type"] == "tool_use"]
    assert len(recovered) == len(calls)
    for expected, actual in zip(calls, recovered):
        assert actual["block"]["id"] == expected["id"]
        assert actual["block"]["name"] == expected["function"]["name"]
        assert actual["arguments"] == expected["function"]["arguments"]
        assert json.loads(actual["arguments"]) == json.loads(expected["function"]["arguments"])
        assert actual["closed"]
    assert "".join(row["text"] for row in blocks if row["block"]["type"] == "text") == (message["content"] or "")
    all_closed = all(row["closed"] for row in blocks)
    if not all_closed:
        assert not calls and not message["content"]
        _, _, original_events = await convert(load_sse(ORIGINAL), value)
        assert blocks == assemble(original_events)
    final = next(event for event in events if event["type"] == "message_delta")
    finish = {"stop": "end_turn", "tool_calls": "tool_use", "length": "max_tokens"}[value["choices"][0]["finish_reason"]]
    assert final["delta"]["stop_reason"] == finish
    assert final["usage"]["input_tokens"] == value["usage"]["prompt_tokens"]
    assert final["usage"]["output_tokens"] == value["usage"]["completion_tokens"]
    assert events[-1]["type"] == "message_stop"
    return {"case": name, "passed": True, "tools": len(calls), "chunks": len(chunks),
            "body_exact": True, "tool_ids_names_indices_arguments_exact": True,
            "sse_usage_exact": True, "anthropic_input_output_usage_exact": True,
            "finish_reason": finish, "all_blocks_closed": all_closed,
            "empty_text_closure_matches_original": not all_closed}


async def main():
    frozen_before = ORIGINAL.read_bytes()
    tools = [tool(0, "Read", {"file_path": "/app/input.py"}),
             tool(1, "Edit", {"file_path": "/app/input.py", "old_string": "before", "new_string": "after"}),
             tool(2, "Bash", {"command": "python -m unittest", "timeout": 30000})]
    escaped = [tool(0, "Write", {"file_path": "/app/示例.txt", "content": "引号\"、反斜杠\\、换行\n制表\temoji🙂"}),
               tool(1, "Bash", {"command": "printf '%s\\n' 'a\"b'", "description": "Unicode café 🙂"}),
               tool(2, "Read", {"file_path": "/app/δ.json", "nested": {"list": [None, True, 3.5]}})]
    fixtures = [("plain_text", response("A complete response.")),
                ("empty_text", response("")),
                ("single_tool", response(tools=tools[:1])),
                ("three_tools", response(tools=tools)),
                ("body_and_three_tools", response("Inspecting three files.", tools)),
                ("unicode_and_escaped_arguments", response("检查：café 🙂\n", escaped)),
                ("length_finish", response("Truncated response", finish="length"))]
    results = [await verify_case(name, value) for name, value in fixtures]
    _, _, old_events = await convert(load_sse(ORIGINAL), fixtures[4][1])
    old_tools = [row for row in assemble(old_events) if row["block"]["type"] == "tool_use"]
    assert len(old_tools) == 1
    try:
        json.loads(old_tools[0]["arguments"])
    except json.JSONDecodeError:
        reproduced = True
    else:
        reproduced = False
    assert reproduced
    assert ORIGINAL.read_bytes() == frozen_before
    assert not network_attempts
    result = {"passed": True, "litellm_version": importlib.metadata.version("litellm"),
              "streaming_fix": str(ROOT / "source_parallel_08_static/litellm_proxy/streaming_fix.py"),
              "model_calls": 0, "network_attempts": network_attempts,
              "candidate_deployed": False, "frozen_source_unchanged": True,
              "original_three_tool_corruption_reproduced": reproduced,
              "unchanged_limitation": "The existing streaming adapter leaves an empty text-only response block unclosed; candidate and original match for that extra control. Nonempty text and tool cases close all blocks.",
              "cases": results}
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
