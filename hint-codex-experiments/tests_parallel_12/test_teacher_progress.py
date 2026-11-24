"""Offline teacher-service tests; no real CLI, HTTP service, or model is called."""

import asyncio
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source_parallel_12"))
from teacher_progress import MODEL, TeacherProgress, create_app  # noqa: E402


def registration(session="student-one"):
    return {"session": session, "task": "sample-task", "problem_statement": "Issue",
            "golden_diff": "PRIVATE REFERENCE", "current_hint": "Initial guidance",
            "api_base": "http://127.0.0.1:8765/sessions/old/teacher/initial/v1",
            "api_key": "codex-local", "model": MODEL}


def payload(session="student-one", count=20):
    return {"session": session, "task": "sample-task", "trajectory": "Observed student tools",
            "current_hint": "Untrusted request field", "tool_count": count}


class TeacherTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.candidate = Mock(return_value={"needs_hint": True, "corrective_hint": "Check scope."})
        self.screen = Mock(return_value={"deliver": True, "hint": "Can both calling forms agree?",
                                         "reason": "Observed difference"})
        self.stopper = Mock()
        self.bridge_status = {"stopped": False, "stop_reason": None}
        self.service = TeacherProgress(self.tmp.name, candidate=self.candidate, screen=self.screen,
                                       status_reader=lambda: dict(self.bridge_status), stopper=self.stopper)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(self.service)),
                                        base_url="http://test")
        response = await self.client.post("/experiment/register", json=registration())
        self.assertEqual(response.status_code, 200)

    async def asyncTearDown(self):
        await self.client.aclose()
        self.tmp.cleanup()

    async def progress(self, count=20):
        response = await self.client.post("/experiment/progress", json=payload(count=count))
        self.assertEqual(response.status_code, 200)
        return response.json()

    async def test_registered_context_and_fresh_candidate_screen(self):
        result = await self.progress()
        self.assertEqual(result["hint"], "Can both calling forms agree?")
        self.assertFalse(result["stopped"])
        args, kwargs = self.candidate.call_args
        self.assertEqual(args[:2], ("Issue", "PRIVATE REFERENCE"))
        self.assertEqual(args[3], "Initial guidance")
        self.assertEqual(kwargs["model"], MODEL)
        self.assertLessEqual(kwargs["request_timeout"], 600)
        self.assertNotEqual(kwargs["api_base"], self.screen.call_args.kwargs["api_base"])
        self.assertEqual(self.screen.call_args.kwargs["previous_hints"], ["Initial guidance"])
        self.assertNotIn("PRIVATE REFERENCE", result["hint"])
        records = [json.loads(line) for line in (Path(self.tmp.name)/"progress.jsonl").read_text().splitlines()]
        self.assertEqual(records[0]["decision"], "delivered")
        self.assertEqual(records[0]["screen"]["reason"], "Observed difference")

    async def test_no_hint_consumes_three_checks(self):
        self.candidate.return_value = {"needs_hint": False, "corrective_hint": ""}
        for count in (20, 40, 60, 80):
            result = await self.progress(count)
            self.assertEqual(result["hint"], "")
        self.assertEqual(result["checks"], 3)
        self.assertEqual(self.candidate.call_count, 3)
        self.screen.assert_not_called()

    async def test_screen_rejection_and_cumulative_hints(self):
        await self.progress()
        self.screen.return_value = {"deliver": False, "hint": "This must not be sent", "reason": "Recipe"}
        result = await self.progress(40)
        self.assertEqual(result["hint"], "")
        self.assertEqual(self.screen.call_args.kwargs["previous_hints"],
                         ["Initial guidance", "Can both calling forms agree?"])
        self.assertEqual(self.candidate.call_args.kwargs["previous_hints"],
                         ["Can both calling forms agree?"])

    async def test_final_word_and_language_limits(self):
        self.screen.return_value = {"deliver": True, "hint": " ".join(["word"]*101)}
        self.assertEqual((await self.progress())["hint"], "")
        self.screen.return_value = {"deliver": True, "hint": "中文提示"}
        self.assertEqual((await self.progress(40))["hint"], "")

    async def test_teacher_failure_stops_student_without_more_calls(self):
        self.candidate.side_effect = TimeoutError("Deadline reached")
        result = await self.progress()
        self.assertTrue(result["stopped"])
        self.assertIn("Deadline reached", result["stop_reason"])
        self.assertEqual(result["hint"], "")
        await self.progress(40)
        self.assertEqual(self.candidate.call_count, 1)
        self.stopper.assert_called_once_with(result["stop_reason"])

    async def test_global_quota_stop_is_merged(self):
        self.bridge_status.update(stopped=True, stop_reason="Account quota reached")
        result = (await self.client.get("/experiment/status", params={"session":"student-one"})).json()
        self.assertTrue(result["stopped"])
        self.assertEqual(result["stop_reason"], "Account quota reached")
        self.assertEqual((await self.progress())["hint"], "")
        self.candidate.assert_not_called()

    async def test_status_counts_current_wait_and_deadline_remainder(self):
        entered, release = threading.Event(), threading.Event()
        def candidate(*args, **kwargs):
            entered.set()
            release.wait(2)
            return {"needs_hint": True, "corrective_hint": "Check scope."}
        self.candidate.side_effect = candidate
        task = asyncio.create_task(self.progress())
        await asyncio.to_thread(entered.wait, 2)
        await asyncio.sleep(.02)
        status = (await self.client.get("/experiment/status", params={"session":"student-one"})).json()
        self.assertGreater(status["teacher_wait_seconds"], 0)
        release.set()
        await task
        self.assertLess(self.screen.call_args.kwargs["request_timeout"],
                        self.candidate.call_args.kwargs["request_timeout"])

    async def test_total_deadline_prevents_screen_and_stops(self):
        self.service.check_timeout = .005
        def delayed(*args, **kwargs):
            time.sleep(.01)
            return {"needs_hint": True, "corrective_hint": "Check scope."}
        self.candidate.side_effect = delayed
        result = await self.progress()
        self.assertTrue(result["stopped"])
        self.screen.assert_not_called()

    async def test_late_no_hint_still_stops_at_deadline(self):
        self.service.check_timeout = .005
        def delayed(*args, **kwargs):
            time.sleep(.01)
            return {"needs_hint": False, "corrective_hint": ""}
        self.candidate.side_effect = delayed
        result = await self.progress()
        self.assertTrue(result["stopped"])
        self.stopper.assert_called_once()

    async def test_unregistered_control_session_has_zero_wait(self):
        response = await self.client.get("/experiment/status", params={"session":"baseline-B-r1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["teacher_wait_seconds"], 0)
        self.assertFalse(response.json()["stopped"])

    async def test_unregistered_control_session_sees_global_stop(self):
        self.bridge_status.update(stopped=True, stop_reason="Global account limit")
        response = await self.client.get("/experiment/status", params={"session":"control-H-r1"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["stopped"])
        self.assertEqual(response.json()["stop_reason"], "Global account limit")

    async def test_http_timeout_is_forwarded_without_retry(self):
        import review_hint_traj
        with patch.object(review_hint_traj.litellm, "completion", side_effect=TimeoutError("Read timeout")) as completion:
            with self.assertRaises(RuntimeError):
                review_hint_traj.generate_progress_hint("Issue", "GT", "Trace", "Hint", request_timeout=12)
        self.assertEqual(completion.call_count, 1)
        self.assertEqual(completion.call_args.kwargs["timeout"], 12)
        self.assertEqual(completion.call_args.kwargs["num_retries"], 0)


if __name__ == "__main__":
    unittest.main()
