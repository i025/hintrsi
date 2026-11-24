#!/usr/bin/env python3
"""Use Codex CLI as the model behind the existing Claude SDK tool executor."""

import argparse
import asyncio
import inspect
import json
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

MODEL = "gpt-6.1-terra"
EFFORT = "low"
STDIO_STREAM_LIMIT = 16 * 1024 * 1024
SDK_FORK_RESULT = "Fork started — that fork is you."
SDK_FORK_MARKER = "<fork-boilerplate>"
EXTERNAL_TOOL_INSTRUCTIONS = (
    "The registered dynamic tools are executed by the existing Claude SDK inside the "
    "isolated task container using their original permissions. The Codex host filesystem "
    "policy does not restrict these external tools. Follow the original role instructions "
    "and actual tool results, including any role-specific read-only restrictions. Do not "
    "infer a container write failure from the host policy. Never use native Codex "
    "filesystem or command tools."
)
LOG = logging.getLogger("codex_cli_bridge")
NATIVE_ITEMS = {
    "commandExecution", "fileChange", "webSearch", "imageView", "mcpToolCall",
    "collabAgentToolCall", "subAgentActivity",
}
DISABLED_FEATURES = (
    "shell_tool", "view_image", "multi_agent", "plugins", "apps",
    "skill_search", "skill_mcp_dependency_install", "remote_plugin",
)


class CodexBridgeError(RuntimeError):
    def __init__(self, message: str, code: str = "codex_bridge_error", status: int = 503):
        super().__init__(message)
        self.code = code
        self.status = status


def default_command() -> List[str]:
    command = ["codex", "app-server", "--stdio"]
    for name in DISABLED_FEATURES:
        command += ["-c", f"features.{name}=false"]
    command += ["-c", 'web_search="disabled"', "-c", "project_doc_max_bytes=0",
                "-c", "mcp_servers={}"]
    return command


class CodexRPCClient:
    """Small JSON-RPC stdio client; server tool requests stay pending until replied."""

    def __init__(self, command=None, event_callback=None, stderr_path=None, cwd=None):
        self.command = command or default_command()
        self.event_callback = event_callback
        self.stderr_path = Path(stderr_path) if stderr_path else None
        self.cwd = str(cwd) if cwd else None
        self.process = None
        self.incoming = asyncio.Queue()
        self._requests = {}
        self._next_id = 0
        self._write_lock = asyncio.Lock()
        self._reader_task = None
        self._stderr_task = None

    async def start(self):
        self.process = await asyncio.create_subprocess_exec(
            *self.command, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=self.cwd, limit=STDIO_STREAM_LIMIT,
        )
        self._reader_task = asyncio.create_task(self._read())
        self._stderr_task = asyncio.create_task(self._read_stderr())
        result = await self.request("initialize", {
            "clientInfo": {"name": "hint-experiment", "version": "1.0.0"},
            "capabilities": {"experimentalApi": True},
        })
        await self.notify("initialized", {})
        return result

    async def _send(self, message):
        async with self._write_lock:
            self.process.stdin.write((json.dumps(message) + "\n").encode())
            await self.process.stdin.drain()

    async def request(self, method, params=None):
        self._next_id += 1
        request_id = self._next_id
        future = asyncio.get_running_loop().create_future()
        self._requests[request_id] = future
        await self._send({"id": request_id, "method": method, "params": params or {}})
        try:
            return await future
        finally:
            self._requests.pop(request_id, None)

    async def notify(self, method, params=None):
        await self._send({"method": method, "params": params or {}})

    async def respond(self, request_id, result):
        await self._send({"id": request_id, "result": result})

    def _emit(self, message):
        if self.event_callback:
            result = self.event_callback(message)
            if inspect.isawaitable(result):
                asyncio.create_task(result)

    async def _read(self):
        try:
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    break
                message = json.loads(line)
                self._emit(message)
                if "method" in message:
                    if "id" in message:
                        await self.incoming.put(message)
                elif message.get("id") in self._requests:
                    future = self._requests[message["id"]]
                    if not future.done():
                        if "error" in message:
                            error = message["error"]
                            future.set_exception(CodexBridgeError(
                                json.dumps(error), str(error.get("code", "rpc_error"))))
                        else:
                            future.set_result(message.get("result"))
        except Exception as exc:
            LOG.exception("Codex stdio reader failed")
            error = CodexBridgeError(str(exc), "transport_error")
        else:
            error = CodexBridgeError("Codex app-server closed stdout", "transport_closed")
        for future in self._requests.values():
            if not future.done():
                future.set_exception(error)
        self._emit({"method": "bridge/transportClosed", "params": {"error": str(error)}})

    async def _read_stderr(self):
        while True:
            line = await self.process.stderr.readline()
            if not line:
                return
            if self.stderr_path:
                with self.stderr_path.open("ab") as output:
                    output.write(line)

    async def close(self):
        if self.process and self.process.returncode is None:
            self.process.terminate()
            await self.process.wait()
        for task in (self._reader_task, self._stderr_task):
            if task and not task.done():
                task.cancel()
        await asyncio.gather(*(t for t in (self._reader_task, self._stderr_task) if t),
                             return_exceptions=True)


@dataclass
class ToolRequest:
    call_id: str
    rpc_id: Any
    name: str
    arguments: Any
    served: bool = False
    completed: bool = False


@dataclass
class Session:
    session_id: str
    role: str
    phase: str
    source_id: str = ""
    requested_model: str = ""
    fork_call_id: Optional[str] = None
    thread_id: Optional[str] = None
    turn_id: Optional[str] = None
    active: bool = False
    tools: List[str] = field(default_factory=list)
    tool_specs: List[Dict] = field(default_factory=list)
    user_inputs: List[Any] = field(default_factory=list)
    pending: Dict[str, ToolRequest] = field(default_factory=dict)
    ready: deque = field(default_factory=deque)
    text: deque = field(default_factory=deque)
    usage_total: Optional[Dict] = None
    reported_usage: Dict[str, int] = field(default_factory=dict)
    error: Optional[str] = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    changed: asyncio.Event = field(default_factory=asyncio.Event)


def _quota_error(value) -> bool:
    text = json.dumps(value).lower()
    return any(word in text for word in (
        "usagelimit", "usage_limit", "rate_limit", "ratelimit", "quota",
        "usage limit", "rate limit", "insufficient_quota", "limit reached",
        "credits exhausted", "out of credits", "too many requests",
    ))


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(part.get("text", "") for part in content
                         if isinstance(part, dict) and part.get("type") in ("text", "input_text"))
    return "" if content is None else json.dumps(content)


def _input(content):
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    result = []
    for part in content or []:
        if part.get("type") in ("text", "input_text"):
            result.append({"type": "text", "text": part["text"]})
        elif part.get("type") == "image_url":
            result.append({"type": "image", "url": part["image_url"]["url"]})
    return result


def _history_items(messages):
    """Preserve SDK fork reference history as role-bearing Responses items."""
    items = []
    for message in messages:
        role = message["role"]
        if role in ("user", "assistant"):
            content = []
            for part in _input(message.get("content")):
                if part["type"] == "text":
                    content.append({"type": "output_text" if role == "assistant" else "input_text",
                                    "text": part["text"]})
                elif part["type"] == "image":
                    content.append({"type": "input_image", "image_url": part["url"]})
            if content:
                items.append({"type": "message", "role": role, "content": content})
            for call in message.get("tool_calls") or []:
                function = call["function"]
                arguments = function.get("arguments", "{}")
                items.append({"type": "function_call", "call_id": call["id"],
                              "name": function["name"], "arguments": arguments if isinstance(arguments, str)
                              else json.dumps(arguments)})
        elif role == "tool":
            items.append({"type": "function_call_output", "call_id": message["tool_call_id"],
                          "output": _text(message.get("content"))})
    return items


class CodexBridge:
    def __init__(self, run_dir, rpc=None):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.rpc = rpc or CodexRPCClient(stderr_path=self.run_dir / "codex_stderr.log",
                                        cwd=self.run_dir)
        self.rpc.event_callback = self.on_event
        self.sessions = {}
        self.by_thread = {}
        self.by_call = {}
        self.stopped = False
        self.stop_reason = None
        self._started = False
        self._start_lock = asyncio.Lock()
        self._opening = None
        self._open_lock = asyncio.Lock()
        self._interrupts = set()

    def record(self, filename, value):
        with (self.run_dir / filename).open("a", encoding="utf-8") as output:
            output.write(json.dumps({"timestamp": time.time(), **value}, ensure_ascii=False) + "\n")

    def status(self):
        return {
            "stopped": self.stopped, "stop_reason": self.stop_reason,
            "sessions": [{
                "session": state.session_id, "role": state.role, "phase": state.phase,
                "source_id": state.source_id, "requested_model": state.requested_model,
                "fork_call_id": state.fork_call_id,
                "thread_id": state.thread_id, "turn_id": state.turn_id,
                "active": state.active, "error": state.error,
                "pending": [vars(tool) for tool in state.pending.values() if not tool.completed],
                "usage": state.usage_total,
            } for state in self.sessions.values()],
        }

    def checkpoint(self):
        (self.run_dir / "bridge_state.json").write_text(
            json.dumps(self.status(), ensure_ascii=False, indent=2), encoding="utf-8")
        recovery = []
        for key, state in self.sessions.items():
            if state.role != "teacher":
                continue
            values = {name: value for name, value in vars(state).items()
                      if name not in ("lock", "changed", "pending", "ready", "text")}
            values.update(pending=[vars(tool) for tool in state.pending.values()],
                          ready=list(state.ready), text=list(state.text))
            recovery.append({"key": list(key), "state": values})
        target = self.run_dir / "bridge_recovery.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(recovery, ensure_ascii=False), encoding="utf-8")
        temporary.replace(target)

    def stop(self, reason):
        if self.stopped:
            return
        self.stopped = True
        self.stop_reason = reason
        LOG.error("Stopping Codex model bridge: %s", reason)
        for state in self.sessions.values():
            state.error = state.error or reason
            state.changed.set()
            if state.active and state.thread_id and state.turn_id:
                task = asyncio.create_task(self._interrupt(state))
                self._interrupts.add(task)
                task.add_done_callback(self._interrupts.discard)
        self.checkpoint()

    async def _interrupt(self, state):
        try:
            await self.rpc.request("turn/interrupt", {
                "threadId": state.thread_id, "turnId": state.turn_id,
            })
        except Exception:
            LOG.exception("Could not interrupt stopped Codex turn")

    def on_event(self, event):
        params = event.get("params") or {}
        thread_id = params.get("threadId")
        if not thread_id and isinstance(params.get("thread"), dict):
            thread_id = params["thread"].get("id")
        state = self.by_thread.get(thread_id)
        if not state and self._opening and thread_id:
            state = self._opening
            state.thread_id = thread_id
            self.by_thread[thread_id] = state
        attribution = {"session": state.session_id, "role": state.role, "phase": state.phase} if state else {}
        self.record("codex_events.jsonl", {**attribution, "event": event})
        method = event.get("method", "")
        item = params.get("item") or {}
        native_method = any(method.startswith("item/" + name + "/") for name in NATIVE_ITEMS)
        if item.get("type") in NATIVE_ITEMS or native_method:
            self.stop("Native Codex tool event: " + item.get("type", method))
            return
        if "approval" in method.lower() or "requestPermissions" in method:
            self.stop("Unexpected native permission request: " + method)
            return
        if "id" in event and method and method != "item/tool/call":
            self.stop("Unexpected Codex server request: " + method)
            return
        if method == "bridge/transportClosed":
            if self._started:
                self.stop(params.get("error", "Codex transport closed"))
            return
        if not state:
            if method == "error" and _quota_error(params):
                self.stop(json.dumps(params))
            return
        if params.get("turnId"):
            state.turn_id = params["turnId"]
        if method == "item/tool/call":
            name = params["tool"]
            if name not in state.tools:
                self.stop("Unexpected Codex tool request: " + name)
                return
            call_id = params["callId"]
            if call_id not in state.pending:
                state.pending[call_id] = ToolRequest(call_id, event["id"], name, params["arguments"])
                state.ready.append(call_id)
                self.by_call[call_id] = state
            state.changed.set()
        elif method == "item/completed" and item.get("type") == "agentMessage":
            state.text.append(item.get("text", ""))
            state.changed.set()
        elif method == "thread/tokenUsage/updated":
            usage = params.get("tokenUsage") or {}
            total = usage.get("total")
            if total is not None and total != state.usage_total:
                previous = state.usage_total or {}
                delta = {key: value - previous.get(key, 0) for key, value in total.items()
                         if isinstance(value, int)}
                state.usage_total = dict(total)
                self.record("token_usage.jsonl", {**attribution, "thread_id": state.thread_id,
                            "turn_id": state.turn_id, "usage": usage, "delta": delta})
                self.checkpoint()
        elif method == "turn/started":
            state.turn_id = params["turn"]["id"]
            state.active = True
        elif method == "turn/completed":
            turn = params.get("turn") or {}
            state.active = False
            if turn.get("status") in ("failed", "interrupted"):
                state.error = json.dumps(turn.get("error") or {"status": turn["status"]})
                if _quota_error(turn):
                    self.stop(state.error)
            state.changed.set()
            self.checkpoint()
        elif method == "error":
            state.error = json.dumps(params)
            if _quota_error(params):
                self.stop(state.error)
            state.changed.set()

    async def start(self):
        async with self._start_lock:
            if not self._started:
                await self.rpc.start()
                self._started = True

    async def close(self):
        self._started = False
        await self.rpc.close()

    def resolve_session(self, body, headers, route=None):
        metadata = body.get("metadata") or {}
        route = route or {}
        session_id = route.get("session") or headers.get("x-experiment-session") or metadata.get("experiment_session")
        role = route.get("role") or headers.get("x-experiment-role") or metadata.get("experiment_role") or "student"
        phase = route.get("phase") or headers.get("x-experiment-phase") or metadata.get("experiment_phase") or "solve"
        source_id = str(body.get("user") or metadata.get("user_id") or "")
        requested_model = str(body.get("model") or "")
        fork = self._sdk_fork(body)
        if fork:
            call_id, _ = fork
            parent = self.by_call[call_id]
            session_id = session_id or parent.session_id
            key = (session_id, role, source_id, requested_model, "sdk-fork", call_id)
            state = self.sessions.get(key)
            if state is None:
                state = self.sessions[key] = Session(
                    session_id, role, phase, source_id, requested_model, fork_call_id=call_id)
            state.phase = phase
            return state
        # Tool ids also route SDK auxiliary/sub-agent requests without relying on proxy headers.
        for message in reversed(body.get("messages", [])):
            call_id = message.get("tool_call_id")
            if call_id in self.by_call:
                state = self.by_call[call_id]
                if (not session_id or state.session_id == session_id) and state.role == role:
                    state.phase = phase
                    return state
        session_id = session_id or str(uuid.uuid4())
        key = (session_id, role, source_id, requested_model)
        state = self.sessions.get(key)
        # SDK sub-agents can inherit both the model alias and metadata.user_id.
        # A new, independent user history starts a separate model conversation;
        # subsequent calls are then routed by their actual tool call ids above.
        if state and state.user_inputs:
            inputs = [_input(message.get("content")) for message in body["messages"]
                      if message["role"] == "user"]
            prefix = inputs[:len(state.user_inputs)] == state.user_inputs
            one_shot = ("haiku" in requested_model.lower() and not state.active
                        and not any(message["role"] in ("assistant", "tool") for message in body["messages"]))
            if not prefix and role == "teacher" and phase != state.phase and not one_shot:
                self.stop("Persistent teacher history was replaced between phases")
                raise CodexBridgeError(self.stop_reason, "teacher_history_changed", 409)
            if not prefix or one_shot:
                key += (str(uuid.uuid4()),)
                state = None
        if state is None:
            state = self.sessions[key] = Session(session_id, role, phase, source_id, requested_model)
        state.phase = phase
        return state

    def _sdk_fork(self, body):
        messages = body.get("messages", [])
        markers = [index for index, message in enumerate(messages)
                   if message["role"] == "user" and SDK_FORK_MARKER in _text(message.get("content"))]
        if not markers:
            return None
        marker_index = markers[-1]
        for message in reversed(messages[:marker_index]):
            call_id = message.get("tool_call_id")
            parent = self.by_call.get(call_id)
            if (parent and parent.pending[call_id].name == "Agent"
                    and _text(message.get("content")) == SDK_FORK_RESULT):
                return call_id, marker_index
        return None

    async def _open(self, state, body):
        system = "\n\n".join(_text(message.get("content")) for message in body["messages"]
                              if message["role"] in ("system", "developer"))
        tools = []
        for tool in body.get("tools") or []:
            function = tool["function"]
            tools.append({"type": "function", "name": function["name"],
                          "description": function.get("description", ""),
                          "inputSchema": function.get("parameters", {"type": "object"})})
        state.tools = [tool["name"] for tool in tools]
        state.tool_specs = body.get("tools") or []
        async with self._open_lock:
            self._opening = state
            try:
                result = await self.rpc.request("thread/start", {
                    "model": MODEL, "allowProviderModelFallback": False,
                    "baseInstructions": system, "developerInstructions": EXTERNAL_TOOL_INSTRUCTIONS,
                    "dynamicTools": tools, "environments": [],
                    "approvalPolicy": "never", "cwd": str(self.run_dir),
                    "config": {"model_reasoning_effort": EFFORT},
                })
                thread = result["thread"]
                state.thread_id = thread["id"]
                self.by_thread[state.thread_id] = state
                actual_model = result.get("model") or thread.get("model")
                if actual_model and actual_model != MODEL:
                    self.stop("Codex selected an unexpected model: " + actual_model)
                if state.fork_call_id:
                    _, marker_index = self._sdk_fork(body)
                    inherited = body["messages"][:marker_index]
                    await self.rpc.request("thread/inject_items", {
                        "threadId": state.thread_id, "items": _history_items(inherited),
                    })
                    state.user_inputs = [_input(message.get("content")) for message in inherited
                                         if message["role"] == "user"]
            finally:
                self._opening = None

    def _new_inputs(self, state, messages):
        inputs = [_input(message.get("content")) for message in messages if message["role"] == "user"]
        previous = state.user_inputs
        common = 0
        while common < min(len(previous), len(inputs)) and previous[common] == inputs[common]:
            common += 1
        if common < len(previous):
            # SDKs can append hook context to the most recent user text in place.
            old = previous[common]
            new = inputs[common] if common < len(inputs) else []
            if (common == len(previous) - 1 and len(old) == len(new) == 1
                    and old[0]["type"] == new[0]["type"] == "text"
                    and new[0]["text"].startswith(old[0]["text"])):
                delta = new[0]["text"][len(old[0]["text"]):]
                result = ([{"type": "text", "text": delta}] if delta else [])
                result += [part for value in inputs[common + 1:] for part in value]
            else:
                raise CodexBridgeError("SDK user history changed; refusing to replay it as a new prompt",
                                       "history_changed", 409)
        else:
            result = [part for value in inputs[common:] for part in value]
        state.user_inputs = inputs
        return result

    async def chat(self, body, headers=None, route=None):
        if self.stopped:
            raise CodexBridgeError(self.stop_reason, "experiment_stopped")
        await self.start()
        state = self.resolve_session(body, headers or {}, route)
        async with state.lock:
            if self.stopped or state.error:
                raise CodexBridgeError(state.error or self.stop_reason, "experiment_stopped")
            start_time = time.time()
            self.record("model_requests.jsonl", {
                "session": state.session_id, "role": state.role, "phase": state.phase,
                "requested_model": body.get("model"), "actual_model": MODEL,
                "fork_call_id": state.fork_call_id,
                "reasoning_effort": EFFORT, "request": body,
                "bridge_developer_instructions": EXTERNAL_TOOL_INSTRUCTIONS,
            })
            try:
                if not state.thread_id:
                    await self._open(state, body)
                elif (body.get("tools") or []) != state.tool_specs:
                    self.stop("SDK tool definitions changed inside an existing Codex thread")
                if self.stopped:
                    raise CodexBridgeError(self.stop_reason, "experiment_stopped")
                new_inputs = self._new_inputs(state, body["messages"])
                if new_inputs:
                    if state.active:
                        await self.rpc.request("turn/steer", {
                            "threadId": state.thread_id, "expectedTurnId": state.turn_id,
                            "input": new_inputs,
                        })
                    else:
                        state.active = True
                        result = await self.rpc.request("turn/start", {
                            "threadId": state.thread_id, "model": MODEL,
                            "effort": EFFORT, "input": new_inputs, "environments": [],
                        })
                        state.turn_id = result["turn"]["id"]
                for message in body["messages"]:
                    if message["role"] != "tool":
                        continue
                    tool = state.pending.get(message.get("tool_call_id"))
                    if tool and tool.served and not tool.completed:
                        await self.rpc.respond(tool.rpc_id, {
                            "success": not message.get("is_error", False),
                            "contentItems": [{"type": "inputText", "text": _text(message.get("content"))}],
                        })
                        tool.completed = True
                while True:
                    if self.stopped or state.error:
                        raise CodexBridgeError(state.error or self.stop_reason, "experiment_stopped")
                    if state.ready or not state.active:
                        break
                    # Commentary is buffered until a real tool call or final completion.
                    state.changed.clear()
                    await state.changed.wait()
                text = "\n".join(state.text)
                state.text.clear()
                calls = []
                while state.ready:
                    tool = state.pending[state.ready.popleft()]
                    tool.served = True
                    calls.append({"id": tool.call_id, "type": "function", "function": {
                        "name": tool.name, "arguments": (tool.arguments if isinstance(tool.arguments, str)
                                                          else json.dumps(tool.arguments)),
                    }})
                usage = None
                if state.usage_total is not None:
                    delta = {key: value - state.reported_usage.get(key, 0) for key, value in state.usage_total.items()
                             if isinstance(value, int)}
                    usage = {"prompt_tokens": delta.get("inputTokens", 0),
                             "completion_tokens": delta.get("outputTokens", 0),
                             "total_tokens": delta.get("totalTokens", 0),
                             "prompt_tokens_details": {"cached_tokens": delta.get("cachedInputTokens", 0)},
                             "completion_tokens_details": {"reasoning_tokens": delta.get("reasoningOutputTokens", 0)}}
                    state.reported_usage = dict(state.usage_total)
                message = {"role": "assistant", "content": text or None}
                if calls:
                    message["tool_calls"] = calls
                response = {"id": "chatcmpl-" + uuid.uuid4().hex, "object": "chat.completion",
                            "created": int(time.time()), "model": MODEL,
                            "choices": [{"index": 0, "message": message,
                                         "finish_reason": "tool_calls" if calls else "stop"}], "usage": usage}
                self.record("model_responses.jsonl", {
                    "session": state.session_id, "role": state.role, "phase": state.phase,
                    "thread_id": state.thread_id, "turn_id": state.turn_id,
                    "started_at": start_time, "elapsed_seconds": time.time() - start_time,
                    "response": response,
                })
                self.checkpoint()
                return response
            except CodexBridgeError as exc:
                state.error = str(exc)
                if _quota_error(str(exc)):
                    self.stop(str(exc))
                self.record("model_errors.jsonl", {
                    "session": state.session_id, "role": state.role, "phase": state.phase,
                    "elapsed_seconds": time.time() - start_time, "error": str(exc),
                    "code": exc.code, "usage": state.usage_total,
                })
                self.checkpoint()
                raise


async def _sse(response):
    choice = response["choices"][0]
    message = choice["message"]
    base = {key: response[key] for key in ("id", "created", "model")}
    base["object"] = "chat.completion.chunk"
    delta = {"role": "assistant"}
    if message.get("content"):
        delta["content"] = message["content"]
    chunks = [
        {**base, "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
    ]
    for index, tool in enumerate(message.get("tool_calls") or []):
        chunks.append({**base, "choices": [{"index": 0, "delta": {
            "tool_calls": [{"index": index, **tool}]}, "finish_reason": None}]})
    chunks.append({**base, "choices": [
        {"index": 0, "delta": {}, "finish_reason": choice["finish_reason"]}],
        "usage": response["usage"]})
    for chunk in chunks:
        yield "data: " + json.dumps(chunk) + "\n\n"
    yield "data: [DONE]\n\n"


def create_app(bridge):
    app = FastAPI()
    app.state.bridge = bridge

    @app.get("/status")
    async def status():
        return bridge.status()

    @app.post("/stop")
    async def stop(request: Request):
        body = await request.json()
        bridge.stop(body["reason"])
        return bridge.status()

    @app.get("/health")
    async def health():
        return {"status": "stopped" if bridge.stopped else "ok", "model": MODEL}

    @app.get("/v1/models")
    async def models():
        return {"object": "list", "data": [{"id": MODEL, "object": "model", "owned_by": "openai"}]}

    async def complete(request, route=None):
        body = await request.json()
        try:
            response = await bridge.chat(body, request.headers, route)
        except CodexBridgeError as exc:
            return JSONResponse({"error": {"message": str(exc), "type": exc.code, "code": exc.code}},
                                status_code=exc.status)
        if body.get("stream"):
            return StreamingResponse(_sse(response), media_type="text/event-stream")
        return JSONResponse(response)

    @app.post("/v1/chat/completions")
    async def chat(request: Request):
        return await complete(request)

    @app.post("/sessions/{session}/v1/chat/completions")
    async def session_chat(session: str, request: Request):
        return await complete(request, {"session": session})

    @app.post("/sessions/{session}/{role}/{phase}/v1/chat/completions")
    async def phase_chat(session: str, role: str, phase: str, request: Request):
        return await complete(request, {"session": session, "role": role, "phase": phase})

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--run_dir", required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    import uvicorn
    bridge = CodexBridge(args.run_dir)
    app = create_app(bridge)

    @app.on_event("shutdown")
    async def shutdown():
        await bridge.close()

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
