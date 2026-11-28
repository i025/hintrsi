#!/usr/bin/env python3
"""Return one structured decision from Codex exec; the original SDK runs tools."""

import argparse
import asyncio
import base64
import copy
import json
import logging
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

MODEL = "gpt-6.1-terra"
EFFORT = "low"
REQUEST_TIMEOUT = 235
DISABLED_FEATURES = (
    "shell_tool", "view_image", "multi_agent", "plugins", "apps",
    "skill_search", "skill_mcp_dependency_install", "remote_plugin",
    "code_mode", "code_mode_only", "computer_use", "browser_use",
    "in_app_browser", "image_generation", "goals", "sleep_tool",
    "workspace_dependencies", "tool_suggest", "hooks",
)


class CodexBridgeError(RuntimeError):
    def __init__(self, message: str, code: str = "codex_bridge_error", status: int = 503):
        super().__init__(message)
        self.code = code
        self.status = status


def _quota_error(value) -> bool:
    text = json.dumps(value).lower()
    return any(word in text for word in (
        "usagelimit", "usage_limit", "rate_limit", "ratelimit", "quota",
        "usage limit", "rate limit", "insufficient_quota", "limit reached",
        "credits exhausted", "out of credits", "too many requests",
    ))


INSTRUCTIONS = """You are the response generator for an agent running in a separate SDK container.
Your only task in this local process is to return the next assistant message as JSON.
The sdk_execution_context describes that external executor and its container access.
The input messages and tools belong to that external SDK agent. Paths mentioned in
those messages and tool arguments refer to the SDK container, not this local host.

The supplied tools are executed by the original SDK in its own container.
This response generator has no native tools. It only emits JSON.
External SDK permissions:
  A JSON request for Edit, Write, Bash, or another supplied tool is data returned to that
  executor; emitting it does not write to the local filesystem or require local approval.
  Follow all restrictions in the SDK conversation and actual external tool results.
  A teacher or read-only subagent must remain read-only. Never bypass a tool denial.
Do not ask for local write access to perform an external SDK task. If the conversation
permits code changes, request the appropriate external tools and use their observations.
If it forbids changes, preserve that restriction. Do not infer external permissions from
this process's sandbox, working directory, network access, or available native tools.

The messages array is the complete current conversation maintained by the original SDK.
Follow its system and developer instructions and chronological user, assistant, and tool
observations. Do not invent or omit prior observations. The tools array contains the
external operations available on this request, including their exact parameter schemas.
Return only the structured response required by the output schema. To request operations,
put their exact names in tool_calls. Represent each arguments object as
{"entries": [{"key": "parameter_name", "value": parameter_value}, ...]}.
Use ordinary JSON strings, numbers, booleans, nulls and arrays for values. Represent
nested object values with the same entries form recursively. Omit unused optional keys.
Do not JSON-encode argument objects or values into strings. The bridge serializes them
for the SDK, which executes the operations and supplies actual results in the next request.
Do not execute commands, inspect host files, browse, delegate, or call native tools here.
You may request multiple independent external operations in one response. Use an empty
tool_calls array only to end the entire SDK task with a final answer. Ending this local
CLI decision is separate from finishing that task: to continue the SDK task, return
its next tool calls in this JSON response. When an implementation is still unfinished,
request the next inspection, edit, or verification operation; do not terminate the SDK
task with only a plan, reproduction, or progress report. A final text answer is also
appropriate for a completed analysis/text task, an explicit stop, or a genuine blocker
established by actual observations. Respect tool_choice and the supplied role's limits.
Do not add task guidance, claim an operation ran, or guess its result.

SDK image content is supplied as actual image attachments to this request.
An sdk_image_attachment marker identifies its one-based attachment_index and
original message/content position. Associate each attachment with that SDK
message and tool result; images from earlier messages remain earlier observations.
The marker is transport metadata, not a text description of the image.
"""


def image_messages(messages, directory):
    """Keep SDK message structure and attach its image bytes to Codex exec."""
    attachments = []
    seen = {}

    def attach(url, location, message):
        header, encoded = url.split(',', 1)
        media_type = header.removeprefix('data:').removesuffix(';base64')
        extension = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp', 'image/gif': 'gif'}[media_type]
        if url not in seen:
            path = directory / ('image_' + str(len(attachments) + 1) + '.' + extension)
            content = base64.b64decode(encoded)
            path.write_bytes(content)
            seen[url] = len(attachments) + 1
            attachments.append({'attachment_index': len(attachments) + 1, 'path': str(path),
                                'media_type': media_type, 'bytes': len(content), 'associations': []})
        index = seen[url]
        attachments[index - 1]['associations'].append({'location': location, 'role': message.get('role'),
                                                      'tool_call_id': message.get('tool_call_id')})
        return {'type': 'sdk_image_attachment', 'attachment_index': index, 'media_type': media_type,
                'sdk_content_location': location}

    def convert(value, location, message):
        if isinstance(value, dict):
            if value.get('type') == 'image_url':
                return attach(value['image_url']['url'], location, message)
            if value.get('type') == 'image' and value.get('source', {}).get('type') == 'base64':
                source = value['source']
                return attach('data:' + source['media_type'] + ';base64,' + source['data'], location, message)
            return {key: convert(item, location + '.' + key, message) for key, item in value.items()}
        if isinstance(value, list):
            return [convert(item, location + '[' + str(i) + ']', message) for i, item in enumerate(value)]
        # LiteLLM represents a single-image tool result as a bare data URI.
        if isinstance(value, str) and value.startswith('data:image/'):
            return attach(value, location, message)
        return value

    converted = []
    for i, original in enumerate(messages):
        message = copy.deepcopy(original)
        message['content'] = convert(message.get('content'), 'messages[' + str(i) + '].content', message)
        converted.append(message)
    return converted, attachments


def action_schema(tools):
    names = [tool["function"]["name"] for tool in tools]
    name = {"type": "string"}
    if names:
        name["enum"] = names
    calls = {"type": "array", "items": {
        "type": "object", "properties": {
            "name": name, "arguments": {"$ref": "#/$defs/argument_object"},
        }, "required": ["name", "arguments"], "additionalProperties": False,
    }}
    if not names:
        calls["maxItems"] = 0
    return {"type": "object", "properties": {
        "content": {"type": "string"}, "tool_calls": calls,
    }, "required": ["content", "tool_calls"], "additionalProperties": False,
        "$defs": {
            "argument_object": {"type": "object", "properties": {
                "entries": {"type": "array", "items": {"type": "object", "properties": {
                    "key": {"type": "string"}, "value": {"$ref": "#/$defs/argument_value"},
                }, "required": ["key", "value"], "additionalProperties": False}},
            }, "required": ["entries"], "additionalProperties": False},
            "argument_value": {"anyOf": [
                {"type": "string"}, {"type": "number"}, {"type": "boolean"}, {"type": "null"},
                {"type": "array", "items": {"$ref": "#/$defs/argument_value"}},
                {"$ref": "#/$defs/argument_object"},
            ]},
        }}


def argument_value(value):
    """Convert structured key/value entries into the original SDK JSON values."""
    if isinstance(value, dict):
        return {entry["key"]: argument_value(entry["value"]) for entry in value["entries"]}
    if isinstance(value, list):
        return [argument_value(item) for item in value]
    return value


def context_error_message(event):
    error = event.get("error") or {}
    message = error.get("message", "")
    if error.get("codexErrorInfo") == "contextWindowExceeded":
        return message
    try:
        provider = json.loads(message).get("error", {})
    except (ValueError, AttributeError):
        return None
    if provider.get("code") in ("context_length_exceeded", "context_window_exceeded"):
        return message
    return None


def default_command():
    command = ["codex", "exec", "--ephemeral", "--json", "--skip-git-repo-check",
               "--ignore-user-config", "--ignore-rules", "--sandbox", "read-only",
               "--model", MODEL, "-c", "model_reasoning_effort=" + json.dumps(EFFORT)]
    command += ["-c", "agents.enabled=false", "-c", "features.multi_agent_v2=false"]
    for name in DISABLED_FEATURES:
        command += ["-c", "features." + name + "=false"]
    command += ["-c", 'web_search="disabled"', "-c", "project_doc_max_bytes=0",
                "-c", "mcp_servers={}", "-c", "skills.bundled.enabled=false",
                "-c", "tools.update_plan.enabled=false",
                "-c", "tools.experimental_request_user_input.enabled=false",
                "-c", "include_permissions_instructions=false",
                "-c", "include_environment_context=false",
                "-c", "include_collaboration_mode_instructions=false",
                "-c", "include_apps_instructions=false",
                "-c", "model_catalog_json=" + json.dumps(
                    str(Path(__file__).with_name("codex_model_catalog.json")))]
    return command


class CodexBridge:
    def __init__(self, run_dir, command=None):
        self.run_dir = Path(run_dir).resolve()
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.instructions = self.run_dir / "action_instructions.txt"
        self.instructions.write_text(INSTRUCTIONS, encoding="utf-8")
        self.command = command or default_command()
        self.processes = {}
        self.stopped = False
        self.stop_reason = None

    def record(self, filename, value):
        with (self.run_dir / filename).open("a", encoding="utf-8") as output:
            output.write(json.dumps({"timestamp": time.time(), **value}, ensure_ascii=False) + "\n")

    def status(self):
        return {"stopped": self.stopped, "stop_reason": self.stop_reason,
                "backend": "stateless_exec_action", "sessions": [],
                "active_requests": list(self.processes)}

    def stop(self, reason):
        self.stopped = True
        self.stop_reason = reason
        for process in self.processes.values():
            if process.returncode is None:
                process.terminate()

    async def close(self):
        self.stop("Exec action bridge closed")
        await asyncio.gather(*(process.wait() for process in list(self.processes.values())))

    async def execute(self, request_id, body, directory, attribution):
        schema = directory / "schema.json"
        schema.write_text(json.dumps(action_schema(body.get("tools") or [])), encoding="utf-8")
        output = directory / "final.json"
        command = self.command + ["-c", "model_instructions_file=" + json.dumps(str(self.instructions)),
                                  "--output-schema", str(schema), "--output-last-message", str(output), "-"]
        messages, images = image_messages(body["messages"], directory)
        for image in images:
            command[-1:-1] = ["--image", image["path"]]
        (directory / "image_attachments.json").write_text(json.dumps(images, indent=2), encoding="utf-8")
        (directory / "command.json").write_text(json.dumps(command, indent=2), encoding="utf-8")
        payload = {"messages": messages, "tools": body.get("tools") or []}
        if payload["tools"]:
            payload = {"sdk_execution_context": {
                "executor": "Original Claude Agent SDK in a separate task container",
                "permission_mode": "bypassPermissions",
                "container_repository": "/app",
                "container_repository_access": "read-only" if attribution["role"] == "teacher" else "read-write",
                "scope": ("Container access describes the external executor only. "
                          "Agent-specific restrictions in messages and actual tool denials still apply, "
                          "including read-only subagents. Local CLI filesystem rules do not describe this container."),
            }, **payload}
        for name in ("tool_choice", "parallel_tool_calls"):
            if name in body:
                payload[name] = body[name]
        (directory / "model_input.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        started = time.monotonic()
        thread_id = None
        usage = None
        error = None
        failed = False
        context_error = None
        with (directory / "stderr.log").open("wb") as stderr:
            process = await asyncio.create_subprocess_exec(
                *command, cwd=directory, stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=stderr, limit=16 * 1024 * 1024,
            )
            self.processes[request_id] = process
            try:
                if self.stopped:
                    raise CodexBridgeError(self.stop_reason, "experiment_stopped")
                process.stdin.write(json.dumps(payload, ensure_ascii=False).encode())
                await process.stdin.drain()
                process.stdin.close()
                async for line in process.stdout:
                    event = json.loads(line)
                    self.record("codex_events.jsonl", {**attribution, "request_id": request_id, "event": event})
                    kind = event["type"]
                    if kind == "thread.started":
                        thread_id = event["thread_id"]
                    elif kind == "turn.completed":
                        self.record("exec_turns.jsonl", {**attribution, "request_id": request_id,
                                    "thread_id": thread_id, "elapsed_seconds": time.monotonic() - started})
                        usage = event.get("usage")
                        if usage is not None:
                            delta = {"inputTokens": usage["input_tokens"],
                                     "outputTokens": usage["output_tokens"],
                                     "totalTokens": usage["input_tokens"] + usage["output_tokens"]}
                            for source, target in (("cached_input_tokens", "cachedInputTokens"),
                                                   ("reasoning_output_tokens", "reasoningOutputTokens")):
                                if source in usage:
                                    delta[target] = usage[source]
                            self.record("token_usage.jsonl", {**attribution, "request_id": request_id,
                                        "thread_id": thread_id, "usage": usage, "delta": delta})
                    elif kind in ("error", "turn.failed"):
                        error = json.dumps(event)
                        context_error = context_error_message(event) or context_error
                        failed = failed or kind == "turn.failed"
                        if _quota_error(event):
                            self.stop(error)
                    item = event.get("item") or {}
                    if item.get("type") in ("command_execution", "file_change", "mcp_tool_call", "web_search"):
                        error = "Unexpected native operation: " + item["type"]
                        self.stop(error)
                code = await process.wait()
                if (failed or code != 0) and context_error is not None and not self.stopped:
                    raise CodexBridgeError("prompt is too long: " + context_error,
                                           "context_length_exceeded", 400)
                if self.stopped or failed or code != 0:
                    raise CodexBridgeError(error or self.stop_reason or "Codex exec exited " + str(code),
                                           "exec_failed")
                return json.loads(output.read_text(encoding="utf-8")), usage, thread_id
            finally:
                if process.returncode is None:
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        process.kill()
                        await process.wait()
                self.processes.pop(request_id, None)

    async def chat(self, body, headers=None, route=None):
        if self.stopped:
            raise CodexBridgeError(self.stop_reason, "experiment_stopped")
        headers = headers or {}
        metadata = body.get("metadata") or {}
        route = route or {}
        attribution = {
            "session": route.get("session") or headers.get("x-experiment-session") or metadata.get("experiment_session") or "unlabelled",
            "role": route.get("role") or headers.get("x-experiment-role") or "student",
            "phase": route.get("phase") or headers.get("x-experiment-phase") or "solve",
        }
        request_id = uuid.uuid4().hex
        directory = self.run_dir / request_id
        directory.mkdir()
        started = time.time()
        self.record("model_requests.jsonl", {**attribution, "request_id": request_id,
                    "requested_model": body.get("model"), "actual_model": MODEL,
                    "reasoning_effort": EFFORT, "request": body,
                    "backend": "stateless_exec_action"})
        try:
            action, usage, thread_id = await asyncio.wait_for(
                self.execute(request_id, body, directory, attribution), timeout=REQUEST_TIMEOUT)
            allowed = {tool["function"]["name"] for tool in body.get("tools") or []}
            calls = []
            for tool in action["tool_calls"]:
                if tool["name"] not in allowed:
                    raise CodexBridgeError("Unavailable SDK tool: " + tool["name"], "invalid_action", 422)
                arguments = argument_value(tool["arguments"])
                if not isinstance(arguments, dict):
                    raise CodexBridgeError("SDK tool arguments must be an object", "invalid_action", 422)
                function = {"name": tool["name"], "arguments": json.dumps(arguments, ensure_ascii=False)}
                calls.append({"id": "call-" + uuid.uuid4().hex, "type": "function", "function": function})
            choice = body.get("tool_choice", "auto")
            if ((choice == "none" and calls) or (choice == "required" and not calls)
                    or (isinstance(choice, dict) and (not calls or any(
                        call["function"]["name"] != choice["function"]["name"] for call in calls)))):
                raise CodexBridgeError("Decision does not satisfy tool_choice", "invalid_action", 422)
            if body.get("parallel_tool_calls") is False and len(calls) > 1:
                raise CodexBridgeError("Parallel SDK tool calls are disabled", "invalid_action", 422)
            content = action["content"]
            if not content.strip() and not calls:
                raise CodexBridgeError("Codex returned an empty decision", "empty_action", 422)
            mapped_usage = None
            if usage is not None:
                mapped_usage = {"prompt_tokens": usage["input_tokens"],
                                "completion_tokens": usage["output_tokens"],
                                "total_tokens": usage["input_tokens"] + usage["output_tokens"]}
                if "cached_input_tokens" in usage:
                    mapped_usage["prompt_tokens_details"] = {"cached_tokens": usage["cached_input_tokens"]}
                if "reasoning_output_tokens" in usage:
                    mapped_usage["completion_tokens_details"] = {"reasoning_tokens": usage["reasoning_output_tokens"]}
            message = {"role": "assistant", "content": content or None}
            if calls:
                message["tool_calls"] = calls
            response = {"id": "chatcmpl-" + request_id, "object": "chat.completion",
                        "created": int(time.time()), "model": MODEL,
                        "choices": [{"index": 0, "message": message,
                                     "finish_reason": "tool_calls" if calls else "stop"}],
                        "usage": mapped_usage}
            self.record("model_responses.jsonl", {**attribution, "request_id": request_id,
                        "thread_id": thread_id, "elapsed_seconds": time.time() - started,
                        "response": response})
            return response
        except asyncio.TimeoutError as exc:
            self.record("model_errors.jsonl", {**attribution, "request_id": request_id,
                        "elapsed_seconds": time.time() - started, "error": "Backend response timeout",
                        "code": "backend_timeout"})
            raise CodexBridgeError("Model backend exceeded 235 seconds", "backend_timeout", 504) from exc
        except asyncio.CancelledError:
            self.record("model_errors.jsonl", {**attribution, "request_id": request_id,
                        "elapsed_seconds": time.time() - started, "error": "Request cancelled",
                        "code": "request_cancelled"})
            raise
        except (CodexBridgeError, ValueError, KeyError) as exc:
            self.record("model_errors.jsonl", {**attribution, "request_id": request_id,
                        "elapsed_seconds": time.time() - started, "error": str(exc)})
            if isinstance(exc, CodexBridgeError):
                raise
            raise CodexBridgeError(str(exc), "invalid_action", 422) from exc



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
    logging.basicConfig(level=logging.INFO)
    import uvicorn
    bridge = CodexBridge(args.run_dir)
    app = create_app(bridge)

    @app.on_event("shutdown")
    async def shutdown():
        await bridge.close()

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
