"""Replay saved SDK decisions without executing task tools."""
import asyncio
import copy
import json
import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
sys.path.insert(0, str(ROOT / "source_parallel_12"))
from codex_cli_bridge import CodexBridge


async def main():
    saved = json.loads((OUT / "replay_cases.json").read_text())
    cases = [copy.deepcopy(case) for case in saved if case["label"] in (
        "saved_student_1", "readonly_student")]
    assert len(cases) == 2
    (OUT / "context_cases.json").write_text(json.dumps(cases, indent=2))
    bridge = CodexBridge(OUT / "real_context")
    semaphore = asyncio.Semaphore(6)
    results = []
    async def run(case):
        async with semaphore:
            started = time.monotonic()
            result = {key: value for key, value in case.items() if key != "body"}
            try:
                result["response"] = await asyncio.wait_for(bridge.chat(case["body"], route={
                    "session": "permissions-preflight-" + case["label"], "role": case["role"], "phase": "decision_replay"}), 360)
            except Exception as exc:
                result["error"] = repr(exc)
            result["elapsed_seconds"] = time.monotonic() - started
            results.append(result)
            (OUT / "context_results.json").write_text(json.dumps(results, indent=2))
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
