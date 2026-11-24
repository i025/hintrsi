"""Measured fixture reports without model, Docker, or network calls."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source_parallel_12"))
from report_codex_experiments import aggregate_experiment, write_reports  # noqa: E402


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.output = self.root / "runs" / "formal-one"
        self.output.mkdir(parents=True)
        self.bridge = self.root / "logs" / "bridge"
        self.bridge.mkdir(parents=True)
        self.progress = self.root / "logs" / "progress"
        self.progress.mkdir(parents=True)
        self.state_path = self.output / "experiment_state.json"
        self.state = {"experiment": "formal-one", "stage": "formal", "status": "stopped",
                      "model": "gpt-6.1-terra", "reasoning_effort": "low", "max_rounds": 5,
                      "groups": ["B", "H", "M", "I"], "tasks": ["task-a", "task-b"],
                      "shared": {"task-a": {"cost_shared_by": ["H", "M", "I"]}},
                      "attempts": [
                          {"task":"task-a", "group":"B", "round":1, "status":"not_solved"},
                          {"task":"task-a", "group":"B", "round":2, "status":"solved"},
                          {"task":"task-a", "group":"H", "round":1, "status":"solved"},
                          {"task":"task-a", "group":"M", "round":1, "status":"incomplete"},
                          {"task":"task-b", "group":"I", "round":1, "status":"not_solved", "elapsed_seconds":150},
                          {"task":"task-b", "group":"I", "round":2, "status":"incomplete"},
                      ]}
        self.save_state()
        integration = self.root / "runs" / "integration-one"
        integration.mkdir()
        (integration / "experiment_state.json").write_text(json.dumps({
            "experiment":"integration-one", "stage":"integration", "tasks":["task-a"], "attempts":[]}))

    def tearDown(self):
        self.tmp.cleanup()

    def save_state(self):
        self.state_path.write_text(json.dumps(self.state))

    def log(self, name, rows):
        (self.bridge / name).write_text("".join(json.dumps(row)+"\n" for row in rows))

    def usage(self, session, role, phase, inputs, outputs, cached=0, reasoning=0):
        return {"session":session, "role":role, "phase":phase,
                "delta":{"inputTokens":inputs,"cachedInputTokens":cached,"outputTokens":outputs,
                         "reasoningOutputTokens":reasoning,"totalTokens":inputs+outputs},
                "usage":{"total":{"totalTokens":999999}}}

    def fixtures(self):
        self.log("token_usage.jsonl", [
            self.usage("formal-one-task-a-shared","teacher","generate",100,20,60,7),
            self.usage("formal-one-task-a-shared-compress_r1","compressor","compress_r1",20,2,10,1),
            self.usage("formal-one-task-a-shared","teacher","review_r1",40,5,30,2),
            self.usage("formal-one-task-a-H-r1","student","solve",50,10,20,5),
            self.usage("formal-one-task-b-I-r1_progress_1_candidate","teacher","progress_1_candidate",30,5),
            self.usage("formal-one-task-b-I-r1_progress_1_screen","compressor","progress_1_screen",10,2),
            self.usage("formal-one-task-a-B-r2","student","solve",70,10),
            self.usage("preflight-sdk","student","solve",999,1),
            self.usage("integration-one-task-a-H-r1","student","solve",50,5),
        ])
        self.log("model_requests.jsonl", [{"session":"formal-one-task-a-H-r1","role":"student","phase":"solve"}])
        self.log("model_responses.jsonl", [{"session":"formal-one-task-a-H-r1","role":"student","phase":"solve",
                  "elapsed_seconds":2.5,"response":{"usage":{"total_tokens":9999999}}}])
        self.log("model_errors.jsonl", [{"session":"formal-one-task-a-shared","role":"teacher","phase":"review_r1",
                  "elapsed_seconds":1.5,"usage":{"totalTokens":100000}}])
        self.log("codex_events.jsonl", [{"session":"formal-one-task-a-H-r1","role":"student","phase":"solve",
                  "event":{"method":"turn/completed","params":{"turn":{"durationMs":6000}}}}])

    def test_exec_usage_unknown_and_turn_duration_are_distinct(self):
        self.fixtures()
        dimensions = {"session":"formal-one-task-a-H-r1", "role":"student", "phase":"solve"}
        self.log("model_requests.jsonl", [{**dimensions, "request_id":"reported"},
                                        {**dimensions, "request_id":"unreported"}])
        self.log("token_usage.jsonl", [{**dimensions, "request_id":"reported", "delta":{
            "inputTokens":100, "outputTokens":20, "totalTokens":120}}])
        self.log("exec_turns.jsonl", [{**dimensions, "request_id":"reported", "elapsed_seconds":2.0}])
        self.log("codex_events.jsonl", [{**dimensions, "event":{"type":"turn.completed",
                                        "usage":{"input_tokens":100,"output_tokens":20}}}])
        result = aggregate_experiment(self.state_path,self.bridge)
        self.assertEqual(result["totals"]["total_tokens"],120)
        self.assertEqual(result["totals"]["usage_unknown_requests"],1)
        self.assertEqual(result["usage_unknown_requests"][0]["request_id"],"unreported")
        self.assertEqual(result["totals"]["codex_turn_count"],1)
        self.assertEqual(result["totals"]["codex_turn_seconds"],2.0)
        self.assertEqual(result["totals"]["request_seconds"],4)

    def test_delta_only_and_shared_memory_attribution(self):
        self.fixtures()
        result = aggregate_experiment(self.state_path, self.bridge)
        self.assertEqual(result["totals"]["total_tokens"],374)
        self.assertEqual(result["totals"]["input_tokens"] + result["totals"]["output_tokens"],374)
        self.assertEqual(result["shared_totals"]["total_tokens"],142)
        self.assertEqual(result["group_totals"]["M"]["total_tokens"],45)
        self.assertEqual(result["group_totals"]["I"]["total_tokens"],47)
        self.assertEqual(result["totals"]["request_seconds"],4)
        self.assertEqual(result["totals"]["codex_turn_seconds"],6)

    def test_scopes_and_optional_allocation_do_not_double_count(self):
        self.fixtures()
        result = aggregate_experiment(self.state_path,self.bridge,allocate_shared=True)
        self.assertEqual(result["bridge_scope_totals"]["preflight"]["total_tokens"],1000)
        self.assertEqual(result["bridge_scope_totals"]["integration"]["total_tokens"],55)
        self.assertEqual(result["bridge_scope_totals"]["formal"]["total_tokens"],374)
        self.assertAlmostEqual(sum(row["total_tokens"] for row in result["shared_allocations"]),142)
        self.assertEqual(result["totals"]["total_tokens"],374)

    def test_cumulative_results_and_incomplete_are_separate(self):
        result=aggregate_experiment(self.state_path,self.bridge)
        groups={row["group"]:row for row in result["outcomes"]}
        self.assertEqual(groups["B"]["first_round_solved"],0)
        self.assertEqual(groups["B"]["cumulative"][1]["solved_tasks"],1)
        self.assertEqual(groups["M"]["incomplete_attempts"],1)
        self.assertEqual(groups["M"]["normal_failed_attempts"],0)
        self.assertEqual(groups["I"]["normal_failed_attempts"],1)
        self.assertEqual(groups["I"]["normal_failed_tasks"],0)
        self.assertGreater(groups["I"]["cumulative"][4]["pending_tasks"],0)

    def test_partial_state_uses_raw_evaluation_without_overwriting_zero(self):
        evaluation = self.output / "eval_result.json"
        evaluation.write_text(json.dumps({"reward":1, "f2p_passed":2, "f2p_total":2,
                                          "p2p_passed":119, "p2p_total":119}))
        self.state["attempts"][0].update(eval_path=str(evaluation),
            eval={"reward":0, "f2p_passed":0, "f2p_total":2})
        self.state["attempts"][1].update(eval_path=str(evaluation), eval={"p2p_passed":0})
        self.save_state()
        result = write_reports(self.state_path, self.bridge)
        first, second = result["attempts"][:2]
        self.assertEqual((first["p2p_passed"], first["p2p_total"]), (119,119))
        self.assertEqual((first["reward"], first["f2p_passed"]), (0,0))
        self.assertEqual((second["p2p_passed"], second["p2p_total"]), (0,119))
        self.assertIsNone(result["attempts"][3]["p2p_passed"])
        self.assertIn(",119,119,", (self.output / "attempt_metrics.csv").read_text())

    def test_student_wall_active_and_teacher_wait_sources(self):
        trajectory=self.output/"trajs.json"
        trajectory.write_text(json.dumps({"metadata":{"wall_seconds":100,"teacher_wait_seconds":25,"teacher_checks":1}}))
        self.state["attempts"][4]["trajs_path"]=str(trajectory)
        self.save_state()
        (self.progress/"progress.jsonl").write_text(json.dumps({"session":"formal-one-task-b-I-r1",
                 "duration_seconds":23,"hint":"Check both forms."})+"\n")
        result=aggregate_experiment(self.state_path,self.bridge)
        row=result["attempts"][4]
        self.assertEqual(row["attempt_wall_seconds"],150)
        self.assertEqual(row["student_wall_seconds"],100)
        self.assertEqual(row["teacher_wait_seconds"],25)
        self.assertEqual(row["student_active_seconds"],75)
        self.assertEqual(row["teacher_wait_source"],"student_metadata")
        self.assertEqual(row["delivered_hints"],1)
        self.assertIsNone(result["attempts"][5]["student_active_seconds"])

    def test_dry_run_placeholders_do_not_become_results(self):
        self.state["dry_run"]=True
        self.save_state()
        result=write_reports(self.state_path,self.bridge)
        self.assertEqual(result["attempts"],[])
        self.assertEqual(result["dry_run_attempts_excluded"],6)
        self.assertTrue(all(row["solved_tasks"]==0 for row in result["outcomes"]))
        self.assertIn("不计入实验结果",(self.output/"report.md").read_text())

    def test_chinese_outputs_and_independent_cli_preflight(self):
        self.fixtures()
        directory=self.root/"preflight";directory.mkdir()
        (directory/"cli_tool_result.json").write_text(json.dumps({"usage":{"total":{"totalTokens":17,
          "inputTokens":15,"cachedInputTokens":8,"outputTokens":2,"reasoningOutputTokens":1}},"elapsed_seconds":.5}))
        result=write_reports(self.state_path,self.bridge,allocate_shared=True)
        self.assertEqual(result["preflight_cli"]["tokens"]["total_tokens"],17)
        self.assertEqual(result["totals"]["total_tokens"],374)
        for name in ["metrics.json","token_usage_by_stage.csv","attempt_metrics.csv","shared_allocations.csv","report.md"]:
            self.assertTrue((self.output/name).is_file())
        text=(self.output/"report.md").read_text()
        self.assertIn("仅计一次",text)
        self.assertNotIn("$",text)

    def set_shared_first(self, attempts):
        self.state["attempts"] = attempts
        self.state["task_protocols"] = {task:"shared_first_v2" for task in self.state["tasks"]}
        self.state["shared_first_attempts"] = {
            row["task"]: {"origin_experiment":self.state["experiment"], "group":"H", "round":1,
                          "shared_with":["H","M"], "status":row["status"]}
            for row in attempts if row["group"] == "H" and row["round"] == 1}
        for row in attempts:
            if row["group"] == "H" and row["round"] == 1:
                row.update(shared_with=["H","M"], attribution_group="HM", stage="shared_first_student")
        self.save_state()

    def test_shared_first_pass_is_one_execution_and_correlated_policy_result(self):
        self.set_shared_first([
            {"task":"task-a","group":"H","round":1,"status":"solved"},
            {"task":"task-a","group":"I","round":1,"status":"not_solved"},
        ])
        self.log("token_usage.jsonl", [
            self.usage("formal-one-task-a-shared","teacher","generate",100,20),
            self.usage("formal-one-task-a-shared-compress_r1","compressor","compress_r1",20,2),
            self.usage("formal-one-task-a-H-r1","student","solve",50,10),
            self.usage("formal-one-task-a-H-review-r1","teacher","review_r1",10,5),
            self.usage("formal-one-task-a-I-r1","student","solve",7,2),
        ])
        result = write_reports(self.state_path, self.bridge, allocate_shared=True)
        self.assertEqual(len(result["attempts"]),2)
        self.assertFalse(any(row["group"] == "M" for row in result["attempts"]))
        self.assertEqual(result["shared_first_outcomes"]["actual_student_executions"],1)
        self.assertEqual(result["shared_first_outcomes"]["solved_tasks"],1)
        groups = {row["group"]:row for row in result["outcomes"]}
        for group in ("H","M"):
            self.assertEqual(groups[group]["first_round_solved"],1)
            self.assertTrue(groups[group]["shared_prefix_correlated"])
            self.assertEqual(groups[group]["metric_unit"],"policy")
        self.assertEqual(groups["I"]["first_round_solved"],0)
        self.assertTrue(all(row["eligible_tasks"] == 0 for row in result["conditional_branch_outcomes"]))
        self.assertEqual(result["totals"]["total_tokens"],226)
        self.assertEqual(result["group_totals"]["HM"]["total_tokens"],75)
        self.assertEqual(result["shared_first_totals"]["total_tokens"],75)
        stages = {row["stage"]:row for row in result["stages"] if row["group"] == "HM"}
        self.assertEqual(stages["shared_success_review"]["total_tokens"],15)
        self.assertEqual(stages["shared_first_student"]["native_group"],"H")
        self.assertAlmostEqual(sum(row["total_tokens"] for row in result["shared_allocations"]),217)
        text = (self.output/"report.md").read_text()
        self.assertIn("不是两个独立样本",text)
        self.assertIn("M教师记忆机制未触发",text)
        import csv
        with (self.output/"attempt_metrics.csv").open() as stream:
            self.assertEqual([row["group"] for row in csv.DictReader(stream)],["H","I"])

    def test_shared_failure_branches_start_at_two_without_a_second_m_first_attempt(self):
        self.set_shared_first([
            {"task":"task-a","group":"H","round":1,"status":"not_solved"},
            {"task":"task-a","group":"H","round":2,"status":"solved"},
            {"task":"task-a","group":"M","round":2,"status":"not_solved"},
            {"task":"task-a","group":"M","round":3,"status":"solved"},
            {"task":"task-b","group":"H","round":1,"status":"solved"},
        ])
        self.log("token_usage.jsonl", [
            self.usage("formal-one-task-a-H-r1","student","solve",18,2),
            self.usage("formal-one-task-a-H-review-r1","teacher","review_r1",8,2),
            self.usage("formal-one-task-a-shared","teacher","review_r1",10,2),
        ])
        result = aggregate_experiment(self.state_path,self.bridge)
        self.assertEqual(len(result["attempts"]),5)
        self.assertEqual(result["shared_first_outcomes"]["not_solved_tasks"],1)
        branches = {row["group"]:row for row in result["conditional_branch_outcomes"]}
        self.assertEqual(branches["H"]["actual_branch_attempts"],1)
        self.assertEqual(branches["M"]["actual_branch_attempts"],2)
        self.assertEqual(branches["M"]["eligible_tasks"],1)
        self.assertEqual(branches["M"]["first_branch_round"],2)
        self.assertEqual(branches["M"]["cumulative"][1]["solved_tasks"],0)
        self.assertEqual(branches["M"]["cumulative"][2]["solved_tasks"],1)
        groups = {row["group"]:row for row in result["outcomes"]}
        self.assertEqual(groups["M"]["first_round_solved"],1)
        self.assertEqual(groups["M"]["solved_tasks"],2)
        self.assertEqual(groups["M"]["cumulative"][1]["solved_tasks"],1)
        self.assertEqual(result["group_totals"]["HM"]["total_tokens"],20)
        self.assertEqual(result["group_totals"]["H"]["total_tokens"],10)
        self.assertEqual(result["group_totals"]["M"]["total_tokens"],12)
        self.assertTrue(all(row["stage"] == "failure_review" for row in result["stages"]
                            if row["group"] in ("H","M")))

    def create_origin(self, attempts):
        output = self.root/"runs"/"formal-three"
        output.mkdir()
        path = output/"experiment_state.json"
        path.write_text(json.dumps({"experiment":"formal-three","stage":"formal",
            "tasks":self.state["tasks"],"attempts":attempts}))
        self.state["continuation"] = {"source_experiment":"formal-three","state_path":str(path)}
        return path

    def test_continuation_excludes_transition_and_cancelled_result_without_losing_spend(self):
        prior = [
            {"task":"task-a","group":"B","round":1,"status":"not_solved"},
            {"task":"task-a","group":"H","round":1,"status":"solved"},
            {"task":"task-a","group":"M","round":1,"status":"running"},
        ]
        source = self.create_origin(prior)
        self.set_shared_first([
            {**prior[0],"origin_experiment":"formal-three"},
            {**prior[1],"origin_experiment":"formal-three"},
            {"task":"task-a","group":"B","round":2,"status":"solved"},
            {"task":"task-a","group":"I","round":1,"status":"not_solved"},
            {"task":"task-b","group":"H","round":1,"status":"solved"},
        ])
        self.state["task_protocols"]["task-a"] = "v1_transition"
        del self.state["shared_first_attempts"]["task-a"]
        self.state["attempts"][1].pop("shared_with")
        self.state["attempts"][1].pop("attribution_group")
        self.state["attempts"][1].pop("stage")
        self.state["excluded_prior_attempts"] = [{"task":"task-a","group":"M","round":1,
            "origin_experiment":"formal-three","status":"cancelled_by_user",
            "formal_score":None,"actual_model_tokens":300}]
        self.save_state()
        self.log("token_usage.jsonl", [
            self.usage("formal-three-task-a-B-r1","student","solve",90,10),
            self.usage("formal-three-task-a-H-r1","student","solve",90,10),
            self.usage("formal-three-task-a-M-r1","student","solve",290,10),
            self.usage("formal-three-task-a-shared","teacher","generate",45,5),
            self.usage("formal-three-task-a-shared-compress_r1","compressor","compress_r1",9,1),
            self.usage("formal-three-task-a-H-review-r1","teacher","review_r1",18,2),
            self.usage("formal-one-task-a-B-r2","student","solve",70,10),
            self.usage("formal-one-task-a-I-r1","student","solve",60,10),
            self.usage("formal-one-task-b-H-r1","student","solve",80,10),
            self.usage("formal-one-task-b-shared","teacher","generate",25,5),
        ])
        before = source.read_bytes()
        result = write_reports(self.state_path,self.bridge)
        self.assertEqual(source.read_bytes(),before)
        self.assertEqual(result["totals"]["total_tokens"],850)
        self.assertEqual(result["origin_totals"]["formal-three"]["total_tokens"],580)
        self.assertEqual(result["current_experiment_totals"]["total_tokens"],270)
        self.assertEqual(result["cancelled_prior_totals"]["total_tokens"],300)
        self.assertEqual(result["group_totals"]["cancelled_prior"]["total_tokens"],300)
        self.assertEqual(result["shared_totals"]["total_tokens"],90)
        self.assertEqual(result["shared_first_totals"]["total_tokens"],90)
        self.assertEqual(result["protocol_group_totals"]["v1_transition"]["cancelled_prior"]["total_tokens"],300)
        self.assertEqual(len(result["attempts"]),5)
        self.assertFalse(any(row["group"] == "M" for row in result["attempts"]))
        self.assertEqual(result["attempts"][0]["origin_experiment"],"formal-three")
        self.assertEqual(result["excluded_prior_attempts"][0]["status"],"cancelled_by_user")
        self.assertIsNone(result["excluded_prior_attempts"][0]["reward"])
        groups = {row["group"]:row for row in result["outcomes"]}
        for group in ("H","M"):
            self.assertEqual(groups[group]["planned_tasks"],1)
            self.assertEqual(groups[group]["first_round_solved"],1)
            self.assertEqual(groups[group]["incomplete_attempts"],0)
            self.assertEqual(groups[group]["excluded_transition_tasks"],["task-a"])
        self.assertTrue((self.output/"excluded_prior_attempt_metrics.csv").is_file())

    def test_imported_attempt_uses_origin_progress_session(self):
        prior = {"task":"task-b","group":"I","round":1,"status":"not_solved"}
        self.create_origin([prior])
        trajectory = self.output/"imported_trajs.json"
        trajectory.write_text(json.dumps({"metadata":{"wall_seconds":100}}))
        self.state["attempts"] = [{**prior,"origin_experiment":"formal-three","trajs_path":str(trajectory)}]
        self.save_state()
        (self.progress/"progress.jsonl").write_text("".join(json.dumps(row)+"\n" for row in [
            {"session":"formal-three-task-b-I-r1","duration_seconds":25,"hint":"Check both forms."},
            {"session":"formal-one-task-b-I-r1","duration_seconds":999,"hint":"Different attempt."},
        ]))
        result = aggregate_experiment(self.state_path,self.bridge)
        row = result["attempts"][0]
        self.assertEqual(row["session"],"formal-three-task-b-I-r1")
        self.assertEqual(row["teacher_wait_seconds"],25)
        self.assertEqual(row["student_active_seconds"],75)
        self.assertEqual(row["delivered_hints"],1)
        self.assertEqual(row["teacher_wait_source"],"teacher_service")

    def test_incomplete_common_first_is_not_a_branch_failure(self):
        self.set_shared_first([{"task":"task-a","group":"H","round":1,"status":"incomplete"}])
        result = aggregate_experiment(self.state_path,self.bridge)
        self.assertEqual(result["shared_first_outcomes"]["assessed_tasks"],0)
        self.assertEqual(result["shared_first_outcomes"]["incomplete_attempts"],1)
        self.assertIsNone(result["shared_first_outcomes"]["success_rate"])
        self.assertTrue(all(row["eligible_tasks"] == 0 for row in result["conditional_branch_outcomes"]))
        groups = {row["group"]:row for row in result["outcomes"]}
        self.assertEqual(groups["M"]["normal_failed_attempts"],0)
        self.assertEqual(groups["M"]["incomplete_attempts"],1)
        self.assertEqual(len(result["attempts"]),1)

    def test_actual_common_first_before_reference_is_written_is_counted_once(self):
        for status in ("running", "incomplete"):
            with self.subTest(status=status):
                self.set_shared_first([{"task":"task-a","group":"H","round":1,"status":status}])
                self.state["shared_first_attempts"] = {}
                self.save_state()
                self.log("token_usage.jsonl", [
                    self.usage("formal-one-task-a-H-r1","student","solve",90,10)])
                result = aggregate_experiment(self.state_path,self.bridge)
                self.assertEqual(result["shared_first_outcomes"]["actual_student_executions"],1)
                self.assertEqual(result["shared_first_outcomes"]["incomplete_attempts"],1)
                self.assertEqual(result["shared_first_outcomes"]["assessed_tasks"],0)
                self.assertEqual(result["shared_first_totals"]["total_tokens"],100)
                self.assertEqual(result["group_totals"]["HM"]["total_tokens"],100)
                self.assertNotIn("H",result["group_totals"])
                self.assertEqual(len(result["attempts"]),1)
                groups = {row["group"]:row for row in result["outcomes"]}
                self.assertEqual(groups["M"]["shared_first_references"],1)
                self.assertEqual(groups["M"]["incomplete_attempts"],1)
                self.assertEqual(groups["M"]["normal_failed_attempts"],0)
                self.assertTrue(all(row["eligible_tasks"] == 0 for row in result["conditional_branch_outcomes"]))

    def test_independent_v1_protocol_mapping_keeps_legacy_group_results(self):
        self.state["task_protocols"] = {task:"independent_v1" for task in self.state["tasks"]}
        self.save_state()
        result = aggregate_experiment(self.state_path,self.bridge)
        groups = {row["group"]:row for row in result["outcomes"]}
        self.assertEqual(groups["H"]["planned_tasks"],2)
        self.assertEqual(groups["H"]["first_round_solved"],1)
        self.assertFalse(groups["H"]["shared_prefix_correlated"])
        self.assertEqual(groups["M"]["incomplete_attempts"],1)




class SelectedTasksReportTests(unittest.TestCase):
    def test_subset_report_names_deferred_tasks_and_preserves_full_usage_scope(self):
        module = sys.modules["report_codex_experiments"]
        metrics = {"stage":"formal", "status":"stopped", "model":"gpt-6.1-terra",
            "reasoning_effort":"low", "dry_run":False, "selected_tasks":["new-task"],
            "deferred_prior_tasks":["unfinished-old-task"], "outcomes":[],
            "excluded_prior_attempts":[], "group_totals":{},
            "totals":{"total_tokens":123,"request_seconds":1.0}, "continuation":None,
            "included_experiment_states":["new-worker-state"], "parallelism":1,
            "parallel_new_totals":{"total_tokens":0}, "parallel_workers":[],
            "preflight_cli":None, "missing_token_fields":{}, "stop_reason":None}
        metrics["totals"]["usage_unknown_requests"] = 0
        text = module.render_report(metrics)
        self.assertIn("本批结果主表仅统计所选新题：new-task", text)
        self.assertIn("延后题：unfinished-old-task", text)
        self.assertIn("旧批延后题仍未完成", text)
        self.assertIn("123 Token", text)
        self.assertNotIn("其余九题各执行一次", text)


if __name__=="__main__":
    unittest.main()
