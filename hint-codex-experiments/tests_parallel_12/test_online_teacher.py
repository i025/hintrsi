"""Offline checks for the SDK's actual online-teacher hook class."""

import asyncio
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"source_parallel_12"))
from run_cc_sdk import OnlineTeacher  # noqa: E402


class OnlineTeacherTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.output=Path(self.tmp.name)
        self.transcript=self.output/"transcript.jsonl"
        self.transcript.write_text('{"type":"assistant","message":{"content":[]}}\n')
        with patch.dict(os.environ,{"APPEND_SYSTEM_PROMPT_FILE":""}):
            self.teacher=OnlineTeacher("http://127.0.0.1:8766/experiment/progress",
                                       "fixture-session","fixture-task",self.output)
        self.teacher.request_hint=Mock(return_value={"hint":"", "stopped":False})

    async def asyncTearDown(self):
        self.tmp.cleanup()

    def data(self,event,call_id,**extra):
        return {"hook_event_name":event,"tool_use_id":call_id,"tool_name":"Read",
                "tool_input":{"file_path":"/app/fixture.py"},
                "tool_response":"Actual file content", "transcript_path":str(self.transcript),**extra}

    async def event(self,event,call_id,**extra):
        return await self.teacher.on_tool(self.data(event,call_id,**extra),call_id,{})

    async def operation(self,number,event="PostToolUse"):
        call_id=f"call-{number}"
        await self.event("PreToolUse",call_id)
        return await self.event(event,call_id)

    async def test_large_batch_checks_at_45_then_65_not_46(self):
        for number in range(1,46):
            await self.event("PreToolUse",f"call-{number}")
        for number in range(1,45):
            await self.event("PostToolUse",f"call-{number}")
        self.teacher.request_hint.assert_not_called()
        await self.event("PostToolUse","call-45")
        self.assertEqual(self.teacher.tool_count,45)
        self.assertEqual(self.teacher.checks,1)
        self.assertEqual(self.teacher.next_check,65)
        await self.operation(46)
        self.assertEqual(self.teacher.request_hint.call_count,1)
        for number in range(47,65):
            await self.operation(number)
        self.assertEqual(self.teacher.request_hint.call_count,1)
        await self.operation(65)
        self.assertEqual(self.teacher.request_hint.call_count,2)

    async def test_subagent_ignored_and_main_agent_type_counts(self):
        await self.event("PreToolUse","child",agent_id="subagent-one",agent_type="Explore")
        await self.event("PostToolUse","child",agent_id="subagent-one",agent_type="Explore")
        self.assertEqual(self.teacher.tool_count,0)
        self.assertEqual(self.teacher.inflight,set())
        await self.event("PreToolUse","main",agent_type="custom-main")
        await self.event("PostToolUse","main",agent_type="custom-main")
        self.assertEqual(self.teacher.tool_count,1)

    async def test_no_hint_consumes_three_checks(self):
        for number in range(1,81):
            await self.operation(number)
        self.assertEqual(self.teacher.checks,3)
        self.assertEqual(self.teacher.request_hint.call_count,3)
        self.assertEqual([call.args[0]["tool_count"] for call in self.teacher.request_hint.call_args_list],
                         [20,40,60])

    async def test_hint_is_additional_context_without_replacing_result(self):
        self.teacher.request_hint.return_value={"hint":"Check whether both calling forms agree.",
                                               "stopped":False,"reason":"Private teacher analysis"}
        for number in range(1,20):
            await self.operation(number)
        result=await self.operation(20)
        self.assertEqual(result,{"hookSpecificOutput":{"hookEventName":"PostToolUse",
                         "additionalContext":"Teacher guidance:\nCheck whether both calling forms agree."}})
        self.assertNotIn("updatedToolOutput",str(result))
        self.assertNotIn("Private teacher analysis",str(result))
        sent=self.teacher.request_hint.call_args.args[0]
        self.assertIn("Actual file content",sent["trajectory"])
        self.assertIn('"tool_count": 20', (self.output/"online_teacher_state.json").read_text())

    async def test_tool_failure_counts_and_can_deliver_context(self):
        for number in range(1,20):
            await self.operation(number)
        self.teacher.request_hint.return_value={"hint":"Check the observed error.","stopped":False}
        result=await self.operation(20,event="PostToolUseFailure")
        self.assertEqual(self.teacher.tool_count,20)
        self.assertEqual(self.teacher.inflight,set())
        self.assertEqual(result["hookSpecificOutput"]["hookEventName"],"PostToolUseFailure")

    async def test_stopped_response_blocks_subsequent_operations(self):
        for number in range(1,20):
            await self.operation(number)
        self.teacher.request_hint.return_value={"hint":"Must not be delivered", "stopped":True,
                                               "stop_reason":"Account limit"}
        result=await self.operation(20)
        self.assertEqual(result,{"continue_":False,"stopReason":"Account limit"})
        self.assertEqual(await self.event("PreToolUse","next"),result)


if __name__=="__main__":
    unittest.main()
