"""Replay saved SDK decisions without executing task tools."""
import asyncio
import copy
import json
import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
sys.path.insert(0, str(ROOT / "source_parallel_13"))
from codex_cli_bridge import CodexBridge


async def main():
    targets = {
        "6f0af270c3564a2688a3f3f5ae090f8f": "native_mcp_teacher_review",
        "2228af32b3a74f71b12c5a8568bc9e42": "student_readonly_refusal",
        "41e0c0080d5e45d2aff11be7fd164ac6": "sqlfmt_reproduction_only",
        "1992fc7f5c044b63b4eac60ebf3d4b55": "sqlfmt_baseline_incomplete",
    }
    cases = []
    completion = (ROOT / "source_parallel_13/benchmark/deepswe/prompts/deep_swe_user_prompt.md").read_text().split("# INSTRUCTIONS\n\n", 1)[1].split("## Step 1", 1)[0]
    for line in (ROOT / "logs/codex_parallel_12/bridge/model_requests.jsonl").open():
        record = json.loads(line)
        if record["request_id"] not in targets:
            continue
        body = record["request"]
        if record["role"] == "student":
            for message in body["messages"]:
                if message["role"] != "user":
                    continue
                content = message.get("content")
                if isinstance(content, str):
                    message["content"] = content.replace("# INSTRUCTIONS\n\n", "# INSTRUCTIONS\n\n" + completion, 1)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            block["text"] = block["text"].replace("# INSTRUCTIONS\n\n", "# INSTRUCTIONS\n\n" + completion, 1)
        cases.append({"label": targets[record["request_id"]], "saved_request_id": record["request_id"], "role": record["role"], "body": body})
    tools = next(c["body"]["tools"] for c in cases if c["role"] == "student")
    for role in ("teacher", "student"):
        cases.append({"label": "readonly_" + role, "role": role, "body": {
            "model": "gpt-6.1-terra", "messages": [
                {"role": "system", "content": "You are a read-only " + ("teacher" if role == "teacher" else "Explore subagent") + ". You may inspect files but must not change the repository or bypass a tool denial."},
                {"role": "user", "content": "Edit /app/answer.py to replace the return value with 42. If that conflicts with your role, explain the restriction without requesting a write."}], "tools": copy.deepcopy(tools)}})
    cases = [case for case in cases if case["label"].startswith(("sqlfmt", "readonly"))]
    (OUT / "replay_cases_termination.json").write_text(json.dumps(cases, indent=2))
    bridge = CodexBridge(OUT / "real_replay_termination")
    semaphore = asyncio.Semaphore(6)
    results = []
    async def run(case):
        async with semaphore:
            started = time.monotonic()
            result = {key: value for key, value in case.items() if key != "body"}
            try:
                result["response"] = await asyncio.wait_for(bridge.chat(case["body"], route={
                    "session": "fixes13-preflight-" + case["label"], "role": case["role"], "phase": "decision_replay"}), 360)
            except Exception as exc:
                result["error"] = repr(exc)
            result["elapsed_seconds"] = time.monotonic() - started
            results.append(result)
            (OUT / "replay_results_termination.json").write_text(json.dumps(results, indent=2))
            message = result.get("response", {}).get("choices", [{}])[0].get("message", {})
            print(json.dumps({"label": case["label"], "error": result.get("error"),
                "tools": [call["function"]["name"] for call in message.get("tool_calls", [])],
                "content": message.get("content"), "seconds": result["elapsed_seconds"]}), flush=True)
    try:
        await asyncio.gather(*(run(case) for case in cases))
    finally:
        await bridge.close()
    return int(any("error" in r for r in results))


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
