#!/usr/bin/env python3
"""Local stage guidance for the existing student tool-execution loop."""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request

sys.path.insert(0, str(Path(__file__).resolve().parent / "benchmark" / "deepswe"))
from review_hint_traj import generate_progress_hint  # noqa: E402
from compress_hint import screen_progress_hint  # noqa: E402

MODEL = "gpt-6.1-terra"
CHECK_TIMEOUT = 600.0
MAX_CHECKS = 3
LOG = logging.getLogger("teacher_progress")


@dataclass
class StudentProgress:
    registration: Dict[str, Any]
    checks: int = 0
    delivered_hints: List[str] = field(default_factory=list)
    teacher_wait_seconds: float = 0.0
    active_since: Optional[float] = None
    stopped: bool = False
    stop_reason: Optional[str] = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class TeacherProgress:
    def __init__(self, run_dir, bridge_base="http://127.0.0.1:8765",
                 candidate=None, screen=None, status_reader=None, stopper=None,
                 check_timeout=CHECK_TIMEOUT):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.bridge_base = bridge_base.rstrip("/")
        self.candidate = candidate or generate_progress_hint
        self.screen = screen or screen_progress_hint
        self.status_reader = status_reader or self.read_bridge_status
        self.stopper = stopper or self.stop_bridge
        self.check_timeout = check_timeout
        self.sessions: Dict[str, StudentProgress] = {}
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def read_bridge_status(self):
        with self.opener.open(self.bridge_base + "/status", timeout=5) as response:
            return json.load(response)

    def stop_bridge(self, reason):
        request = urllib.request.Request(
            self.bridge_base + "/stop", data=json.dumps({"reason": reason}).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with self.opener.open(request, timeout=5) as response:
            return json.load(response)

    def register(self, registration):
        session = registration["session"]
        if registration.get("model", MODEL) != MODEL:
            raise HTTPException(400, "The experiment uses gpt-6.1-terra")
        if session not in self.sessions:
            for name in ("task", "problem_statement", "golden_diff", "current_hint", "api_base"):
                if name not in registration:
                    raise HTTPException(400, "Missing registration field: " + name)
            self.sessions[session] = StudentProgress(dict(registration))
        return {"session": session, "registered": True}

    def state(self, session):
        if session not in self.sessions:
            raise HTTPException(404, "The student session is not registered")
        return self.sessions[session]

    async def status(self, session):
        state = self.sessions.get(session)
        snapshot = self.snapshot(session) if state else {
            "session": session, "checks": 0, "teacher_wait_seconds": 0.0,
            "stopped": False, "stop_reason": None}
        try:
            bridge = await asyncio.to_thread(self.status_reader)
            if bridge.get("stopped"):
                snapshot["stopped"] = True
                snapshot["stop_reason"] = bridge.get("stop_reason") or "The model bridge stopped"
        except Exception as exc:
            snapshot["stopped"] = True
            snapshot["stop_reason"] = "Could not read model bridge status: " + str(exc)
        if state:
            state.stopped = snapshot["stopped"]
            state.stop_reason = snapshot["stop_reason"]
        return snapshot

    def snapshot(self, session):
        state = self.state(session)
        wait = state.teacher_wait_seconds
        if state.active_since is not None:
            wait += time.monotonic() - state.active_since
        return {"session": session, "checks": state.checks,
                "teacher_wait_seconds": wait, "stopped": state.stopped,
                "stop_reason": state.stop_reason}

    def stage_api_base(self, registration, check, stage):
        # Each text-only teacher call is a fresh conversation, including the screen.
        base = registration["api_base"].rstrip("/")
        if "/sessions/" in base:
            base = base.split("/sessions/", 1)[0]
        elif base.endswith("/v1"):
            base = base[:-3]
        session = quote(registration["session"] + f"_progress_{check}_{stage}", safe="")
        role = "teacher" if stage == "candidate" else "compressor"
        return f"{base}/sessions/{session}/{role}/progress_{check}_{stage}/v1"

    def remaining(self, started, reserve_stop=False):
        reserve = min(5.0, self.check_timeout / 10) if reserve_stop else 0.0
        seconds = self.check_timeout - (time.monotonic() - started) - reserve
        if seconds <= 0:
            raise TimeoutError("The teacher check exceeded its 600-second limit")
        return seconds

    def run_check(self, state, payload, record):
        registration = state.registration
        observed = payload["trajectory"]
        previous = list(state.delivered_hints)
        kwargs = {"model": MODEL, "api_key": registration.get("api_key", "codex-local")}
        started = time.monotonic()
        candidate_started = time.monotonic()
        candidate = self.candidate(
            registration["problem_statement"], registration["golden_diff"],
            observed, registration["current_hint"], previous_hints=previous,
            api_base=self.stage_api_base(registration, state.checks, "candidate"),
            request_timeout=self.remaining(started, reserve_stop=True), **kwargs,
        )
        record["candidate"] = candidate
        record["candidate_seconds"] = time.monotonic() - candidate_started
        self.remaining(started)
        if candidate.get("needs_hint") is not True:
            record["decision"] = "no_hint_needed"
            return ""
        candidate_hint = candidate.get("corrective_hint") or ""
        if not candidate_hint:
            record["decision"] = "empty_candidate"
            return ""
        screen_started = time.monotonic()
        screened = self.screen(
            candidate_hint, observed,
            previous_hints=[registration["current_hint"]] + previous,
            api_base=self.stage_api_base(registration, state.checks, "screen"),
            request_timeout=self.remaining(started, reserve_stop=True), **kwargs,
        )
        record["screen"] = screened
        record["screen_seconds"] = time.monotonic() - screen_started
        self.remaining(started)
        hint = (screened.get("hint") or "").strip()
        if (screened.get("deliver") is not True or not hint
                or len(hint.split()) > 100 or re.search(r"[\u4e00-\u9fff]", hint)):
            record["decision"] = "not_delivered"
            return ""
        record["decision"] = "delivered"
        return hint

    async def progress(self, payload):
        session = payload["session"]
        state = self.state(session)
        async with state.lock:
            status = await self.status(session)
            if status["stopped"] or state.checks >= MAX_CHECKS:
                return dict(status, hint="")
            if payload.get("task") != state.registration["task"]:
                state.stopped = True
                state.stop_reason = "The guidance request does not match the registered task"
                return dict(await self.status(session), hint="")
            state.checks += 1
            state.active_since = time.monotonic()
            record = {"session": session, "task": state.registration["task"],
                      "check": state.checks, "tool_count": payload.get("tool_count"),
                      "started_at": time.time(), "candidate": None, "screen": None,
                      "hint": "", "decision": None}
            try:
                # The HTTP calls receive the remaining deadline and perform one attempt.
                # Await completion rather than cancelling a live worker thread.
                hint = await asyncio.to_thread(self.run_check, state, payload, record)
                if hint:
                    state.delivered_hints.append(hint)
                    record["hint"] = hint
            except Exception as exc:
                state.stopped = True
                state.stop_reason = "Teacher guidance failed: " + str(exc)
                record["decision"] = "stopped"
                record["error"] = state.stop_reason
                LOG.warning("Guidance stopped for %s: %s", session, exc)
                try:
                    await asyncio.to_thread(self.stopper, state.stop_reason)
                except Exception as stop_error:
                    record["bridge_stop_error"] = str(stop_error)
                    LOG.warning("Could not stop the upstream bridge: %s", stop_error)
            finally:
                duration = time.monotonic() - state.active_since
                state.teacher_wait_seconds += duration
                state.active_since = None
                record.update(duration_seconds=duration, finished_at=time.time(),
                              teacher_wait_seconds=state.teacher_wait_seconds,
                              stopped=state.stopped, stop_reason=state.stop_reason)
                with (self.run_dir / "progress.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            status = self.snapshot(session)
            return dict(status, hint="" if status["stopped"] else record["hint"])


def create_app(service):
    app = FastAPI()
    app.state.teacher = service

    @app.post("/experiment/register")
    async def register(request: Request):
        return service.register(await request.json())

    @app.get("/experiment/status")
    async def status(session: str):
        return await service.status(session)

    @app.post("/experiment/progress")
    async def progress(request: Request):
        return await service.progress(await request.json())

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--bridge_base", default="http://127.0.0.1:8765")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    os.environ.pop("ALL_PROXY", None)
    os.environ.pop("all_proxy", None)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    import uvicorn
    uvicorn.run(create_app(TeacherProgress(args.run_dir, args.bridge_base)),
                host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
