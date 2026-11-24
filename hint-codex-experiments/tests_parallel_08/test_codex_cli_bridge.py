"""Offline tests: the real Codex executable and model are never invoked."""

import asyncio
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source_parallel_08"))
from codex_cli_bridge import (  # noqa: E402
    CodexBridge, CodexBridgeError, CodexRPCClient, EXTERNAL_TOOL_INSTRUCTIONS,
    MODEL, SDK_FORK_RESULT, SDK_FORK_MARKER, create_app, default_command,
)


def body(text="Solve this issue", tools=False):
    value = {"model": "claude-haiku-4-5-20251001", "messages": [
        {"role": "system", "content": "Original system instructions."},
        {"role": "user", "content": text},
    ]}
    if tools:
        value["tools"] = [{"type": "function", "function": {
            "name": "Read", "description": "Read the original container file",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
        }}]
    return value


def usage(input_tokens=100, output_tokens=20):
    return {"inputTokens": input_tokens, "cachedInputTokens": 60,
            "outputTokens": output_tokens, "reasoningOutputTokens": 8,
            "totalTokens": input_tokens + output_tokens}


class FakeRPC:
    def __init__(self):
        self.event_callback = None
        self.calls = []
        self.responses = []
        self.starts = 0
        self.on_turn = None
        self.on_response = None
        self.thread = None
        self.turn = None

    async def start(self):
        self.starts += 1
        return {}

    async def close(self):
        pass

    def emit(self, method, params=None, request_id=None):
        event = {"method": method, "params": params or {}}
        if request_id is not None:
            event["id"] = request_id
        self.event_callback(event)

    async def request(self, method, params=None):
        self.calls.append((method, params))
        if method == "thread/start":
            self.thread = "thread-" + str(sum(name == method for name, _ in self.calls))
            self.emit("thread/started", {"thread": {"id": self.thread}})
            return {"thread": {"id": self.thread}, "model": MODEL}
        if method == "turn/start":
            self.turn = "turn-" + str(sum(name == method for name, _ in self.calls))
            self.emit("turn/started", {"threadId": self.thread, "turn": {"id": self.turn}})
            if self.on_turn:
                self.on_turn(self)
            else:
                self.finish("A real public final answer")
            return {"turn": {"id": self.turn}}
        return {}

    async def respond(self, request_id, result):
        self.responses.append((request_id, result))
        if self.on_response:
            self.on_response(self, request_id)

    def tool(self, call_id="call-a", request_id=70, arguments=None):
        self.emit("item/tool/call", {
            "threadId": self.thread, "turnId": self.turn, "callId": call_id,
            "tool": "Read", "arguments": arguments or {"path": "/app/file.py"},
        }, request_id)

    def tokens(self, value=None):
        current = value or usage()
        self.emit("thread/tokenUsage/updated", {
            "threadId": self.thread, "turnId": self.turn,
            "tokenUsage": {"last": current, "total": current},
        })

    def finish(self, text="Done"):
        self.emit("item/completed", {"threadId": self.thread, "turnId": self.turn,
                                     "item": {"type": "agentMessage", "id": "answer", "text": text}})
        self.emit("turn/completed", {"threadId": self.thread, "turn": {
            "id": self.turn, "status": "completed"}})


class BridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.rpc = FakeRPC()
        self.bridge = CodexBridge(self.directory.name, rpc=self.rpc)
        self.route = {"session": "task-a", "role": "student", "phase": "solve"}

    async def asyncTearDown(self):
        await self.bridge.close()
        self.directory.cleanup()

    async def test_plain_text_and_original_system_are_separate(self):
        result = await self.bridge.chat(body(), route=self.route)
        self.assertEqual(result["model"], MODEL)
        self.assertEqual(result["choices"][0]["message"]["content"], "A real public final answer")
        self.assertIsNone(result["usage"])
        params = self.rpc.calls[0][1]
        self.assertEqual(params["baseInstructions"], "Original system instructions.")
        self.assertEqual(params["environments"], [])
        self.assertFalse(params["allowProviderModelFallback"])
        turn = next(params for method, params in self.rpc.calls if method == "turn/start")
        self.assertEqual(turn["input"], [{"type": "text", "text": "Solve this issue"}])
        self.assertEqual(turn["effort"], "low")

    async def test_external_tool_permissions_do_not_override_teacher_read_only(self):
        request = body()
        teacher_system = "The repository is read-only. Only write analysis artifacts under /tmp."
        request["messages"][0]["content"] = teacher_system
        await self.bridge.chat(request, route={**self.route, "role": "teacher", "phase": "generate"})
        params = next(params for method, params in self.rpc.calls if method == "thread/start")
        self.assertEqual(params["baseInstructions"], teacher_system)
        self.assertEqual(params["developerInstructions"], EXTERNAL_TOOL_INSTRUCTIONS)
        self.assertIn("role-specific read-only restrictions", params["developerInstructions"])
        self.assertIn("using their original permissions", params["developerInstructions"])
        self.assertEqual(params["environments"], [])
        self.assertNotIn(params.get("sandbox"), ("workspace-write", "danger-full-access"))
        command = default_command()
        for feature in ("shell_tool", "view_image", "multi_agent", "plugins", "apps"):
            self.assertIn(f"features.{feature}=false", command)
        logs = [json.loads(line) for line in (Path(self.directory.name) / "model_requests.jsonl").read_text().splitlines()]
        self.assertEqual(logs[0]["bridge_developer_instructions"], EXTERNAL_TOOL_INSTRUCTIONS)

    async def test_sdk_fork_keeps_parent_pending_and_seeds_child_reference_history(self):
        parent = body(tools=True)
        parent["model"] = MODEL
        parent["metadata"] = {"user_id": "same-sdk-parent-and-child"}
        parent["tools"].append({"type": "function", "function": {
            "name": "Agent", "description": "Delegate using the existing SDK",
            "parameters": {"type": "object"}}})

        def tool(rpc, thread, turn, call_id, rpc_id, name):
            rpc.emit("item/tool/call", {"threadId": thread, "turnId": turn,
                "callId": call_id, "tool": name, "arguments": {"path": "/app/fixture.txt"}}, rpc_id)

        self.rpc.on_turn = lambda rpc: tool(rpc, rpc.thread, rpc.turn,
            "parent-read" if rpc.thread == "thread-1" else "child-read",
            100 if rpc.thread == "thread-1" else 102, "Read")

        def response(rpc, rpc_id):
            if rpc_id == 100:
                tool(rpc, "thread-1", "turn-1", "parent-agent", 101, "Agent")
            elif rpc_id == 101:
                rpc.emit("turn/completed", {"threadId": "thread-1", "turn": {
                    "id": "turn-1", "status": "completed"}})
            elif rpc_id == 102:
                rpc.finish("Child final summary")

        self.rpc.on_response = response
        first = await self.bridge.chat(parent, route=self.route)
        parent["messages"] += [first["choices"][0]["message"],
            {"role": "tool", "tool_call_id": "parent-read", "content": "Original parent file contents"}]
        second = await self.bridge.chat(parent, route=self.route)
        parent["messages"] += [second["choices"][0]["message"]]
        parent_state = self.bridge.by_call["parent-agent"]
        parent_inputs = copy.deepcopy(parent_state.user_inputs)
        child = copy.deepcopy(parent)
        child["messages"] += [
            {"role": "tool", "tool_call_id": "parent-agent", "content": SDK_FORK_RESULT},
            {"role": "user", "content": SDK_FORK_MARKER + "\nExecute the child directive.\n</fork-boilerplate>"}]
        child_first = await self.bridge.chat(child, route=self.route)
        child_state = self.bridge.by_call["child-read"]
        self.assertIsNot(parent_state, child_state)
        self.assertEqual(child_state.fork_call_id, "parent-agent")
        self.assertTrue(parent_state.active)
        self.assertFalse(parent_state.pending["parent-agent"].completed)
        self.assertNotIn(101, [rpc_id for rpc_id, _ in self.rpc.responses])
        self.assertEqual(parent_state.user_inputs, parent_inputs)
        child["messages"] += [child_first["choices"][0]["message"],
            {"role": "tool", "tool_call_id": "child-read", "content": "Original child file contents"}]
        await self.bridge.chat(child, route=self.route)
        parent["messages"] += [{"role": "tool", "tool_call_id": "parent-agent",
                                "content": "The actual child final summary"}]
        await self.bridge.chat(parent, route=self.route)
        final_summary = [result for rpc_id, result in self.rpc.responses if rpc_id == 101]
        self.assertEqual(len(final_summary), 1)
        self.assertEqual(final_summary[0]["contentItems"][0]["text"], "The actual child final summary")
        self.assertEqual(sum(method == "thread/start" for method, _ in self.rpc.calls), 2)
        injects = [params for method, params in self.rpc.calls if method == "thread/inject_items"]
        self.assertEqual(len(injects), 1)
        self.assertEqual(injects[0]["threadId"], child_state.thread_id)
        seeded = injects[0]["items"]
        self.assertTrue(any(item.get("type") == "function_call" and item["call_id"] == "parent-read"
                            for item in seeded))
        self.assertTrue(any(item.get("type") == "function_call_output"
                            and item["output"] == "Original parent file contents" for item in seeded))
        self.assertTrue(any(item.get("type") == "function_call_output"
                            and item["output"] == SDK_FORK_RESULT for item in seeded))
        self.assertFalse(any(item.get("role") == "system" for item in seeded))
        self.assertNotIn(SDK_FORK_MARKER, json.dumps(seeded))
        child_turn = [params for method, params in self.rpc.calls if method == "turn/start"][1]
        self.assertEqual(child_turn["input"], [{"type": "text", "text": child["messages"][-3]["content"]}])
        self.assertEqual(child_turn["environments"], [])
        self.assertFalse(self.bridge.stopped)

    async def test_late_tool_queue_and_real_rpc_ids(self):
        self.rpc.on_turn = lambda rpc: rpc.tool()
        first_body = body(tools=True)
        first = await self.bridge.chat(first_body, route=self.route)
        self.assertEqual(first["choices"][0]["message"]["tool_calls"][0]["id"], "call-a")
        # A second request from the same model step arrives after HTTP response one.
        self.rpc.tool("call-b", 91, {"path": "/app/second.py"})
        second_body = {**first_body, "messages": first_body["messages"] + [
            first["choices"][0]["message"],
            {"role": "tool", "tool_call_id": "call-a", "content": "Real file contents A"},
        ]}
        second = await self.bridge.chat(second_body, route=self.route)
        self.assertEqual(second["choices"][0]["message"]["tool_calls"][0]["id"], "call-b")
        self.assertEqual(self.rpc.responses, [(70, {"success": True, "contentItems": [
            {"type": "inputText", "text": "Real file contents A"}]})])
        self.rpc.on_response = lambda rpc, request_id: rpc.finish() if request_id == 91 else None
        third_body = {**second_body, "messages": second_body["messages"] + [
            second["choices"][0]["message"],
            {"role": "tool", "tool_call_id": "call-b", "content": "Real file contents B"},
        ]}
        third = await self.bridge.chat(third_body, route=self.route)
        self.assertEqual(third["choices"][0]["finish_reason"], "stop")
        self.assertEqual([request_id for request_id, _ in self.rpc.responses], [70, 91])
        self.assertEqual(sum(method == "thread/start" for method, _ in self.rpc.calls), 1)
        self.assertEqual(sum(method == "turn/start" for method, _ in self.rpc.calls), 1)

    async def test_multiple_arrived_calls_and_out_of_order_results(self):
        def start(rpc):
            rpc.tool()
            rpc.tool("call-b", 80)
        self.rpc.on_turn = start
        request = body(tools=True)
        result = await self.bridge.chat(request, route=self.route)
        self.assertEqual(len(result["choices"][0]["message"]["tool_calls"]), 2)
        def after(rpc, request_id):
            if len(rpc.responses) == 2:
                rpc.finish()
        self.rpc.on_response = after
        request["messages"] += [result["choices"][0]["message"],
                                {"role": "tool", "tool_call_id": "call-b", "content": "B"},
                                {"role": "tool", "tool_call_id": "call-a", "content": "A", "is_error": True}]
        await self.bridge.chat(request, route=self.route)
        self.assertEqual([value[0] for value in self.rpc.responses], [80, 70])
        self.assertFalse(self.rpc.responses[1][1]["success"])

    async def test_concurrent_independent_sessions_keep_tool_results_and_usage_separate(self):
        turns = {}
        rpc_ids = {}

        def start(rpc):
            thread = rpc.calls[-1][1]["threadId"]
            turns[thread] = rpc.turn
            rpc_ids[thread] = 200 + len(turns)
            if len(turns) == 2:
                for target in reversed(turns):
                    rpc.emit("item/tool/call", {"threadId": target, "turnId": turns[target],
                        "callId": "call-" + target, "tool": "Read",
                        "arguments": {"path": "/app/" + target}}, rpc_ids[target])

        self.rpc.on_turn = start
        requests = [body("Independent task A", tools=True), body("Independent task B", tools=True)]
        routes = [{**self.route, "session": "lane-a-task"}, {**self.route, "session": "lane-b-task"}]
        first = await asyncio.wait_for(asyncio.gather(*[
            self.bridge.chat(request, route=route) for request, route in zip(requests, routes)]), 2)
        self.assertEqual(len(self.bridge.sessions), 2)
        for index, response in enumerate(first, 1):
            call = response["choices"][0]["message"]["tool_calls"][0]
            state = self.bridge.by_call[call["id"]]
            self.assertEqual(state.thread_id, f"thread-{index}")
            self.assertEqual(state.pending[call["id"]].rpc_id, 200 + index)
            self.assertFalse(state.pending[call["id"]].completed)
            requests[index - 1]["messages"] += [response["choices"][0]["message"],
                {"role": "tool", "tool_call_id": call["id"], "content": f"Real result {index}"}]

        def respond(rpc, request_id):
            if len(rpc.responses) == 2:
                for index, (thread, turn) in enumerate(turns.items(), 1):
                    value = usage(100 * index, 20)
                    rpc.emit("thread/tokenUsage/updated", {"threadId": thread, "turnId": turn,
                        "tokenUsage": {"last": value, "total": value}})
                    rpc.emit("item/completed", {"threadId": thread, "turnId": turn,
                        "item": {"type": "agentMessage", "id": "answer-" + thread,
                                 "text": "Final for " + thread}})
                    rpc.emit("turn/completed", {"threadId": thread, "turn": {
                        "id": turn, "status": "completed"}})

        self.rpc.on_response = respond
        second = await asyncio.wait_for(asyncio.gather(
            self.bridge.chat(requests[1], route=routes[1]),
            self.bridge.chat(requests[0], route=routes[0])), 2)
        self.assertEqual([(rpc_id, result["contentItems"][0]["text"])
                          for rpc_id, result in self.rpc.responses],
                         [(202, "Real result 2"), (201, "Real result 1")])
        self.assertEqual([item["choices"][0]["message"]["content"] for item in second],
                         ["Final for thread-2", "Final for thread-1"])
        self.assertEqual([item["usage"]["total_tokens"] for item in second], [220, 120])
        self.assertFalse(any(state.active for state in self.bridge.sessions.values()))
        self.assertFalse(self.bridge.stopped)

    async def test_quota_or_native_event_interrupts_both_live_independent_sessions(self):
        for trigger in ("quota", "native"):
            with self.subTest(trigger=trigger):
                rpc = FakeRPC()
                bridge = CodexBridge(Path(self.directory.name) / trigger, rpc=rpc)
                rpc.on_turn = lambda current: current.tool(
                    "call-" + current.thread, 300 + int(current.thread.rsplit("-", 1)[1]))
                requests = [body("Task A", tools=True), body("Task B", tools=True)]
                routes = [{**self.route, "session": trigger + "-lane-a"},
                          {**self.route, "session": trigger + "-lane-b"}]
                try:
                    initial = await asyncio.wait_for(asyncio.gather(*[
                        bridge.chat(request, route=route)
                        for request, route in zip(requests, routes)]), 2)
                    for request, response in zip(requests, initial):
                        message = response["choices"][0]["message"]
                        request["messages"] += [message, {"role": "tool",
                            "tool_call_id": message["tool_calls"][0]["id"],
                            "content": "Actual external tool output"}]
                    waiting = asyncio.Event()
                    rpc.on_response = lambda current, request_id: waiting.set() \
                        if len(current.responses) == 2 else None
                    tasks = [asyncio.create_task(bridge.chat(request, route=route))
                             for request, route in zip(requests, routes)]
                    await asyncio.wait_for(waiting.wait(), 2)
                    self.assertTrue(all(state.active for state in bridge.sessions.values()))
                    if trigger == "quota":
                        rpc.emit("error", {"threadId": "thread-1", "turnId": "turn-1",
                            "error": {"codexErrorInfo": "usageLimitExceeded",
                                      "message": "Usage limit reached"}})
                    else:
                        rpc.emit("item/started", {"threadId": "thread-1", "turnId": "turn-1",
                            "item": {"type": "commandExecution", "command": "forbidden-native"}})
                    results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 2)
                    self.assertTrue(all(isinstance(result, CodexBridgeError) for result in results))
                    self.assertTrue(bridge.stopped)
                    self.assertTrue(all(state.error for state in bridge.sessions.values()))
                    await asyncio.sleep(0)
                    self.assertEqual({(params["threadId"], params["turnId"])
                                      for method, params in rpc.calls if method == "turn/interrupt"},
                                     {("thread-1", "turn-1"), ("thread-2", "turn-2")})
                    count = len(rpc.calls)
                    with self.assertRaises(CodexBridgeError):
                        await bridge.chat(body("Do not resume"), route=routes[1])
                    self.assertEqual(len(rpc.calls), count)
                finally:
                    await bridge.close()

    async def test_guidance_steers_before_tool_result(self):
        self.rpc.on_turn = lambda rpc: rpc.tool()
        request = body(tools=True)
        first = await self.bridge.chat(request, route=self.route)
        self.rpc.on_response = lambda rpc, request_id: rpc.finish()
        request["messages"] += [first["choices"][0]["message"],
                                {"role": "tool", "tool_call_id": "call-a", "content": "File A"},
                                {"role": "user", "content": "Check the boundary case before changing code."}]
        await self.bridge.chat(request, route=self.route)
        steering = [params for method, params in self.rpc.calls if method == "turn/steer"]
        self.assertEqual(len(steering), 1)
        self.assertEqual(steering[0]["expectedTurnId"], "turn-1")
        self.assertEqual(steering[0]["input"][0]["text"], "Check the boundary case before changing code.")

    async def test_cumulative_usage_duplicates_and_teacher_phases(self):
        def start(rpc):
            rpc.tokens()
            rpc.tokens()  # An identical notification must not be counted twice.
            rpc.finish()
        self.rpc.on_turn = start
        route = {"session": "teacher-a", "role": "teacher", "phase": "generate"}
        request = body("Generate a hint")
        first = await self.bridge.chat(request, route=route)
        self.assertEqual(first["usage"]["total_tokens"], 120)
        request["messages"] += [{"role": "assistant", "content": "Done"},
                                {"role": "user", "content": "Review the student trajectory"}]
        self.rpc.on_turn = lambda rpc: (rpc.tokens(usage(150, 30)), rpc.finish())
        second = await self.bridge.chat(request, route={**route, "phase": "review"})
        self.assertEqual(second["usage"]["total_tokens"], 60)
        records = [json.loads(line) for line in (Path(self.directory.name) / "token_usage.jsonl").read_text().splitlines()]
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["phase"], "generate")
        self.assertEqual(records[1]["phase"], "review")
        self.assertEqual(records[1]["delta"]["totalTokens"], 60)
        self.assertEqual(sum(method == "thread/start" for method, _ in self.rpc.calls), 1)

    async def test_late_usage_is_not_lost_between_http_requests(self):
        self.rpc.on_turn = lambda rpc: rpc.tool()
        request = body(tools=True)
        first = await self.bridge.chat(request, route=self.route)
        self.assertIsNone(first["usage"])
        self.rpc.tokens()  # Usage arrives after the first HTTP response.
        self.rpc.on_response = lambda rpc, request_id: rpc.finish()
        request["messages"] += [first["choices"][0]["message"],
                                {"role": "tool", "tool_call_id": "call-a", "content": "File A"}]
        second = await self.bridge.chat(request, route=self.route)
        self.assertEqual(second["usage"]["total_tokens"], 120)

    async def test_auxiliary_model_and_source_have_separate_threads(self):
        request = body()
        request["model"] = "original-main-model"
        request["user"] = "sdk-main-session"
        await self.bridge.chat(request, route=self.route)
        auxiliary = body("Summarize the current conversation")
        auxiliary["user"] = "sdk-main-session"
        await self.bridge.chat(auxiliary, route=self.route)
        await self.bridge.chat(body("Another short auxiliary request"), route=self.route)
        self.assertEqual(sum(method == "thread/start" for method, _ in self.rpc.calls), 3)
        self.assertTrue(all(params["model"] == MODEL for method, params in self.rpc.calls
                            if method == "thread/start"))

    async def test_subagent_can_inherit_parent_model_and_source(self):
        self.rpc.on_turn = lambda rpc: rpc.tool("call-" + rpc.thread)
        request = body(tools=True)
        request["model"] = "original-main-model"
        request["user"] = "shared-sdk-session"
        parent = await self.bridge.chat(request, route=self.route)
        child = {**request, "messages": [request["messages"][0],
                                        {"role": "user", "content": "Inspect the parser for the parent"}]}
        result = await self.bridge.chat(child, route=self.route)
        self.assertEqual(sum(method == "thread/start" for method, _ in self.rpc.calls), 2)
        parent_call = parent["choices"][0]["message"]["tool_calls"][0]["id"]
        child_call = result["choices"][0]["message"]["tool_calls"][0]["id"]
        self.assertIsNot(self.bridge.by_call[parent_call], self.bridge.by_call[child_call])
        self.assertFalse(self.bridge.stopped)

    async def test_tool_set_cannot_change_on_persistent_teacher(self):
        request = body()
        request["model"] = "original-main-model"
        await self.bridge.chat(request, route=self.route)
        request["tools"] = body(tools=True)["tools"]
        request["messages"] += [{"role": "assistant", "content": "Answer"},
                                {"role": "user", "content": "Review"}]
        with self.assertRaises(CodexBridgeError):
            await self.bridge.chat(request, route=self.route)
        self.assertTrue(self.bridge.stopped)

    async def test_native_tool_stops_all_sessions(self):
        def start(rpc):
            rpc.emit("item/started", {"threadId": rpc.thread, "turnId": rpc.turn,
                                     "item": {"type": "commandExecution", "command": "touch forbidden"}})
        self.rpc.on_turn = start
        with self.assertRaises(CodexBridgeError):
            await self.bridge.chat(body(), route=self.route)
        self.assertTrue(self.bridge.status()["stopped"])
        count = len(self.rpc.calls)
        with self.assertRaises(CodexBridgeError):
            await self.bridge.chat(body(), route={**self.route, "session": "other"})
        self.assertEqual(len(self.rpc.calls), count)
        await asyncio.sleep(0)

    async def test_quota_saves_state_and_stops(self):
        def start(rpc):
            rpc.emit("error", {"threadId": rpc.thread, "turnId": rpc.turn,
                               "error": {"codexErrorInfo": "usageLimitExceeded", "message": "Usage limit reached"}})
        self.rpc.on_turn = start
        with self.assertRaises(CodexBridgeError):
            await self.bridge.chat(body(), route=self.route)
        state = json.loads((Path(self.directory.name) / "bridge_state.json").read_text())
        self.assertTrue(state["stopped"])
        self.assertIsNone(state["sessions"][0]["usage"])
        await asyncio.sleep(0)

    async def test_fastapi_url_route_sse_and_status(self):
        app = create_app(self.bridge)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/sessions/url-teacher/teacher/generate/v1/chat/completions",
                                         json={**body(), "stream": True})
            self.assertEqual(response.status_code, 200)
            self.assertIn("data: [DONE]", response.text)
            events = [json.loads(line[6:]) for line in response.text.splitlines()
                      if line.startswith("data: {")]
            self.assertEqual(events[0]["choices"][0]["delta"]["role"], "assistant")
            state = (await client.get("/status")).json()
            self.assertEqual(state["sessions"][0]["session"], "url-teacher")
            self.assertEqual(state["sessions"][0]["role"], "teacher")
            response = await client.post("/sessions/plain/v1/chat/completions", json=body())
            self.assertEqual(response.json()["model"], MODEL)

    async def test_stop_endpoint_interrupts_and_rejects_further_model_calls(self):
        self.rpc.on_turn = lambda rpc: rpc.tool("call-" + rpc.thread)
        await self.bridge.chat(body(tools=True), route=self.route)
        await self.bridge.chat(body(tools=True), route={**self.route, "session": "task-b"})
        transport = httpx.ASGITransport(app=create_app(self.bridge))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/stop", json={"reason": "Teacher progress deadline exceeded"})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["stopped"])
            await asyncio.sleep(0)
            interruptions = [params for method, params in self.rpc.calls if method == "turn/interrupt"]
            self.assertEqual(interruptions, [{"threadId": "thread-1", "turnId": "turn-1"},
                                             {"threadId": "thread-2", "turnId": "turn-2"}])
            calls = len(self.rpc.calls)
            response = await client.post("/sessions/new/v1/chat/completions", json=body())
            self.assertEqual(response.status_code, 503)
            await client.post("/stop", json={"reason": "A second progress error"})
            await asyncio.sleep(0)
            self.assertEqual(len(self.rpc.calls), calls)
            self.assertEqual(self.bridge.stop_reason, "Teacher progress deadline exceeded")

    def test_native_config_uses_known_keys(self):
        command = default_command()
        self.assertIn("features.shell_tool=false", command)
        self.assertIn("features.view_image=false", command)
        self.assertNotIn("features.skills=false", command)


class RPCClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_large_jsonl_tool_request_does_not_break_the_reader(self):
        script = """
import json, sys
for line in sys.stdin:
    request = json.loads(line)
    if 'method' not in request or 'id' not in request:
        continue
    if request['method'] == 'test/large':
        print(json.dumps({'id': 'large-tool-rpc', 'method': 'item/tool/call', 'params': {
            'threadId': 'thread-large', 'turnId': 'turn-large', 'callId': 'call-large',
            'tool': 'Write', 'arguments': {'content': 'x' * 200000}}}), flush=True)
    print(json.dumps({'id': request['id'], 'result': {'method': request['method']}}), flush=True)
"""
        events = []
        client = CodexRPCClient(command=[sys.executable, "-u", "-c", script],
                                event_callback=events.append)
        try:
            await asyncio.wait_for(client.start(), timeout=5)
            await asyncio.wait_for(client.request("test/large"), timeout=5)
            event = next(value for value in events if value.get("method") == "item/tool/call")
            self.assertGreater(len(json.dumps(event)), 128 * 1024)
            self.assertEqual(len(event["params"]["arguments"]["content"]), 200000)
            self.assertEqual((await client.incoming.get())["id"], "large-tool-rpc")
            await client.respond("large-tool-rpc", {"success": True, "contentItems": []})
            response = await asyncio.wait_for(client.request("test/after"), timeout=5)
            self.assertEqual(response["method"], "test/after")
        finally:
            await client.close()

    async def test_stdio_round_trip_with_python_mock(self):
        script = """
import json, sys
for line in sys.stdin:
    request = json.loads(line)
    if 'id' not in request:
        continue
    if 'method' not in request:
        continue
    result = {'method': request['method'], 'params': request.get('params')}
    print(json.dumps({'id': request['id'], 'result': result}), flush=True)
"""
        client = CodexRPCClient(command=[sys.executable, "-u", "-c", script])
        try:
            initialized = await client.start()
            self.assertEqual(initialized["method"], "initialize")
            result = await client.request("model/list", {"includeHidden": False})
            self.assertEqual(result["method"], "model/list")
        finally:
            await client.close()


if __name__ == "__main__":
    unittest.main()
