#!/usr/bin/env python3
"""Run the four paired Hint conditions through the original experiment steps."""

import argparse
import csv
import json
import logging
import os
import shutil
import signal
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

from benchmark.deepswe.run_loop_by_hint import HintLoopOrchestrator, build_parser, run_step, _sigint_handler
from report_codex_experiments import records, write_reports

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT.parent / "hint-baseline-run/data"
MODEL = "gpt-6.1-terra"
GROUPS = ("B", "H", "M", "I")
TASKS = (
    "anko-default-function-arguments", "claude-code-by-agents-recursive-delegation",
    "igel-persist-feature-schema", "ink-grid-box-layout", "kea-atomic-signal-selectors",
    "obsidian-linter-auto-table-of-contents", "sqlfmt-create-table-ddl-formatting",
    "termenv-preserve-ansi-resets", "textual-kitty-key-phases",
    "valibot-recursive-schema-composition",
)
LOG = logging.getLogger("codex_experiments")


def request_json(url, data=None):
    body = json.dumps(data).encode() if data is not None else None
    request = Request(url, data=body, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


class PairedExperiments:
    def __init__(self, args):
        self.args = args
        self.task_ids = getattr(args, "task_ids", None)
        if self.task_ids:
            if args.stage != "formal" or getattr(args, "continue_from", ""):
                raise ValueError("Task workers require the formal stage without continuation")
            if any(task not in TASKS for task in self.task_ids):
                raise ValueError("Task workers must select tasks from the fixed experiment list")
        self.output = Path(args.output_base) / args.experiment_name
        self.output.mkdir(parents=True, exist_ok=True)
        self.summary_path = self.output / "experiment_state.json"
        if self.summary_path.exists():
            raise FileExistsError("Choose a new experiment name; existing results are preserved")
        self.state = {
            "experiment": args.experiment_name, "stage": args.stage, "status": "running",
            "dry_run": args.dry_run,
            "started_at": time.time(), "model": MODEL, "reasoning_effort": "low",
            "max_rounds": 5, "groups": list(GROUPS), "tasks": list(TASKS),
            "student_cpus": 8, "student_memory": "128g", "verifier_memory": "8g",
            "student_active_timeout_seconds": 7200, "initial_teacher_timeout_seconds": 3600,
            "online_interval_tools": 20, "online_max_checks": 3,
            "online_max_hint_words": 100, "online_check_timeout_seconds": 600,
            "teacher_review_interface": "shared_sdk_tools",
            "initial_hints_shared": True, "student_attempts_independent": True,
            "tool_delivery": "stateless_exec_actions", "model_backend": "stateless_exec_action",
            "context_owner": "claude_sdk", "sdk_auto_compact_window": 400000,
            "native_roles": "sdk_messages_serialized_as_json", "native_sampling": "cli_defaults",
            "unmapped_api_parameters": ["temperature", "top_p", "max_tokens"], "attempts": [], "shared": {},
            "quota_policy": "save_and_stop_without_automatic_resume",
            "container_http_proxy": getattr(args, "container_http_proxy", "http://10.0.2.2:7897"),
        }
        self.kept_teachers = []
        self.shared_first_attempt = getattr(args, "shared_first_attempt", False)
        if self.shared_first_attempt and args.stage != "formal":
            raise ValueError("Shared first attempts require the formal stage")
        self.state["shared_first_attempt"] = self.shared_first_attempt
        self.state["student_attempts_independent"] = not self.shared_first_attempt
        self.state["fresh_student_state_each_actual_attempt"] = True
        self.state["shared_first_attempts"] = {}
        self.state["task_protocols"] = {}
        self.state["skipped_groups"] = {}
        if getattr(args, "continue_from", ""):
            self.load_continuation(Path(args.continue_from))

    def load_continuation(self, path):
        """Import completed observations without resuming or rewriting the old run."""
        if not self.shared_first_attempt or self.args.stage != "formal":
            raise ValueError("Continuation requires --shared_first_attempt in the formal stage")
        path = (path / "experiment_state.json" if path.is_dir() else path).resolve()
        source = json.loads(path.read_text())
        if source["experiment"] == self.args.experiment_name:
            raise ValueError("Continuation requires a new experiment name")
        reason = source.get("stop_reason", "").lower()
        if source["status"] != "stopped" or any(
                word in reason for word in ("quota", "rate limit", "rate_limit", "ratelimit",
                                            "usage limit", "usage_limit", "usagelimit",
                                            "limit reached", "429", "balance", "credit")):
            raise ValueError("Only an explicitly stopped, non-quota experiment can be continued")
        self.state["continuation"] = {
            "source_experiment": source["experiment"], "state_path": str(path),
        }
        completed = [dict(row, origin_experiment=source["experiment"])
                     for row in source["attempts"] if row["group"] in ("B", "H")
                     and row["status"] in ("solved", "not_solved")]
        self.state["attempts"] = completed
        for task in {row["task"] for row in completed}:
            self.state["task_protocols"][task] = "v1_transition"
            self.state["skipped_groups"][task] = ["M"]
            shared = dict(source["shared"][task], origin_experiment=source["experiment"])
            shared["golden_diff"] = str(Path(shared["full_hint"]).parent / "golden_diff.diff")
            self.state["shared"][task] = shared
        manifest = path.parents[2] / "preflight" / (
            source["experiment"].removeprefix("codex_") + "_user_protocol_change") / "M1_cancellation.json"
        cancellation = json.loads(manifest.read_text())
        self.state["excluded_prior_attempts"] = [dict(
            cancellation, origin_experiment=source["experiment"],
            original_status=next(row["status"] for row in source["attempts"]
                                 if row["task"] == cancellation["task"]
                                 and row["group"] == cancellation["group"]
                                 and row["round"] == cancellation["round"]),
            manifest_path=str(manifest),
        )]

    def continued_shared(self, task):
        shared = self.loop(task, "shared")
        source = self.state["shared"][task]
        shared.args.teacher_state = source["teacher_state"]
        shared.full_hint_path = Path(source["full_hint"])
        shared.golden_diff_path = Path(source["golden_diff"])
        shared.hint_gen_dir = Path(source["first_hint"]).parent
        return shared

    def save(self):
        temporary = self.summary_path.with_name(self.summary_path.name + ".tmp")
        temporary.write_text(json.dumps(self.state, ensure_ascii=False, indent=2) + "\n")
        temporary.replace(self.summary_path)
        self.write_report()

    def bridge_status(self):
        if self.args.dry_run:
            return {"stopped": False}
        return request_json(self.args.api_base.rstrip("/") + "/status")

    def check_running(self):
        status = self.bridge_status()
        if status["stopped"]:
            raise RuntimeError(status.get("stop_reason") or "The model bridge stopped")

    def loop(self, task, group, teacher_state=""):
        name = f"{self.args.experiment_name}_{group}"
        session = f"{self.args.experiment_name}-{task}-{group}"
        argv = [
            "--instance_id", task, "--run_name", name,
            "--output_base", str(self.output), "--python_bin", sys.executable,
            "--parquet_file", str(DATA / "deep_swe_tasks.parquet"),
            "--tasks_dir", str(DATA / "tasks"), "--model_name", MODEL,
            "--api_base", self.args.api_base, "--container_api_base", self.args.container_api_base,
            "--api_key", "codex-local", "--codex_session", session,
            "--container_cpus", "8", "--mem_limit", "128g", "--max_rounds", "5",
            "--baseline_rounds", "5", "--skip_docker_login",
            "--teacher_status_url", self.args.progress_base + "/experiment/status",
        ]
        if group == "B":
            argv.append("--no_hint_run")
        else:
            argv += ["--teacher_state", str(teacher_state),
                     "--teacher_session_mode", "resume" if group == "M" else "fresh"]
            if group == "M":
                argv += ["--teacher_codex_session", f"{self.args.experiment_name}-{task}-shared"]
        if group == "I":
            argv += ["--teacher_progress_url", self.args.container_progress_base + "/experiment/progress"]
        if self.args.dry_run:
            argv.append("--dry_run")
        loop = HintLoopOrchestrator(build_parser().parse_args(argv))
        loop.sub_env["HTTP_PROXY"] = self.state["container_http_proxy"]
        loop.sub_env["ALL_PROXY"] = ""
        loop.sub_env["all_proxy"] = ""
        loop.sub_env["NO_PROXY"] = loop.sub_env.get("NO_PROXY", "localhost,127.0.0.1") + ",172.17.0.1"
        loop.sub_env["no_proxy"] = loop.sub_env["NO_PROXY"]
        loop.summary["group"] = group
        return loop

    def prepare_shared(self, task):
        shared = self.loop(task, "shared")
        shared.args.teacher_state = str(shared.hint_gen_dir / "teacher_state.json")
        shared.args.teacher_codex_session = f"{self.args.experiment_name}-{task}-shared"
        shared.args.keep_teacher = True
        self.check_running()
        if not shared.step_get_hint():
            raise RuntimeError(f"Initial teacher generation failed for {task}")
        state_path = Path(shared.args.teacher_state)
        self.kept_teachers.append(state_path)
        self.check_running()
        if not shared.step_compress(1, []):
            raise RuntimeError(f"Initial Hint compression failed for {task}")
        self.state["shared"][task] = {
            "teacher_state": str(state_path), "full_hint": str(shared.full_hint_path),
            "first_hint": str(shared._hint_path_for_round(1)),
            "golden_diff": str(shared.golden_diff_path),
            "origin_experiment": self.args.experiment_name,
            "cost_shared_by": ["H", "M", "I"],
        }
        self.save()
        return shared

    def use_shared(self, loop, shared):
        loop.hint_gen_dir.mkdir(parents=True, exist_ok=True)
        if self.args.dry_run:
            return
        for source, target in (
            (shared.full_hint_path, loop.full_hint_path),
            (shared.golden_diff_path, loop.golden_diff_path),
            (shared._hint_path_for_round(1), loop._hint_path_for_round(1)),
        ):
            shutil.copyfile(source, target)

    def register_online(self, task, loop, round_num):
        if self.args.dry_run:
            return
        import pyarrow.parquet as pq
        row = next(row for row in pq.read_table(DATA / "deep_swe_tasks.parquet").to_pylist()
                   if row["instance_id"] == task)
        session = f"{loop.args.codex_session}-r{round_num}"
        request_json(self.args.progress_base + "/experiment/register", {
            "session": session, "task": task, "problem_statement": row["problem_statement"],
            "golden_diff": loop.golden_diff_path.read_text(),
            "current_hint": loop._hint_path_for_round(round_num).read_text(),
            "api_base": loop._phase_api_base("online_teacher", f"r{round_num}"),
            "api_key": "codex-local", "model": MODEL,
        })

    def run_attempt(self, task, group, loop, round_num, reviews, review=True, shared_first=False):
        self.check_running()
        if group != "B" and round_num > 1:
            if not loop.step_compress(round_num, reviews):
                raise RuntimeError(f"Hint compression failed: {task}/{group}/{round_num}")
        if group == "I":
            self.register_online(task, loop, round_num)
        started = time.monotonic()
        entry = {"task": task, "group": group, "round": round_num,
                 "started_at": time.time(), "status": "running",
                 "origin_experiment": self.args.experiment_name}
        if shared_first:
            entry.update(shared_with=["H", "M"], attribution_group="HM",
                         stage="shared_first_student")
        self.state["attempts"].append(entry)
        self.save()
        result = loop.step_solve(round_num, no_hint=group == "B")
        entry["elapsed_seconds"] = time.monotonic() - started
        entry["finished_at"] = time.time()
        entry["trajs_path"] = str(loop._trajs_path(round_num))
        entry["eval_path"] = str(loop._eval_path(round_num))
        if result is None:
            entry["status"] = "incomplete"
            self.save()
            self.check_running()
            raise RuntimeError(f"Student attempt did not produce a formal evaluation: {task}/{group}/{round_num}")
        entry.update(result)
        entry["status"] = "solved" if result["solved"] else "not_solved"
        loop.summary["rounds"].append(dict(entry))
        loop.summary["total_rounds"] = round_num
        loop.summary["solved"] = result["solved"]
        if result["solved"]:
            loop.summary["solved_round"] = round_num
        loop._save_summary()
        self.save()
        self.check_running()
        if review:
            self.review_attempt(task, group, loop, round_num, reviews, entry)
        return result["solved"]

    def review_attempt(self, task, group, loop, round_num, reviews, entry,
                       trajs_override=None, review_results=None):
        if group != "B" and (entry["solved"] or round_num < self.round_limit):
            kwargs = {"solved": entry["solved"]}
            if trajs_override is not None:
                kwargs["trajs_override"] = trajs_override
            ok = loop.step_review(round_num, **kwargs)
            status = "done" if ok else "failed"
            if entry["group"] == group:
                entry["review"] = status
            if review_results is not None:
                review_results[group] = status
            self.save()
            self.check_running()
            if not ok and not entry["solved"]:
                raise RuntimeError(f"Teacher review failed: {task}/{group}/{round_num}")
            if ok and not entry["solved"]:
                reviews.append(loop._review_json_path(round_num))

    def run_shared_first(self, task, get_loop, reviews, solved):
        loop = get_loop("H")
        passed = self.run_attempt(task, "H", loop, 1, reviews["H"],
                                  review=False, shared_first=True)
        entry = self.state["attempts"][-1]
        reference = {key: entry[key] for key in (
            "origin_experiment", "group", "round", "shared_with", "trajs_path",
            "eval_path", "status", "solved")}
        reference.update(mechanism_triggered=not passed, reviews={})
        self.state["shared_first_attempts"][task] = reference
        self.save()
        self.review_attempt(task, "H", loop, 1, reviews["H"], entry,
                            review_results=reference["reviews"])
        if passed:
            solved.update(("H", "M"))
            reference["reviews"]["M"] = "not_triggered"
        else:
            memory_loop = get_loop("M")
            memory_loop.summary["shared_first_attempt"] = dict(reference)
            memory_loop.summary["total_rounds"] = 1
            self.review_attempt(task, "M", memory_loop, 1, reviews["M"], entry,
                                trajs_override=Path(entry["trajs_path"]),
                                review_results=reference["reviews"])
            memory_loop._save_summary()
        self.save()

    def verify_teacher_resume(self, loop, shared):
        """Use the integration trajectory to check the persistent teacher before formal runs."""
        if self.args.dry_run:
            return
        session = shared.args.teacher_codex_session
        before = json.loads(Path(shared.args.teacher_state).read_text())["session_id"]
        bridge_dir = Path(self.args.bridge_dir)
        initial = [row for row in records(bridge_dir / "model_responses.jsonl")
                   if row["session"] == session and row["role"] == "teacher"
                   and row["phase"] == "generate"]
        output = self.output / "teacher_resume_probe"
        output.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable, str(Path(__file__).resolve().parent / "benchmark/deepswe/review_hint_traj.py"),
            "--trajs", str(loop._trajs_path(1)), "--hint", str(loop._hint_path_for_round(1)),
            "--golden_diff", str(loop.golden_diff_path),
            "--teacher_state", shared.args.teacher_state, "--teacher_session", "resume",
            "--teacher_output_dir", str(output / "teacher"),
            "--output", str(output / "review.md"), "--json_output", str(output / "review.json"),
            "--model", MODEL, "--api_key", "codex-local",
            "--api_base", shared._phase_api_base("teacher", "resume_probe", container=True,
                                                 session=session),
        ]
        if loop.summary["solved"]:
            command.append("--solved")
        code = run_step("teacher_resume_probe", command, output / "run.log", env=loop.sub_env)
        self.check_running()
        after = json.loads(Path(shared.args.teacher_state).read_text())["session_id"]
        requests = [row for row in records(bridge_dir / "model_requests.jsonl")
                    if row["session"] == session and row["role"] == "teacher"
                    and row["phase"] == "resume_probe"]
        history = requests[0]["request"]["messages"] if requests else []
        initial_final = initial[-1]["response"]["choices"][0]["message"] if initial else None
        preserved_final = initial_final is not None and initial_final in history
        passed = (code == 0 and (output / "review.json").is_file()
                  and before == after and preserved_final)
        self.state["teacher_resume_probe"] = {
            "passed": passed, "output": str(output), "before_sdk_session": before,
            "after_sdk_session": after, "initial_final_in_review_history": preserved_final,
            "review_request_ids": [row["request_id"] for row in requests],
        }
        self.save()
        if not passed:
            raise RuntimeError("The persistent teacher integration check did not pass")

    def run(self):
        self.round_limit = 1 if self.args.stage == "integration" else 5
        tasks = ("termenv-preserve-ansi-resets", "kea-atomic-signal-selectors") \
            if self.args.stage == "integration" else TASKS
        if self.task_ids:
            tasks = tuple(task for task in TASKS if task in self.task_ids)
            self.state["task_partition"] = {
                "requested_task_ids": list(self.task_ids), "task_ids": list(tasks),
                "global_task_indices": {task: TASKS.index(task) for task in tasks},
            }
        self.state["tasks"] = list(tasks)
        self.state["max_rounds"] = self.round_limit
        for task in tasks:
            self.state["task_protocols"].setdefault(
                task, "shared_first_v2" if self.shared_first_attempt else "independent_v1")
        if self.args.stage == "integration":
            self.state["groups"] = ["H", "I"]
            self.state["task_groups"] = {"H": [tasks[0]], "I": [tasks[1]]}
        self.save()
        try:
            for index, task in enumerate(tasks):
                if self.args.stage == "formal":
                    index = TASKS.index(task)
                previous = [row for row in self.state["attempts"] if row["task"] == task]
                completed = {(row["group"], row["round"]) for row in previous}
                shared = self.continued_shared(task) if task in self.state["shared"] else None
                loops, reviews = {}, {}
                solved = {row["group"] for row in previous if row["status"] == "solved"}
                skipped = self.state["skipped_groups"].get(task, [])
                order = GROUPS[index % 4:] + GROUPS[:index % 4]
                if self.args.stage == "integration":
                    order = ("H",) if index == 0 else ("I",)

                def get_loop(group):
                    nonlocal shared
                    if group not in loops:
                        if group != "B" and shared is None:
                            shared = self.prepare_shared(task)
                        state = shared.args.teacher_state if shared and group != "B" else ""
                        loops[group] = self.loop(task, group, state)
                        reviews[group] = []
                        if group != "B":
                            self.use_shared(loops[group], shared)
                        imported = [row for row in previous if row["group"] == group]
                        if imported:
                            loops[group].summary["rounds"] = [dict(row) for row in imported]
                            loops[group].summary["total_rounds"] = max(row["round"] for row in imported)
                    return loops[group]

                for round_num in range(1, self.round_limit + 1):
                    for group in order:
                        if group in solved or group in skipped or (group, round_num) in completed:
                            continue
                        if (self.state["task_protocols"][task] == "shared_first_v2"
                                and round_num == 1 and group in ("H", "M")):
                            if task not in self.state["shared_first_attempts"]:
                                self.run_shared_first(task, get_loop, reviews, solved)
                            continue
                        loop = get_loop(group)
                        if self.run_attempt(task, group, loop, round_num, reviews[group]):
                            solved.add(group)
                if self.args.stage == "integration" and index == 0:
                    self.verify_teacher_resume(loops["H"], shared)
                for group, loop in loops.items():
                    loop._finish_summary(0 if group in solved else 1,
                                         "solved" if group in solved else "not_solved")
                self.close_teachers()
            self.state["status"] = "complete"
        except (Exception, KeyboardInterrupt) as exc:
            self.state["status"] = "stopped"
            self.state["stop_reason"] = str(exc) or "Interrupted"
            LOG.exception("Experiment stopped; preserving all completed results")
            if not self.args.dry_run:
                try:
                    request_json(self.args.api_base.rstrip("/") + "/stop",
                                 {"reason": self.state["stop_reason"]})
                except Exception as stop_error:
                    self.state["bridge_stop_error"] = str(stop_error)
        finally:
            try:
                self.close_teachers()
            except Exception as cleanup_error:
                self.state["cleanup_error"] = str(cleanup_error)
                LOG.exception("Could not remove the kept teacher containers")
            self.state["finished_at"] = time.time()
            self.save()
            write_reports(self.summary_path,
                          getattr(self.args, "bridge_dir", ROOT / "logs/bridge"),
                          getattr(self.args, "progress_dir", ROOT / "logs/progress"))
        return 0 if self.state["status"] == "complete" else 2

    def close_teachers(self):
        if self.args.dry_run:
            self.kept_teachers.clear()
            return
        import docker
        client = docker.from_env()
        if self.state["status"] == "stopped":
            retained = []
            for container in client.containers.list(all=True, filters={
                    "label": "hint.experiment_name=" + self.args.experiment_name}):
                container.stop(timeout=10)
                retained.append(container.name)
            self.state["retained_containers"] = retained
            self.kept_teachers.clear()
            client.close()
            return
        for path in self.kept_teachers:
            if path.exists():
                name = json.loads(path.read_text())["container_name"]
                try:
                    client.containers.get(name).remove(force=True)
                except docker.errors.NotFound:
                    pass
        for container in client.containers.list(all=True, filters={
                "label": "hint.experiment_name=" + self.args.experiment_name}):
            container.remove(force=True)
        self.kept_teachers.clear()
        client.close()

    def write_report(self):
        attempts = self.state["attempts"]
        with (self.output / "results.csv").open("w", newline="") as stream:
            fields = ["task", "group", "round", "status", "elapsed_seconds", "eval_path", "trajs_path"]
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(attempts)
        if self.shared_first_attempt and not self.args.dry_run:
            write_reports(self.summary_path,
                          getattr(self.args, "bridge_dir", ROOT / "logs/bridge"),
                          getattr(self.args, "progress_dir", ROOT / "logs/progress"))
            return
        if self.args.dry_run:
            scope_note = "本次仅演练编排，占位结果不计入实验成绩。"
        elif self.args.stage == "integration":
            scope_note = "联调仅运行 Termenv-H、Kea-I 各1题，使用正式评测；两题不同，不比较组间效果。"
        else:
            scope_note = "本次比较采用原十题；所有成绩来自正式评测。联调结果单独记录。"
        if self.shared_first_attempt:
            scope_note += " H/M 共用一次实际首轮，表中只记录实际执行的学生；过渡题与后续共同首轮题分开分析。"
        lines = ["# Codex Hint 实验进度", "", f"状态：{self.state['status']}",
                 f"模型：{MODEL}；思考强度：low。", "",
                 scope_note, "",
                 "| 组别 | 首轮通过 | 已尝试题数 | 累计通过 | 未完成尝试 |",
                 "|---|---:|---:|---:|---:|"]
        for group in GROUPS:
            entries = [row for row in attempts if row["group"] == group]
            first = sum(row["round"] == 1 and row["status"] == "solved" for row in entries)
            total = len({row["task"] for row in entries})
            passed = len({row["task"] for row in entries if row["status"] == "solved"})
            incomplete = sum(row["status"] == "incomplete" for row in entries)
            lines.append(f"| {group} | {first} | {total} | {passed} | {incomplete} |")
        if self.state.get("stop_reason"):
            lines += ["", "停止原因：" + self.state["stop_reason"]]
        lines += ["", "B：无 Hint；H：原框架对齐版；M：持续教师会话；I：新增轮内指导。",
                  "", "首轮与累计结果分别统计；未完成不等同正常失败。Token 与各阶段耗时见模型及教师调用日志。"]
        (self.output / "report.md").write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("integration", "formal"), required=True)
    parser.add_argument("--experiment_name", required=True)
    parser.add_argument("--output_base", default=str(ROOT / "runs"))
    parser.add_argument("--api_base", default="http://127.0.0.1:8765")
    parser.add_argument("--container_api_base", default="http://172.17.0.1:8765")
    parser.add_argument("--progress_base", default="http://127.0.0.1:8766")
    parser.add_argument("--container_progress_base", default="http://172.17.0.1:8766")
    parser.add_argument("--container_http_proxy", default="http://10.0.2.2:7897")
    parser.add_argument("--bridge_dir", default=str(ROOT / "logs/bridge"))
    parser.add_argument("--progress_dir", default=str(ROOT / "logs/progress"))
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--shared_first_attempt", action="store_true")
    parser.add_argument("--continue_from", default="", help="Stopped source experiment state or directory")
    parser.add_argument("--task_ids", nargs="+", choices=TASKS,
                        help="Fixed task subset for an independent worker; original task order is preserved")
    args = parser.parse_args()
    os.environ.setdefault("DOCKER_HOST", "unix://" + str(ROOT / "vm/docker.sock"))
    os.environ["HINT_CODEX_RUNTIME"] = "/opt/hint-codex-runtime/python"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["HINT_EXPERIMENT_NAME"] = args.experiment_name
    os.environ.pop("ALL_PROXY", None)
    os.environ.pop("all_proxy", None)
    def stop_experiment(signum, frame):
        try:
            _sigint_handler(signum, frame)
        except SystemExit:
            raise KeyboardInterrupt("Interrupted")
    signal.signal(signal.SIGINT, stop_experiment)
    signal.signal(signal.SIGTERM, stop_experiment)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    return PairedExperiments(args).run()


if __name__ == "__main__":
    sys.exit(main())
