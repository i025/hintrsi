"""Check experiment scheduling and isolation without running models or Docker."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source_parallel_12"))
from benchmark.deepswe import run_loop_by_hint as hint_loop  # noqa: E402
import run_codex_experiments as paired  # noqa: E402
import report_codex_experiments as reporting  # noqa: E402


def outcome(solved=False):
    return {"solved": solved, "exit_code": 0 if solved else 1,
            "eval": {"reward": 1 if solved else 0, "solved": solved}}


class BaselineRoundsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.directory.cleanup()

    def loop(self, extra=()):
        args = hint_loop.build_parser().parse_args([
            "--instance_id", "offline-task", "--run_name", "offline-baseline",
            "--output_base", self.directory.name, "--api_key", "codex-local",
            "--no_hint_run", "--dry_run", *extra,
        ])
        return hint_loop.HintLoopOrchestrator(args)

    def test_original_default_is_one_attempt_even_with_max_rounds_five(self):
        loop = self.loop()
        with patch.object(loop, "step_solve", return_value=outcome()) as solve:
            self.assertEqual(loop.run(), 1)
        solve.assert_called_once_with(1, no_hint=True)
        self.assertEqual(loop.summary["max_rounds"], 1)
        self.assertEqual(loop.summary["rounds"][0]["status"], "not_solved")

    def test_requested_five_attempts_do_not_silently_reuse_old_results(self):
        loop = self.loop(["--baseline_rounds", "5"])
        with patch.object(loop, "step_solve", return_value=outcome()) as solve, \
                patch.object(loop, "_find_eval_result", return_value={"solved": True}) as previous:
            self.assertEqual(loop.run(), 1)
        self.assertEqual([call.args[0] for call in solve.call_args_list], [1, 2, 3, 4, 5])
        self.assertTrue(all(call.kwargs == {"no_hint": True} for call in solve.call_args_list))
        previous.assert_not_called()
        self.assertEqual(loop.summary["total_rounds"], 5)

    def test_early_pass_stops_remaining_attempts(self):
        loop = self.loop(["--baseline_rounds", "5"])
        with patch.object(loop, "step_solve", side_effect=[outcome(), outcome(True)]) as solve:
            self.assertEqual(loop.run(), 0)
        self.assertEqual(solve.call_count, 2)
        self.assertTrue(loop.summary["solved"])
        self.assertEqual(loop.summary["solved_round"], 2)

    def test_incomplete_attempt_is_distinct_from_a_normal_failed_evaluation(self):
        loop = self.loop(["--baseline_rounds", "5"])
        with patch.object(loop, "step_solve", side_effect=[outcome(), None]) as solve:
            self.assertEqual(loop.run(), 2)
        self.assertEqual(solve.call_count, 2)
        self.assertEqual([row["status"] for row in loop.summary["rounds"]],
                         ["not_solved", "incomplete"])
        self.assertFalse(loop.summary["solved"])
        self.assertNotIn("eval", loop.summary["rounds"][1])


class PairedDriverTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.args = SimpleNamespace(
            output_base=self.directory.name, experiment_name="offline",
            stage="formal", api_base="http://model-bridge:8765",
            container_api_base="http://guest-model-bridge:8765",
            progress_base="http://progress:8766",
            container_progress_base="http://guest-progress:8766", dry_run=True,
        )
        self.driver = paired.PairedExperiments(self.args)

    def tearDown(self):
        self.directory.cleanup()

    def test_group_configuration_is_matched_and_only_i_enables_online_guidance(self):
        loops = {group: self.driver.loop("offline-task", group, "shared-state.json")
                 for group in paired.GROUPS}
        for group, loop in loops.items():
            self.assertEqual(loop.args.model_name, "gpt-6.1-terra")
            self.assertEqual(loop.args.container_cpus, 8)
            self.assertEqual(loop.args.mem_limit, "128g")
            self.assertEqual(loop.args.max_rounds, 5)
            self.assertEqual(loop.args.baseline_rounds, 5)
            self.assertFalse(loop.args.continue_run)
            self.assertEqual(loop.args.no_hint_run, group == "B")
            self.assertEqual(bool(loop.args.teacher_progress_url), group == "I")
            self.assertEqual(loop.args.teacher_session_mode, "resume" if group == "M" else "fresh")
        self.assertEqual(len({loop.args.codex_session for loop in loops.values()}), 4)

    def test_each_student_round_has_new_session_and_one_original_solver_attempt(self):
        loop = self.driver.loop("offline-task", "B")
        with patch.object(hint_loop, "run_step", return_value=0) as run:
            loop.step_solve(1, no_hint=True)
            loop.step_solve(2, no_hint=True)
        commands = [call.args[1] for call in run.call_args_list]
        sessions = [command[command.index("--experiment_session") + 1] for command in commands]
        self.assertEqual(sessions, ["offline-offline-task-B-r1", "offline-offline-task-B-r2"])
        names = [command[command.index("--run_name") + 1] for command in commands]
        self.assertEqual(names, ["offline_B_r1", "offline_B_r2"])
        for command in commands:
            self.assertEqual(command[command.index("--max_turns") + 1], "1")
            self.assertNotIn("--hint_path", command)
            self.assertNotIn("--resume_session_id", command)

    def test_m_teacher_url_keeps_identity_while_h_starts_fresh_reviews(self):
        shared_session = "offline-offline-task-shared"
        loops = {group: self.driver.loop("offline-task", group, "shared-state.json")
                 for group in ("H", "M")}
        with patch.object(hint_loop, "run_step", return_value=0) as run:
            loops["M"].step_review(1)
            loops["M"].step_review(2)
            loops["H"].step_review(1)
            loops["H"].step_review(2)
        commands = [call.args[1] for call in run.call_args_list]
        urls = [command[command.index("--api_base") + 1] for command in commands]
        self.assertIn(f"/sessions/{shared_session}/teacher/review_r1/v1", urls[0])
        self.assertIn(f"/sessions/{shared_session}/teacher/review_r2/v1", urls[1])
        self.assertIn("/sessions/offline-offline-task-H-review-r1/teacher/review_r1/v1", urls[2])
        self.assertIn("/sessions/offline-offline-task-H-review-r2/teacher/review_r2/v1", urls[3])
        self.assertTrue(all(url.startswith("http://guest-model-bridge:8765/") for url in urls))

    def test_all_hint_groups_receive_identical_initial_full_and_compressed_hints(self):
        self.driver.args.dry_run = False
        shared = self.driver.loop("offline-task", "shared")
        shared.hint_gen_dir.mkdir(parents=True, exist_ok=True)
        originals = {
            shared.full_hint_path: "A shared full teacher guide.\n",
            shared.golden_diff_path: "A fixed reference patch.\n",
            shared._hint_path_for_round(1): "A shared compressed student guide.\n",
        }
        for path, text in originals.items():
            path.write_text(text)
        for group in ("H", "M", "I"):
            loop = self.driver.loop("offline-task", group, "shared-state.json")
            self.driver.use_shared(loop, shared)
            self.assertEqual(loop.full_hint_path.read_text(), originals[shared.full_hint_path])
            self.assertEqual(loop.golden_diff_path.read_text(), originals[shared.golden_diff_path])
            self.assertEqual(loop._hint_path_for_round(1).read_text(), originals[shared._hint_path_for_round(1)])

    def test_five_round_schedule_is_paired_rotates_order_and_stops_solved_groups(self):
        attempts = []
        shared = SimpleNamespace(args=SimpleNamespace(teacher_state="shared-state.json"))
        pass_at = {"B": 2, "H": 1, "M": None, "I": 3}

        def attempt(task, group, loop, round_num, reviews):
            self.assertFalse(loop.args.continue_run)
            attempts.append((task, group, round_num))
            return pass_at[group] == round_num

        with patch.object(paired, "TASKS", ("task-a", "task-b")), \
                patch.object(self.driver, "prepare_shared", return_value=shared) as prepare, \
                patch.object(self.driver, "use_shared") as use_shared, \
                patch.object(self.driver, "run_attempt", side_effect=attempt), \
                patch.object(paired, "write_reports"), \
                patch.object(self.driver, "close_teachers"):
            self.assertEqual(self.driver.run(), 0)
        self.assertEqual(prepare.call_count, 2)
        self.assertEqual(use_shared.call_count, 6)
        for task in ("task-a", "task-b"):
            for group in paired.GROUPS:
                rounds = [number for item, condition, number in attempts if item == task and condition == group]
                expected = pass_at[group] or 5
                self.assertEqual(rounds, list(range(1, expected + 1)))
        first = [group for task, group, number in attempts if task == "task-a" and number == 1]
        second = [group for task, group, number in attempts if task == "task-b" and number == 1]
        self.assertEqual(first, ["B", "H", "M", "I"])
        self.assertEqual(second, ["H", "M", "I", "B"])
        self.assertEqual(self.driver.state["status"], "complete")

    def test_compression_failure_still_tracks_initial_teacher_for_cleanup(self):
        shared = SimpleNamespace(
            args=SimpleNamespace(), hint_gen_dir=Path(self.directory.name) / "shared",
            step_get_hint=Mock(return_value=True),
            step_compress=Mock(side_effect=RuntimeError("Teacher quota reached")),
        )
        with patch.object(self.driver, "loop", return_value=shared):
            with self.assertRaisesRegex(RuntimeError, "quota"):
                self.driver.prepare_shared("offline-task")
        self.assertEqual(self.driver.kept_teachers,
                         [Path(self.directory.name) / "shared" / "teacher_state.json"])

    def test_incomplete_attempt_stops_driver_and_upstream_without_retry(self):
        self.driver.args.dry_run = False
        with patch.object(paired, "TASKS", ("task-a",)), \
                patch.object(self.driver, "bridge_status", return_value={"stopped": False}), \
                patch.object(hint_loop.HintLoopOrchestrator, "step_solve", return_value=None) as solve, \
                patch.object(paired, "request_json", return_value={"stopped": True}) as stop, \
                patch.object(paired, "write_reports"), \
                patch.object(self.driver, "close_teachers"):
            self.assertEqual(self.driver.run(), 2)
        solve.assert_called_once_with(1, no_hint=True)
        self.assertEqual(self.driver.state["status"], "stopped")
        self.assertEqual(len(self.driver.state["attempts"]), 1)
        self.assertEqual(self.driver.state["attempts"][0]["status"], "incomplete")
        self.assertEqual(stop.call_args.args[0], "http://model-bridge:8765/stop")
        self.assertIn("formal evaluation", stop.call_args.args[1]["reason"])
        self.assertEqual(self.driver.state["quota_policy"], "save_and_stop_without_automatic_resume")

    def resume_fixture(self, after_session, preserve_history=True):
        self.driver.args.dry_run = False
        self.driver.args.bridge_dir = self.driver.output / "bridge"
        self.driver.args.bridge_dir.mkdir()
        loop = self.driver.loop("offline-task", "H", "shared-state.json")
        shared = self.driver.loop("offline-task", "shared")
        session = "offline-offline-task-shared"
        shared.args.teacher_codex_session = session
        state = self.driver.output / "teacher_state.json"
        state.write_text(json.dumps({"session_id": "teacher-original"}))
        shared.args.teacher_state = str(state)
        initial = {"role": "assistant", "content": "Original teacher guidance"}
        record = {"session": session, "role": "teacher", "phase": "generate",
                  "response": {"choices": [{"message": initial}]}}
        (self.driver.args.bridge_dir / "model_responses.jsonl").write_text(json.dumps(record)+"\n")
        def review(step, command, log_path, env=None):
            output = self.driver.output / "teacher_resume_probe" / "review.json"
            output.write_text(json.dumps({"used_hint": True}))
            state.write_text(json.dumps({"session_id": after_session}))
            request = {"session": session, "role": "teacher", "phase": "resume_probe",
                       "request_id": "fresh-native-request", "request": {"messages":
                           [initial] if preserve_history else [{"role": "user", "content": "Fresh task"}]}}
            (self.driver.args.bridge_dir / "model_requests.jsonl").write_text(json.dumps(request)+"\n")
            return 0
        return loop, shared, review

    def test_teacher_resume_probe_uses_sdk_session_and_actual_history(self):
        loop, shared, review = self.resume_fixture("teacher-original")
        loop.summary["solved"] = True
        with patch.object(self.driver, "bridge_status", return_value={"stopped": False}), \
                patch.object(paired, "run_step", side_effect=review) as run:
            self.driver.verify_teacher_resume(loop, shared)
        probe = self.driver.state["teacher_resume_probe"]
        self.assertTrue(probe["passed"])
        self.assertEqual(probe["before_sdk_session"], "teacher-original")
        self.assertEqual(probe["after_sdk_session"], "teacher-original")
        self.assertTrue(probe["initial_final_in_review_history"])
        command = run.call_args.args[1]
        self.assertEqual(command[command.index("--teacher_session") + 1], "resume")
        self.assertIn("--solved", command)
        self.assertIn("/sessions/offline-offline-task-shared/teacher/resume_probe/v1",
                      command[command.index("--api_base") + 1])

    def test_teacher_resume_probe_rejects_replaced_sdk_session(self):
        loop, shared, review = self.resume_fixture("teacher-replacement")
        with patch.object(self.driver, "bridge_status", return_value={"stopped": False}), \
                patch.object(paired, "run_step", side_effect=review):
            with self.assertRaisesRegex(RuntimeError, "persistent teacher"):
                self.driver.verify_teacher_resume(loop, shared)
        self.assertFalse(self.driver.state["teacher_resume_probe"]["passed"])

    def test_teacher_resume_probe_rejects_missing_initial_history(self):
        loop, shared, review = self.resume_fixture("teacher-original", preserve_history=False)
        with patch.object(self.driver, "bridge_status", return_value={"stopped": False}), \
                patch.object(paired, "run_step", side_effect=review):
            with self.assertRaisesRegex(RuntimeError, "persistent teacher"):
                self.driver.verify_teacher_resume(loop, shared)
        self.assertFalse(self.driver.state["teacher_resume_probe"]["passed"])

    def test_existing_name_is_rejected_and_new_name_preserves_previous_results(self):
        self.driver.state["status"] = "stopped"
        self.driver.state["stop_reason"] = "Preserve this earlier result"
        self.driver.save()
        original = self.driver.summary_path.read_bytes()
        artifact = self.driver.output / "previous-patch.diff"
        artifact.write_text("Existing patch contents\n")
        with self.assertRaisesRegex(FileExistsError, "new experiment name"):
            paired.PairedExperiments(self.args)
        self.assertEqual(self.driver.summary_path.read_bytes(), original)
        self.assertEqual(artifact.read_text(), "Existing patch contents\n")
        new_args = SimpleNamespace(**{**vars(self.args), "experiment_name": "another-offline-run"})
        new_driver = paired.PairedExperiments(new_args)
        new_driver.save()
        self.assertNotEqual(new_driver.output, self.driver.output)
        self.assertEqual(self.driver.summary_path.read_bytes(), original)

    def test_final_integration_report_keeps_stopped_status_and_original_reason(self):
        self.args.stage = "integration"
        self.args.dry_run = False
        self.driver = paired.PairedExperiments(self.args)
        bridge = Path(self.directory.name) / "logs" / "bridge"
        progress = Path(self.directory.name) / "logs" / "progress"
        bridge.mkdir(parents=True)
        progress.mkdir(parents=True)

        def write_local_reports(state_path, ignored_bridge, ignored_progress):
            return reporting.write_reports(state_path, bridge, progress)

        reason = "SDK fixture did not exercise a permitted edit"
        with patch.object(self.driver, "prepare_shared", side_effect=RuntimeError(reason)), \
                patch.object(paired, "request_json", return_value={"stopped": True}), \
                patch.object(paired, "write_reports", side_effect=write_local_reports), \
                patch.object(self.driver, "close_teachers"):
            self.assertEqual(self.driver.run(), 2)
        metrics = json.loads((self.driver.output / "metrics.json").read_text())
        report = (self.driver.output / "report.md").read_text()
        self.assertEqual(metrics["stage"], "integration")
        self.assertEqual(metrics["status"], "stopped")
        self.assertEqual(metrics["stop_reason"], reason)
        self.assertIn("# Codex Hint 联调报告", report)
        self.assertIn("状态：stopped", report)
        self.assertIn("停止原因：" + reason, report)
        self.assertEqual(metrics["attempts"], [])

    def shared_driver(self):
        self.args.shared_first_attempt = True
        self.driver = paired.PairedExperiments(self.args)
        return self.driver

    def run_shared_schedule(self, pass_at):
        driver = self.shared_driver()
        task = "offline-task"
        shared = driver.loop(task, "shared", "initial-teacher.json")
        solves, reviews, compressions = [], [], []

        def solve(loop, number, no_hint=False):
            group = loop.summary["group"]
            solves.append((group, number, no_hint))
            return outcome(pass_at.get(group) == number)

        def review(loop, number, solved=False, trajs_override=None):
            reviews.append({"group": loop.summary["group"], "round": number,
                            "solved": solved, "trajs": trajs_override or loop._trajs_path(number),
                            "mode": loop.args.teacher_session_mode,
                            "session": loop.args.teacher_codex_session})
            return True

        def compress(loop, number, paths):
            compressions.append((loop.summary["group"], number, list(paths)))
            return True

        with patch.object(paired, "TASKS", (task,)), \
                patch.object(driver, "prepare_shared", return_value=shared), \
                patch.object(driver, "use_shared"), \
                patch.object(driver, "register_online") as online, \
                patch.object(hint_loop.HintLoopOrchestrator, "step_solve", autospec=True,
                             side_effect=solve), \
                patch.object(hint_loop.HintLoopOrchestrator, "step_review", autospec=True,
                             side_effect=review), \
                patch.object(hint_loop.HintLoopOrchestrator, "step_compress", autospec=True,
                             side_effect=compress), \
                patch.object(paired, "write_reports"), patch.object(driver, "close_teachers"):
            self.assertEqual(driver.run(), 0)
        return driver, solves, reviews, compressions, online

    def test_shared_pass_has_one_observation_and_one_success_review_without_memory_branch(self):
        driver, solves, reviews, compressions, online = self.run_shared_schedule(
            {"B": 1, "H": 1, "I": 1})
        self.assertEqual(solves, [("B", 1, True), ("H", 1, False), ("I", 1, False)])
        self.assertEqual([(row["group"], row["round"], row["solved"]) for row in reviews],
                         [("H", 1, True), ("I", 1, True)])
        self.assertFalse(any(row["mode"] == "resume" for row in reviews))
        self.assertEqual(compressions, [])
        self.assertEqual(online.call_count, 1)
        common = driver.state["shared_first_attempts"]["offline-task"]
        self.assertEqual(common["reviews"], {"H": "done", "M": "not_triggered"})
        self.assertFalse(common["mechanism_triggered"])
        self.assertEqual(common["shared_with"], ["H", "M"])
        rows = driver.state["attempts"]
        self.assertEqual(len(rows), 3)
        self.assertFalse(any(row["group"] == "M" for row in rows))
        actual = next(row for row in rows if row["group"] == "H")
        self.assertEqual(actual["stage"], "shared_first_student")
        self.assertEqual(actual["attribution_group"], "HM")
        self.assertEqual(actual["origin_experiment"], "offline")
        self.assertEqual(actual["review"], "done")
        self.assertFalse(driver.state["student_attempts_independent"])
        self.assertTrue(driver.state["fresh_student_state_each_actual_attempt"])

    def test_shared_failure_branches_same_trajectory_and_preserves_five_round_budget(self):
        driver, solves, reviews, compressions, online = self.run_shared_schedule({})
        for group in ("B", "H", "I"):
            self.assertEqual([number for name, number, _ in solves if name == group], [1, 2, 3, 4, 5])
        self.assertEqual([number for name, number, _ in solves if name == "M"], [2, 3, 4, 5])
        self.assertEqual(len(solves), 19)
        common_reviews = [row for row in reviews if row["round"] == 1
                          and row["group"] in ("H", "M")]
        self.assertEqual([row["group"] for row in common_reviews], ["H", "M"])
        self.assertEqual(common_reviews[0]["trajs"], common_reviews[1]["trajs"])
        self.assertEqual([row["mode"] for row in common_reviews], ["fresh", "resume"])
        self.assertEqual(common_reviews[1]["session"], "offline-offline-task-shared")
        for group in ("H", "M"):
            first_compression = next(paths for name, number, paths in compressions
                                     if name == group and number == 2)
            self.assertEqual(len(first_compression), 1)
            self.assertIn(f"offline_{group}/reviews/offline-task/round_1/", str(first_compression[0]))
        self.assertEqual(online.call_count, 5)
        self.assertTrue(driver.state["shared_first_attempts"]["offline-task"]["mechanism_triggered"])
        self.assertEqual(driver.state["shared_first_attempts"]["offline-task"]["reviews"],
                         {"H": "done", "M": "done"})

    def test_shared_student_runs_once_when_rotated_order_places_m_before_h(self):
        driver = self.shared_driver()
        tasks = ("task-a", "task-b", "task-c", "task-d")
        shared = SimpleNamespace(args=SimpleNamespace(teacher_state="initial-teacher.json"))
        solves = []

        def solve(loop, number, no_hint=False):
            solves.append((loop.args.instance_id, loop.summary["group"], number))
            return outcome(True)

        with patch.object(paired, "TASKS", tasks), \
                patch.object(driver, "prepare_shared", return_value=shared) as prepare, \
                patch.object(driver, "use_shared"), patch.object(driver, "register_online"), \
                patch.object(hint_loop.HintLoopOrchestrator, "step_solve", autospec=True,
                             side_effect=solve), \
                patch.object(hint_loop.HintLoopOrchestrator, "step_review", return_value=True), \
                patch.object(paired, "write_reports"), patch.object(driver, "close_teachers"):
            self.assertEqual(driver.run(), 0)
        self.assertEqual(prepare.call_count, 4)
        for task in tasks:
            actual = [(group, number) for item, group, number in solves if item == task]
            self.assertEqual(sorted(actual), [("B", 1), ("H", 1), ("I", 1)])
        self.assertEqual([group for task, group, _ in solves if task == "task-c"], ["H", "I", "B"])
        self.assertEqual(set(driver.state["shared_first_attempts"]), set(tasks))

    def continuation_fixture(self, reason="Interrupted"):
        base = Path(self.directory.name)
        old = base / "runs" / "old"
        hint_dir = old / "old_shared" / "hint_gen" / "offline-task"
        hint_dir.mkdir(parents=True)
        for filename, content in (("hint_output.md", "Original full guidance\n"),
                                  ("hint_compact_r1.md", "Original compressed guidance\n"),
                                  ("golden_diff.diff", "Original reference patch\n"),
                                  ("teacher_state.json", '{"session_id":"old-teacher"}\n')):
            (hint_dir / filename).write_text(content)
        attempts = []
        for group, status in (("B", "not_solved"), ("H", "solved"), ("M", "running")):
            entry = {"task": "offline-task", "group": group, "round": 1, "status": status,
                     "trajs_path": str(old / group / "trajs.json"),
                     "eval_path": str(old / group / "eval_result.json")}
            if group != "M":
                entry.update(outcome(group == "H"))
            attempts.append(entry)
        state = {"experiment": "old", "status": "stopped", "stop_reason": reason,
                 "attempts": attempts, "shared": {"offline-task": {
                     "teacher_state": str(hint_dir / "teacher_state.json"),
                     "full_hint": str(hint_dir / "hint_output.md"),
                     "first_hint": str(hint_dir / "hint_compact_r1.md"),
                     "cost_shared_by": ["H", "M", "I"]}}}
        path = old / "experiment_state.json"
        path.write_text(json.dumps(state))
        manifest = base / "preflight" / "old_user_protocol_change" / "M1_cancellation.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"source_experiment": "old", "task": "offline-task",
            "group": "M", "round": 1, "status": "cancelled_by_user", "formal_score": None,
            "formal_eval_exists": False, "actual_model_tokens": 123,
            "trajs_path": str(old / "M" / "trajs.json")}))
        args = SimpleNamespace(**{**vars(self.args), "output_base": str(base / "runs"),
            "experiment_name": "continued", "shared_first_attempt": True,
            "continue_from": str(path), "dry_run": False})
        return path, manifest, hint_dir, args

    def test_continuation_imports_only_completed_observations_and_keeps_old_artifacts_read_only(self):
        source_path, manifest, hint_dir, args = self.continuation_fixture()
        preserved = {path: path.read_bytes() for path in (source_path, manifest, *hint_dir.iterdir())}
        driver = paired.PairedExperiments(args)
        solves, review_modes = [], []

        def solve(loop, number, no_hint=False):
            solves.append((loop.summary["group"], number))
            if loop.summary["group"] == "I":
                self.assertEqual(loop._hint_path_for_round(1).read_text(),
                                 (hint_dir / "hint_compact_r1.md").read_text())
                self.assertEqual(loop.golden_diff_path.read_text(),
                                 (hint_dir / "golden_diff.diff").read_text())
            return outcome(True)

        def review(loop, number, solved=False, trajs_override=None):
            review_modes.append((loop.summary["group"], loop.args.teacher_session_mode,
                                 loop.args.teacher_state))
            return True

        with patch.object(paired, "TASKS", ("offline-task",)), \
                patch.object(driver, "prepare_shared") as prepare, \
                patch.object(driver, "check_running"), patch.object(driver, "register_online"), \
                patch.object(driver, "close_teachers"), patch.object(paired, "write_reports"), \
                patch.object(hint_loop.HintLoopOrchestrator, "step_solve", autospec=True,
                             side_effect=solve), \
                patch.object(hint_loop.HintLoopOrchestrator, "step_review", autospec=True,
                             side_effect=review):
            self.assertEqual(driver.run(), 0)
        prepare.assert_not_called()
        self.assertEqual(solves, [("I", 1), ("B", 2)])
        self.assertEqual(review_modes, [("I", "fresh", str(hint_dir / "teacher_state.json"))])
        self.assertEqual(driver.state["continuation"],
                         {"source_experiment": "old", "state_path": str(source_path)})
        self.assertEqual(driver.state["task_protocols"]["offline-task"], "v1_transition")
        self.assertEqual(driver.state["skipped_groups"], {"offline-task": ["M"]})
        self.assertEqual(driver.state["shared_first_attempts"], {})
        imported = [row for row in driver.state["attempts"] if row["origin_experiment"] == "old"]
        self.assertEqual([(row["group"], row["round"]) for row in imported], [("B", 1), ("H", 1)])
        self.assertFalse(any(row["group"] == "M" for row in driver.state["attempts"]))
        excluded = driver.state["excluded_prior_attempts"][0]
        self.assertEqual(excluded["status"], "cancelled_by_user")
        self.assertEqual(excluded["original_status"], "running")
        self.assertIsNone(excluded["formal_score"])
        self.assertEqual(excluded["actual_model_tokens"], 123)
        self.assertEqual(excluded["manifest_path"], str(manifest))
        self.assertEqual(driver.kept_teachers, [])
        for path, original in preserved.items():
            self.assertEqual(path.read_bytes(), original)

    def test_continuation_is_explicit_and_does_not_resume_after_quota_stop(self):
        path, _, _, args = self.continuation_fixture("Token quota exhausted")
        for reason in ("Token quota exhausted", "Codex usage limit reached", "rate_limit_exceeded"):
            state = json.loads(path.read_text())
            state["stop_reason"] = reason
            path.write_text(json.dumps(state))
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, "non-quota"):
                paired.PairedExperiments(args)
        args.shared_first_attempt = False
        with self.assertRaisesRegex(ValueError, "shared_first_attempt"):
            paired.PairedExperiments(args)

    def test_continuation_codex_experiment_uses_actual_preflight_directory_name(self):
        old_path, old_manifest, _, args = self.continuation_fixture()
        new_directory = old_path.parent.with_name("codex_formal_03")
        old_path.parent.rename(new_directory)
        source_path = new_directory / "experiment_state.json"
        source = source_path.read_text().replace(str(old_path.parent), str(new_directory))
        source_path.write_text(source.replace('"experiment": "old"',
                                             '"experiment": "codex_formal_03"'))
        manifest_directory = old_manifest.parent.with_name("formal_03_user_protocol_change")
        old_manifest.parent.rename(manifest_directory)
        manifest = manifest_directory / "M1_cancellation.json"
        cancellation = json.loads(manifest.read_text())
        cancellation["source_experiment"] = "codex_formal_03"
        manifest.write_text(json.dumps(cancellation))
        args.continue_from = str(source_path)
        preserved = {source_path: source_path.read_bytes(), manifest: manifest.read_bytes()}
        driver = paired.PairedExperiments(args)
        self.assertEqual(driver.state["continuation"]["source_experiment"], "codex_formal_03")
        excluded = driver.state["excluded_prior_attempts"][0]
        self.assertEqual(excluded["manifest_path"], str(manifest))
        self.assertEqual(excluded["status"], "cancelled_by_user")
        self.assertEqual(excluded["origin_experiment"], "codex_formal_03")
        for path, content in preserved.items():
            self.assertEqual(path.read_bytes(), content)

    def test_shared_review_override_preserves_original_hint_gt_and_teacher_session(self):
        loop = self.driver.loop("offline-task", "M", "shared-state.json")
        common = Path(self.directory.name) / "actual-H-first-trajs.json"
        with patch.object(hint_loop, "run_step", return_value=0) as run:
            loop.step_review(1, trajs_override=common)
        command = run.call_args.args[1]
        self.assertEqual(command[command.index("--trajs") + 1], str(common))
        self.assertEqual(command[command.index("--hint") + 1], str(loop._hint_path_for_round(1)))
        self.assertEqual(command[command.index("--golden_diff") + 1], str(loop.golden_diff_path))
        self.assertEqual(command[command.index("--teacher_session") + 1], "resume")
        self.assertIn("/sessions/offline-offline-task-shared/teacher/review_r1/v1",
                      command[command.index("--api_base") + 1])

    def test_shared_live_report_uses_the_same_policy_reporter_as_final_results(self):
        driver = self.shared_driver()
        driver.args.dry_run = False
        with patch.object(paired, "write_reports") as report:
            driver.save()
        report.assert_called_once_with(driver.summary_path, paired.ROOT / "logs/bridge",
                                       paired.ROOT / "logs/progress")
        self.assertTrue((driver.output / "results.csv").is_file())
        self.assertFalse((driver.output / "report.md").exists())


if __name__ == "__main__":
    unittest.main()
