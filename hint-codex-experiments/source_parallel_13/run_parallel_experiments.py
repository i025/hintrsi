#!/usr/bin/env python3
"""Run fixed task queues in separate existing experiment runtimes."""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from report_codex_experiments import write_reports
from run_codex_experiments import GROUPS, MODEL, ROOT, TASKS, request_json

LOG = logging.getLogger("parallel_experiments")


def task_queues(lanes):
    queues = {lane["lane"]: [] for lane in lanes}
    for index, task in enumerate(TASKS[1:]):
        queues[lanes[index % len(lanes)]["lane"]].append(task)
    return queues


class ParallelExperiments:
    def __init__(self, args):
        self.args = args
        requested = getattr(args, "task_ids", None)
        self.subset = requested is not None
        self.selected_task_ids = [task for task in TASKS[1:]
                                  if requested is None or task in requested]
        self.prior_path = Path(args.prior_state).resolve()
        if self.prior_path.is_dir():
            self.prior_path /= "experiment_state.json"
        self.prior = json.loads(self.prior_path.read_text())
        self.check_prior()
        self.lanes = sorted(json.loads(Path(args.runtime_manifest).read_text())["lanes"],
                            key=lambda lane: lane["lane"])
        if [lane["lane"] for lane in self.lanes] != list(range(6)):
            raise ValueError("The runtime manifest must contain lanes0 through5")
        self.output = Path(args.output_base) / args.experiment_name
        self.output.mkdir(parents=True, exist_ok=True)
        self.state_path = self.output / "experiment_state.json"
        if self.state_path.exists():
            raise FileExistsError("Choose a new experiment name; existing results are preserved")
        queues = task_queues(self.lanes)
        self.workers = []
        for lane in self.lanes:
            selected = [task for task in queues[lane["lane"]] if task in self.selected_task_ids]
            if not selected:
                continue
            name = f"{args.experiment_name}_lane{lane['lane']}"
            self.workers.append({
                "lane": lane["lane"], "experiment": name, "task_ids": selected,
                "docker_host": lane["docker_host"],
                "state_path": str(self.output / "lanes" / name / "experiment_state.json"),
                "log_path": str(self.output / "worker_logs" / (name + ".log")),
                "status": "not_started",
            })
        self.state = {key: self.prior.get(key) for key in (
            "model", "reasoning_effort", "max_rounds", "student_cpus", "student_memory",
            "verifier_memory", "student_active_timeout_seconds", "initial_teacher_timeout_seconds",
            "online_interval_tools", "online_max_checks", "online_max_hint_words",
            "online_check_timeout_seconds", "teacher_review_interface", "tool_delivery",
            "container_http_proxy", "quota_policy")}
        self.state.update(
            experiment=args.experiment_name, stage="formal", status="running", dry_run=args.dry_run,
            tool_delivery="stateless_exec_actions", model_backend="stateless_exec_action",
            context_owner="claude_sdk", sdk_auto_compact_window=400000,
            native_roles="sdk_messages_serialized_as_json", native_sampling="cli_defaults",
            unmapped_api_parameters=["temperature", "top_p", "max_tokens"],
            started_at=time.time(), groups=list(GROUPS), tasks=list(self.prior.get("tasks", TASKS)),
            protocol_version="shared_first_v2_with_anko_v1_transition_parallel",
            shared_first_attempt=True, initial_hints_shared=True,
            student_attempts_independent=False, fresh_student_state_each_actual_attempt=True,
            task_protocols={task: self.prior.get("task_protocols", {}).get(
                task, "v1_transition" if task == TASKS[0] else "shared_first_v2") for task in TASKS},
            continuation={"source_experiment": self.prior["experiment"],
                          "state_path": str(self.prior_path)},
            included_experiment_states=[worker["state_path"] for worker in self.workers],
            excluded_prior_attempts=self.prior.get("excluded_prior_attempts", []),
            parallelism=len(self.workers), available_runtime_lanes=6,
            runtime_manifest=str(Path(args.runtime_manifest).resolve()),
            worker_assignment="Fixed round-robin of TASKS[1:] across lanes0..5; original task indices retained",
            workers=self.workers, shared={}, shared_first_attempts={}, attempts=[],
            prior_task_segment="Anko v1 transition; completed observations adopted without reruns",
            timing_note="Parallel batch wall time is distinct from per-attempt SDK/active/teacher-wait time; lanes share the host and account quota.",
        )
        if self.subset:
            observed = {row["task"] for row in self.prior.get("attempts", [])}
            observed.update(self.prior.get("shared", {}))
            self.state.update(
                selected_tasks=self.selected_task_ids,
                deferred_prior_tasks=[task for task in TASKS[1:] if task in observed],
                unselected_unstarted_tasks=[task for task in TASKS[1:]
                                           if task not in observed and task not in self.selected_task_ids],
                completion_scope="selected_tasks_only",
                deferred_prior_tasks_completed=False,
                selection_note="Only never-started selected tasks run in this segment; prior observations are retained read-only, prior running entries become interrupted only in this derived state. Deferred tasks remain unfinished and outside the selected-task outcome denominator.",
                prior_task_segment="All prior observations retained; selected new tasks only, no deferred task rerun",
            )
        self.processes = {}
        self.logs = []
        self.refresh()

    def check_prior(self):
        reason = self.prior.get("stop_reason", "").lower()
        quota_words = ("quota", "rate limit", "rate_limit", "ratelimit", "usage limit",
                       "usage_limit", "usagelimit", "limit reached", "429", "balance", "credit")
        if self.prior["status"] != "stopped" or any(word in reason for word in quota_words):
            raise ValueError("Parallel handoff requires a stopped non-quota prior experiment")
        attempts = self.prior.get("attempts", [])
        observed = {row["task"] for row in attempts}
        observed.update(self.prior.get("shared", {}))
        if self.subset:
            if any(task in observed for task in self.selected_task_ids):
                raise ValueError("Selected tasks must have no prior attempt or shared initial Hint")
        elif any(task != TASKS[0] for task in observed):
            raise ValueError("The prior experiment must stop before any next-task attempt")
        for group in ("B", "H", "I"):
            rows = [row for row in attempts if row["task"] == TASKS[0] and row["group"] == group]
            finished = any(row["status"] == "solved" for row in rows) or any(
                row["round"] == 5 and row["status"] == "not_solved" for row in rows)
            if not finished or any(row["status"] not in ("solved", "not_solved") for row in rows):
                raise ValueError("Anko B/H/I must finish naturally before the parallel handoff")

    def worker_command(self, worker):
        command = [sys.executable, "-u", "-B", str(Path(__file__).with_name("run_codex_experiments.py")),
                   "--stage", "formal", "--shared_first_attempt",
                   "--experiment_name", worker["experiment"],
                   "--output_base", str(self.output / "lanes"),
                   "--api_base", self.args.api_base,
                   "--container_api_base", self.args.container_api_base,
                   "--progress_base", self.args.progress_base,
                   "--container_progress_base", self.args.container_progress_base,
                   "--container_http_proxy", self.args.container_http_proxy,
                   "--bridge_dir", str(self.args.bridge_dir),
                   "--progress_dir", str(self.args.progress_dir),
                   "--task_ids", *worker["task_ids"]]
        if self.args.dry_run:
            command.append("--dry_run")
        return command

    def worker_environment(self, worker):
        env = os.environ.copy()
        env.update(DOCKER_HOST=worker["docker_host"], PYTHONDONTWRITEBYTECODE="1",
                   HINT_EXPERIMENT_NAME=worker["experiment"])
        env.pop("ALL_PROXY", None)
        env.pop("all_proxy", None)
        return env

    def launch(self):
        (self.output / "worker_logs").mkdir(parents=True, exist_ok=True)
        for worker in self.workers:
            stream = Path(worker["log_path"]).open("w")
            self.logs.append(stream)
            process = subprocess.Popen(self.worker_command(worker), env=self.worker_environment(worker),
                                       stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            self.processes[worker["lane"]] = process
            worker.update(pid=process.pid, status="starting")
        self.save()

    def refresh(self):
        self.state["attempts"] = []
        for original in self.prior["attempts"]:
            row = dict(original, origin_experiment=original.get("origin_experiment", self.prior["experiment"]))
            if row["status"] == "running":
                row.update(original_status="running", status="interrupted")
            self.state["attempts"].append(row)
        self.state["shared"] = {task: dict(value) for task, value in self.prior.get("shared", {}).items()}
        self.state["shared_first_attempts"] = {task: dict(value) for task, value in
                                              self.prior.get("shared_first_attempts", {}).items()}
        for reference in self.state["shared_first_attempts"].values():
            if reference.get("status") == "running":
                reference.update(original_status="running", status="interrupted")
        for worker in self.workers:
            path = Path(worker["state_path"])
            if not path.exists():
                continue
            state = json.loads(path.read_text())
            worker["status"] = state["status"]
            worker["stop_reason"] = state.get("stop_reason")
            worker["started_at"] = state.get("started_at")
            worker["finished_at"] = state.get("finished_at")
            self.state["attempts"].extend(dict(row, origin_experiment=row.get(
                "origin_experiment", state["experiment"])) for row in state.get("attempts", []))
            self.state["shared"].update(state.get("shared", {}))
            self.state["shared_first_attempts"].update(state.get("shared_first_attempts", {}))
        self.save()

    def save(self):
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, ensure_ascii=False, indent=2) + "\n")
        temporary.replace(self.state_path)
        write_reports(self.state_path, self.args.bridge_dir, self.args.progress_dir)

    def stop_workers(self):
        active = [process for process in self.processes.values() if process.poll() is None]
        for process in active:
            process.send_signal(signal.SIGINT)
        deadline = time.monotonic() + 60
        while any(process.poll() is None for process in active) and time.monotonic() < deadline:
            time.sleep(1)
        for process in active:
            if process.poll() is None:
                process.kill()
            process.wait()
        if self.args.dry_run:
            return
        import docker
        for worker in self.workers:
            if worker["lane"] not in self.processes:
                continue
            client = docker.DockerClient(base_url=worker["docker_host"])
            try:
                for container in client.containers.list(all=True, filters={
                        "label": "hint.experiment_name=" + worker["experiment"]}):
                    container.stop(timeout=10)
            finally:
                client.close()

    def run(self):
        try:
            self.launch()
            while True:
                codes = {lane: process.poll() for lane, process in self.processes.items()}
                self.refresh()
                if not self.args.dry_run:
                    status = request_json(self.args.api_base.rstrip("/") + "/status")
                    if status["stopped"]:
                        raise RuntimeError(status.get("stop_reason") or "The model bridge stopped")
                for worker in self.workers:
                    code = codes[worker["lane"]]
                    worker["exit_code"] = code
                    if worker["status"] == "stopped" or (code is not None and code != 0):
                        raise RuntimeError(worker.get("stop_reason") or
                                           f"Worker lane{worker['lane']} exited with code {code}")
                    if code == 0 and worker["status"] != "complete":
                        raise RuntimeError(f"Worker lane{worker['lane']} exited without a complete state")
                if all(worker["exit_code"] == 0 for worker in self.workers):
                    self.state["status"] = "complete"
                    break
                time.sleep(self.args.poll_seconds)
        except (Exception, KeyboardInterrupt) as exc:
            self.state["status"] = "stopped"
            self.state["stop_reason"] = str(exc) or "Interrupted"
            LOG.exception("Parallel experiment stopped; preserving worker artifacts")
            if not self.args.dry_run:
                try:
                    request_json(self.args.api_base.rstrip("/") + "/stop",
                                 {"reason": self.state["stop_reason"]})
                except Exception as stop_error:
                    self.state["bridge_stop_error"] = str(stop_error)
            try:
                self.stop_workers()
            except Exception as cleanup_error:
                self.state["cleanup_error"] = str(cleanup_error)
        finally:
            self.state["finished_at"] = time.time()
            self.state["elapsed_seconds"] = self.state["finished_at"] - self.state["started_at"]
            self.refresh()
            for stream in self.logs:
                stream.close()
        return 0 if self.state["status"] == "complete" else 2


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment_name", required=True)
    parser.add_argument("--prior_state", required=True)
    parser.add_argument("--runtime_manifest", required=True)
    parser.add_argument("--output_base", default=str(ROOT / "runs"))
    parser.add_argument("--api_base", default="http://127.0.0.1:8765")
    parser.add_argument("--container_api_base", default="http://172.17.0.1:8765")
    parser.add_argument("--progress_base", default="http://127.0.0.1:8766")
    parser.add_argument("--container_progress_base", default="http://172.17.0.1:8766")
    parser.add_argument("--container_http_proxy", default="http://10.0.2.2:7897")
    parser.add_argument("--bridge_dir", default=str(ROOT / "logs/bridge"))
    parser.add_argument("--progress_dir", default=str(ROOT / "logs/progress"))
    parser.add_argument("--poll_seconds", type=float, default=30)
    parser.add_argument("--task_ids", nargs="+", choices=TASKS[1:],
                        help="Only select never-started tasks, retaining their original lane assignments")
    parser.add_argument("--dry_run", action="store_true")
    return parser


def main():
    args = build_parser().parse_args()
    os.environ.pop("ALL_PROXY", None)
    os.environ.pop("all_proxy", None)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    def interrupted(signum, frame):
        raise KeyboardInterrupt("Interrupted")
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    return ParallelExperiments(args).run()


if __name__ == "__main__":
    sys.exit(main())
