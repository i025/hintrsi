"""Check injection reporting against actual prompt text, including SDK reminders."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source_parallel_13"))
import run_multi_turn_loop as runner_module


class PromptInjectionReportingTests(unittest.TestCase):
    def capture(self, hint, actual):
        with tempfile.TemporaryDirectory() as directory:
            runner = runner_module.MultiTurnLoopRunner.__new__(runner_module.MultiTurnLoopRunner)
            runner.container = Mock()
            runner.infer_dir = Path(directory)
            runner.compact_hint_path = None
            if hint is not None:
                runner.compact_hint_path = Path(directory) / "hint.md"
                runner.compact_hint_path.write_text(hint)
            (Path(directory) / "system_prompt_actual.json").write_text(json.dumps({
                "char_count": len(actual), "contains_system_reminder": True,
                "system_prompt": actual,
            }))
            with patch.object(runner_module, "copy_from_container", return_value=True), \
                    self.assertLogs(runner_module.log, level="INFO") as logs:
                runner.collect_artifacts(1)
            return "\n".join(logs.output)

    def test_baseline_sdk_reminder_is_not_reported_as_a_hint(self):
        logs = self.capture(None, "<system-reminder>SDK context only</system-reminder>")
        self.assertIn("未请求初始 Hint", logs)
        self.assertNotIn("已确认完整 Hint", logs)
        self.assertNotIn("hint 已加载", logs)

    def test_actual_injected_content_is_reported(self):
        logs = self.capture("Inspect both endpoint conventions.",
                            "Preset\n<system-reminder>Inspect both endpoint conventions.</system-reminder>")
        self.assertIn("已确认完整 Hint 内容", logs)

    def test_unrelated_or_empty_reminder_does_not_confirm_injection(self):
        for hint in ("Inspect both endpoint conventions.", ""):
            with self.subTest(hint=hint):
                logs = self.capture(hint, "<system-reminder>SDK context only</system-reminder>")
                self.assertIn("未找到请求的 Hint 内容", logs)
                self.assertNotIn("已确认完整 Hint", logs)


if __name__ == "__main__":
    unittest.main()
