#!/usr/bin/env python3
"""Exercise the unchanged 20-tool SDK hook with the real local teacher service."""

import argparse
import json
import time
import urllib.request

import docker

from probe_sdk_bridge import ROOT, SOURCE, PYTHON, copy_file, put_file, status
from constant_zhy import render_proxy_config

SESSION = "preflight-online-real"
TASK = "toy-independent-default-calls"
NAME = "codex-sdk-online-real-preflight"
OUT = ROOT / "preflight/sdk_online_real"
PROBLEM = (
    "The remember helper appends an item to a supplied list and returns it. Calls "
    "without a supplied list must start independent collections. The current helper "
    "unexpectedly carries an earlier item into a later independent call. Preserve "
    "mutation of an explicitly supplied list."
)
HINT = "Check repeated independent calls and the lifetime of state used by default."
GOLDEN_DIFF = (
    "--- a/remember.py\n+++ b/remember.py\n@@ -1,3 +1,5 @@\n"
    "-def remember(item, items=[]):\n+def remember(item, items=None):\n"
    "+    if items is None:\n+        items = []\n"
    "     items.append(item)\n     return items\n"
)
FILES = [f"/app/evidence/read_{index:02d}.txt" for index in range(1, 21)]
PROMPT = (
    "Run a protocol compatibility check on a tiny local project, not a benchmark "
    "attempt. First issue exactly one Read tool call for each of these 20 files: "
    + ", ".join(FILES) + ". Each must be a separate Read call; parallel calls are "
    "allowed. Do not use any other tool, delegate, modify files, or solve the toy "
    "problem. After all 20 responses have returned, report ONLINE_GATE_COMPLETE, "
    "the number of distinct evidence tags seen, and whether teacher guidance "
    "arrived. If guidance arrived, quote its first sentence once under "
    "GUIDANCE_RECEIVED. Otherwise report GUIDANCE_ABSENT. Stop after that report."
)
NATIVE_ITEMS = {
    "commandExecution", "fileChange", "webSearch", "imageView", "mcpToolCall",
    "collabAgentToolCall", "subAgentActivity",
}


def service(path, payload=None):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(
        "http://127.0.0.1:8766/experiment/" + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with opener.open(request, timeout=10) as response:
        return json.load(response)


def records(filename, prefix=SESSION):
    path = ROOT / "logs/bridge" / filename
    rows = [json.loads(line) for line in path.open()] if path.exists() else []
    return [row for row in rows if row.get("session", "").startswith(prefix)]


def occurrences(value, needle):
    if isinstance(value, str):
        return value.count(needle)
    if isinstance(value, list):
        return sum(occurrences(item, needle) for item in value)
    if isinstance(value, dict):
        return sum(occurrences(item, needle) for item in value.values())
    return 0


def save_evidence(result):
    data = {}
    for name in ("model_requests.jsonl", "model_responses.jsonl", "codex_events.jsonl", "token_usage.jsonl"):
        data[name] = records(name)
        (OUT / name).write_text("".join(json.dumps(row) + "\n" for row in data[name]))
    progress_path = ROOT / "logs/progress/progress.jsonl"
    checks = [json.loads(line) for line in progress_path.open()] if progress_path.exists() else []
    checks = [row for row in checks if row.get("session") == SESSION]
    (OUT / "progress_checks.json").write_text(json.dumps(checks, indent=2) + "\n")
    result["progress_checks"] = checks
    result["native_tool_event_count"] = sum(
        row["event"].get("params", {}).get("item", {}).get("type") in NATIVE_ITEMS
        or any(row["event"].get("method", "").startswith("item/" + name + "/") for name in NATIVE_ITEMS)
        for row in data["codex_events.jsonl"]
    )
    final_requests = [row for row in data["model_requests.jsonl"] if row["session"] == SESSION]
    final_messages = final_requests[-1]["request"]["messages"] if final_requests else []
    result["delivery"] = []
    for check in checks:
        hint = check.get("hint") or ""
        result["delivery"].append({
            "check": check["check"], "tool_count": check["tool_count"],
            "decision": check["decision"], "word_count": len(hint.split()),
            "contains_chinese": any("\u4e00" <= char <= "\u9fff" for char in hint),
            "hint_occurrences_in_final_request": occurrences(final_messages, hint) if hint else 0,
        })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.run:
        print(json.dumps({"prepared": True, "session": SESSION, "real_model_calls": 0,
                          "expected_main_reads": 20, "production_interval": 20,
                          "production_max_checks": 3, "unforced_teacher_decision": True}))
        return
    before = status()
    assert not before["stopped"], before["stop_reason"]
    assert not any(row["session"] == SESSION for row in before["sessions"]), "Use a fresh fixture session"
    OUT.mkdir(parents=True)
    result = {"session": SESSION, "purpose": "20-Read online-hook compatibility fixture, no benchmark score",
              "started_at_unix": time.time(), "status": "incomplete"}
    client = docker.DockerClient(base_url="unix://" + str(ROOT / "vm/docker.sock"), timeout=1200)
    image = client.images.get(json.loads((ROOT / "preflight/sdk_fixture_container.json").read_text())["image"])
    env = {item.split("=", 1)[0]: "experiment-local" for item in image.attrs["Config"]["Env"]
           if any(word in item.split("=", 1)[0].upper() for word in
                  ("KEY", "TOKEN", "SECRET", "PASSWORD", "ANTHROPIC", "OPENAI", "OFOX", "HUBROUTER"))}
    env.update({"ANTHROPIC_BASE_URL": "http://127.0.0.1:4000", "ANTHROPIC_AUTH_TOKEN": "experiment-local",
                "ANTHROPIC_MODEL": "gpt-6.1-terra", "ANTHROPIC_SMALL_FAST_MODEL": "gpt-6.1-terra",
                "ANTHROPIC_DEFAULT_OPUS_MODEL": "gpt-6.1-terra", "ANTHROPIC_DEFAULT_SONNET_MODEL": "gpt-6.1-terra",
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": "gpt-6.1-terra", "EXPERIMENT_SESSION": SESSION,
                "EXPERIMENT_TASK": TASK, "TEACHER_PROGRESS_URL": "http://172.17.0.1:8766/experiment/progress",
                "APPEND_SYSTEM_PROMPT_FILE": "/tmp/initial_hint.md", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
                "IS_SANDBOX": "1", "API_TIMEOUT_MS": "600000", "PYTHONDONTWRITEBYTECODE": "1",
                "PROXY_MAX_TOKENS_CLAMP": "65536", "HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": "",
                "http_proxy": "", "https_proxy": "", "all_proxy": "", "NO_PROXY": "*"})
    container = client.containers.run(image.id, name=NAME, entrypoint="", command=["tail", "-f", "/dev/null"],
        detach=True, mem_limit="128g", nano_cpus=8_000_000_000, privileged=True, environment=env,
        volumes={"/opt/hint-codex-runtime/python": {"bind": "/opt/python3.12-tmp", "mode": "ro"}})
    result["container"] = {"id": container.id, "name": NAME, "cpus": 8, "memory": "128g"}
    try:
        print(json.dumps({"stage": "setup", "container": container.id}), flush=True)
        code, output = container.exec_run(["bash", "-c", "rm -rf /app /root/.claude; mkdir -p /app/evidence /tmp/online_gate_out"])
        assert code == 0, output.decode()
        for local, remote in [(SOURCE / "run_cc_sdk.py", "/tmp/sdk_script.py"),
                              (SOURCE / "logging_utils.py", "/tmp/logging_utils.py"),
                              (SOURCE / "litellm_proxy/claude_code_proxy.py", "/tmp/litellm_call_backs.py"),
                              (SOURCE / "litellm_proxy/streaming_fix.py", "/tmp/streaming_fix.py")]:
            put_file(container, remote, local.read_bytes())
        put_file(container, "/tmp/config.yaml", render_proxy_config("openai", "gpt-6.1-terra", "experiment-local",
            "http://172.17.0.1:8765/sessions/" + SESSION + "/student/online_gate/v1", reasoning_effort="low", max_tokens=65536))
        put_file(container, "/tmp/initial_hint.md", HINT)
        put_file(container, "/app/remember.py", "def remember(item, items=[]):\n    items.append(item)\n    return items\n")
        for index, path in enumerate(FILES, 1):
            put_file(container, path, f"EVIDENCE_TAG_{index:02d}\n" + PROBLEM + "\n"
                     "Observed: remember('a') returns ['a']; a later default remember('b') returns ['a', 'b'].\n")
        code, output = container.exec_run(["bash", "-c", "git init -q && git config user.email fixture@example.com && "
            "git config user.name Fixture && git add . && git commit -qm initial && git rev-parse HEAD"], workdir="/app")
        assert code == 0, output.decode()
        base = output.decode().strip()
        result["registration"] = service("register", {"session": SESSION, "task": TASK,
            "problem_statement": PROBLEM, "golden_diff": GOLDEN_DIFF, "current_hint": HINT,
            "api_base": "http://127.0.0.1:8765", "model": "gpt-6.1-terra", "api_key": "codex-local"})
        container.exec_run(["bash", "-c", "PYTHONPATH=/tmp nohup /opt/python3.12-tmp/bin/litellm --config /tmp/config.yaml > /tmp/proxy.log 2>&1 &"])
        print(json.dumps({"stage": "proxy_warmup"}), flush=True)
        code, output = container.exec_run(["bash", "-c", "for i in $(seq 1 600); do curl -sf http://127.0.0.1:4000/health/liveliness >/dev/null && exit 0; sleep 1; done; exit 1"])
        assert code == 0, "Fixture proxy did not become ready"
        print(json.dumps({"stage": "real_sdk_query", "session": SESSION}), flush=True)
        started = time.monotonic()
        code, output = container.exec_run(["timeout", "--signal=INT", "--kill-after=35", "900", PYTHON,
            "/tmp/sdk_script.py", "--cwd", "/app", "--base_commit", base, "--output_dir", "/tmp/online_gate_out",
            "--log_path", "/tmp/sdk_script.log", "--problem_statement", PROMPT], workdir="/app", environment=env)
        result["sdk_wall_seconds"] = time.monotonic() - started
        result["sdk_exit_code"] = code
        (OUT / "stdout.log").write_bytes(output)
        for name in ("trajs.json", "patch.diff", "online_teacher_state.json", "online_teacher_events.json"):
            copy_file(container, "/tmp/online_gate_out/" + name, OUT / name)
        trajectory = json.loads((OUT / "trajs.json").read_text())
        metadata = trajectory["metadata"]
        result["bridge_status"] = status()
        result["teacher_status"] = service("status?session=" + SESSION)
        result["metadata"] = metadata
        assert code == 0 and metadata["status"] == "completed", "Original SDK did not complete"
        assert not result["bridge_status"]["stopped"], result["bridge_status"]["stop_reason"]
        assert metadata["main_tool_count"] == 20 and metadata["teacher_checks"] == 1
        state = json.loads((OUT / "online_teacher_state.json").read_text())
        assert state["inflight"] == [] and state["error"] is None
        events = json.loads((OUT / "online_teacher_events.json").read_text())
        completed = [event for event in events if event.get("hook_event_name") in ("PostToolUse", "PostToolUseFailure")]
        assert len(completed) == 20 and all(event["tool_name"] == "Read" for event in completed)
        assert sorted(event["tool_input"]["file_path"] for event in completed) == FILES
        assert not (OUT / "patch.diff").read_bytes(), "The compatibility fixture source changed"
        assert "ONLINE_GATE_COMPLETE" in metadata["ResultMessage"]["result"]
        save_evidence(result)
        assert result["native_tool_event_count"] == 0
        assert len(result["progress_checks"]) == 1 and result["progress_checks"][0]["tool_count"] == 20
        for delivery in result["delivery"]:
            assert delivery["word_count"] <= 100 and not delivery["contains_chinese"]
            if delivery["word_count"]:
                assert delivery["hint_occurrences_in_final_request"] == 1
        result["status"] = "passed"
        result["scope"] = "Actual threshold and teacher decision verified; delivery is covered only when a hint was returned."
    except BaseException as exc:
        result["error"] = str(exc) or type(exc).__name__
        raise
    finally:
        for name in ("proxy.log", "sdk_script.log", "system_prompt_config.json", "system_prompt_actual.json"):
            try:
                copy_file(container, "/tmp/" + name, OUT / name)
            except docker.errors.NotFound:
                pass
        if "progress_checks" not in result:
            save_evidence(result)
        result["finished_at_unix"] = time.time()
        (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        container.stop(timeout=10)
        client.close()
        print(json.dumps({"status": result["status"], "error": result.get("error"), "result": str(OUT / "result.json")}), flush=True)


if __name__ == "__main__":
    main()
