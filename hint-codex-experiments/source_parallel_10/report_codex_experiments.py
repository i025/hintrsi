#!/usr/bin/env python3
"""Aggregate measured Codex usage and paired experiment outcomes."""

import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

TOKEN_FIELDS = {
    "input_tokens": "inputTokens", "cached_input_tokens": "cachedInputTokens",
    "output_tokens": "outputTokens", "reasoning_output_tokens": "reasoningOutputTokens",
    "total_tokens": "totalTokens",
}
COUNTERS = tuple(TOKEN_FIELDS) + (
    "token_events", "request_count", "response_count", "error_count", "request_seconds",
    "codex_turn_count", "codex_turn_seconds", "usage_unknown_requests",
)
DIMENSIONS = ("scope", "experiment", "task", "group", "round", "role", "stage", "phase",
              "native_group", "cost_status")
STAGES = {
    "initial_teacher": "初始教师生成", "initial_compression": "首轮指导压缩",
    "compression": "后续指导压缩", "success_review": "成功轨迹审查",
    "failure_review": "失败复盘", "online_teacher": "轮内教师判断",
    "online_hint_screen": "轮内提示筛查", "student": "学生解题",
    "shared_first_student": "H/M共同首轮学生",
    "shared_success_review": "共同首轮成功轨迹审查",
}


def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def records(path):
    path = Path(path)
    if path.is_file():
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    # The final line may still be in flight while a progress report is written.
                    if not line.endswith("\n"):
                        break
                    yield json.loads(line)


def counters():
    return {name: 0 for name in COUNTERS}


def add_counters(target, source):
    for name in COUNTERS:
        target[name] += source.get(name, 0) or 0


def experiment_catalog(state_path, current):
    catalog = {}
    for path in Path(state_path).parent.parent.glob("*/experiment_state.json"):
        item = read_json(path)
        if item and item.get("experiment"):
            catalog[item["experiment"]] = item
    catalog[current["experiment"]] = current
    if current.get("included_experiment_states"):
        visited = set()
        def include(item):
            if item["experiment"] in visited:
                return
            visited.add(item["experiment"])
            catalog[item["experiment"]] = item
            paths = list(item.get("included_experiment_states", []))
            if item.get("continuation"):
                paths.append(item["continuation"]["state_path"])
            for path in paths:
                child = read_json(path)
                if child:
                    include(child)
        include(current)
    elif current.get("continuation"):
        source = read_json(current["continuation"]["state_path"])
        catalog[source["experiment"]] = source
    return catalog


def experiment_origins(state, catalog):
    origins = {state["experiment"]}
    if not state.get("included_experiment_states"):
        if state.get("continuation"):
            origins.add(state["continuation"]["source_experiment"])
        return origins
    def include(item):
        paths = list(item.get("included_experiment_states", []))
        if item.get("continuation"):
            paths.append(item["continuation"]["state_path"])
        for path in paths:
            child = read_json(path)
            if child and child["experiment"] not in origins:
                origins.add(child["experiment"])
                catalog.setdefault(child["experiment"], child)
                include(catalog[child["experiment"]])
    include(state)
    return origins


def attempt_session(entry, experiment):
    origin = entry.get("origin_experiment", experiment)
    return f"{origin}-{entry['task']}-{entry['group']}-r{entry['round']}"


def shared_first_rows(state):
    rows = []
    for task, reference in state.get("shared_first_attempts", {}).items():
        for entry in state.get("attempts", []):
            if (entry["task"] == task and entry["group"] == reference["group"]
                    and entry["round"] == reference["round"]
                    and entry.get("origin_experiment", state["experiment"])
                    == reference.get("origin_experiment", state["experiment"])):
                rows.append(entry)
                break
    for entry in state.get("attempts", []):
        if (entry.get("stage") == "shared_first_student"
                and entry.get("shared_with") == ["H", "M"] and entry not in rows):
            rows.append(entry)
    return rows


def protocol_tasks(state, tasks):
    return [task for task in tasks
            if state.get("task_protocols", {}).get(task) == "shared_first_v2"]


def attribution(record, catalog, overrides=None):
    session = record.get("session") or ""
    phase = record.get("phase") or "unknown"
    role = record.get("role") or "unknown"
    result = dict.fromkeys(DIMENSIONS)
    result.update(scope="preflight" if session.startswith("preflight") else "other_sessions",
                  role=role, phase=phase, stage=phase, cost_status="actual")
    for name in sorted(catalog, key=len, reverse=True):
        if not session.startswith(name + "-"):
            continue
        state = catalog[name]
        result.update(scope="dry_run" if state.get("dry_run") else state.get("stage", "unknown"),
                      experiment=name)
        tasks = set(state.get("tasks", [])) | set(state.get("selected_tasks", []))
        tasks.update(row["task"] for row in state.get("attempts", []))
        for task in sorted(tasks, key=len, reverse=True):
            prefix = name + "-" + task + "-"
            if not session.startswith(prefix):
                continue
            suffix = session[len(prefix):]
            result["task"] = task
            result["group"] = suffix.split("-", 1)[0].split("_", 1)[0]
            match = re.search(r"(?:^|_)r(\d+)(?:$|_)", phase)
            if not match:
                match = re.search(r"-(?:review-)?r(\d+)(?:$|_|-)", "-" + suffix)
            result["round"] = int(match.group(1)) if match else None
            if result["group"] == "shared" and phase.startswith("review_r"):
                result["group"] = "M"
            elif phase == "resume_probe":
                result["group"] = "teacher_resume_probe"
                result["stage"] = "teacher_resume_probe"
            break
        if phase == "generate":
            result["stage"] = "initial_teacher"
        elif phase.startswith("compress_r"):
            result["stage"] = "initial_compression" if result["group"] == "shared" else "compression"
        elif phase.startswith("review_r"):
            solved = any(row["task"] == result["task"] and row["group"] == result["group"]
                         and row["round"] == result["round"] and row["status"] == "solved"
                         for row in state.get("attempts", []))
            result["stage"] = "success_review" if solved else "failure_review"
        elif "progress_" in phase:
            result["stage"] = "online_hint_screen" if "screen" in phase else "online_teacher"
        elif role == "student":
            result["stage"] = "student"
        result["native_group"] = result["group"]
        if overrides:
            result.update(overrides.get((session, role), {}))
        return result
    return result


def attempt_metrics(entry, experiment, progress):
    result = {key: entry.get(key) for key in ("task", "group", "round", "status", "eval_path", "trajs_path")}
    result.update(origin_experiment=entry.get("origin_experiment", experiment),
                  shared_with=entry.get("shared_with", []),
                  attribution_group=entry.get("attribution_group", entry["group"]),
                  stage=entry.get("stage", "student"))
    result["attempt_wall_seconds"] = entry.get("elapsed_seconds")
    metadata = read_json(entry.get("trajs_path") or "/nonexistent", {}).get("metadata", {})
    execution = entry.get("execution") or {}
    if not execution and entry.get("trajs_path"):
        path = Path(entry["trajs_path"])
        for parent in (path.parent, path.parent.parent):
            rounds = read_json(parent / "rounds_meta.json", {}).get("rounds", [])
            if rounds:
                execution = rounds[-1].get("execution") or {}
                break
    session = attempt_session(entry, experiment)
    result["session"] = session
    checks = [record for record in progress if record.get("session") == session]
    wall = metadata.get("wall_seconds", execution.get("wall_seconds"))
    wait = metadata.get("teacher_wait_seconds", execution.get("teacher_wait_seconds"))
    wait_source = "student_metadata" if "teacher_wait_seconds" in metadata else "runner_execution"
    if wait is None and checks:
        wait = sum(record.get("duration_seconds", 0) for record in checks)
        wait_source = "teacher_service"
    if wait is None and entry["group"] != "I":
        wait, wait_source = 0.0, "no_online_teacher"
    if wait is None:
        wait_source = None
    result.update(student_wall_seconds=wall, teacher_wait_seconds=wait,
                  teacher_wait_source=wait_source,
                  student_active_seconds=(wall - wait if wall is not None and wait is not None else None),
                  teacher_checks=metadata.get("teacher_checks", len(checks)),
                  delivered_hints=sum(bool(record.get("hint")) for record in checks),
                  stop_reason=execution.get("stop_reason") or metadata.get("error_log"))
    evaluation = entry.get("eval") or {}
    raw_evaluation = read_json(entry.get("eval_path") or "/nonexistent", {})
    for key in ("reward", "f2p_passed", "f2p_total", "p2p_passed", "p2p_total"):
        value = evaluation.get(key)
        result[key] = value if value is not None else raw_evaluation.get(key)
    return result


def task_list(state, attempts):
    tasks = state.get("selected_tasks")
    if tasks is None:
        tasks = (state.get("tasks", []) if state.get("stage") == "formal"
                 else sorted({row["task"] for row in attempts}))
    return list(tasks)


def summarize_outcomes(group, tasks, entries, limit):
    first = {row["task"] for row in entries if row["round"] == 1 and row["status"] == "solved"}
    solved = {row["task"] for row in entries if row["status"] == "solved"}
    incomplete = [row for row in entries if row["status"] not in ("solved", "not_solved")]
    failed = {task for task in tasks if task not in solved and any(
        row["task"] == task and row["round"] >= limit and row["status"] == "not_solved" for row in entries)}
    cumulative = []
    for round_num in range(1, 6):
        passed = {row["task"] for row in entries if row["round"] <= round_num and row["status"] == "solved"}
        assessed = passed | {row["task"] for row in entries if row["round"] == round_num
                             and row["status"] in ("solved", "not_solved")}
        cumulative.append({"round": round_num, "solved_tasks": len(passed),
                           "assessed_tasks": len(assessed), "planned_tasks": len(tasks),
                           "pending_tasks": len(set(tasks) - assessed),
                           "within_protocol": round_num <= limit})
    return {"group": group, "planned_tasks": len(tasks),
            "attempted_tasks": len({row["task"] for row in entries}),
            "attempts": len(entries), "first_round_solved": len(first),
            "solved_tasks": len(solved), "normal_failed_tasks": len(failed),
            "incomplete_attempts": len(incomplete),
            "normal_failed_attempts": sum(row["status"] == "not_solved" for row in entries),
            "unfinished_tasks": len(set(tasks) - solved - failed), "cumulative": cumulative}


def outcomes(state, attempts):
    base_tasks = task_list(state, attempts)
    limit = state.get("round_limit", 1 if state.get("stage") == "integration" else state.get("max_rounds", 5))
    common = shared_first_rows(state) if not state.get("dry_run") else []
    results = []
    for group in state.get("groups", ["B", "H", "M", "I"]):
        tasks = state.get("task_groups", {}).get(group, base_tasks)
        paired = group in ("H", "M") and any(value in ("shared_first_v2", "v1_transition")
                   for value in state.get("task_protocols", {}).values())
        if paired:
            tasks = protocol_tasks(state, tasks)
        entries = [row for row in attempts if row["group"] == group and row["task"] in tasks]
        branch_attempts = sum(row["round"] > 1 for row in entries)
        if paired and group == "M":
            entries += [row for row in common if row["task"] in tasks]
        row = summarize_outcomes(group, tasks, entries, limit)
        row.update(metric_unit="policy" if paired else "actual_attempt",
                   shared_prefix_correlated=paired,
                   actual_branch_attempts=branch_attempts,
                   shared_first_references=sum(entry["task"] in tasks for entry in common) if paired else 0,
                   excluded_transition_tasks=[task for task in base_tasks
                       if paired and state["task_protocols"].get(task) == "v1_transition"])
        results.append(row)
    return results


def shared_first_outcomes(state, attempts):
    tasks = protocol_tasks(state, task_list(state, attempts))
    common = ([row for row in shared_first_rows(state) if row["task"] in tasks]
              if not state.get("dry_run") else [])
    passed = [row for row in common if row["task"] in tasks and row["status"] == "solved"]
    failed = [row for row in common if row["task"] in tasks and row["status"] == "not_solved"]
    assessed = len(passed) + len(failed)
    result = {"planned_tasks": len(tasks), "actual_student_executions": len(common),
              "assessed_tasks": assessed, "solved_tasks": len(passed),
              "not_solved_tasks": len(failed),
              "incomplete_attempts": sum(row["status"] not in ("solved", "not_solved") for row in common),
              "pending_tasks": len(tasks) - assessed,
              "success_rate": len(passed) / assessed if assessed else None,
              "references": state.get("shared_first_attempts", {})}
    branches = []
    eligible = [row["task"] for row in failed]
    for group in ("H", "M"):
        entries = [row for row in attempts if row["group"] == group
                   and row["task"] in eligible and row["round"] > 1]
        branch = summarize_outcomes(group, eligible, entries, state.get("max_rounds", 5))
        branch.update(condition="common_first_not_solved", first_branch_round=2,
                      eligible_tasks=len(eligible), actual_branch_attempts=len(entries))
        branches.append(branch)
    return result, branches


def aggregate_experiment(experiment_state_path, bridge_dir, progress_dir=None, allocate_shared=False):
    state_path, bridge_dir = Path(experiment_state_path), Path(bridge_dir)
    state = read_json(state_path)
    catalog = experiment_catalog(state_path, state)
    origins = experiment_origins(state, catalog)
    overrides = {}
    for entry in shared_first_rows(state):
        overrides[(attempt_session(entry, state["experiment"]), "student")] = {
            "group": "HM", "stage": "shared_first_student"}
        if entry["status"] == "solved":
            origin = entry.get("origin_experiment", state["experiment"])
            session = f"{origin}-{entry['task']}-{entry['group']}-review-r1"
            overrides[(session, "teacher")] = {"group": "HM", "stage": "shared_success_review"}
    for entry in state.get("excluded_prior_attempts", []):
        overrides[(attempt_session(entry, state["experiment"]), "student")] = {
            "cost_status": "cancelled_prior"}
    rows, missing_fields = {}, defaultdict(int)
    def bucket(record):
        info = attribution(record, catalog, overrides)
        key = tuple(info[name] for name in DIMENSIONS)
        if key not in rows:
            rows[key] = dict(info, **counters())
        return rows[key]
    usage_ids = set()
    unknown_usage = []
    for record in records(bridge_dir / "token_usage.jsonl"):
        if record.get("request_id"):
            usage_ids.add(record["request_id"])
        row = bucket(record)
        delta = record.get("delta") or {}
        for field, native in TOKEN_FIELDS.items():
            if native in delta:
                row[field] += delta[native]
            elif row["experiment"] in origins:
                missing_fields[field] += 1
        row["token_events"] += 1
    for filename, field in (("model_requests.jsonl", "request_count"),
                            ("model_responses.jsonl", "response_count"),
                            ("model_errors.jsonl", "error_count")):
        for record in records(bridge_dir / filename):
            row = bucket(record)
            row[field] += 1
            if field == "request_count" and record.get("request_id") not in usage_ids:
                row["usage_unknown_requests"] += 1
                if row["experiment"] in origins:
                    unknown_usage.append({**{key: record.get(key) for key in
                        ("request_id", "session", "role", "phase")}, "status": "not_reported"})
            if field != "request_count":
                row["request_seconds"] += record.get("elapsed_seconds", 0) or 0
    for record in records(bridge_dir / "codex_events.jsonl"):
        event = record.get("event") or {}
        turn = (event.get("params") or {}).get("turn") or {}
        if event.get("method") == "turn/completed" and turn.get("durationMs") is not None:
            row = bucket(record)
            row["codex_turn_count"] += 1
            row["codex_turn_seconds"] += turn["durationMs"] / 1000
    for record in records(bridge_dir / "exec_turns.jsonl"):
        row = bucket(record)
        row["codex_turn_count"] += 1
        row["codex_turn_seconds"] += record["elapsed_seconds"]
    selected = [row for row in rows.values() if row["experiment"] in origins]
    selected.sort(key=lambda row: tuple(str(row[name] or "") for name in DIMENSIONS))
    total, shared, shared_first, cancelled = counters(), counters(), counters(), counters()
    group_totals, scope_totals, origin_totals = defaultdict(counters), defaultdict(counters), defaultdict(counters)
    protocol_group_totals = defaultdict(lambda: defaultdict(counters))
    for row in rows.values():
        add_counters(scope_totals[row["scope"]], row)
    for row in selected:
        add_counters(total, row)
        group = "cancelled_prior" if row["cost_status"] == "cancelled_prior" else row["group"] or "unattributed"
        add_counters(group_totals[group], row)
        add_counters(origin_totals[row["experiment"]], row)
        protocol = state.get("task_protocols", {}).get(row["task"], "independent_v1")
        add_counters(protocol_group_totals[protocol][group], row)
        if row["group"] == "shared":
            add_counters(shared, row)
        if row["group"] == "HM":
            add_counters(shared_first, row)
        if row["cost_status"] == "cancelled_prior":
            add_counters(cancelled, row)
    progress_dir = Path(progress_dir) if progress_dir else bridge_dir.parent / "progress"
    progress = [row for row in records(progress_dir / "progress.jsonl")
                if any((row.get("session") or "").startswith(origin + "-") for origin in origins)]
    attempts = [] if state.get("dry_run") else state.get("attempts", [])
    attempt_rows = [attempt_metrics(row, state["experiment"], progress) for row in attempts]
    for row in attempt_rows:
        row["task_protocol"] = state.get("task_protocols", {}).get(row["task"], "independent_v1")
    excluded = [{**row, **attempt_metrics(row, state["experiment"], progress)}
                for row in state.get("excluded_prior_attempts", [])]
    common_outcomes, branch_outcomes = shared_first_outcomes(state, attempts)
    allocations = []
    if allocate_shared:
        for row in selected:
            if row["group"] not in ("shared", "HM"):
                continue
            members = (["H", "M"] if row["group"] == "HM" else
                       state.get("shared", {}).get(row["task"], {}).get("cost_shared_by", ["H", "M", "I"]))
            for group in members:
                allocations.append({**{name: row[name] for name in DIMENSIONS}, "group": group,
                                    "allocation_only": True, "share": 1 / len(members),
                                    **{field: row[field] / len(members) for field in COUNTERS}})
    preflight_path = bridge_dir.parent.parent / "preflight" / "cli_tool_result.json"
    preflight = read_json(preflight_path)
    preflight_cli = None
    if preflight:
        native = (preflight.get("usage") or {}).get("total") or {}
        preflight_cli = {"source": str(preflight_path), "scope": "preflight_cli",
                         "elapsed_seconds": preflight.get("elapsed_seconds"),
                         "tokens": {field: native.get(key) for field, key in TOKEN_FIELDS.items()},
                         "included_in_experiment": False}
    parallel_new = counters()
    included_names = {state["experiment"]}
    for path in state.get("included_experiment_states", []):
        child = read_json(path)
        if child:
            included_names.add(child["experiment"])
    for name in included_names:
        add_counters(parallel_new, origin_totals[name])
    return {"experiment": state["experiment"], "stage": state.get("stage"),
            "status": state.get("status"), "dry_run": state.get("dry_run", False),
            "model": state.get("model"), "reasoning_effort": state.get("reasoning_effort"),
            "stop_reason": state.get("stop_reason"), "state_source": str(state_path),
            "bridge_source": str(bridge_dir), "totals": total, "shared_totals": shared,
            "shared_first_totals": shared_first, "cancelled_prior_totals": cancelled,
            "origin_totals": dict(origin_totals),
            "current_experiment_totals": origin_totals[state["experiment"]],
            "included_experiment_states": state.get("included_experiment_states", []),
            "included_experiments": sorted(origins),
            "parallel_new_totals": parallel_new,
            "parallel_workers": state.get("workers", []),
            "parallelism": state.get("parallelism"),
            "selected_tasks": state.get("selected_tasks"),
            "deferred_prior_tasks": state.get("deferred_prior_tasks", []),
            "available_runtime_lanes": state.get("available_runtime_lanes"),
            "protocol_group_totals": {name: dict(groups) for name, groups in protocol_group_totals.items()},
            "group_totals": dict(group_totals), "bridge_scope_totals": dict(scope_totals),
            "stages": selected, "attempts": attempt_rows, "outcomes": outcomes(state, attempts),
            "task_protocols": state.get("task_protocols", {}),
            "continuation": state.get("continuation"),
            "excluded_prior_attempts": excluded,
            "shared_first_outcomes": common_outcomes,
            "conditional_branch_outcomes": branch_outcomes,
            "progress_checks": progress, "shared_allocations": allocations,
            "preflight_cli": preflight_cli, "missing_token_fields": dict(missing_fields),
            "usage_unknown_requests": unknown_usage,
            "dry_run_attempts_excluded": len(state.get("attempts", [])) if state.get("dry_run") else 0}


def write_csv(path, rows, fields):
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def render_report(metrics):
    title = {"formal": "正式实验", "integration": "联调", "preflight": "预检"}.get(metrics["stage"], metrics["stage"])
    updated = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"# Codex Hint {title}报告", "", f"更新时间：{updated}（北京时间）。",
             f"状态：{metrics['status']}；模型：{metrics['model']}；思考强度：{metrics['reasoning_effort']}。", ""]
    lines += ["用量以桥接逐请求原始记录为准；SDK 汇总不重复相加。",
              f"未上报 token 的请求：{metrics['totals']['usage_unknown_requests']}；这些请求的消耗未知。", ""]
    if metrics["dry_run"]:
        lines += ["本次是执行路径演练，所有占位成绩均排除，不计入实验结果。", ""]
    elif metrics["stage"] == "integration":
        lines += ["H 与 I 在各自指定题上验证流程，题目不同，不据此比较组间效果。", ""]
    if metrics.get("selected_tasks") is not None:
        lines += ["本批结果主表仅统计所选新题：" + "、".join(metrics["selected_tasks"]) + "。",
                  "历史观察保留在逐次尝试明细；旧批延后题仍未完成，不计作新批已完成。实际用量覆盖明确引用的全部来源。", ""]
        if metrics.get("deferred_prior_tasks"):
            lines += ["延后题：" + "、".join(metrics["deferred_prior_tasks"]) + "。", ""]
    lines += ["## 解题结果", "", "各组首轮与累计结果分开统计。未完成和未跑满轮次不等同正常失败。", "",
              "| 组别 | 协议题数 | 已尝试题数 | 首轮通过 | 累计通过 | 跑满仍失败题数 | 未完成尝试 | 尚未结束题数 |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in metrics["outcomes"]:
        lines.append("| {group} | {planned_tasks} | {attempted_tasks} | {first_round_solved} | {solved_tasks} | {normal_failed_tasks} | {incomplete_attempts} | {unfinished_tasks} |".format(**row))
    lines += ["", "B：无指导；H：原框架对齐版；M：教师会话连续；I：增加轮内指导。", "",
              "| 组别 | 第1轮累计 | 第2轮累计 | 第3轮累计 | 第4轮累计 | 第5轮累计 |",
              "|---|---:|---:|---:|---:|---:|"]
    for row in metrics["outcomes"]:
        values = [str(item["solved_tasks"]) if item["within_protocol"] else "不适用" for item in row["cumulative"]]
        lines.append("| " + row["group"] + " | " + " | ".join(values) + " |")
    lines += ["", "进行中或因额度停止时，累计通过是已观察到的数量；尚未执行的尝试不计为失败。每轮覆盖题数见 metrics.json。", ""]
    if any(row["shared_prefix_correlated"] for row in metrics["outcomes"]):
        common = metrics["shared_first_outcomes"]
        lines += ["## 共同首轮与失败后分支", "",
                  "H/M 策略指标引用同一个共同首轮，结果相关，不是两个独立样本。共同首轮占各自最多5轮中的第1轮；实际学生执行和费用仅计一次，不生成独立M1记录。", "",
                  "| v2计划题数 | 实际共同学生执行 | 已正式评测 | 首轮通过 | 首轮未解出 | 未完成 | 尚未评测 |",
                  "|---:|---:|---:|---:|---:|---:|---:|",
                  "| {planned_tasks} | {actual_student_executions} | {assessed_tasks} | {solved_tasks} | {not_solved_tasks} | {incomplete_attempts} | {pending_tasks} |".format(**common), "",
                  "共同首轮通过后，保留一次H成功轨迹审查作为共享诊断，H/M均停止；M教师记忆机制未触发。首轮未解出时，H新教师与M原教师复盘同一轨迹，后续学生从第2轮各自独立执行。", "",
                  "以下分支统计仅以共同首轮正常未解出的题为条件，不包含共同首轮通过、未完成或尚未执行的题。", "",
                  "| 分支 | 可进入题数 | 已执行后续尝试 | 已尝试题数 | 后续通过题数 | 跑满仍失败 | 未完成尝试 | 尚未结束 |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for row in metrics["conditional_branch_outcomes"]:
            lines.append("| {group} | {eligible_tasks} | {actual_branch_attempts} | {attempted_tasks} | {solved_tasks} | {normal_failed_tasks} | {incomplete_attempts} | {unfinished_tasks} |".format(**row))
        transition = [task for task, protocol in metrics["task_protocols"].items() if protocol == "v1_transition"]
        if transition:
            lines += ["", "v1过渡题（" + "、".join(transition) + "）保留真实历史结果，排除在上述v2 H/M策略及条件分支统计之外；B/I仍按其真实尝试统计。"]
    if metrics["excluded_prior_attempts"]:
        lines += ["", f"旧批用户取消的{len(metrics['excluded_prior_attempts'])}次尝试单列在 excluded_prior_attempt_metrics.csv，没有正式成绩，不计正常失败，也不充当共同首轮。"]
    lines += ["",
              "## 实际 Token 与模型请求耗时", "",
              "缓存输入包含在输入内，推理输出包含在输出内；总量采用模型返回的 totalTokens，不重复相加。", "",
              "| 归属 | 输入 | 缓存输入 | 输出 | 推理输出 | 总 Token | 请求耗时（秒） | 请求错误数 |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for group, row in sorted(metrics["group_totals"].items()):
        label = {"shared": "共享初始教师与首轮压缩（仅计一次）",
                 "HM": "H/M共同首轮及共享成功审查（仅计一次）",
                 "cancelled_prior": "旧批用户取消尝试（仅计费用）"}.get(group, group)
        lines.append(f"| {label} | {row['input_tokens']} | {row['cached_input_tokens']} | {row['output_tokens']} | {row['reasoning_output_tokens']} | {row['total_tokens']} | {row['request_seconds']:.2f} | {row['error_count']} |")
    total = metrics["totals"]
    lines += ["", f"本次报告覆盖的实际总量：{total['total_tokens']} Token；模型请求耗时合计 {total['request_seconds']:.2f} 秒。",
              "共享初始产物只计一次；M 后续复盘归 M。分摊表若启用，仅供比较，不再加入实际总量。",
              "请求耗时是各请求耗时之和，不能当作系统墙钟。Codex exec 耗时包含进程启动和一次决策，不含原 SDK 在两次请求之间执行工具的时间。",
              "学生整次流程墙钟、SDK 解题墙钟、教师等待和扣除等待后的时间分列在 attempt_metrics.csv；缺失数据保留为空。", "",
              "## 阶段与数据边界", "",
              "各任务、组别、角色、阶段的明细见 token_usage_by_stage.csv；每次教师决定见原始 progress.jsonl。",
              "预检、联调和正式实验的 Token 分开列在 metrics.json.bridge_scope_totals；成绩仅使用当前状态中的真实尝试及明确引用的共同首轮。"]
    if metrics["continuation"]:
        lines += ["", "用量按指定桥接目录中的 experiment/session 归集；导入成绩保留 origin_experiment。新批日志不含旧调用时，下表不补记旧批费用，旧费用须查看原日志。", "",
                  "| 实际调用来源 | 总Token |", "|---|---:|"]
        for origin, value in sorted(metrics["origin_totals"].items()):
            lines.append(f"| {origin} | {value['total_tokens']} |")
        lines.append(f"当前日志中归属于旧批用户取消尝试的 {metrics['cancelled_prior_totals']['total_tokens']} Token 已包含在上述实际总量内，不计入成绩；原日志中的历史总额另存。")
        lines.append("v1/v2的费用归属另见 metrics.json.protocol_group_totals，避免将过渡题费用用于v2分支效果比较。")
    if metrics.get("included_experiment_states"):
        lines += ["", "## 按题并行与来源", "",
                  f"本次按题固定分配{metrics['parallelism']}路，每路独立运行原有题内流程；实际学生与教师仍为8CPU/128GiB。" + ("本批只启动上述新选题，旧批观察只读保留，不续接旧教师、不跨路复用学生代码。" if metrics.get("selected_tasks") is not None else "Anko保留旧批已完成结果，其余九题各执行一次，不跨路复用学生代码。"),
                  f"本并行段新增实际用量：{metrics['parallel_new_totals']['total_tokens']} Token。本版只汇总指定桥接目录中的调用；Anko 等历史观察的费用保留在旧日志，不自动并入新批用量。",
                  "各路共用账户额度和宿主机；整批墙钟、每次SDK/有效时间、教师等待须分别解释，不能把并行墙钟当作纯模型提速。", "",
                  "| 路 | 实验 | 固定题目 | 状态 |", "|---:|---|---|---|"]
        for worker in metrics["parallel_workers"]:
            lines.append(f"| {worker['lane']} | {worker['experiment']} | {', '.join(worker['task_ids'])} | {worker['status']} |")
    if metrics["preflight_cli"]:
        value = metrics["preflight_cli"]
        lines.append(f"历史独立 CLI 预检另记录 {value['tokens']['total_tokens']} Token、{value['elapsed_seconds']} 秒，未计入本实验总量。")
    if metrics["missing_token_fields"]:
        lines.append("部分 Token 字段未返回，明细只汇总已观测值，缺失事件数见 metrics.json.missing_token_fields。")
    lines.append("未提供可核对的货币账单，因此不换算美元费用。")
    if metrics["stop_reason"]:
        lines += ["", "停止原因：" + metrics["stop_reason"]]
    return "\n".join(lines) + "\n"


def write_reports(experiment_state_path, bridge_dir, progress_dir=None,
                  output_dir=None, allocate_shared=False):
    metrics = aggregate_experiment(experiment_state_path, bridge_dir, progress_dir, allocate_shared)
    output = Path(output_dir) if output_dir else Path(experiment_state_path).parent
    output.mkdir(parents=True, exist_ok=True)
    (output / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(output / "token_usage_by_stage.csv", metrics["stages"], DIMENSIONS + COUNTERS)
    attempt_fields = ("task", "group", "round", "status", "origin_experiment", "session",
                      "task_protocol", "shared_with", "attribution_group", "stage",
                      "reward", "f2p_passed", "f2p_total",
                      "p2p_passed", "p2p_total", "attempt_wall_seconds", "student_wall_seconds",
                      "teacher_wait_seconds", "teacher_wait_source", "student_active_seconds",
                      "teacher_checks", "delivered_hints", "stop_reason", "eval_path", "trajs_path")
    write_csv(output / "attempt_metrics.csv", metrics["attempts"], attempt_fields)
    if metrics["excluded_prior_attempts"]:
        write_csv(output / "excluded_prior_attempt_metrics.csv", metrics["excluded_prior_attempts"],
                  attempt_fields + ("exclusion_reason", "manifest_path", "patch_path", "formal_score", "actual_model_tokens"))
    if allocate_shared:
        write_csv(output / "shared_allocations.csv", metrics["shared_allocations"],
                  DIMENSIONS + ("allocation_only", "share") + COUNTERS)
    (output / "report.md").write_text(render_report(metrics), encoding="utf-8")
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment_state", required=True)
    parser.add_argument("--bridge_dir", required=True)
    parser.add_argument("--progress_dir", default=None)
    parser.add_argument("--output_dir", default=None)
    parser.add_argument("--allocate_shared", action="store_true")
    args = parser.parse_args()
    write_reports(args.experiment_state, args.bridge_dir, args.progress_dir,
                  args.output_dir, args.allocate_shared)


if __name__ == "__main__":
    main()
