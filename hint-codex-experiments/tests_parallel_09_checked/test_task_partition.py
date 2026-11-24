"""Check independent task workers without models, containers, or network calls."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source_parallel_09_checked"))
import run_codex_experiments as paired  # noqa: E402


class TaskPartitionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.args = SimpleNamespace(
            output_base=self.directory.name, experiment_name="parallel_lane_2",
            stage="formal", api_base="http://model-bridge:8765",
            container_api_base="http://guest-model-bridge:8765",
            progress_base="http://progress:8766",
            container_progress_base="http://guest-progress:8766", dry_run=True,
            shared_first_attempt=True, continue_from="",
        )

    def tearDown(self):
        self.directory.cleanup()

    def test_partition_keeps_global_task_order_and_group_rotation(self):
        tasks = paired.TASKS
        self.args.task_ids = [tasks[4], tasks[2], tasks[4]]
        driver = paired.PairedExperiments(self.args)
        seen = []
        shared = SimpleNamespace(args=SimpleNamespace(teacher_state="initial-teacher.json"))

        def attempt(task, group, loop, number, reviews, review=True, shared_first=False):
            seen.append((task, group, number))
            entry = {"task": task, "group": group, "round": number, "solved": True,
                     "status": "solved", "origin_experiment": self.args.experiment_name,
                     "shared_with": ["H", "M"], "trajs_path": str(loop._trajs_path(number)),
                     "eval_path": str(loop._eval_path(number))}
            driver.state["attempts"].append(entry)
            return True

        with patch.object(driver, "prepare_shared", return_value=shared) as prepare, \
                patch.object(driver, "use_shared"), patch.object(driver, "review_attempt"), \
                patch.object(driver, "run_attempt", side_effect=attempt), \
                patch.object(driver, "close_teachers"), patch.object(paired, "write_reports"):
            self.assertEqual(driver.run(), 0)
        self.assertEqual(driver.state["tasks"], [tasks[2], tasks[4]])
        self.assertEqual(driver.state["task_partition"]["global_task_indices"],
                         {tasks[2]: 2, tasks[4]: 4})
        self.assertEqual(seen, [(tasks[2], "H", 1), (tasks[2], "I", 1), (tasks[2], "B", 1),
                                (tasks[4], "B", 1), (tasks[4], "H", 1), (tasks[4], "I", 1)])
        self.assertEqual(prepare.call_count, 2)
        self.assertFalse(any(row["group"] == "M" for row in driver.state["attempts"]))

    def test_workers_have_distinct_sessions_outputs_and_cleanup_labels(self):
        first = paired.PairedExperiments(self.args)
        other_args = SimpleNamespace(**{**vars(self.args), "experiment_name": "parallel_lane_3"})
        second = paired.PairedExperiments(other_args)
        task = paired.TASKS[1]
        self.assertNotEqual(first.output, second.output)
        self.assertNotEqual(first.loop(task, "H").args.codex_session,
                            second.loop(task, "H").args.codex_session)
        first.args.dry_run = False
        client = Mock()
        client.containers.list.return_value = []
        with patch("docker.from_env", return_value=client):
            first.close_teachers()
        client.containers.list.assert_called_once_with(all=True, filters={
            "label": "hint.experiment_name=parallel_lane_2"})
        client.close.assert_called_once_with()

    def test_partition_does_not_adopt_continuation_or_change_integration_scope(self):
        self.args.task_ids = [paired.TASKS[1]]
        self.args.continue_from = "/not-read/experiment_state.json"
        with self.assertRaisesRegex(ValueError, "without continuation"):
            paired.PairedExperiments(self.args)
        self.args.continue_from = ""
        self.args.stage = "integration"
        with self.assertRaisesRegex(ValueError, "formal stage"):
            paired.PairedExperiments(self.args)

    def test_main_honors_worker_docker_socket_and_sets_own_label(self):
        argv = ["run_codex_experiments.py", "--stage", "formal", "--experiment_name", "lane_4",
                "--task_ids", paired.TASKS[3], "--shared_first_attempt", "--dry_run"]
        worker = Mock()
        worker.run.return_value = 0
        socket = "unix:///task-specific/docker.sock"
        with patch.object(sys, "argv", argv), patch.dict(os.environ, {"DOCKER_HOST": socket}), \
                patch.object(paired, "PairedExperiments", return_value=worker) as constructor, \
                patch.object(paired.signal, "signal"):
            self.assertEqual(paired.main(), 0)
            self.assertEqual(os.environ["DOCKER_HOST"], socket)
            self.assertEqual(os.environ["HINT_EXPERIMENT_NAME"], "lane_4")
        args = constructor.call_args.args[0]
        self.assertEqual(args.task_ids, [paired.TASKS[3]])
        self.assertEqual(paired.ROOT, Path(__file__).resolve().parents[1])

    def test_parent_reads_complete_state_during_interrupted_worker_save(self):
        driver = paired.PairedExperiments(self.args)
        with patch.object(driver, "write_report"):
            driver.save()
        previous = json.loads(driver.summary_path.read_text())
        driver.state["status"] = "complete"
        observed = []

        def interrupted(path, contents, *args, **kwargs):
            with path.open("w") as stream:
                stream.write(contents[:len(contents) // 2])
                stream.flush()
                observed.append(json.loads(driver.summary_path.read_text()))
            raise OSError("Interrupted worker write")

        with patch.object(Path, "write_text", autospec=True, side_effect=interrupted), \
                patch.object(driver, "write_report"):
            with self.assertRaisesRegex(OSError, "Interrupted worker write"):
                driver.save()
        self.assertEqual(observed, [previous])
        self.assertEqual(json.loads(driver.summary_path.read_text()), previous)
        with patch.object(driver, "write_report"):
            driver.save()
        self.assertEqual(json.loads(driver.summary_path.read_text())["status"], "complete")
        self.assertEqual(list(driver.output.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
