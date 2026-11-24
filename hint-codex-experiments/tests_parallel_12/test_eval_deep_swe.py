"""An empty submission must reach the verifier; an absent submission must not."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "source_parallel_12/benchmark/deepswe/eval_deep_swe.py"
SPEC = importlib.util.spec_from_file_location("empty_patch_evaluator", SOURCE)
evaluator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluator)


class SubmissionTests(unittest.TestCase):
    def test_empty_submission_runs_verifier_and_persists_reward(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task_id = "kea-atomic-signal-selectors"
            patches = root / "patches"
            submission = patches / task_id / "patch.diff"
            submission.parent.mkdir(parents=True)
            submission.write_bytes(b"")
            output = root / "evaluation"
            task = root / "task"
            client = object()
            graded = {"instance_id": task_id, "reward": {"reward": 0}, "exit_code": 0}
            with mock.patch.object(evaluator.docker, "from_env", return_value=client), \
                    mock.patch.object(evaluator, "build_verifier_image", return_value="kea-verifier") as build, \
                    mock.patch.object(evaluator, "run_verifier", return_value=graded) as run:
                result = evaluator.evaluate_task(task, task_id, patches, output, delete_image=False)
            build.assert_called_once_with(client, task, task_id)
            run.assert_called_once_with(client, task_id, "kea-verifier", b"")
            self.assertEqual(result["reward"]["reward"], 0)
            self.assertEqual(json.loads((output / task_id / "eval_result.json").read_text()), graded)

    def test_missing_submission_stays_no_patch_and_skips_verifier(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task_id = "kea-atomic-signal-selectors"
            output = root / "evaluation"
            with mock.patch.object(evaluator.docker, "from_env", return_value=object()), \
                    mock.patch.object(evaluator, "build_verifier_image") as build, \
                    mock.patch.object(evaluator, "run_verifier") as run:
                result = evaluator.evaluate_task(root / "task", task_id, root / "patches", output,
                                                 delete_image=False)
            self.assertEqual(result, {"instance_id": task_id, "reward": None, "status": "no_patch"})
            build.assert_not_called()
            run.assert_not_called()
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
