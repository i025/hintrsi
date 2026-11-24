#!/usr/bin/env python3
"""Exercise one real Codex external-tool round trip without touching task files."""

import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from codex_cli_bridge import CodexRPCClient, NATIVE_ITEMS


async def main():
    started = time.monotonic()
    events = ROOT / "preflight/cli_tool_events.jsonl"
    result_path = ROOT / "preflight/cli_tool_result.json"
    event_queue = asyncio.Queue()

    def record(event):
        with events.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        if "method" in event:
            event_queue.put_nowait(event)

    client = CodexRPCClient(event_callback=record,
                            stderr_path=ROOT / "preflight/cli_tool_stderr.log", cwd="/tmp")
    result = {"model": "gpt-6.1-terra", "reasoning_effort": "low", "passed": False,
              "external_calls": [], "usage": None, "native_tools": []}
    try:
        await asyncio.wait_for(client.start(), 30)
        thread = await client.request("thread/start", {
            "model": "gpt-6.1-terra", "allowProviderModelFallback": False,
            "baseInstructions": "Test the external tool interface. Use only experiment_echo. "
                                "Do not inspect files or execute commands.",
            "config": {"model_reasoning_effort": "low"},
            "approvalPolicy": "never", "sandbox": "read-only", "environments": [],
            "cwd": "/tmp", "ephemeral": True,
            "dynamicTools": [{"type": "function", "name": "experiment_echo",
                              "description": "Return a string through the external executor.",
                              "inputSchema": {"type": "object", "properties": {
                                  "text": {"type": "string"}}, "required": ["text"],
                                  "additionalProperties": False}}],
        })
        result["thread_id"] = thread["thread"]["id"]
        await client.request("turn/start", {"threadId": result["thread_id"], "input": [{
            "type": "text", "text": "Call experiment_echo once with text CLI_BRIDGE_TEST, "
            "then reply with exactly the string returned by that tool."}]})
        final = []
        while True:
            event = await asyncio.wait_for(event_queue.get(), 90)
            method = event.get("method", "")
            params = event.get("params", {})
            item = params.get("item", {})
            if method == "item/tool/call":
                if params.get("tool") != "experiment_echo":
                    raise RuntimeError("Unexpected external tool: " + str(params.get("tool")))
                result["external_calls"].append(params)
                await client.respond(event["id"], {
                    "success": True,
                    "contentItems": [{"type": "inputText", "text": "SDK_TOOL_OK"}],
                })
            elif method in ("item/started", "item/completed") and item.get("type") in NATIVE_ITEMS:
                result["native_tools"].append(item.get("type"))
                raise RuntimeError("Codex attempted a native environment tool")
            elif method == "item/completed" and item.get("type") == "agentMessage":
                final.append(item.get("text", ""))
            elif method == "thread/tokenUsage/updated":
                result["usage"] = params.get("tokenUsage")
            elif method == "model/rerouted" and params.get("toModel") != result["model"]:
                raise RuntimeError("The service rerouted to a different model")
            elif method == "turn/completed":
                result["turn"] = params.get("turn", {})
                result["final"] = "\n".join(final)
                result["passed"] = (len(result["external_calls"]) == 1
                                    and result["final"].strip() == "SDK_TOOL_OK"
                                    and result["turn"].get("status") == "completed")
                break
        if not result["passed"]:
            raise RuntimeError("External tool round trip did not meet the acceptance criteria")
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        result["elapsed_seconds"] = time.monotonic() - started
        await client.close()
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
