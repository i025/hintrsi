"""Offline Claude tool-result translation and Codex delivery fixtures."""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

import httpx
import litellm
import openai
from litellm.llms.anthropic.experimental_pass_through.adapters.transformation import LiteLLMAnthropicMessagesAdapter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source_parallel_13"))
sys.path.insert(0, str(ROOT / "source_parallel_13" / "litellm_proxy"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import streaming_fix  # noqa: E402
from codex_cli_bridge import CodexBridge, MODEL  # noqa: E402
from test_codex_cli_bridge import ObservedBridge, body  # noqa: E402

streaming_fix.apply()


def translated(separate=False, error=True):
    result = {"type":"tool_result", "tool_use_id":"call-a", "is_error":error,
              "content":"Original tool output"}
    content = [result]
    reminder = "<system-reminder>TEACHER_HINT_MARKER</system-reminder>"
    if separate:
        content.append({"type":"text", "text":reminder})
    else:
        result["content"] += "\n" + reminder
    return LiteLLMAnthropicMessagesAdapter().translate_anthropic_messages_to_openai(
        [{"role":"user", "content":content}], model=MODEL)


class TranslationTests(unittest.TestCase):
    def test_preserves_exact_error_flag_and_original_result(self):
        for value in (True, False):
            messages = translated(error=value)
            self.assertIs(messages[0]["is_error"], value)
            self.assertIn("Original tool output", messages[0]["content"])
            self.assertIn("TEACHER_HINT_MARKER", messages[0]["content"])

    def test_inline_system_keeps_position_and_top_level_system(self):
        raw={"model":MODEL,"max_tokens":100,"system":"Original top-level system", "messages":[
            {"role":"user","content":"Original user prompt"},
            {"role":"system","content":[{"type":"text","text":"Initial context"}]},
            {"role":"assistant","content":[{"type":"tool_use","id":"call-a","name":"Read","input":{}}]},
            {"role":"user","content":[{"type":"tool_result","tool_use_id":"call-a","is_error":True,"content":"Actual failure"}]},
            {"role":"system","content":[{"type":"text","text":"TEACHER_HINT_MARKER"}]},
        ]}
        wire,_=LiteLLMAnthropicMessagesAdapter().translate_anthropic_to_openai(raw)
        messages=wire["messages"]
        self.assertEqual([message["role"] for message in messages],["system","user","user","assistant","tool","user"])
        self.assertEqual(messages[0]["content"],"Original top-level system")
        self.assertIn("TEACHER_HINT_MARKER",json.dumps(messages[-1]))
        self.assertIs(messages[-2]["is_error"],True)

    def test_error_and_context_survive_real_litellm_openai_serialization(self):
        sent=[]
        def handle(request):
            sent.append(json.loads(request.content))
            return httpx.Response(200, json={"id":"fixture", "object":"chat.completion", "created":1,
                "model":MODEL, "choices":[{"index":0,"message":{"role":"assistant","content":"Fixture"},
                    "finish_reason":"stop"}], "usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}})
        client = openai.OpenAI(api_key="fixture", base_url="http://fixture/v1",
                              http_client=httpx.Client(transport=httpx.MockTransport(handle)))
        messages=[{"role":"user","content":"Run the fixture"},
                  {"role":"assistant","content":None,"tool_calls":[{"id":"call-a","type":"function",
                    "function":{"name":"Read","arguments":"{}"}}]}] + translated(separate=True)
        try:
            litellm.completion(model="openai/"+MODEL, messages=messages, client=client,
                               api_base="http://fixture/v1", api_key="fixture", num_retries=0)
        finally:
            client.close()
        self.assertEqual(len(sent),1)
        tool=next(message for message in sent[0]["messages"] if message["role"]=="tool")
        self.assertIs(tool["is_error"],True)
        self.assertEqual(tool["content"],"Original tool output")
        self.assertIn("TEACHER_HINT_MARKER",json.dumps(sent[0]["messages"]))


class DeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self,separate):
        with tempfile.TemporaryDirectory() as directory:
            bridge=ObservedBridge(directory)
            request=body()
            request["messages"] += translated(separate=separate)
            route={"session":"fixture", "role":"student", "phase":"solve"}
            await bridge.chat(request,route=route)
            await bridge.chat(request,route=route)
            captures = [json.loads(p.read_text()) for p in Path(directory).glob("*/fixture_capture.json")]
            self.assertEqual(len(captures), 2)
            for capture in captures:
                messages = capture["payload"]["messages"]
                self.assertEqual(messages, request["messages"])
                self.assertIs(messages[-1 if not separate else -2]["is_error"], True)
                self.assertEqual(json.dumps(messages).count("TEACHER_HINT_MARKER"), 1)
            await bridge.close()

    async def test_context_inside_result_is_delivered_once(self):
        await self.run_case(False)

    async def test_separate_context_is_delivered_once(self):
        await self.run_case(True)


if __name__=="__main__":
    unittest.main()
