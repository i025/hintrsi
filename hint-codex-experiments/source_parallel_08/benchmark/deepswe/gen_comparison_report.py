#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 Baseline vs Hint 对比 HTML 报告。

用法:
  python gen_comparison_report.py \
    --baseline-dir deepswe-output/lisen_hard_baseline \
    --hint-dir deepswe-output/lisen_hard_by_hint \
    --output deepswe-output/comparison_report.html \
    [--llm-analyze]   # 可选: 调用 LLM 生成文字分析

数据来源:
  - {run_dir}/loop_summary_{iid}.json          每任务轮次/eval 汇总
  - {run_dir}_r{N}/infer_logs/{iid}/turn_1/    每轮推理日志
      trajs.json                               轨迹 (duration, num_turns, 内容量)
      eval_result.json                         f2p/p2p 详情
  - {hint_dir}/reviews/{iid}/round_{N}/review_hint_traj.json  hint 轨迹审查
      (leak 型=通过轮: 泄漏风险/developer_note; gap 型=失败轮: 错误归因/key_error_summary)
  - {hint_dir}/hint_gen/{iid}/hint_compact_r{N}_meta.json  hint 压缩统计
"""
import argparse
import html as html_mod
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---- 常量 ----
LLM_API_KEY = os.environ.get("LLM_API_KEY", os.environ.get("HUBROUTER_API_KEY", ""))
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-v4.1-flash-1017-a")
LLM_BASE = os.environ.get("LLM_BASE", "http://hubrouter.jd.com/v1")
CHARS_PER_TOKEN = 4  # 粗估: 4 chars ≈ 1 token (代码/英文混合)


# ============================================================
# 数据收集
# ============================================================

def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _estimate_volume(trajs_path: Path) -> Dict[str, int]:
    """从 trajs.json 估算内容量和 token (usage 字段全为 0, 用内容量粗估)。"""
    data = _load_json(trajs_path)
    if not data:
        return {"chars": 0, "est_tokens": 0, "num_turns": 0,
                "duration_ms": 0, "duration_api_ms": 0}
    main = data.get("trajectories", {}).get("main_agent", "")
    chars = len(main) if isinstance(main, str) else 0
    rm = data.get("metadata", {}).get("ResultMessage", {})
    return {
        "chars": chars,
        "est_tokens": chars // CHARS_PER_TOKEN,
        "num_turns": rm.get("num_turns", 0),
        "duration_ms": rm.get("duration_ms", 0),
        "duration_api_ms": rm.get("duration_api_ms", 0),
    }


def _collect_review(hint_dir: Path, iid: str, round_n: int) -> Dict[str, Any]:
    """读取 reviews/{iid}/round_{N}/review_hint_traj.json。

    两种 review:
    - leak 型 (通过轮): overall_leakage_risk / read_hint_file / developer_note
    - gap  型 (失败轮): error_attribution / key_error_summary / corrective_hint
    公共字段: used_hint / revealed_hint / _meta.stats
    """
    rev_path = (hint_dir / "reviews" / iid /
                f"round_{round_n}" / "review_hint_traj.json")
    rev = _load_json(rev_path)
    if not rev:
        return {}
    is_leak = "overall_leakage_risk" in rev
    out: Dict[str, Any] = {
        "is_leak_review": is_leak,
        "used_hint": rev.get("used_hint", ""),
        "revealed_hint": rev.get("revealed_hint", ""),
    }
    if is_leak:
        out["overall_leakage_risk"] = rev.get("overall_leakage_risk", "")
        out["read_hint_file"] = rev.get("read_hint_file", "")
        out["developer_note"] = rev.get("developer_note", "")
    else:
        out["error_attribution"] = rev.get("error_attribution", "")
        out["key_error_summary"] = rev.get("key_error_summary", "")
    stats = rev.get("_meta", {}).get("stats", {})
    if stats:
        out["stats"] = {
            "total_messages": stats.get("total_messages", 0),
            "tool_use": stats.get("tool_use", 0),
            "thinking": stats.get("thinking", 0),
        }
    return out


def _collect_round_detail(solve_run_dir: Path, iid: str,
                          is_hint: bool,
                          hint_dir: Optional[Path] = None,
                          round_n: int = 0) -> Dict[str, Any]:
    """收集单轮推理的详细数据。"""
    turn_dir = solve_run_dir / "infer_logs" / iid / "turn_1"
    detail: Dict[str, Any] = {"exists": turn_dir.exists()}

    # review (仅 hint 运行) — 读取 reviews 目录的 review_hint_traj.json
    if is_hint and hint_dir and round_n:
        rv = _collect_review(hint_dir, iid, round_n)
        if rv:
            detail["review"] = rv

    if not turn_dir.exists():
        return detail

    # trajs 体积/时长
    detail.update(_estimate_volume(turn_dir / "trajs.json"))

    # eval 结果
    ev = _load_json(turn_dir / "eval_result.json")
    if ev:
        detail["f2p_passed"] = ev.get("f2p_passed", 0)
        detail["f2p_total"] = ev.get("f2p_total", 0)
        detail["p2p_passed"] = ev.get("p2p_passed", 0)
        detail["p2p_total"] = ev.get("p2p_total", 0)
        detail["partial"] = ev.get("partial", 0)
    return detail


def _collect_hint_meta(hint_dir: Path, iid: str, round_n: int) -> Dict[str, Any]:
    """收集 hint 压缩元数据。"""
    meta_path = (hint_dir / "hint_gen" / iid /
                 f"hint_compact_r{round_n}_meta.json")
    meta = _load_json(meta_path)
    if not meta:
        return {}
    return {
        "full_hint_chars": meta.get("full_hint_chars", 0),
        "compressed_chars": meta.get("compressed_chars", 0),
        "final_chars": meta.get("final_chars", 0),
        "compression_ratio": meta.get("compression_ratio", 0),
        "has_review_feedback": meta.get("has_review_feedback", False),
        "review_count": meta.get("review_count", 0),
    }


def collect_task(run_dir: Path, iid: str, is_hint: bool,
                 hint_dir: Optional[Path] = None) -> Dict[str, Any]:
    """收集一个任务在某种模式下的全部数据。"""
    summary = _load_json(run_dir / f"loop_summary_{iid}.json")
    if not summary:
        return {"instance_id": iid, "available": False}

    run_name = summary.get("run_name", "")
    task: Dict[str, Any] = {
        "instance_id": iid,
        "available": True,
        "solved": summary.get("solved", False),
        "solved_round": summary.get("solved_round"),
        "total_rounds": summary.get("total_rounds", 0),
        "final_status": summary.get("final_status"),
        "start_time": summary.get("start_time", ""),
        "end_time": summary.get("end_time", ""),
        "rounds": [],
    }

    # 总耗时
    try:
        t0 = time.mktime(time.strptime(task["start_time"], "%Y-%m-%dT%H:%M:%S"))
        t1 = time.mktime(time.strptime(task["end_time"], "%Y-%m-%dT%H:%M:%S"))
        task["wall_seconds"] = int(t1 - t0)
    except Exception:
        task["wall_seconds"] = 0

    for rd in summary.get("rounds", []):
        round_n = rd.get("round", 0)
        solve_run_name = rd.get("solve_run_name", f"{run_name}_r{round_n}")
        solve_run_dir = run_dir.parent / solve_run_name
        r_detail = _collect_round_detail(solve_run_dir, iid, is_hint,
                                         hint_dir, round_n)
        r_detail["round"] = round_n
        r_detail["status"] = rd.get("status", "")
        r_detail["eval_solved"] = rd.get("eval", {}).get("solved", False)
        r_detail["eval_reward"] = rd.get("eval", {}).get("reward", 0)
        r_detail["eval_f2p_passed"] = rd.get("eval", {}).get("f2p_passed", 0)
        r_detail["eval_f2p_total"] = rd.get("eval", {}).get("f2p_total", 0)
        if is_hint and hint_dir:
            r_detail["hint_meta"] = _collect_hint_meta(hint_dir, iid, round_n)
        task["rounds"].append(r_detail)

    # ---- 磁盘扫描纠正 ----
    # loop_summary 可能因脚本中断未记录后续轮次 (如 kea _r2 已通过但 summary 只记 r1)。
    # 扫描 _r1 ~ _r{max_rounds} 的 eval_result.json, 补充 summary 未记录的轮次,
    # 并以磁盘实际 eval 结果为准重新计算 solved / solved_round / total_rounds。
    max_rounds = summary.get("max_rounds", 5)
    recorded_rounds = {r["round"] for r in task["rounds"]}
    for round_n in range(1, max_rounds + 1):
        if round_n in recorded_rounds:
            continue
        solve_run_dir = run_dir.parent / f"{run_name}_r{round_n}"
        ev_p = (solve_run_dir / "infer_logs" / iid / "turn_1" /
                "eval_result.json")
        if not ev_p.exists():
            continue
        r_detail = _collect_round_detail(solve_run_dir, iid, is_hint,
                                         hint_dir, round_n)
        r_detail["round"] = round_n
        r_detail["status"] = "disk_recovered"
        ev = _load_json(ev_p) or {}
        r_detail["eval_solved"] = ev.get("reward", 0) == 1
        r_detail["eval_reward"] = ev.get("reward", 0)
        r_detail["eval_f2p_passed"] = ev.get("f2p_passed", 0)
        r_detail["eval_f2p_total"] = ev.get("f2p_total", 0)
        if is_hint and hint_dir:
            r_detail["hint_meta"] = _collect_hint_meta(hint_dir, iid, round_n)
        task["rounds"].append(r_detail)
        print(f"  [recover] {iid}: 补充磁盘轮次 r{round_n} "
              f"(eval {r_detail['eval_f2p_passed']}/{r_detail['eval_f2p_total']})")

    task["rounds"].sort(key=lambda r: r["round"])

    # 以磁盘实际 eval 为准重新计算
    disk_solved_round = None
    for r in task["rounds"]:
        if r.get("eval_solved"):
            disk_solved_round = r["round"]
            break
    if disk_solved_round and not task["solved"]:
        task["solved"] = True
        task["solved_round"] = disk_solved_round
        print(f"  [recover] {iid}: summary 记为未通过, 但磁盘 r{disk_solved_round} eval 通过 → 纠正为通过")
    task["total_rounds"] = len(task["rounds"])

    # 汇总
    task["total_chars"] = sum(r.get("chars", 0) for r in task["rounds"])
    task["total_est_tokens"] = sum(r.get("est_tokens", 0) for r in task["rounds"])
    task["total_duration_ms"] = sum(r.get("duration_ms", 0) for r in task["rounds"])
    task["total_num_turns"] = sum(r.get("num_turns", 0) for r in task["rounds"])

    # 代表轮 (通过轮; 未通过则取最后一轮) — 用于表1 单次对比
    rep = None
    if task["solved_round"]:
        for r in task["rounds"]:
            if r.get("round") == task["solved_round"]:
                rep = r
                break
    if rep is None and task["rounds"]:
        rep = task["rounds"][-1]
    if rep:
        task["solve_duration_ms"] = rep.get("duration_ms", 0)
        task["solve_est_tokens"] = rep.get("est_tokens", 0)
        task["solve_num_turns"] = rep.get("num_turns", 0)
        task["solve_round_n"] = rep.get("round", 0)
    else:
        task["solve_duration_ms"] = 0
        task["solve_est_tokens"] = 0
        task["solve_num_turns"] = 0
        task["solve_round_n"] = 0
    return task


def discover_tasks(baseline_dir: Path, hint_dir: Path) -> List[str]:
    """发现所有任务 ID (两个目录的并集)。"""
    ids = set()
    for d in (baseline_dir, hint_dir):
        for f in d.glob("loop_summary_*.json"):
            if "_all" in f.name:
                continue
            iid = f.stem.replace("loop_summary_", "")
            ids.add(iid)
    return sorted(ids)


def collect_all(baseline_dir: Path, hint_dir: Path) -> Dict[str, Any]:
    """收集全部数据。"""
    task_ids = discover_tasks(baseline_dir, hint_dir)
    baseline_tasks = {}
    hint_tasks = {}
    for iid in task_ids:
        baseline_tasks[iid] = collect_task(baseline_dir, iid, is_hint=False)
        hint_tasks[iid] = collect_task(hint_dir, iid, is_hint=True,
                                       hint_dir=hint_dir)
    return {
        "task_ids": task_ids,
        "baseline": baseline_tasks,
        "hint": hint_tasks,
        "baseline_dir": str(baseline_dir),
        "hint_dir": str(hint_dir),
    }


# ============================================================
# 统计计算
# ============================================================

def _fmt_duration(ms: int) -> str:
    if not ms:
        return "-"
    s = ms / 1000
    if s < 60:
        return f"{s:.0f}s"
    m = s / 60
    if m < 60:
        return f"{m:.1f}min"
    return f"{m / 60:.1f}h"


def _fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _pass_label(solved: Optional[bool]) -> str:
    if solved is True:
        return '<span class="pass">PASS</span>'
    if solved is False:
        return '<span class="fail">FAIL</span>'
    return '<span class="na">-</span>'


def compute_stats(data: Dict[str, Any]) -> Dict[str, Any]:
    """计算汇总统计。"""
    task_ids = data["task_ids"]
    bl = data["baseline"]
    ht = data["hint"]

    bl_solved = [iid for iid in task_ids if bl.get(iid, {}).get("solved")]
    ht_solved = [iid for iid in task_ids if ht.get(iid, {}).get("solved")]
    both_solved = set(bl_solved) & set(ht_solved)
    bl_only = set(bl_solved) - set(ht_solved)
    ht_only = set(ht_solved) - set(bl_solved)
    both_fail = set(task_ids) - set(bl_solved) - set(ht_solved)

    def _avg(tasks: Dict, field: str, filter_solved: bool = False) -> float:
        vals = []
        for iid in task_ids:
            t = tasks.get(iid, {})
            if not t.get("available"):
                continue
            if filter_solved and not t.get("solved"):
                continue
            v = t.get(field, 0)
            if v:
                vals.append(v)
        return sum(vals) / len(vals) if vals else 0

    return {
        "n_tasks": len(task_ids),
        "bl_pass_rate": len(bl_solved) / len(task_ids) if task_ids else 0,
        "ht_pass_rate": len(ht_solved) / len(task_ids) if task_ids else 0,
        "bl_solved_n": len(bl_solved),
        "ht_solved_n": len(ht_solved),
        "both_solved": sorted(both_solved),
        "bl_only": sorted(bl_only),
        "ht_only": sorted(ht_only),
        "both_fail": sorted(both_fail),
        "bl_avg_rounds": _avg(bl, "total_rounds"),
        "ht_avg_rounds": _avg(ht, "total_rounds"),
        "bl_avg_rounds_solved": _avg(bl, "total_rounds", True),
        "ht_avg_rounds_solved": _avg(ht, "total_rounds", True),
        "bl_avg_duration": _avg(bl, "total_duration_ms"),
        "ht_avg_duration": _avg(ht, "total_duration_ms"),
        "bl_avg_tokens": _avg(bl, "total_est_tokens"),
        "ht_avg_tokens": _avg(ht, "total_est_tokens"),
        "bl_total_tokens": sum(bl.get(iid, {}).get("total_est_tokens", 0)
                               for iid in task_ids),
        "ht_total_tokens": sum(ht.get(iid, {}).get("total_est_tokens", 0)
                               for iid in task_ids),
        "bl_avg_turns": _avg(bl, "total_num_turns"),
        "ht_avg_turns": _avg(ht, "total_num_turns"),
    }


def _leak_dist(data: Dict[str, Any]) -> Dict[str, int]:
    """泄漏风险分布 (取每任务 leak 型 review, 即通过轮)。"""
    dist: Dict[str, int] = {}
    for iid in data["task_ids"]:
        t = data["hint"].get(iid, {})
        risk = "-"
        for r in t.get("rounds", []):
            rv = r.get("review")
            if rv and rv.get("is_leak_review"):
                risk = rv.get("overall_leakage_risk") or "-"
        dist[risk] = dist.get(risk, 0) + 1
    return dist


def _used_hint_dist(data: Dict[str, Any]) -> Dict[str, int]:
    """used_hint 分布 (取最后一轮 review)。"""
    dist: Dict[str, int] = {}
    for iid in data["task_ids"]:
        t = data["hint"].get(iid, {})
        used = "-"
        for r in t.get("rounds", []):
            rv = r.get("review")
            if rv:
                used = rv.get("used_hint") or "-"
        dist[used] = dist.get(used, 0) + 1
    return dist


def _solved_by_round(data: Dict[str, Any], key: str) -> Dict[int, int]:
    """通过轮次分布。"""
    dist: Dict[int, int] = {}
    for iid in data["task_ids"]:
        t = data[key].get(iid, {})
        if t.get("solved") and t.get("solved_round"):
            dist[t["solved_round"]] = dist.get(t["solved_round"], 0) + 1
    return dist


# ============================================================
# HTML 生成
# ============================================================

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, 'Segoe UI', Roboto, 'Noto Sans SC', sans-serif;
       background: #f5f7fa; color: #2c3e50; line-height: 1.6; padding: 20px; }
.container { max-width: 1200px; margin: 0 auto; }
h1 { font-size: 28px; margin-bottom: 8px; color: #1a1a2e; }
h2 { font-size: 20px; margin: 32px 0 12px; color: #16213e;
     border-bottom: 2px solid #e8ecf1; padding-bottom: 6px; }
h3 { font-size: 16px; margin: 20px 0 8px; color: #2c3e50; }
.subtitle { color: #7f8c8d; font-size: 14px; margin-bottom: 24px; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
         gap: 16px; margin-bottom: 24px; }
.card { background: #fff; border-radius: 10px; padding: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06); text-align: center; }
.card .label { font-size: 13px; color: #7f8c8d; margin-bottom: 6px; }
.card .value { font-size: 32px; font-weight: 700; }
.card .delta { font-size: 13px; margin-top: 4px; }
.card.highlight { border-top: 4px solid #27ae60; }
.card.highlight-r { border-top: 4px solid #e74c3c; }
.card.neutral { border-top: 4px solid #3498db; }
table { width: 100%; border-collapse: collapse; background: #fff;
        border-radius: 8px; overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 20px; }
th { background: #16213e; color: #fff; padding: 10px 12px; text-align: left;
     font-size: 13px; white-space: nowrap; }
td { padding: 8px 12px; border-bottom: 1px solid #eef1f5; font-size: 13px;
     vertical-align: top; }
tr:hover td { background: #f8f9fb; }
.pass { color: #27ae60; font-weight: 700; }
.fail { color: #e74c3c; font-weight: 700; }
.na { color: #bdc3c7; }
.improved { color: #27ae60; }
.regressed { color: #e74c3c; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 10px;
       font-size: 11px; font-weight: 600; }
.tag-high { background: #fdecea; color: #e74c3c; }
.tag-medium { background: #fef5e7; color: #f39c12; }
.tag-low { background: #eafaf1; color: #27ae60; }
.tag-na { background: #f0f0f0; color: #999; }
.bar-chart { margin: 12px 0; }
.bar-row { display: flex; align-items: center; margin-bottom: 6px; }
.bar-label { width: 140px; font-size: 13px; color: #555; text-align: right;
             padding-right: 10px; flex-shrink: 0; }
.bar-track { flex: 1; background: #eef1f5; border-radius: 4px; height: 24px;
             position: relative; }
.bar-fill { height: 100%; border-radius: 4px; display: flex; align-items: center;
            padding-left: 8px; color: #fff; font-size: 11px; font-weight: 600;
            min-width: 30px; transition: width 0.3s; }
.bar-green { background: #27ae60; }
.bar-red { background: #e74c3c; }
.bar-blue { background: #3498db; }
.bar-orange { background: #f39c12; }
.bar-gray { background: #95a5a6; }
.llm-section { background: #fff; border-radius: 10px; padding: 24px;
               box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 20px; }
.llm-section h3 { color: #16213e; }
.llm-section p { margin: 8px 0; font-size: 14px; }
.llm-section ul { margin: 8px 0 8px 20px; }
.llm-section li { margin: 4px 0; font-size: 14px; }
.note { font-size: 12px; color: #95a5a6; margin-top: 4px; }
.review-sum { font-size: 11px; color: #7f8c8d; cursor: help; }
.review-sum:hover { color: #2c3e50; }
.section-desc { font-size: 13px; color: #7f8c8d; margin-bottom: 12px; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
@media (max-width: 800px) { .two-col { grid-template-columns: 1fr; } }
"""


def _bar(label: str, value: int, max_val: int, color: str = "bar-blue") -> str:
    pct = (value / max_val * 100) if max_val else 0
    return (f'<div class="bar-row"><div class="bar-label">{label}</div>'
            f'<div class="bar-track"><div class="bar-fill {color}" '
            f'style="width:{max(pct, 8)}%">{value}</div></div></div>')


def _risk_tag(risk: str) -> str:
    m = {"HIGH": "tag-high", "MEDIUM": "tag-medium", "LOW": "tag-low",
         "NONE": "tag-low", "OBVIOUS": "tag-high", "SUBTLE": "tag-medium",
         "NO": "tag-low"}
    cls = m.get(risk, "tag-na")
    return f'<span class="tag {cls}">{risk or "-"}</span>'


def gen_html(data: Dict[str, Any], stats: Dict[str, Any],
             llm_analysis: str = "") -> str:
    """生成完整 HTML 报告。"""
    task_ids = data["task_ids"]
    bl = data["baseline"]
    ht = data["hint"]
    n = stats["n_tasks"]

    # ---- 摘要卡片 ----
    delta_rate = (stats["ht_pass_rate"] - stats["bl_pass_rate"]) * 100
    delta_sign = "+" if delta_rate >= 0 else ""
    cards = f"""
    <div class="cards">
      <div class="card neutral"><div class="label">任务总数</div>
        <div class="value">{n}</div></div>
      <div class="card highlight-r"><div class="label">Baseline 通过率</div>
        <div class="value">{stats['bl_pass_rate']*100:.0f}%</div>
        <div class="delta">{stats['bl_solved_n']}/{n} 通过</div></div>
      <div class="card highlight"><div class="label">Hint 通过率</div>
        <div class="value">{stats['ht_pass_rate']*100:.0f}%</div>
        <div class="delta improved">{delta_sign}{delta_rate:.0f}pp vs baseline</div></div>
      <div class="card neutral"><div class="label">Hint 新增通过</div>
        <div class="value improved">+{len(stats['ht_only'])}</div>
        <div class="delta">{'、'.join(i.split('-')[0] for i in stats['ht_only']) or '无'}</div></div>
      <div class="card neutral"><div class="label">Hint 仍未通过</div>
        <div class="value fail">{len(stats['both_fail'])}</div>
        <div class="delta">{'、'.join(i.split('-')[0] for i in stats['both_fail']) or '无'}</div></div>
    </div>"""

    # ---- 表 1: 逐任务对比 ----
    rows1 = []
    for iid in task_ids:
        b, h = bl.get(iid, {}), ht.get(iid, {})
        b_ok = b.get("solved") if b.get("available") else None
        h_ok = h.get("solved") if h.get("available") else None
        h_r = h.get("total_rounds", "-")
        b_f2p = "-"
        if b.get("available") and b.get("rounds"):
            ev = b["rounds"][-1]
            b_f2p = f"{ev.get('eval_f2p_passed',0)}/{ev.get('eval_f2p_total',0)}"
        h_f2p = "-"
        if h.get("available") and h.get("rounds"):
            ev = h["rounds"][-1]
            h_f2p = f"{ev.get('eval_f2p_passed',0)}/{ev.get('eval_f2p_total',0)}"
        b_dur = _fmt_duration(b.get("solve_duration_ms", 0))
        h_dur = _fmt_duration(h.get("solve_duration_ms", 0))
        b_tok = _fmt_tokens(b.get("solve_est_tokens", 0))
        h_tok = _fmt_tokens(h.get("solve_est_tokens", 0))
        b_turns = b.get("solve_num_turns", 0) or "-"
        h_turns = h.get("solve_num_turns", 0) or "-"

        # 效果标注
        if b_ok and h_ok:
            effect = '<span class="pass">维持通过</span>'
        elif not b_ok and h_ok:
            effect = '<span class="improved">Hint 帮助通过</span>'
        elif b_ok and not h_ok:
            effect = '<span class="regressed">Hint 反而失败</span>'
        else:
            effect = '<span class="fail">均未通过</span>'

        rows1.append(f"""
      <tr>
        <td><b>{iid}</b></td>
        <td>{_pass_label(b_ok)}</td><td>{b_f2p}</td>
        <td>{b_turns}</td><td>{b_dur}</td><td>{b_tok}</td>
        <td>{_pass_label(h_ok)}</td><td>{h_r}</td><td>{h_f2p}</td>
        <td>{h_turns}</td><td>{h_dur}</td><td>{h_tok}</td>
        <td>{effect}</td>
      </tr>""")

    table1 = f"""
    <table>
      <thead><tr>
        <th rowspan="2">任务</th>
        <th colspan="5" style="background:#c0392b">Baseline (无 Hint)</th>
        <th colspan="6" style="background:#27ae60">With Hint</th>
        <th rowspan="2">效果</th>
      </tr><tr>
        <th>结果</th><th>F2P</th><th>Turns</th><th>耗时</th><th>Token*</th>
        <th>结果</th><th>尝试次数</th><th>F2P</th><th>Turns</th><th>耗时</th><th>Token*</th>
      </tr></thead>
      <tbody>{''.join(rows1)}</tbody>
    </table>
    <div class="note">* Token 为基于轨迹内容量的粗估值 (chars/4), 实际 API usage 未记录。
    Turns = agent 对话轮数, 耗时 = API 调用总时长, F2P = 最后一轮 fail-to-pass 测试通过数。
    <b>耗时/Token/Turns 均为通过轮的单次值</b> (未通过则取最后一轮), 非多轮累计。</div>"""

    # ---- 表 2: Hint 详情 ----
    rows2 = []
    for iid in task_ids:
        h = ht.get(iid, {})
        if not h.get("available"):
            rows2.append(f'<tr><td><b>{iid}</b></td><td colspan="10" class="na">无 hint 数据</td></tr>')
            continue
        h_ok = h.get("solved")
        h_sr = h.get("solved_round") or "-"
        h_r = h.get("total_rounds", 0)
        # 从各轮 review 中提取
        used, revealed = "-", "-"
        risk, read_hf, dev_note = "-", "-", ""
        err_summary = ""
        for r in h.get("rounds", []):
            rv = r.get("review")
            if not rv:
                continue
            # used/revealed 取最后一个有 review 的轮次
            used = rv.get("used_hint") or "-"
            revealed = rv.get("revealed_hint") or "-"
            if rv.get("is_leak_review"):
                # leak 型 (通过轮): 泄漏风险 / 读取Hint / developer_note
                risk = rv.get("overall_leakage_risk") or "-"
                read_hf = rv.get("read_hint_file") or "-"
                dev_note = rv.get("developer_note", "")
            else:
                # gap 型 (失败轮): key_error_summary
                err_summary = rv.get("key_error_summary", "")
        # Review 摘要: 优先 developer_note (通过轮), 否则 key_error_summary (失败轮)
        summary_full = dev_note or err_summary
        summary_html = "-"
        if summary_full:
            _esc_full = html_mod.escape(summary_full, quote=True)
            _short = summary_full[:80] + ("..." if len(summary_full) > 80 else "")
            summary_html = (f'<span class="review-sum" title="{_esc_full}">'
                            f'{html_mod.escape(_short)}</span>')
        # hint 压缩信息 (第一轮)
        hint_chars = "-"
        if h.get("rounds"):
            hm = h["rounds"][0].get("hint_meta", {})
            if hm:
                hint_chars = f"{hm.get('final_chars', 0)} chars"
        rows2.append(f"""
      <tr>
        <td><b>{iid}</b></td>
        <td>{_pass_label(h_ok)}</td><td>{h_sr}</td><td>{h_r}</td>
        <td>{hint_chars}</td>
        <td>{used}</td><td>{revealed}</td><td>{read_hf}</td><td>{_risk_tag(risk)}</td>
        <td>{summary_html}</td>
      </tr>""")

    table2 = f"""
    <table>
      <thead><tr>
        <th>任务</th><th>结果</th><th>通过轮次</th><th>尝试次数</th>
        <th>Hint 大小</th><th>Used Hint</th><th>Revealed</th>
        <th>读取Hint文件</th><th>泄漏风险</th><th>Review 摘要</th>
      </tr></thead>
      <tbody>{''.join(rows2)}</tbody>
    </table>
    <div class="note">数据来源: reviews/&#123;iid&#125;/round_N/review_hint_traj.json。
    Used Hint / Revealed 取最后一轮 review; 泄漏风险 / 读取Hint文件 取通过轮的 leak 型 review (无则为 -)。
    Review 摘要: 通过轮显示 developer_note, 未通过显示最后一轮 key_error_summary (悬浮查看全文)。</div>"""

    # ---- 分布图 ----
    leak_d = _leak_dist(data)
    used_d = _used_hint_dist(data)
    bl_rd = _solved_by_round(data, "baseline")
    ht_rd = _solved_by_round(data, "hint")
    max_leak = max(leak_d.values()) if leak_d else 1
    max_round = max(list(bl_rd.values()) + list(ht_rd.values()) + [1])

    dist_html = f"""
    <div class="two-col">
      <div>
        <h3>通过轮次分布</h3>
        <div class="bar-chart">
          <div class="bar-row"><div class="bar-label">Baseline</div><div class="bar-track"></div></div>
          {''.join(_bar(f'  第{r}轮通过', v, max_round, 'bar-red') for r, v in sorted(bl_rd.items()))}
          {'<div class="bar-row"><div class="bar-label" style="color:#999">  (全部失败)</div></div>' if not bl_rd else ''}
        </div>
        <div class="bar-chart">
          <div class="bar-row"><div class="bar-label">With Hint</div><div class="bar-track"></div></div>
          {''.join(_bar(f'  第{r}轮通过', v, max_round, 'bar-green') for r, v in sorted(ht_rd.items()))}
          {'<div class="bar-row"><div class="bar-label" style="color:#999">  (全部失败)</div></div>' if not ht_rd else ''}
        </div>
      </div>
      <div>
        <h3>泄漏风险分布 (通过轮 leak review)</h3>
        <div class="bar-chart">
          {''.join(_bar(k or '无数据', v, max_leak, 'bar-orange') for k, v in sorted(leak_d.items(), key=lambda x: -x[1]))}
        </div>
        <h3>Used Hint 分布 (最后一轮 review)</h3>
        <div class="bar-chart">
          {''.join(_bar(k or '无数据', v, max_leak, 'bar-blue') for k, v in sorted(used_d.items(), key=lambda x: -x[1]))}
        </div>
      </div>
    </div>"""

    # ---- LLM 分析 ----
    llm_html = ""
    if llm_analysis:
        import html as _html
        # 简易 markdown → html
        lines = llm_analysis.strip().split("\n")
        parts = []
        in_list = False
        for ln in lines:
            ln = _html.escape(ln)
            if ln.startswith("### "):
                if in_list:
                    parts.append("</ul>"); in_list = False
                parts.append(f"<h3>{ln[4:]}</h3>")
            elif ln.startswith("- ") or ln.startswith("* "):
                if not in_list:
                    parts.append("<ul>"); in_list = True
                parts.append(f"<li>{ln[2:]}</li>")
            elif ln.strip():
                if in_list:
                    parts.append("</ul>"); in_list = False
                parts.append(f"<p>{ln}</p>")
        if in_list:
            parts.append("</ul>")
        llm_html = f'<div class="llm-section"><h2>LLM 分析</h2>{"".join(parts)}</div>'

    # ---- 组装 ----
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Baseline vs Hint 对比报告</title>
<style>{_CSS}</style>
</head>
<body>
<div class="container">
  <h1>Baseline vs Hint 对比报告</h1>
  <div class="subtitle">生成时间: {now} | Baseline: {data['baseline_dir']} | Hint: {data['hint_dir']}</div>

  {cards}

  <h2>1. 逐任务对比</h2>
  <div class="section-desc">Baseline (无 hint) 与 With Hint 的逐任务结果对比。</div>
  {table1}

  <h2>2. Hint 效果详情</h2>
  <div class="section-desc">每个任务在 hint 模式下的尝试次数、hint 使用/泄漏情况及 review 审查摘要。</div>
  {table2}

  <h2>3. 分布统计</h2>
  {dist_html}

  {llm_html}

  <div class="note" style="margin: 40px 0 20px; text-align: center;">
    Generated by gen_comparison_report.py | {now}
  </div>
</div>
</body>
</html>"""
    return html


# ============================================================
# LLM 分析 (可选)
# ============================================================

def _llm_call(prompt: str, max_tokens: int = 4096) -> str:
    """调用 LLM 生成分析文本。"""
    body = json.dumps({
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "你是数据分析专家。基于提供的实验数据, "
             "用中文输出简洁、有洞察力的分析。使用 markdown 格式 (### 标题, - 列表)。"},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "stream": False,
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{LLM_BASE}/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {LLM_API_KEY}"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    msg = data["choices"][0]["message"]
    # content 为空时 fallback 到 reasoning_content
    text = msg.get("content", "") or ""
    if not text.strip():
        text = msg.get("reasoning_content", "") or ""
    return text


def llm_analyze(data: Dict[str, Any], stats: Dict[str, Any]) -> str:
    """构造 prompt 让 LLM 分析实验结果。"""
    # 构造紧凑数据摘要
    lines = []
    for iid in data["task_ids"]:
        b = data["baseline"].get(iid, {})
        h = data["hint"].get(iid, {})
        b_s = "通过" if b.get("solved") else "未通过"
        h_s = "通过" if h.get("solved") else "未通过"
        h_sr = h.get("solved_round") or "-"
        # review 信息
        risk, used, read_hf = "-", "-", "-"
        err_sum = ""
        for r in h.get("rounds", []):
            rv = r.get("review")
            if not rv:
                continue
            used = rv.get("used_hint") or "-"
            if rv.get("is_leak_review"):
                risk = rv.get("overall_leakage_risk") or "-"
                read_hf = rv.get("read_hint_file") or "-"
            else:
                err_sum = rv.get("key_error_summary", "")
        b_tok = b.get("total_est_tokens", 0)
        h_tok = h.get("total_est_tokens", 0)
        err_part = f", 失败原因={err_sum[:60]}" if err_sum else ""
        lines.append(
            f"- {iid}: baseline={b_s}, hint={h_s}(第{h_sr}轮), "
            f"used_hint={used}, 泄漏风险={risk}, 读取hint文件={read_hf}{err_part}, "
            f"token估算 baseline={b_tok} hint={h_tok}")

    prompt = f"""以下是 10 道 SWE 任务的实验对比数据 (baseline = 无提示直接解题, hint = 注入解题提示后解题):

任务总数: {stats['n_tasks']}
Baseline 通过率: {stats['bl_pass_rate']*100:.0f}% ({stats['bl_solved_n']}/{stats['n_tasks']})
Hint 通过率: {stats['ht_pass_rate']*100:.0f}% ({stats['ht_solved_n']}/{stats['n_tasks']})
Hint 新增通过: {stats['ht_only'] or '无'}
Hint 反而失败: {stats['bl_only'] or '无'}
两者均未通过: {stats['both_fail'] or '无'}
Baseline 平均尝试轮次: {stats['bl_avg_rounds']:.1f}, Hint: {stats['ht_avg_rounds']:.1f}
Baseline 平均耗时: {_fmt_duration(int(stats['bl_avg_duration']))}, Hint: {_fmt_duration(int(stats['ht_avg_duration']))}
Baseline 平均 token: {_fmt_tokens(int(stats['bl_avg_tokens']))}, Hint: {_fmt_tokens(int(stats['ht_avg_tokens']))}

逐任务数据:
{chr(10).join(lines)}

请从以下角度分析 (每个角度用 ### 标题 + 要点列表):
### Hint 整体效果
通过率提升幅度、哪些任务因 hint 受益最大、哪些任务 hint 无效及可能原因 (参考失败轮的 key_error_summary)。

### Hint 的代价
token/耗时/轮次的额外开销, 多轮重试的成本。

### Hint 泄漏风险
used_hint 和泄漏风险的分布说明了什么, agent 是否直接读取了 hint 文件 (read_hint_file), 对评测公平性的影响。

### 总结建议
hint 机制的整体评价、适用场景、改进方向。"""
    try:
        return _llm_call(prompt)
    except Exception as e:
        return f"LLM 分析失败: {e}"


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="生成 Baseline vs Hint 对比 HTML 报告")
    parser.add_argument("--baseline-dir", required=True,
                        help="baseline 运行目录 (如 deepswe-output/lisen_hard_baseline)")
    parser.add_argument("--hint-dir", required=True,
                        help="hint 运行目录 (如 deepswe-output/lisen_hard_by_hint)")
    parser.add_argument("--output", default="comparison_report.html",
                        help="输出 HTML 路径")
    parser.add_argument("--llm-analyze", action="store_true",
                        help="调用 LLM 生成文字分析 (需要网络)")
    args = parser.parse_args()

    baseline_dir = Path(args.baseline_dir).resolve()
    hint_dir = Path(args.hint_dir).resolve()
    if not baseline_dir.exists():
        print(f"[error] baseline 目录不存在: {baseline_dir}", file=sys.stderr)
        sys.exit(1)
    if not hint_dir.exists():
        print(f"[error] hint 目录不存在: {hint_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"[1/3] 收集数据: baseline={baseline_dir.name}, hint={hint_dir.name}")
    data = collect_all(baseline_dir, hint_dir)
    stats = compute_stats(data)
    print(f"      任务数: {stats['n_tasks']}, "
          f"baseline 通过: {stats['bl_solved_n']}, hint 通过: {stats['ht_solved_n']}")

    llm_text = ""
    if args.llm_analyze:
        print("[2/3] 调用 LLM 分析...")
        llm_text = llm_analyze(data, stats)
        print(f"      分析文本: {len(llm_text)} chars")
    else:
        print("[2/3] 跳过 LLM 分析 (加 --llm-analyze 启用)")

    print("[3/3] 生成 HTML...")
    html = gen_html(data, stats, llm_text)
    out = Path(args.output).resolve()
    out.write_text(html, encoding="utf-8")
    print(f"完成: {out} ({len(html) // 1024} KB)")


if __name__ == "__main__":
    main()