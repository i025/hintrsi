"""Check real-model use of an earlier external observation; not a benchmark task."""
import asyncio
import copy
import json
import sys
import time
import uuid
from pathlib import Path

OUT = Path(__file__).parent / "real_memory"
sys.path.insert(0, str(Path(__file__).parent))
from codex_exec_bridge import CodexExecBridge, MODEL


async def main():
    OUT.mkdir()
    marker = "OBSERVATION_" + uuid.uuid4().hex[:12]
    fixture = OUT / "observation.txt"
    fixture.write_text(marker + "\n")
    tools = [{"type": "function", "function": {
        "name": "Read", "description": "Read a file through the external executor.",
        "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}},
                       "required": ["file_path"], "additionalProperties": False},
    }}]
    body = {"model": MODEL, "messages": [
        {"role": "system", "content": "Use only actual observations. Request Read for the supplied file, then return its marker exactly, with no extra words or further tools."},
        {"role": "user", "content": "Read /app/observation.txt and return the marker stored in it."},
    ], "tools": tools}
    bridge = CodexExecBridge(OUT / "bridge")
    route = {"session": "exec-real-memory-preflight", "role": "student", "phase": "memory"}
    result = {"passed": False, "started_at": time.time(), "formal_task": False,
              "max_bridge_calls": 3, "bridge_calls": 0, "real_model": MODEL,
              "ofox_calls": 0, "external_executor": "Fixture Read; real SDK execution is a separate gate."}
    try:
        result["bridge_calls"] += 1
        first = await asyncio.wait_for(bridge.chat(body, route=route), 180)
        calls = first["choices"][0]["message"].get("tool_calls", [])
        assert len(calls) == 1 and calls[0]["function"]["name"] == "Read", first
        assert json.loads(calls[0]["function"]["arguments"]) == {"file_path": "/app/observation.txt"}
        assert marker not in json.dumps(body)
        follow = copy.deepcopy(body)
        follow["messages"] += [first["choices"][0]["message"], {
            "role": "tool", "tool_call_id": calls[0]["id"], "content": fixture.read_text(),
        }]
        result["bridge_calls"] += 1
        second = await asyncio.wait_for(bridge.chat(follow, route=route), 180)
        assert second["choices"][0]["message"]["content"].strip() == marker, second
        assert second["choices"][0]["finish_reason"] == "stop"
        replacement_marker = "SUMMARY_" + uuid.uuid4().hex[:12]
        compacted = {"model": MODEL, "messages": [
            {"role": "system", "content": "Return the marker from the current conversation summary exactly. Do not call tools."},
            {"role": "user", "content": "Current conversation summary: the required marker is " + replacement_marker},
        ], "tools": []}
        assert marker not in json.dumps(compacted)
        result["bridge_calls"] += 1
        third = await asyncio.wait_for(bridge.chat(compacted, route=route), 180)
        assert third["choices"][0]["message"]["content"].strip() == replacement_marker, third
        responses = [json.loads(line) for line in (OUT / "bridge/model_responses.jsonl").read_text().splitlines()]
        assert len({row["thread_id"] for row in responses}) == 3
        result.update(passed=True, prior_tool_observation_used=True,
                      replacement_history_used_without_old_context=True,
                      native_threads=[row["thread_id"] for row in responses],
                      returned_marker=marker, replacement_marker=replacement_marker)
    except Exception as exc:
        result["error"] = repr(exc)
    finally:
        await bridge.close()
        ledger = OUT / "bridge/token_usage.jsonl"
        rows = [json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []
        result.update(finished_at=time.time(), elapsed_seconds=time.time() - result["started_at"],
                      reported_model_tokens=sum(row["delta"]["totalTokens"] for row in rows),
                      usage_events=len(rows), usage_scope="Reported CLI usage only; implementation/chat activity excluded.")
        (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
