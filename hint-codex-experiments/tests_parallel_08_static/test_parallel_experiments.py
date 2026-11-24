"""Check fixed task queues, handoff and shared-origin accounting without models."""

import json
import signal
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source_parallel_08_static"))
import run_parallel_experiments as parallel
import report_codex_experiments as reporting
from report_codex_experiments import aggregate_experiment


class FakeProcess:
    def __init__(self, pid, path, code=0):
        self.pid, self.path, self.code = pid, path, code
        self.signals = []

    def poll(self):
        return self.code

    def send_signal(self, signum):
        self.signals.append(signum)
        self.code = -signum
        state = json.loads(self.path.read_text())
        state["status"] = "stopped"
        self.path.write_text(json.dumps(state))

    def kill(self):
        self.code = -9

    def wait(self):
        return self.code


class ParallelTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.bridge = self.root / "logs/bridge"
        self.bridge.mkdir(parents=True)
        self.progress = self.root / "logs/progress"
        self.progress.mkdir()
        self.prior3 = self.root / "runs/codex_formal_03/experiment_state.json"
        self.prior4 = self.root / "runs/codex_formal_04/experiment_state.json"
        self.manifest = self.root / "runtime_manifest.json"
        self.manifest.write_text(json.dumps({"lanes":[
            {"lane":lane,"docker_host":f"unix:///runtime/lane{lane}/docker.sock"}
            for lane in range(6)]}))
        anko = parallel.TASKS[0]
        rows = [
            {"task":anko,"group":"B","round":1,"status":"not_solved","origin_experiment":"codex_formal_03"},
            {"task":anko,"group":"H","round":1,"status":"solved","origin_experiment":"codex_formal_03"},
            {"task":anko,"group":"I","round":1,"status":"solved","origin_experiment":"codex_formal_04"},
            {"task":anko,"group":"B","round":2,"status":"solved","origin_experiment":"codex_formal_04"},
        ]
        self.prior3.parent.mkdir(parents=True)
        self.prior3.write_text(json.dumps({"experiment":"codex_formal_03","stage":"formal",
            "status":"stopped","tasks":list(parallel.TASKS),"attempts":rows[:2]+[
                {"task":anko,"group":"M","round":1,"status":"running"}]}))
        prior = {"experiment":"codex_formal_04","stage":"formal","status":"stopped",
            "stop_reason":"Interrupted","model":"gpt-6.1-terra","reasoning_effort":"low",
            "tasks":list(parallel.TASKS),"groups":list(parallel.GROUPS),"max_rounds":5,
            "student_cpus":8,"student_memory":"128g","attempts":rows,
            "continuation":{"source_experiment":"codex_formal_03","state_path":str(self.prior3)},
            "shared":{anko:{"full_hint":"original-full","first_hint":"original-compact",
                              "origin_experiment":"codex_formal_03"}},
            "excluded_prior_attempts":[{"task":anko,"group":"M","round":1,
                "origin_experiment":"codex_formal_03","status":"cancelled_by_user",
                "formal_score":None,"actual_model_tokens":30}]}
        self.prior4.parent.mkdir(parents=True)
        self.prior4.write_text(json.dumps(prior))
        self.args = parallel.build_parser().parse_args([
            "--experiment_name","codex_parallel_05","--prior_state",str(self.prior4),
            "--runtime_manifest",str(self.manifest),"--output_base",str(self.root/"runs"),
            "--bridge_dir",str(self.bridge),"--progress_dir",str(self.progress),
            "--poll_seconds","0"])
        self.commands = []
        self.processes = []

    def tearDown(self):
        self.directory.cleanup()

    def driver(self):
        return parallel.ParallelExperiments(self.args)

    def fake_popen(self, command, **kwargs):
        name = command[command.index("--experiment_name")+1]
        base = Path(command[command.index("--output_base")+1])
        tasks = command[command.index("--task_ids")+1:]
        if "--dry_run" in tasks:
            tasks = tasks[:tasks.index("--dry_run")]
        path = base/name/"experiment_state.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"experiment":name,"stage":"formal","status":"complete",
            "dry_run":"--dry_run" in command,"tasks":tasks,"groups":list(parallel.GROUPS),
            "max_rounds":5,"attempts":[],"task_protocols":{task:"shared_first_v2" for task in tasks}}))
        process = FakeProcess(100+len(self.processes),path)
        self.processes.append(process)
        self.commands.append((command,kwargs))
        return process

    def test_fixed_six_queues_cover_nine_tasks_once(self):
        driver = self.driver()
        queues = {row["lane"]:row["task_ids"] for row in driver.workers}
        self.assertEqual(queues[0],[parallel.TASKS[1],parallel.TASKS[7]])
        self.assertEqual(queues[1],[parallel.TASKS[2],parallel.TASKS[8]])
        self.assertEqual(queues[2],[parallel.TASKS[3],parallel.TASKS[9]])
        actual = [task for row in driver.workers for task in row["task_ids"]]
        self.assertEqual(sorted(actual),sorted(parallel.TASKS[1:]))
        self.assertEqual(len(actual),len(set(actual)))
        self.assertEqual(driver.state["task_protocols"][parallel.TASKS[0]],"v1_transition")
        self.assertTrue(all(row["task"] == parallel.TASKS[0] for row in driver.state["attempts"]))
        self.assertFalse(any(row["group"] == "M" for row in driver.state["attempts"]))

    def test_dry_schedule_uses_original_driver_and_separate_runtime_labels(self):
        self.args.dry_run = True
        source3, source4 = self.prior3.read_bytes(), self.prior4.read_bytes()
        driver = self.driver()
        with patch.object(parallel.subprocess,"Popen",side_effect=self.fake_popen), \
                patch.object(parallel,"request_json") as request, \
                patch.dict(parallel.os.environ,{"ALL_PROXY":"old","all_proxy":"old"}):
            self.assertEqual(driver.run(),0)
        self.assertEqual(len(self.commands),6)
        request.assert_not_called()
        for lane,(command,options) in enumerate(self.commands):
            self.assertIn("source_parallel_08_static/run_codex_experiments.py",command[3])
            self.assertIn("--shared_first_attempt",command)
            self.assertIn("--dry_run",command)
            self.assertNotIn("--continue_from",command)
            self.assertEqual(options["env"]["DOCKER_HOST"],f"unix:///runtime/lane{lane}/docker.sock")
            self.assertEqual(options["env"]["HINT_EXPERIMENT_NAME"],f"codex_parallel_05_lane{lane}")
            self.assertEqual(options["env"]["PYTHONDONTWRITEBYTECODE"],"1")
            self.assertNotIn("ALL_PROXY",options["env"])
            self.assertNotIn("all_proxy",options["env"])
            self.assertTrue(options["start_new_session"])
        self.assertEqual(self.prior3.read_bytes(),source3)
        self.assertEqual(self.prior4.read_bytes(),source4)
        self.assertFalse(driver.state_path.with_suffix(".tmp").exists())

    def test_worker_completes_at_poll_after_earlier_running_state(self):
        self.args.dry_run = True
        driver = self.driver()
        def start(command, **kwargs):
            process = self.fake_popen(command, **kwargs)
            state = json.loads(process.path.read_text())
            state["status"] = "running"
            process.path.write_text(json.dumps(state))
            def complete_at_poll():
                completed = json.loads(process.path.read_text())
                completed["status"] = "complete"
                process.path.write_text(json.dumps(completed))
                return 0
            process.poll = complete_at_poll
            return process
        with patch.object(parallel.subprocess, "Popen", side_effect=start), \
                patch.object(parallel, "request_json") as request:
            self.assertEqual(driver.run(), 0)
        self.assertEqual(driver.state["status"], "complete")
        self.assertTrue(all(worker["status"] == "complete" for worker in driver.workers))
        self.assertFalse(any(process.signals for process in self.processes))
        request.assert_not_called()

    def test_prior_must_be_stopped_nonquota_and_naturally_complete(self):
        original = json.loads(self.prior4.read_text())
        invalid = [dict(original,status="running"),dict(original,stop_reason="usage_limit reached")]
        unfinished = json.loads(json.dumps(original))
        unfinished["attempts"] = [row for row in unfinished["attempts"]
                                  if not (row["group"] == "B" and row["round"] == 2)]
        invalid.append(unfinished)
        started_next = json.loads(json.dumps(original))
        started_next["attempts"].append({"task":parallel.TASKS[1],"group":"H","round":1,"status":"running"})
        invalid.append(started_next)
        with patch.object(parallel.subprocess,"Popen") as popen:
            for prior in invalid:
                self.prior4.write_text(json.dumps(prior))
                with self.assertRaises(ValueError):
                    self.driver()
            popen.assert_not_called()

    def test_worker_failure_stops_global_models_and_only_owned_workers(self):
        driver = self.driver()
        def start(command,**kwargs):
            process = self.fake_popen(command,**kwargs)
            state = json.loads(process.path.read_text())
            if len(self.processes) == 1:
                process.code = 2
                state.update(status="stopped",stop_reason="worker error")
            else:
                process.code = None
                state["status"] = "running"
            process.path.write_text(json.dumps(state))
            return process
        clients = []
        def docker_client(base_url):
            calls = []
            client = SimpleNamespace(containers=SimpleNamespace(
                list=lambda **kwargs:calls.append(kwargs) or []),close=lambda:None)
            clients.append((base_url,calls))
            return client
        with patch.object(parallel.subprocess,"Popen",side_effect=start), \
                patch.object(parallel,"request_json",return_value={"stopped":False}) as request, \
                patch.dict(sys.modules,{"docker":SimpleNamespace(DockerClient=docker_client)}):
            self.assertEqual(driver.run(),2)
        self.assertEqual(driver.state["status"],"stopped")
        self.assertTrue(any(call.args[0].endswith("/stop") for call in request.call_args_list))
        self.assertTrue(all(process.signals == [signal.SIGINT] for process in self.processes[1:]))
        self.assertEqual(len(clients),6)
        labels=[calls[0]["filters"]["label"] for _,calls in clients]
        self.assertEqual(labels,[f"hint.experiment_name=codex_parallel_05_lane{lane}" for lane in range(6)])
        self.assertFalse(any("formal_04" in label or "formal_03" in label for label in labels))

    def create_prior05(self):
        source = json.loads(self.prior4.read_text())
        path = self.root / "runs/codex_parallel_05/experiment_state.json"
        path.parent.mkdir(parents=True)
        source.update(experiment="codex_parallel_05", status="stopped",
                      stop_reason="Teacher review failed: stopped fixture",
                      continuation={"source_experiment":"codex_formal_04", "state_path":str(self.prior4)},
                      included_experiment_states=[], shared_first_attempts={})
        queues = parallel.task_queues(json.loads(self.manifest.read_text())["lanes"])
        for lane in range(6):
            task = queues[lane][0]
            name = f"codex_parallel_05_lane{lane}"
            row = {"task":task,"group":"H","round":1,
                   "status":"not_solved" if lane in (0,5) else "running",
                   "origin_experiment":name,"shared_with":["H","M"],
                   "attribution_group":"HM","stage":"shared_first_student"}
            source["attempts"].append(row)
            source["shared"][task] = {"full_hint":"retained-old-hint","origin_experiment":name}
            worker = path.parent/"lanes"/name/"experiment_state.json"
            worker.parent.mkdir(parents=True)
            worker.write_text(json.dumps({"experiment":name,"stage":"formal","status":"stopped",
                "tasks":queues[lane],"attempts":[row]}))
            source["included_experiment_states"].append(str(worker))
            source["shared_first_attempts"][task] = {"origin_experiment":name,"group":"H","round":1,
                                                      "status":row["status"]}
        path.write_text(json.dumps(source))
        self.args.prior_state = str(path)
        self.args.experiment_name = "codex_parallel_06"
        self.args.task_ids = list(parallel.TASKS[7:])
        return path

    def test_new_task_subset_keeps_original_lanes_and_all_prior_observations(self):
        prior05 = self.create_prior05()
        before = {path:path.read_bytes() for path in (self.prior3,self.prior4,prior05)}
        self.args.dry_run = True
        driver = self.driver()
        self.assertEqual([(row["lane"],row["task_ids"]) for row in driver.workers],
                         [(0,[parallel.TASKS[7]]),(1,[parallel.TASKS[8]]),(2,[parallel.TASKS[9]])])
        self.assertEqual(driver.state["tasks"],list(parallel.TASKS))
        self.assertEqual(driver.state["selected_tasks"],list(parallel.TASKS[7:]))
        self.assertEqual(driver.state["deferred_prior_tasks"],list(parallel.TASKS[1:7]))
        self.assertEqual(driver.state["available_runtime_lanes"],6)
        self.assertEqual(driver.state["parallelism"],3)
        self.assertEqual(driver.state["completion_scope"],"selected_tasks_only")
        self.assertFalse(driver.state["deferred_prior_tasks_completed"])
        self.assertEqual(len(driver.state["attempts"]),10)
        interrupted=[row for row in driver.state["attempts"] if row["status"] == "interrupted"]
        self.assertEqual(len(interrupted),4)
        self.assertTrue(all(row["original_status"] == "running" for row in interrupted))
        self.assertEqual(driver.state["shared_first_attempts"][parallel.TASKS[2]]["status"],"interrupted")
        with patch.object(parallel.subprocess,"Popen",side_effect=self.fake_popen), \
                patch.object(parallel,"request_json") as request:
            self.assertEqual(driver.run(),0)
        self.assertEqual(len(self.commands),3)
        self.assertTrue(all(path.read_bytes() == value for path,value in before.items()))
        self.assertFalse(driver.state["deferred_prior_tasks_completed"])
        request.assert_not_called()

    def test_subset_rejects_prepared_hint_even_without_student_attempt(self):
        prior05 = self.create_prior05()
        source = json.loads(prior05.read_text())
        source["shared"][parallel.TASKS[8]] = {"full_hint":"already-prepared"}
        prior05.write_text(json.dumps(source))
        with patch.object(parallel.subprocess,"Popen") as popen:
            with self.assertRaisesRegex(ValueError,"no prior attempt or shared"):
                self.driver()
            self.args.task_ids = [parallel.TASKS[1]]
            with self.assertRaisesRegex(ValueError,"no prior attempt or shared"):
                self.driver()
            popen.assert_not_called()

    def test_subset_recursive_usage_keeps_old_workers_once_and_new_cost_separate(self):
        prior05 = self.create_prior05()
        before = prior05.read_bytes()
        anko = parallel.TASKS[0]
        logs = [
            self.usage(f"codex_formal_03-{anko}-B-r1","student","solve",10),
            self.usage(f"codex_formal_03-{anko}-M-r1","student","solve",30),
            self.usage(f"codex_formal_04-{anko}-I-r1","student","solve",20),
            self.usage(f"codex_parallel_05_lane0-{parallel.TASKS[1]}-H-r1","student","solve",30),
            self.usage(f"codex_parallel_05_lane1-{parallel.TASKS[2]}-H-r1","student","solve",40),
            self.usage(f"codex_parallel_06_lane0-{parallel.TASKS[7]}-I-r1","student","solve",50),
        ]
        (self.bridge/"token_usage.jsonl").write_text("".join(json.dumps(row)+"\n" for row in logs))
        driver = self.driver()
        with patch.object(parallel.subprocess,"Popen",side_effect=self.fake_popen), \
                patch.object(parallel,"request_json",return_value={"stopped":False}):
            self.assertEqual(driver.run(),0)
        result = aggregate_experiment(driver.state_path,self.bridge,self.progress)
        self.assertEqual(result["totals"]["total_tokens"],180)
        self.assertEqual(result["parallel_new_totals"]["total_tokens"],50)
        self.assertEqual(result["cancelled_prior_totals"]["total_tokens"],30)
        self.assertEqual(result["origin_totals"]["codex_formal_03"]["total_tokens"],40)
        self.assertEqual(result["origin_totals"]["codex_formal_04"]["total_tokens"],20)
        self.assertEqual(result["origin_totals"]["codex_parallel_05_lane0"]["total_tokens"],30)
        self.assertEqual(result["origin_totals"]["codex_parallel_05_lane1"]["total_tokens"],40)
        self.assertEqual(len(result["included_experiments"]),13)
        self.assertTrue(all(row["planned_tasks"] == 3 for row in result["outcomes"]))
        self.assertEqual(prior05.read_bytes(),before)

    def usage(self, session, role, phase, total):
        return {"session":session,"role":role,"phase":phase,"delta":{
            "inputTokens":total-1,"cachedInputTokens":0,"outputTokens":1,
            "reasoningOutputTokens":0,"totalTokens":total}}

    def test_worker_first_state_appearing_between_catalog_and_origin_reads_is_attributed(self):
        driver = self.driver()
        worker = driver.workers[0]
        task = worker["task_ids"][0]
        path = Path(worker["state_path"])
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"experiment":worker["experiment"],"stage":"formal",
            "status":"running","tasks":worker["task_ids"],"attempts":[]}))
        event = self.usage(f"{worker['experiment']}-{task}-B-r1", "student", "solve", 100)
        (self.bridge/"token_usage.jsonl").write_text(json.dumps(event)+"\n")
        read_json = reporting.read_json
        observations = []

        def appearing_state(filename, default=None):
            if Path(filename) == path:
                observations.append(filename)
                if len(observations) == 1:
                    return default
            return read_json(filename, default)

        with patch.object(reporting,"read_json",side_effect=appearing_state):
            result = aggregate_experiment(driver.state_path,self.bridge,self.progress)
        self.assertGreaterEqual(len(observations), 2)
        self.assertIn(worker["experiment"], result["included_experiments"])
        self.assertEqual(result["totals"]["total_tokens"], 100)
        self.assertEqual(result["parallel_new_totals"]["total_tokens"], 100)
        self.assertEqual(result["origin_totals"][worker["experiment"]]["total_tokens"], 100)
        self.assertEqual([(row["experiment"],row["task"],row["group"])
                          for row in result["stages"]], [(worker["experiment"],task,"B")])

    def test_recursive_origins_cost_once_and_transition_not_in_v2_effects(self):
        driver = self.driver()
        anko = parallel.TASKS[0]
        logs = [
            self.usage(f"codex_formal_03-{anko}-B-r1","student","solve",10),
            self.usage(f"codex_formal_03-{anko}-H-r1","student","solve",20),
            self.usage(f"codex_formal_03-{anko}-M-r1","student","solve",30),
            self.usage(f"codex_formal_03-{anko}-shared","teacher","generate",4),
            self.usage(f"codex_formal_03-{anko}-shared-compress_r1","compressor","compress_r1",2),
            self.usage(f"codex_formal_03-{anko}-H-review-r1","teacher","review_r1",3),
            self.usage(f"codex_formal_04-{anko}-I-r1","student","solve",40),
            self.usage(f"codex_formal_04-{anko}-B-r2","student","solve",50),
            self.usage(f"codex_formal_04-{anko}-I-review-r1","teacher","review_r1",5),
            self.usage(f"codex_formal_01-{anko}-B-r1","student","solve",999),
        ]
        for worker in driver.workers:
            task = worker["task_ids"][0]
            failed = worker["lane"] == 0
            row = {"task":task,"group":"H","round":1,
                   "status":"not_solved" if failed else "solved",
                   "origin_experiment":worker["experiment"],"shared_with":["H","M"],
                   "attribution_group":"HM","stage":"shared_first_student"}
            attempts = [row]
            if failed:
                attempts.extend([{**row,"group":"H","round":2,"status":"not_solved","stage":"student","shared_with":[]},
                                 {**row,"group":"M","round":2,"status":"solved","stage":"student","shared_with":[]}])
            path = Path(worker["state_path"])
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"experiment":worker["experiment"],"stage":"formal",
                "status":"complete","tasks":worker["task_ids"],"attempts":attempts,
                "shared_first_attempts":{task:{"origin_experiment":worker["experiment"],"group":"H","round":1}},
                "task_protocols":{task:"shared_first_v2" for task in worker["task_ids"]}}))
            logs.append(self.usage(f"{worker['experiment']}-{task}-H-r1","student","solve",100))
            if failed:
                logs.extend([
                    self.usage(f"{worker['experiment']}-{task}-H-review-r1","teacher","review_r1",7),
                    self.usage(f"{worker['experiment']}-{task}-shared","teacher","review_r1",8),
                    self.usage(f"{worker['experiment']}-{task}-H-r2","student","solve",60),
                    self.usage(f"{worker['experiment']}-{task}-M-r2","student","solve",70),
                    self.usage(f"{worker['experiment']}-{task}-shared","teacher","generate",11),
                    self.usage(f"{worker['experiment']}-{task}-shared-compress_r1","compressor","compress_r1",1),
                ])
            else:
                logs.append(self.usage(f"{worker['experiment']}-{task}-H-review-r1","teacher","review_r1",2))
        (self.bridge/"token_usage.jsonl").write_text("".join(json.dumps(row)+"\n" for row in logs))
        driver.state["included_experiment_states"].append(driver.workers[0]["state_path"])
        driver.refresh()
        result = aggregate_experiment(driver.state_path,self.bridge,self.progress)
        self.assertEqual(result["totals"]["total_tokens"],931)
        self.assertEqual(result["parallel_new_totals"]["total_tokens"],767)
        self.assertEqual(result["origin_totals"]["codex_formal_03"]["total_tokens"],69)
        self.assertEqual(result["origin_totals"]["codex_formal_04"]["total_tokens"],95)
        self.assertEqual(result["cancelled_prior_totals"]["total_tokens"],30)
        self.assertNotIn("codex_formal_01",result["included_experiments"])
        self.assertEqual(len(result["included_experiments"]),9)
        self.assertEqual(result["shared_first_outcomes"]["actual_student_executions"],6)
        self.assertEqual(result["shared_first_outcomes"]["solved_tasks"],5)
        groups={row["group"]:row for row in result["outcomes"]}
        self.assertEqual(groups["H"]["planned_tasks"],9)
        self.assertEqual(groups["M"]["first_round_solved"],5)
        self.assertEqual(groups["M"]["solved_tasks"],6)
        self.assertTrue(all(row["eligible_tasks"] == 1 for row in result["conditional_branch_outcomes"]))
        stages={row["stage"] for row in result["stages"] if row["group"] == "HM"}
        self.assertEqual(stages,{"shared_first_student","shared_success_review"})
        text=(driver.output/"report.md").read_text()
        self.assertIn("M教师记忆机制未触发",text)
        self.assertIn("本并行段新增实际用量：767",text)


if __name__ == "__main__":
    unittest.main()
