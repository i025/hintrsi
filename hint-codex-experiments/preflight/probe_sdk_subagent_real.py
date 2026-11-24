#!/usr/bin/env python3
"""Gate real SDK fork routing through the Codex bridge on a tiny local project."""

import argparse
import json
import time

import docker

from probe_sdk_bridge import ROOT, SOURCE, PYTHON, copy_file, put_file, status
from constant_zhy import render_proxy_config

SESSION = "preflight-subagent-real"
NAME = "codex-sdk-subagent-real-preflight"
OUT = ROOT / "preflight/sdk_subagent_real"
CONTEXT_MARKER = "FORK_CONTEXT_20261121_A7"
NATIVE_ITEMS = {
    "commandExecution", "fileChange", "webSearch", "imageView", "mcpToolCall",
    "collabAgentToolCall", "subAgentActivity",
}
PROMPT = (
    "Run this small SDK fork compatibility check. First use Read on "
    "/app/fixture_context.txt. Then delegate exactly one foreground, read-only "
    "inspection using Agent with subagent_type='fork' and run_in_background=false. "
    "If the Agent tool is deferred, discover it first. Tell the child to read "
    "/app/counter.py, explain what add does, and return a CHILD_SUMMARY containing "
    "the exact context marker from the inherited file-read result and the exact "
    "CONTAINER_MARKER value from counter.py. Do not copy either marker value into the delegation "
    "prompt. The child must use the inherited context directly, must not modify "
    "files, and must not delegate again. Wait for its summary, then run "
    "python3 -m unittest -v with Bash yourself. Do not modify any project files. "
    "Finish with FORK_GATE_COMPLETE, the child summary, and the test outcome. "
    "Use no more than eight parent tool calls; the child should need one Read."
)


def read_rows(path):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    return [row for row in rows if row.get("session") == SESSION]


def blocks(records):
    return [block for record in records
            for block in record["message"].get("content", [])
            if isinstance(block, dict)]


def inspect_result(trajectory, snapshot, container_marker):
    main = [json.loads(line) for line in trajectory["trajectories"]["main_agent"].splitlines()]
    children = [[json.loads(line) for line in group.splitlines()]
                for group in trajectory["trajectories"]["sub_agent"]]
    calls = [block for block in blocks(main)
             if block.get("name") in ("Agent", "Task")]
    assert len(calls) == 1, "Expected exactly one original SDK delegation"
    call = calls[0]
    assert call["input"].get("subagent_type") == "fork", "Expected SDK fork delegation"
    assert call["input"].get("run_in_background") is False, "Expected a foreground child"
    assert CONTEXT_MARKER not in json.dumps(call["input"]), "Parent copied the inherited marker"
    assert container_marker not in json.dumps(call["input"]), "Parent copied the container marker"
    assert len(children) == 1, "Expected one SDK child trajectory"
    child = children[0]
    assert {record["message"].get("parent_tool_use_id") for record in child} == {call["id"]}
    assert any(block.get("name") == "Read"
               and block.get("input", {}).get("file_path") == "/app/counter.py"
               for block in blocks(child)), "Child did not read the local fixture"
    assert not any(block.get("name") in ("Edit", "Write", "Agent", "Task")
                   for block in blocks(child)), "Child exceeded its read-only inspection"
    assert not any(block.get("name") == "Read"
                   and block.get("input", {}).get("file_path") == "/app/fixture_context.txt"
                   for block in blocks(child)), "Child reread the inherited marker instead of using its context"
    summaries = [block for block in blocks(main) if block.get("tool_use_id") == call["id"]]
    assert len(summaries) == 1, "Parent did not receive exactly one child summary"
    summary = json.dumps(summaries[0])
    assert all(marker in summary for marker in ("CHILD_SUMMARY", CONTEXT_MARKER, container_marker))
    bash = [block for block in blocks(main) if block.get("name") == "Bash"
            and "python3 -m unittest -v" in block.get("input", {}).get("command", "")]
    assert bash, "Parent did not run the local unit test"
    assert blocks(main).index(summaries[0]) < blocks(main).index(bash[-1]), "Parent tested before receiving the child summary"
    assert any(block.get("tool_use_id") == bash[-1]["id"]
               and "OK" in json.dumps(block.get("content")) and not block.get("is_error")
               for block in blocks(main)), "The parent test tool did not return success"
    assert "FORK_GATE_COMPLETE" in json.dumps(trajectory["metadata"]["ResultMessage"])
    states = [state for state in snapshot["sessions"] if state["session"] == SESSION]
    parents = [state for state in states if not state.get("fork_call_id")]
    forks = [state for state in states if state.get("fork_call_id") == call["id"]]
    assert len(parents) == len(forks) == 1, "Expected separate parent and fork bridge states"
    assert parents[0]["thread_id"] != forks[0]["thread_id"], "Fork shared the parent Codex thread"
    assert not any(state["active"] or state["error"] for state in states)
    return {"agent_call_id": call["id"], "child_summary_received": True,
            "inherited_context_marker_received": True, "container_marker_received": True,
            "parent_thread_id": parents[0]["thread_id"],
            "child_thread_id": forks[0]["thread_id"],
            "sdk_child_message_count": len(child)}


def save_bridge_records(result):
    rows = {}
    for name in ("model_requests.jsonl", "model_responses.jsonl", "codex_events.jsonl", "token_usage.jsonl"):
        path = ROOT / "logs/bridge" / name
        rows[name] = read_rows(path) if path.exists() else []
        (OUT / name).write_text("".join(json.dumps(row) + "\n" for row in rows[name]))
    events = rows["codex_events.jsonl"]
    native = [row for row in events
              if row["event"].get("method") in ("item/started", "item/completed")
              and row["event"].get("params", {}).get("item", {}).get("type") in NATIVE_ITEMS]
    result["native_tool_event_count"] = len(native)
    threads = {}
    for state in result.get("bridge_status", {}).get("sessions", []):
        if state["session"] != SESSION:
            continue
        thread = state["thread_id"]
        responses = [row for row in rows["model_responses.jsonl"] if row["thread_id"] == thread]
        lifecycle = [row for row in events
                     if row["event"].get("params", {}).get("threadId") == thread]
        started = [row["timestamp"] for row in lifecycle if row["event"].get("method") == "turn/started"]
        ended = [row["timestamp"] for row in lifecycle if row["event"].get("method") == "turn/completed"]
        threads["child" if state.get("fork_call_id") else "parent"] = {
            "thread_id": thread, "fork_call_id": state.get("fork_call_id"),
            "usage": state["usage"], "model_request_count": len(responses),
            "model_request_wall_seconds": sum(row["elapsed_seconds"] for row in responses),
            "turn_wall_seconds": max(ended) - min(started) if started and ended else None,
        }
    result["threads"] = threads
    result["timing_note"] = "Parent turn wall time includes waiting for the child; branch spans overlap."


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Run the authorized real Terra gate")
    args = parser.parse_args()
    if not args.run:
        print(json.dumps({"prepared": True, "session": SESSION, "container": NAME,
                          "real_model_calls": 0, "prompt": PROMPT}))
        return
    initial = status()
    assert not initial["stopped"], initial["stop_reason"]
    assert not any(state["session"] == SESSION for state in initial["sessions"]), "Use a fresh gate session"
    OUT.mkdir(parents=True)
    result = {"session": SESSION, "purpose": "Real SDK fork compatibility preflight only",
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
                "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "IS_SANDBOX": "1",
                "API_TIMEOUT_MS": "600000", "PYTHONDONTWRITEBYTECODE": "1", "PROXY_MAX_TOKENS_CLAMP": "65536",
                "HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": "", "http_proxy": "",
                "https_proxy": "", "all_proxy": "", "NO_PROXY": "*"})
    container = client.containers.run(image.id, name=NAME, entrypoint="", command=["tail", "-f", "/dev/null"],
        detach=True, mem_limit="128g", nano_cpus=8_000_000_000, privileged=True, environment=env,
        volumes={"/opt/hint-codex-runtime/python": {"bind": "/opt/python3.12-tmp", "mode": "ro"}})
    result["container"] = {"id": container.id, "name": NAME, "image": image.id, "cpus": 8, "memory": "128g"}
    try:
        print(json.dumps({"stage": "setup", "container": container.id}), flush=True)
        code, output = container.exec_run(["bash", "-c", "rm -rf /app /root/.claude; mkdir -p /app /tmp/fork_gate_out"])
        assert code == 0, output.decode()
        for local, remote in [(SOURCE / "run_cc_sdk.py", "/tmp/sdk_script.py"),
                              (SOURCE / "logging_utils.py", "/tmp/logging_utils.py"),
                              (SOURCE / "litellm_proxy/claude_code_proxy.py", "/tmp/litellm_call_backs.py"),
                              (SOURCE / "litellm_proxy/streaming_fix.py", "/tmp/streaming_fix.py")]:
            put_file(container, remote, local.read_bytes())
        put_file(container, "/tmp/config.yaml", render_proxy_config("openai", "gpt-6.1-terra", "experiment-local",
            "http://172.17.0.1:8765/sessions/" + SESSION + "/student/fork_gate/v1", reasoning_effort="low", max_tokens=65536))
        put_file(container, "/app/fixture_context.txt", "Inherited context marker: " + CONTEXT_MARKER + "\n")
        put_file(container, "/app/counter.py", "CONTAINER_MARKER = " + repr(container.id) + "\n\ndef add(a, b):\n    return a + b\n")
        put_file(container, "/app/test_counter.py", "import unittest\nfrom counter import add, CONTAINER_MARKER\n\n"
                 "class CounterTest(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(3, 2), 5)\n"
                 "    def test_container(self):\n        self.assertEqual(CONTAINER_MARKER, " + repr(container.id) + ")\n")
        code, output = container.exec_run(["bash", "-c", "git init -q && git config user.email fixture@example.com && "
            "git config user.name Fixture && git add . && git commit -qm initial && git rev-parse HEAD"], workdir="/app")
        assert code == 0, output.decode()
        base = output.decode().strip()
        container.exec_run(["bash", "-c", "PYTHONPATH=/tmp nohup /opt/python3.12-tmp/bin/litellm --config /tmp/config.yaml > /tmp/proxy.log 2>&1 &"])
        print(json.dumps({"stage": "proxy_warmup"}), flush=True)
        code, output = container.exec_run(["bash", "-c", "for i in $(seq 1 600); do curl -sf http://127.0.0.1:4000/health/liveliness >/dev/null && exit 0; sleep 1; done; exit 1"])
        assert code == 0, "Fixture proxy did not become ready"
        print(json.dumps({"stage": "real_sdk_query", "session": SESSION}), flush=True)
        started = time.monotonic()
        code, output = container.exec_run(["timeout", "--signal=INT", "--kill-after=35", "480", PYTHON,
            "/tmp/sdk_script.py", "--cwd", "/app", "--base_commit", base, "--output_dir", "/tmp/fork_gate_out",
            "--log_path", "/tmp/sdk_script.log", "--problem_statement", PROMPT], workdir="/app", environment=env)
        result["sdk_wall_seconds"] = time.monotonic() - started
        result["sdk_exit_code"] = code
        (OUT / "stdout.log").write_bytes(output)
        for name in ("trajs.json", "patch.diff"):
            copy_file(container, "/tmp/fork_gate_out/" + name, OUT / name)
        trajectory = json.loads((OUT / "trajs.json").read_text())
        result["bridge_status"] = status()
        assert code == 0 and trajectory["metadata"]["status"] == "completed", "Original SDK did not complete"
        assert not result["bridge_status"]["stopped"], result["bridge_status"]["stop_reason"]
        result["gate"] = inspect_result(trajectory, result["bridge_status"], container.id)
        code, output = container.exec_run(["bash", "-c", "python3 -m unittest -v && git diff --exit-code"], workdir="/app")
        result["independent_verification"] = {"exit_code": code, "output": output.decode()}
        assert code == 0 and not (OUT / "patch.diff").read_bytes(), "Fixture test or read-only task check failed"
        save_bridge_records(result)
        assert result["native_tool_event_count"] == 0, "Native Codex tool execution was observed"
        result["status"] = "passed"
    except BaseException as exc:
        result["error"] = str(exc) or type(exc).__name__
        raise
    finally:
        for name in ("proxy.log", "sdk_script.log", "system_prompt_config.json", "system_prompt_actual.json"):
            try:
                copy_file(container, "/tmp/" + name, OUT / name)
            except docker.errors.NotFound:
                pass
        if "threads" not in result:
            save_bridge_records(result)
        result["finished_at_unix"] = time.time()
        (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        container.stop(timeout=10)
        client.close()
        print(json.dumps({"status": result["status"], "error": result.get("error"), "result": str(OUT / "result.json")}), flush=True)


if __name__ == "__main__":
    main()
