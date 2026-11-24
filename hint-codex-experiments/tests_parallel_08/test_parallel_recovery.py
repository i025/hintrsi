"""Exercise interrupted-segment recovery without model or Docker calls."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source_parallel_08"))
import run_codex_experiments as paired
import run_parallel_experiments as parallel
import report_codex_experiments as reporting
from benchmark.deepswe.run_loop_by_hint import HintLoopOrchestrator


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.task = paired.TASKS[3]
        self.old_name = "codex_parallel_07_lane2"
        self.source_path = self.root / "old" / "experiment_state.json"
        self.source_path.parent.mkdir()
        hint = self.source_path.parent / "hint"
        hint.mkdir()
        for name, content in (("hint_output.md", "Full guidance\n"),
                              ("hint_compact_r1.md", "Compact guidance\n"),
                              ("golden_diff.diff", "Reference diff\n")):
            (hint / name).write_text(content)
        teacher = hint / "teacher_state.json"
        teacher.write_text(json.dumps({"session_id": "retained-sdk", "container_name": "old-teacher",
                                       "sdk_projects_archive": "old-backup.tar.gz"}))
        self.source = {"experiment": self.old_name, "stage": "formal", "status": "stopped",
            "tasks": [self.task], "shared_first_attempts": {}, "groups": list(paired.GROUPS),
            "attempts": [{"task": self.task, "group": "I", "round": 1, "status": "running",
                          "origin_experiment": self.old_name}],
            "shared": {self.task: {"teacher_state": str(teacher),
                "full_hint": str(hint / "hint_output.md"), "first_hint": str(hint / "hint_compact_r1.md"),
                "golden_diff": str(hint / "golden_diff.diff"), "origin_experiment": self.old_name}}}
        self.source_path.write_text(json.dumps(self.source))
        self.args = SimpleNamespace(output_base=str(self.root / "runs"), experiment_name="codex_parallel_08_lane2",
            stage="formal", shared_first_attempt=True, continue_from="", recover_from=str(self.source_path),
            recovered_evaluations="", task_ids=[self.task], dry_run=False, api_base="http://bridge",
            container_api_base="http://guest", progress_base="http://progress", container_progress_base="http://guest-progress")

    def tearDown(self):
        self.temporary.cleanup()

    def recovered_grade(self, solved=False):
        trajectory = self.root / "trajs.json"
        trajectory.write_text(json.dumps({"metadata": {}}))
        grade = dict(self.source["attempts"][0], status="solved" if solved else "not_solved", solved=solved,
                     trajs_path=str(trajectory), eval_path=str(self.root / "eval.json"),
                     eval={"reward": int(solved), "f2p_passed": 0, "f2p_total": 25}, review="pending")
        path = self.root / "recovered.json"
        path.write_text(json.dumps({"attempts": [grade]}))
        self.args.recovered_evaluations = str(path)
        return grade

    def test_original_hint_and_teacher_state_are_reused_without_overwriting_source(self):
        original = self.source_path.read_bytes()
        state_path = Path(self.source["shared"][self.task]["teacher_state"])
        teacher_bytes = state_path.read_bytes()
        driver = paired.PairedExperiments(self.args)
        shared = driver.continued_shared(self.task)
        self.assertNotEqual(Path(shared.args.teacher_state), state_path)
        self.assertEqual(Path(shared.args.teacher_state).read_bytes(), teacher_bytes)
        for group in ("H", "M", "I"):
            loop = driver.loop(self.task, group, shared.args.teacher_state)
            driver.use_shared(loop, shared)
            self.assertEqual(loop._hint_path_for_round(1).read_text(), "Compact guidance\n")
            self.assertEqual(loop.full_hint_path.read_text(), "Full guidance\n")
            if group == "M":
                self.assertEqual(loop.args.teacher_codex_session, f"{self.old_name}-{self.task}-shared")
        self.assertEqual(driver.state["attempts"], [])
        self.assertEqual(driver.state["excluded_prior_attempts"][0]["exclusion_reason"], "technical_interruption")
        self.assertEqual(self.source_path.read_bytes(), original)
        self.assertEqual(state_path.read_bytes(), teacher_bytes)

    def test_recovered_i1_is_reviewed_once_then_i2_uses_its_feedback(self):
        self.recovered_grade()
        driver = paired.PairedExperiments(self.args)
        calls = []
        compression = []
        def solve(loop, number, no_hint=False):
            calls.append(("solve", loop.summary["group"], number))
            return {"solved": True, "exit_code": 0, "eval": {"reward": 1}}
        def review(loop, number, **kwargs):
            calls.append(("review", loop.summary["group"], number))
            if loop.summary["group"] == "I" and number == 1:
                self.assertEqual(kwargs["trajs_override"], self.root / "trajs.json")
            output = loop._review_json_path(number)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text('{"corrective_hint":"Retained feedback"}')
            return True
        def compress(loop, number, reviews):
            compression.append((loop.summary["group"], number, list(reviews)))
            loop._hint_path_for_round(number).write_text("Updated guidance")
            return True
        with patch.object(driver, "check_running"), patch.object(driver, "register_online"), \
                patch.object(driver, "close_teachers"), patch.object(driver, "prepare_shared") as prepare, \
                patch.object(paired, "write_reports"), \
                patch.object(HintLoopOrchestrator, "step_solve", solve), \
                patch.object(HintLoopOrchestrator, "step_review", review), \
                patch.object(HintLoopOrchestrator, "step_compress", compress):
            self.assertEqual(driver.run(), 0)
        prepare.assert_not_called()
        self.assertEqual(calls[0], ("review", "I", 1))
        self.assertNotIn(("solve", "I", 1), calls)
        self.assertEqual(calls.count(("solve", "I", 2)), 1)
        self.assertEqual(calls.count(("review", "I", 1)), 1)
        self.assertEqual(compression[0][:2], ("I", 2))
        self.assertEqual(len(compression[0][2]), 1)
        self.assertIn("Retained feedback", compression[0][2][0].read_text())
        self.assertEqual(driver.state["attempts"][0]["review"], "done")
        self.assertEqual(driver.state["attempts"][0]["origin_experiment"], self.old_name)
        self.assertEqual(driver.state["excluded_prior_attempts"], [])

    def test_stopping_recovery_also_retains_borrowed_old_teacher(self):
        driver = paired.PairedExperiments(self.args)
        driver.state["status"] = "stopped"
        client = Mock()
        client.containers.list.return_value = []
        teacher = Mock()
        teacher.name = "old-teacher"
        client.containers.get.return_value = teacher
        with patch("docker.from_env", return_value=client):
            driver.close_teachers()
        client.containers.get.assert_called_once_with("old-teacher")
        teacher.stop.assert_called_once_with(timeout=10)
        teacher.remove.assert_not_called()
        self.assertEqual(driver.state["retained_containers"], ["old-teacher"])

    def test_current_segment_usage_includes_resumed_old_teacher_without_double_count(self):
        self.recovered_grade()
        driver = paired.PairedExperiments(self.args)
        driver.state.update(started_at=100, finished_at=200, status="complete")
        driver.state["recovery"]["new_costs_since"] = 100
        driver.save()
        bridge = self.root / "logs/bridge"
        bridge.mkdir(parents=True)
        teacher = f"{self.old_name}-{self.task}-shared"
        student = f"{self.args.experiment_name}-{self.task}-I-r2"
        records = [
            {"timestamp": 90, "session": teacher, "role": "teacher", "phase": "generate", "delta": {"totalTokens": 100}},
            {"timestamp": 110, "session": teacher, "role": "teacher", "phase": "review_r1", "delta": {"totalTokens": 20}},
            {"timestamp": 120, "session": student, "role": "student", "phase": "solve_r2", "delta": {"totalTokens": 30}},
            {"timestamp": 210, "session": teacher, "role": "teacher", "phase": "review_r2", "delta": {"totalTokens": 7}},
        ]
        (bridge / "token_usage.jsonl").write_text("".join(json.dumps(row) + "\n" for row in records))
        metrics = reporting.aggregate_experiment(driver.summary_path, bridge)
        self.assertEqual(metrics["totals"]["total_tokens"], 157)
        self.assertEqual(metrics["parallel_new_totals"]["total_tokens"], 50)
        self.assertEqual(metrics["origin_totals"][self.old_name]["total_tokens"], 127)
        self.assertEqual(metrics["origin_totals"][self.args.experiment_name]["total_tokens"], 30)
        self.assertEqual(metrics["included_experiments"], sorted([self.old_name, self.args.experiment_name]))

    def test_interrupted_student_cost_is_distinct_from_user_cancellation(self):
        driver = paired.PairedExperiments(self.args)
        driver.save()
        bridge = self.root / "bridge"
        bridge.mkdir()
        record = {"session": f"{self.old_name}-{self.task}-I-r1", "role": "student", "phase": "solve_r1",
                  "delta": {"totalTokens": 70}}
        (bridge / "token_usage.jsonl").write_text(json.dumps(record) + "\n")
        metrics = reporting.aggregate_experiment(driver.summary_path, bridge)
        self.assertEqual(metrics["technical_interruption_totals"]["total_tokens"], 70)
        self.assertEqual(metrics["cancelled_prior_totals"]["total_tokens"], 0)
        self.assertEqual(metrics["attempts"], [])

    def test_coordinator_recovers_fixed_queues_and_counts_shared_sources_once(self):
        self.recovered_grade()
        prior3 = self.root / "prior3/experiment_state.json"
        prior4 = self.root / "prior4/experiment_state.json"
        prior3.parent.mkdir()
        prior4.parent.mkdir()
        prior3.write_text(json.dumps({"experiment": "codex_formal_03", "status": "stopped",
                                     "stage": "formal", "tasks": list(paired.TASKS), "attempts": []}))
        baseline = {"experiment": "codex_formal_04", "status": "stopped", "stage": "formal",
            "groups": list(paired.GROUPS), "tasks": list(paired.TASKS), "max_rounds": 5,
            "continuation": {"source_experiment": "codex_formal_03", "state_path": str(prior3)},
            "attempts": [{"task": paired.TASKS[0], "group": group, "round": 1, "status": "solved"}
                         for group in ("B", "H", "I")], "shared": {}}
        prior4.write_text(json.dumps(baseline))
        lanes = [{"lane": lane, "docker_host": f"unix:///lane{lane}"} for lane in range(6)]
        manifest = self.root / "runtime.json"
        manifest.write_text(json.dumps({"lanes": lanes}))
        queues = parallel.task_queues(lanes)
        workers = []
        for lane in range(6):
            path = self.root / f"lane{lane}/experiment_state.json"
            path.parent.mkdir()
            task = queues[lane][0]
            source = json.loads(json.dumps(self.source))
            source.update(experiment=f"codex_parallel_07_lane{lane}", tasks=queues[lane])
            source["attempts"] = [{"task": task, "group": ("H", "H", "I", "B", "H", "H")[lane],
                "round": 1, "status": "running", "origin_experiment": source["experiment"]}]
            shared = dict(source["shared"][self.task], origin_experiment=source["experiment"])
            source["shared"] = {task: shared} if lane != 3 else {}
            path.write_text(json.dumps(source))
            workers.append({"lane": lane, "state_path": str(path), "task_ids": queues[lane]})
        old_master = self.root / "master07/experiment_state.json"
        old_master.parent.mkdir()
        old_master.write_text(json.dumps({"experiment": "codex_parallel_07", "status": "stopped",
            "stage": "formal", "tasks": list(paired.TASKS), "attempts": [], "workers": workers,
            "included_experiment_states": [row["state_path"] for row in workers],
            "continuation": {"source_experiment": "codex_formal_04", "state_path": str(prior4)}}))
        original = old_master.read_bytes()
        args = parallel.build_parser().parse_args([
            "--experiment_name", "codex_parallel_08", "--prior_state", str(prior4),
            "--runtime_manifest", str(manifest), "--output_base", str(self.root / "runs"),
            "--recover_from_parallel", str(old_master), "--recovered_evaluations", self.args.recovered_evaluations,
            "--bridge_dir", str(self.root / "bridge"), "--progress_dir", str(self.root / "progress")])
        driver = parallel.ParallelExperiments(args)
        for worker in driver.workers:
            command = driver.worker_command(worker)
            self.assertEqual(command[command.index("--recover_from") + 1], workers[worker["lane"]]["state_path"])
            self.assertEqual(worker["task_ids"], queues[worker["lane"]])
            worker_args = SimpleNamespace(**vars(self.args))
            worker_args.experiment_name = worker["experiment"]
            worker_args.output_base = str(driver.output / "lanes")
            worker_args.task_ids = worker["task_ids"]
            worker_args.recover_from = worker["recover_from"]
            child = paired.PairedExperiments(worker_args)
            child.save()
        driver.refresh()
        self.assertEqual(len(driver.state["excluded_prior_attempts"]), 5)
        ink = [row for row in driver.state["attempts"] if row["task"] == self.task]
        self.assertEqual(len(ink), 1)
        self.assertEqual(ink[0]["review"], "pending")
        catalog = reporting.experiment_catalog(driver.state_path, driver.state)
        origins = reporting.experiment_origins(driver.state, catalog)
        self.assertEqual(len(origins), 16)  # 03, 04, 07 + six lanes, 08 + six lanes.
        self.assertIn("codex_parallel_07_lane2", origins)
        self.assertIn("codex_formal_03", origins)
        self.assertEqual(old_master.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
