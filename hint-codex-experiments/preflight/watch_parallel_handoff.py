import json
import os
import signal
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path("/srv/lab-disks/disk2/users/xymo/hint-codex-experiments")
OUTPUT = ROOT / "preflight/parallel_handoff"
STATE = ROOT / "runs/codex_formal_04/experiment_state.json"
TASK = "anko-default-function-arguments"
OUTPUT.mkdir(parents=True, exist_ok=True)
process = json.loads((ROOT / "logs/codex_formal_04_process.json").read_text())

def read_state():
    try:
        return json.loads(STATE.read_text())
    except json.JSONDecodeError:
        return None

def task_complete(state):
    rows = [row for row in state["attempts"] if row["task"] == TASK]
    for group in state["groups"]:
        if group in state.get("skipped_groups", {}).get(TASK, []):
            continue
        entries = [row for row in rows if row["group"] == group]
        passed = next((row for row in entries if row["status"] == "solved"), None)
        if passed:
            if group != "B" and passed.get("review") not in ("done", "failed"):
                return False
        elif not any(row["round"] == state["max_rounds"] and row["status"] == "not_solved"
                     for row in entries):
            return False
    return True

print(json.dumps({"watching_pid": process["pid"], "task": TASK,
                  "policy": "Wait for every current-task policy and required review to finish naturally; do not interrupt any student attempt."}), flush=True)
while True:
    state = read_state()
    if state and state["status"] != "running":
        (OUTPUT / "no_action.json").write_text(json.dumps({"reason": "Prior experiment stopped before the handoff boundary", "state_status": state["status"], "stop_reason": state.get("stop_reason")}, indent=2) + "\n")
        break
    if state and task_complete(state):
        (OUTPUT / "state_before_stop.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
        request = {"requested_at_unix": time.time(), "pid": process["pid"], "task": TASK,
                   "reason": "User-authorized parallel transition after Anko naturally completed; preserve its results and assign remaining tasks once.",
                   "current_task_complete": True, "interrupted_student_attempt": False}
        (OUTPUT / "request.json").write_text(json.dumps(request, indent=2) + "\n")
        os.kill(process["pid"], signal.SIGINT)
        while True:
            time.sleep(0.2)
            final = read_state()
            if final and final["status"] != "running" and final.get("finished_at"):
                break
        (OUTPUT / "state_after_stop.json").write_text(json.dumps(final, ensure_ascii=False, indent=2) + "\n")
        with urlopen("http://127.0.0.1:8765/status", timeout=15) as response:
            bridge = json.load(response)
        tokens = 0
        for line in (ROOT / "logs/bridge/token_usage.jsonl").read_text().splitlines():
            row = json.loads(line)
            session = row.get("session") or ""
            if session.startswith("codex_formal_04-") and not session.startswith("codex_formal_04-" + TASK + "-"):
                tokens += row["delta"]["totalTokens"]
        result = dict(request, finished_at_unix=time.time(), prior_status=final["status"],
                      raw_stop_reason=final.get("stop_reason"), cleanup_error=final.get("cleanup_error"),
                      bridge_stopped=bridge["stopped"], active_model_sessions=sum(bool(item.get("active")) for item in bridge["sessions"]),
                      future_task_tokens=tokens)
        (OUTPUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result), flush=True)
        break
    time.sleep(0.2)
