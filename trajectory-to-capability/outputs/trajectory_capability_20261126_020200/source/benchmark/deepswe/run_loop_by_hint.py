#!/usr/bin/env python3
"""端到端 hint 反馈闭环编排脚本。

串联已有脚本,构建完整闭环:
  生成 hint → 压缩 → 解题+评测 → (未解决) → review → 累计压缩 → 再解题 → ...
最多 MAX_ROUNDS 轮,题目解决即提前终止(解决后仍做泄漏审查供开发者复核)。

复用的已有脚本(不重复造轮子):
  - run_one_hint.sh      → 容器探索生成完整 hint (get_hint_by_task.py 的封装)
  - compress_hint.py     → 压缩 hint,支持累计多轮 review feedback (--review_json 多路径)
  - run_one_loop.sh      → 单轮解题+评测 (run_multi_turn_loop.py 的封装, max_turns=1)
  - review_hint_traj.py  → 失败时诊断关键错误(产出 corrective_hint);
                           解决时审查 hint 泄漏(行为泄漏+方案泄漏,供开发者复核)

目录隔离(每步输出保留,不覆盖):
  {OUTPUT_BASE}/{RUN_NAME}/hint_gen/{INSTANCE_ID}/
      hint_output.md / hint.md / golden_diff.diff       ← round 0 生成(run_one_hint.sh)
      hint_compact_r1.md / hint_compact_r1_meta.json    ← 第 1 轮压缩 hint(无 review)
      hint_compact_r2.md / hint_compact_r2_meta.json    ← 第 2 轮(融合 round_1 review)
      hint_compact_r3.md / ...                          ← 第 3 轮(融合 round_1+2 review 累计)
  {OUTPUT_BASE}/{RUN_NAME}_r{N}/infer_logs/{IID}/turn_1/   ← 第 N 轮解题轨迹+评测(独立 run_name)
  {OUTPUT_BASE}/{RUN_NAME}/reviews/{IID}/round_{N}/        ← 第 N 轮 review 产物(按实例隔离)
  {OUTPUT_BASE}/{RUN_NAME}/logs/{IID}/step_{seq}_{name}.log ← 各步骤完整日志(按实例隔离)
  {OUTPUT_BASE}/{RUN_NAME}/loop_summary_{IID}.json          ← 闭环摘要(按实例隔离)

多 task 隔离: 同一 run_name 顺序跑多个 task 时,reviews/logs/summary 均按 instance_id
  隔离,互不覆盖;--continue 对旧版路径(无 instance_id)自动回退兼容。

日志设计:
  - 每步子进程输出实时 tee:控制台原样透传(保留子脚本自身格式) + 完整落盘到独立日志文件
  - 步骤开始前打印醒目分隔条(步骤名/命令/日志路径)
  - 编排脚本自身用 [loop] 前缀的 logging 输出摘要
  - Ctrl+C 时向子进程组转发 SIGTERM(子进程独立 session,避免孤儿进程)

用法:
  # 完整闭环(最多 5 轮)
  python run_loop_by_hint.py \
    --instance_id go-genai-streamed-function-args \
    --run_name lisen_full_loop \
    --max_rounds 5

  # 多 task 模式(顺序处理 parquet 中的所有 task,产物按 instance_id 隔离)
  python run_loop_by_hint.py --instance_id all --run_name lisen_full_loop --max_rounds 5

  # 验证链路(只打印命令不执行)
  python run_loop_by_hint.py --instance_id xxx --run_name test --dry_run

  # 复用已有 hint 跳过生成
  python run_loop_by_hint.py --instance_id xxx --run_name test --skip_hint_gen

  # 续跑(扫描已有完整轮次,从下一轮继续;自动复用已有 hint、补做缺失 review)
  python run_loop_by_hint.py --instance_id xxx --run_name lisen_full_loop --continue

多 task 模式(--instance_id all):
  - 从 parquet 读取所有 instance_id,逐个启动 HintLoopOrchestrator 顺序执行
  - 单个 task 异常不中断后续 task,每跑完一个落盘汇总(loop_summary_all.json)
  - all 模式忽略 --golden_diff_file(多 task 各自从 tasks_dir 获取)
  - 退出码: 0=全部 solved, 1=有未 solved, 2=有异常, 130=Ctrl+C 中断

无 hint 基线模式(--no_hint_run):
  - 只解题+评测,不生成 hint、不压缩、不 review(每 task 仅跑 1 轮)
  - 作为 hint 效果对比的 baseline,摘要 mode=no_hint_baseline
  - 与 hint 闭环用不同 run_name 跑,对比 loop_summary 通过率即可量化 hint 提升
"""
import argparse
import json
import logging
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

SCRIPT_DIR = Path(__file__).resolve().parent
CC_RUN_DIR = SCRIPT_DIR.parent.parent  # benchmark/deepswe/ -> 项目根目录

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [loop] %(message)s",
)
log = logging.getLogger("run_loop_by_hint")

# ==================== 子脚本路径 ====================
RUN_ONE_HINT_SH = SCRIPT_DIR / "run_one_hint.sh"
COMPRESS_HINT_PY = SCRIPT_DIR / "compress_hint.py"
RUN_ONE_LOOP_SH = SCRIPT_DIR / "run_one_loop.sh"
REVIEW_HINT_TRAJ_PY = SCRIPT_DIR / "review_hint_traj.py"

# 跟踪当前子进程,Ctrl+C 时转发信号给整个子进程组
_current_proc: Optional[subprocess.Popen] = None


def _sigint_handler(signum, frame):
    """Ctrl+C 处理:向当前子进程组转发 SIGTERM,避免孤儿进程。"""
    global _current_proc
    if _current_proc is not None and _current_proc.poll() is None:
        try:
            os.killpg(os.getpgid(_current_proc.pid), signal.SIGTERM)
            log.warning("已向子进程组发送 SIGTERM")
        except Exception:
            pass
    sys.exit(130)


# ==================== 子进程 tee 执行 ====================

def run_step(
    step_name: str,
    cmd: List[str],
    log_path: Path,
    env: Optional[Dict[str, str]] = None,
    dry_run: bool = False,
) -> int:
    """运行子进程步骤,stdout/stderr 实时 tee 到控制台和日志文件。

    - 控制台:步骤开始前打印醒目分隔条,子进程输出原样透传
      (不加行前缀,避免干扰子脚本自身的格式化输出)
    - 日志文件:完整记录命令 + 所有输出 + 退出码,事后排查用
    - 信号:子进程独立 session(start_new_session),编排脚本被 Ctrl+C 时
      通过 _sigint_handler 向整个子进程组转发 SIGTERM

    返回子进程 exit code(dry_run 时返回 0)。
    """
    global _current_proc
    log_path.parent.mkdir(parents=True, exist_ok=True)
    # Handoff: redact only the displayed command; execute the original argv.
    display_cmd = list(cmd)
    for index, value in enumerate(display_cmd):
        if value == "--api_key" and index + 1 < len(display_cmd):
            display_cmd[index + 1] = "<REDACTED>"
        elif str(value).startswith("--api_key="):
            display_cmd[index] = "--api_key=<REDACTED>"
    cmd_str = " ".join(shlex.quote(str(c)) for c in display_cmd)

    # 控制台:醒目分隔条
    print(f"\n{'#' * 70}", flush=True)
    print(f"# STEP: {step_name}", flush=True)
    print(f"# CMD : {cmd_str}", flush=True)
    print(f"# LOG : {log_path}", flush=True)
    print(f"{'#' * 70}\n", flush=True)

    if dry_run:
        log.info("[dry_run] 跳过执行: %s", step_name)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(
                f"[DRY_RUN] {time.strftime('%Y-%m-%d %H:%M:%S')} STEP: {step_name}\n"
                f"CMD: {cmd_str}\n"
            )
        return 0

    start_ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(f"\n{'=' * 70}\n[{start_ts}] STEP: {step_name}\nCMD: {cmd_str}\n{'=' * 70}\n")
        fh.flush()

        proc = subprocess.Popen(
            [str(c) for c in cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )
        _current_proc = proc

        assert proc.stdout is not None
        for raw_line in iter(proc.stdout.readline, b""):
            line = raw_line.decode("utf-8", errors="replace")
            fh.write(line)
            fh.flush()
            print(line, end="", flush=True)  # 原样透传(行尾已有 \n)

        proc.wait()
        _current_proc = None

        end_ts = time.strftime("%Y-%m-%d %H:%M:%S")
        fh.write(f"\n{'=' * 70}\n[{end_ts}] STEP END: {step_name} (exit={proc.returncode})\n")

    if proc.returncode != 0:
        log.warning("步骤 [%s] 退出码: %d (日志: %s)", step_name, proc.returncode, log_path)
    else:
        log.info("步骤 [%s] 完成 (日志: %s)", step_name, log_path)
    return proc.returncode


# ==================== 评测结果读取 ====================

def read_eval_result(eval_path: Path) -> Optional[Dict[str, Any]]:
    """读取 eval_result.json,返回状态 dict 或 None(文件不存在/解析失败)。

    返回: {"solved": bool, "reward": value, "f2p_passed": ..., "f2p_total": ...}
    兼容 flatten 前后两种格式(reward 可能是数字或嵌套 dict)。
    """
    if not eval_path.is_file():
        return None
    try:
        data = json.loads(eval_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log.warning("读取 eval_result.json 失败: %s (%s)", eval_path, e)
        return None
    reward_raw = data.get("reward")
    if isinstance(reward_raw, dict):  # 未 flatten 的嵌套格式: f2p 字段在 reward dict 内
        reward = reward_raw.get("reward")
        f2p_passed = reward_raw.get("f2p_passed")
        f2p_total = reward_raw.get("f2p_total")
    else:
        reward = reward_raw
        f2p_passed = data.get("f2p_passed")
        f2p_total = data.get("f2p_total")
    return {
        "solved": reward == 1,
        "reward": reward,
        "f2p_passed": f2p_passed,
        "f2p_total": f2p_total,
    }


# ==================== 编排主类 ====================

class HintLoopOrchestrator:
    """端到端 hint 反馈闭环编排器。"""

    def __init__(self, args):
        self.args = args
        self.instance_id = args.instance_id
        self.run_name = args.run_name
        self.max_rounds = args.max_rounds
        self.output_base = Path(args.output_base)
        self.python_bin = args.python_bin

        # 核心路径(hint 生成 + 各轮压缩 hint 都在 {run_name}/hint_gen/ 下)
        self.hint_gen_dir = self.output_base / self.run_name / "hint_gen" / self.instance_id
        self.golden_diff_path = self.hint_gen_dir / "golden_diff.diff"
        self.full_hint_path = self.hint_gen_dir / "hint_output.md"
        # reviews/logs/summary 均按 instance_id 隔离:
        # 同一 run_name 顺序跑多 task 时互不覆盖(旧版无隔离,--continue 自动回退兼容)
        self.reviews_dir = self.output_base / self.run_name / "reviews" / self.instance_id
        self.logs_dir = self.output_base / self.run_name / "logs" / self.instance_id
        self.summary_path = (self.output_base / self.run_name
                             / f"loop_summary_{self.instance_id}.json")

        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.reviews_dir.mkdir(parents=True, exist_ok=True)

        # 步骤计数器(日志文件命名用)
        self._step_seq = 0

        # loop 摘要
        self.summary: Dict[str, Any] = {
            "instance_id": self.instance_id,
            "run_name": self.run_name,
            "max_rounds": self.max_rounds,
            "solved": False,
            "total_rounds": 0,
            "solved_round": None,
            "rounds": [],
            "start_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "end_time": None,
        }

        # 子进程环境(继承当前环境 + 附加控制变量)
        self.sub_env = dict(os.environ)
        self.sub_env["PYTHON_BIN"] = self.python_bin
        if args.skip_docker_login:
            self.sub_env["SKIP_DOCKER_LOGIN"] = "true"

    # ---------- 路径规则 ----------

    def _next_log_path(self, name: str) -> Path:
        """生成下一步骤日志路径: step_{seq:02d}_{name}.log"""
        path = self.logs_dir / f"step_{self._step_seq:02d}_{name}.log"
        self._step_seq += 1
        return path

    def _hint_path_for_round(self, round_num: int) -> Path:
        """第 round_num 轮使用的压缩 hint 路径(每轮独立文件名,不覆盖)"""
        return self.hint_gen_dir / f"hint_compact_r{round_num}.md"

    def _solve_run_name(self, round_num: int) -> str:
        """第 round_num 轮解题的 run_name(独立目录隔离 infer_logs/eval_output)"""
        return f"{self.run_name}_r{round_num}"

    def _trajs_path(self, round_num: int) -> Path:
        return (self.output_base / self._solve_run_name(round_num)
                / "infer_logs" / self.instance_id / "turn_1" / "trajs.json")

    def _eval_path(self, round_num: int) -> Path:
        """第 round_num 轮评测结果路径(评测脚本写入 eval_output/{instance_id}/)。"""
        return (self.output_base / self._solve_run_name(round_num)
                / "eval_output" / self.instance_id / "eval_result.json")

    def _find_eval_result(self, round_num: int) -> Optional[Dict[str, Any]]:
        """查找并读取第 round_num 轮评测结果(兼容 eval_output 与 infer_logs 两个位置)。"""
        eval_info = read_eval_result(self._eval_path(round_num))
        if eval_info is not None:
            return eval_info
        # 兼容位置: 部分版本写入 infer_logs/{instance_id}/turn_1/
        alt_path = (self.output_base / self._solve_run_name(round_num)
                    / "infer_logs" / self.instance_id / "turn_1" / "eval_result.json")
        return read_eval_result(alt_path)

    def _scan_existing_rounds(self) -> Dict[str, Any]:
        """扫描已有 {run_name}_r{X} 目录,找连续完整轮次(--continue 用)。

        rX 完整定义: ① trajs.json 存在 ② eval_result.json 存在且 f2p 未全部通过(未解决)。
        轮次按序扫描,遇到首个不完整轮次即停止(轮次应连续)。

        返回: {"last_complete_round": int, "solved_round": Optional[int]}
          - last_complete_round: 最大完整轮次(0 = 无完整轮次)
          - solved_round: 已解决的轮次(若某轮 reward=1,闭环本应已终止)
        """
        last_complete = 0
        solved_round = None
        for x in range(1, self.max_rounds + 1):
            trajs = self._trajs_path(x)
            if not trajs.is_file():
                break  # 无 trajs.json → 本轮及后续均不完整
            eval_info = self._find_eval_result(x)
            if eval_info is None:
                log.info("[scan] 第 %d 轮 trajs.json 存在但 eval_result.json 缺失,视为不完整", x)
                break
            if eval_info["solved"]:
                solved_round = x
                log.info("[scan] 第 %d 轮已解决(reward=1)", x)
                break
            last_complete = x
            log.info("[scan] 第 %d 轮完整(未解决, f2p=%s/%s)",
                     x, eval_info.get("f2p_passed"), eval_info.get("f2p_total"))
        return {"last_complete_round": last_complete, "solved_round": solved_round}

    def _review_json_path(self, round_num: int) -> Path:
        """第 round_num 轮 review json 路径(按 instance_id 隔离)。"""
        return self.reviews_dir / f"round_{round_num}" / "review_hint_traj.json"

    @property
    def _legacy_summary_path(self) -> Path:
        """旧版摘要路径(无 instance_id 隔离,--continue 兼容历史数据)。"""
        return self.output_base / self.run_name / "loop_summary.json"

    def _legacy_review_json_path(self, round_num: int) -> Path:
        """旧版 review json 路径(无 instance_id 隔离,--continue 兼容历史数据)。"""
        return (self.output_base / self.run_name / "reviews"
                / f"round_{round_num}" / "review_hint_traj.json")

    def _find_review_json(self, round_num: int) -> Optional[Path]:
        """查找第 round_num 轮 review json:新路径优先,回退旧路径(--continue 兼容历史数据)。

        返回实际存在的路径(新或旧),都不存在返回 None。
        """
        new_path = self._review_json_path(round_num)
        if new_path.is_file():
            return new_path
        legacy = self._legacy_review_json_path(round_num)
        if legacy.is_file():
            log.info("[continue] 第 %d 轮 review 位于旧路径(无 instance_id 隔离): %s",
                     round_num, legacy)
            return legacy
        return None

    def _save_summary(self):
        self.summary_path.write_text(
            json.dumps(self.summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _api_base_v1(self) -> str:
        """compress_hint.py / review_hint_traj.py 的 litellm base_url 需带 /v1"""
        base = self.args.api_base.rstrip("/")
        if not base.endswith("/v1"):
            base += "/v1"
        return base

    def _phase_api_base(self, role: str, phase: str, *, container: bool = False,
                        session: Optional[str] = None) -> str:
        """Keep CLI conversation identity explicit across API calls."""
        base = (getattr(self.args, "container_api_base", "") if container else "") \
            or self.args.api_base
        base = base.rstrip("/")
        session = session or getattr(self.args, "codex_session", "")
        if not session:
            return base
        if role == "compressor":
            session += f"-{phase}"
        if base.endswith("/v1"):
            base = base[:-3]
        return f"{base}/sessions/{quote(session, safe='')}/{role}/{phase}/v1"

    def _resolve_golden_diff_file(self) -> Optional[str]:
        """参考 get_hint_by_task.py 的 golden diff 获取优先级:
        --golden_diff_file > {tasks_dir}/{instance_id}/solution/solution.patch > parquet patch 列

        返回应显式传给 run_one_hint.sh --golden_diff_file 的路径;
        当 parquet patch 列可覆盖时返回 None(由 get_hint_by_task.py 自行读取,
        不传 --golden_diff_file 以免覆盖其内部逻辑)。
        """
        # 1. 显式指定的文件
        if self.args.golden_diff_file:
            p = Path(self.args.golden_diff_file)
            if p.is_file():
                return str(p)
            log.warning("--golden_diff_file 指定的文件不存在: %s", self.args.golden_diff_file)
        # 2. tasks_dir 下的 solution.patch
        solution_patch = Path(self.args.tasks_dir) / self.instance_id / "solution" / "solution.patch"
        if solution_patch.is_file():
            return str(solution_patch)
        # 3. parquet patch 列 → 交由 get_hint_by_task.py 自行读取,不显式传参
        return None

    # ---------- 各步骤 ----------

    def step_get_hint(self) -> bool:
        """Round 0: 调用 run_one_hint.sh 容器探索生成完整 hint。"""
        log.info("=" * 60)
        log.info("Round 0: 生成完整 hint (容器探索)")
        log.info("=" * 60)

        # --continue 或 --skip_hint_gen 时,hint_output.md 已存在则跳过生成
        if (getattr(self.args, "continue_run", False) or self.args.skip_hint_gen) \
                and self.full_hint_path.is_file():
            log.info("hint_output.md 已存在,跳过生成(--continue/--skip_hint_gen): %s",
                     self.full_hint_path)
            return True

        cmd = [
            "bash", str(RUN_ONE_HINT_SH),
            "--instance_id", self.instance_id,
            "--run_name", self.run_name,
            "--parquet_file", self.args.parquet_file,
            "--tasks_dir", self.args.tasks_dir,
            "--output_base", str(self.output_base),
            "--model_name", self.args.model_name,
            "--api_base", self._phase_api_base(
                "teacher", "generate", container=True,
                session=getattr(self.args, "teacher_codex_session", "")),
            "--api_key", self.args.api_key,
            "--hint_task_timeout", str(self.args.hint_task_timeout),
            "--monitor_interval", str(self.args.monitor_interval),
            "--mem_limit", self.args.mem_limit,
            "--proxy_max_tokens", str(self.args.proxy_max_tokens),
        ]
        if getattr(self.args, "teacher_state", ""):
            cmd += ["--teacher_state", self.args.teacher_state]
        if getattr(self.args, "keep_teacher", False):
            cmd.append("--keep_teacher")
        if getattr(self.args, "container_cpus", None):
            cmd += ["--container_cpus", str(self.args.container_cpus)]
        # golden diff 获取:参考 get_hint_by_task.py 的三级优先级
        # (--golden_diff_file > tasks_dir/solution/solution.patch > parquet patch 列)
        golden_diff_file = self._resolve_golden_diff_file()
        if golden_diff_file:
            cmd += ["--golden_diff_file", golden_diff_file]
            log.info("golden diff 文件: %s", golden_diff_file)
        else:
            log.info(
                "未显式指定 golden diff 文件,将由 get_hint_by_task.py 从 "
                "parquet patch 列获取(若 parquet 无 patch 列将报错)"
            )

        exit_code = run_step(
            "get_hint", cmd, self._next_log_path("get_hint"),
            env=self.sub_env, dry_run=self.args.dry_run,
        )

        if self.args.dry_run:
            return True
        if exit_code != 0:
            log.error("hint 生成失败 (exit=%d)", exit_code)
            return False
        if not self.full_hint_path.is_file():
            log.error("hint 生成完成但未找到 hint_output.md: %s", self.full_hint_path)
            return False
        log.info("完整 hint 已就绪: %s", self.full_hint_path)
        return True

    def step_compress(self, round_num: int, review_jsons: List[Path]) -> bool:
        """压缩 hint → hint_compact_r{round_num}.md,可选融合累计 review。"""
        hint_out = self._hint_path_for_round(round_num)
        log.info(
            "压缩 hint → %s (融合 %d 份 review)",
            hint_out, len(review_jsons),
        )

        cmd = [
            self.python_bin, str(COMPRESS_HINT_PY),
            "--instance_id", self.instance_id,
            "--run_name", self.run_name,
            "--output_base", str(self.output_base),
            "--output", str(hint_out),
            "--model", self.args.model_name,
            "--api_base", self._phase_api_base("compressor", f"compress_r{round_num}"),
            "--api_key", self.args.api_key,
        ]
        if review_jsons:
            cmd += ["--review_json"] + [str(p) for p in review_jsons]

        exit_code = run_step(
            f"compress_r{round_num}", cmd,
            self._next_log_path(f"compress_r{round_num}"),
            env=self.sub_env, dry_run=self.args.dry_run,
        )

        if self.args.dry_run:
            return True
        if exit_code != 0:
            log.error("hint 压缩失败 (exit=%d)", exit_code)
            return False
        if not hint_out.is_file():
            log.error("hint 压缩完成但未找到输出: %s", hint_out)
            return False
        log.info("压缩 hint 已就绪: %s", hint_out)
        return True

    def step_solve(self, round_num: int, no_hint: bool = False) -> Optional[Dict[str, Any]]:
        """第 round_num 轮:解题 + 评测 (run_one_loop.sh, max_turns=1)。

        run_one_loop.sh: exit 0 = solved, 1 = not solved, 其他 = 异常。
        以 eval_result.json 的 reward 为最终判定(exit code 作为辅助信号)。

        no_hint=True: 基线模式,不传 --hint_path(run_multi_turn_loop.py 自动查找
        {solve_run_name}/hint_gen/ 也找不到,turn 1 不注入 hint)。
        """
        solve_run_name = self._solve_run_name(round_num)
        log.info("=" * 60)
        log.info("Round %d: 解题+评测 (run_name=%s)", round_num, solve_run_name)
        if no_hint:
            log.info("  hint: (无,基线模式)")
        else:
            log.info("  hint: %s", self._hint_path_for_round(round_num))
        log.info("=" * 60)

        cmd = [
            "bash", str(RUN_ONE_LOOP_SH),
            "--instance_id", self.instance_id,
            "--run_name", solve_run_name,
            "--max_turns", "1",
            "--parquet_file", self.args.parquet_file,
            "--tasks_dir", self.args.tasks_dir,
            "--output_base", str(self.output_base),
            "--model_name", self.args.model_name,
            "--api_base", getattr(self.args, "container_api_base", "") or self.args.api_base,
            "--api_key", self.args.api_key,
            "--task_timeout", str(self.args.task_timeout),
            "--mem_limit", self.args.mem_limit,
            "--proxy_max_tokens", str(self.args.proxy_max_tokens),
            "--monitor_interval", str(self.args.monitor_interval),
        ]
        if getattr(self.args, "container_cpus", None):
            cmd += ["--container_cpus", str(self.args.container_cpus)]
        if getattr(self.args, "capability_path", None):
            cmd += ["--capability_path", str(self.args.capability_path)]
        if getattr(self.args, "codex_session", ""):
            cmd += ["--experiment_session", f"{self.args.codex_session}-r{round_num}",
                    "--teacher_status_url", self.args.teacher_status_url]
        if getattr(self.args, "teacher_progress_url", "") and not no_hint:
            cmd += ["--teacher_progress_url", self.args.teacher_progress_url]
        if not no_hint:
            # 显式指定 hint,避免自动查找错目录;基线模式不传,不注入任何 hint
            cmd += ["--hint_path", str(self._hint_path_for_round(round_num))]

        exit_code = run_step(
            f"solve_r{round_num}", cmd,
            self._next_log_path(f"solve_r{round_num}"),
            env=self.sub_env, dry_run=self.args.dry_run,
        )

        if self.args.dry_run:
            return {"exit_code": 0, "solved": False, "eval": None}

        eval_info = self._find_eval_result(round_num)
        if eval_info is None:
            log.error("Formal evaluation result is missing: %s (exit=%s)",
                      self._eval_path(round_num), exit_code)
            return None
        if eval_info["solved"] != (exit_code == 0):
            log.warning(
                "exit code(%d) 与 eval reward(%s) 不一致,以 eval 为准: solved=%s",
                exit_code, eval_info["reward"], eval_info["solved"],
            )
        return {
            "exit_code": exit_code,
            "solved": eval_info["solved"],
            "eval": eval_info,
        }

    def step_review(self, round_num: int, solved: bool = False,
                    trajs_override: Optional[Path] = None) -> bool:
        """分析第 round_num 轮轨迹,产出 review json。

        solved=False: 失败诊断模式,产出 corrective_hint 供下轮累计压缩。
        solved=True:  泄漏审查模式,审查 hint 泄漏(行为泄漏+方案泄漏),供开发者复核。
        """
        trajs = Path(trajs_override) if trajs_override is not None else self._trajs_path(round_num)
        hint = self._hint_path_for_round(round_num)  # 本轮实际使用的 hint
        golden_diff = self.golden_diff_path
        review_dir = self.reviews_dir / f"round_{round_num}"
        review_dir.mkdir(parents=True, exist_ok=True)
        md_out = review_dir / "review_hint_traj.md"
        json_out = review_dir / "review_hint_traj.json"

        review_purpose = "泄漏审查(检查 hint 泄漏,供开发者复核)" if solved \
            else "失败诊断(产出 corrective_hint 供下轮压缩)"
        log.info("=" * 60)
        log.info("Review Round %d: %s", round_num, review_purpose)
        log.info("  trajs:      %s", trajs)
        log.info("  hint:       %s", hint)
        log.info("  golden_diff: %s", golden_diff)
        log.info("=" * 60)

        if not self.args.dry_run and not trajs.is_file():
            log.error("trajs.json 不存在,无法 review: %s", trajs)
            return False

        cmd = [
            self.python_bin, str(REVIEW_HINT_TRAJ_PY),
            "--trajs", str(trajs),
            "--hint", str(hint),
            "--golden_diff", str(golden_diff),
            "--output", str(md_out),
            "--json_output", str(json_out),
            "--model", self.args.model_name,
            "--api_base", self._phase_api_base(
                "teacher", f"review_r{round_num}", container=True,
                session=(getattr(self.args, "teacher_codex_session", "")
                         if getattr(self.args, "teacher_session_mode", "fresh") == "resume"
                         else f"{getattr(self.args, 'codex_session', self.run_name)}-review-r{round_num}")),
            "--api_key", self.args.api_key,
        ]
        if getattr(self.args, "teacher_state", ""):
            cmd += ["--teacher_state", self.args.teacher_state,
                    "--teacher_session", self.args.teacher_session_mode,
                    "--teacher_output_dir", str(review_dir / "teacher")]
        if solved:
            cmd.append("--solved")

        exit_code = run_step(
            f"review_r{round_num}", cmd,
            self._next_log_path(f"review_r{round_num}"),
            env=self.sub_env, dry_run=self.args.dry_run,
        )

        if self.args.dry_run:
            return True
        if exit_code != 0:
            log.error("review 失败 (exit=%d)", exit_code)
            return False
        if not json_out.is_file():
            log.error("review 完成但未找到 json: %s", json_out)
            return False
        log.info("review 产物已就绪: %s", json_out)
        return True

    # ---------- 主循环 ----------

    def run_baseline(self) -> int:
        """Run independent no-Hint attempts; preserve the original one-attempt default."""
        self.summary["mode"] = "no_hint_baseline"
        attempts = getattr(self.args, "baseline_rounds", 1)
        self.summary["max_rounds"] = attempts
        if not self.args.dry_run and not RUN_ONE_LOOP_SH.is_file():
            self._finish_summary(2, "missing_script")
            return 2

        for round_num in range(1, attempts + 1):
            round_info = {
                "round": round_num,
                "hint_path": None,
                "solve_run_name": self._solve_run_name(round_num),
                "trajs_path": str(self._trajs_path(round_num)),
            }
            eval_info = self._find_eval_result(round_num) if self.args.continue_run else None
            if eval_info is not None and self._trajs_path(round_num).is_file():
                result = {"eval": eval_info, "solved": eval_info["solved"], "exit_code": None}
            else:
                result = self.step_solve(round_num, no_hint=True)
            self.summary["total_rounds"] = round_num
            if result is None:
                round_info["status"] = "incomplete"
                self.summary["rounds"].append(round_info)
                self._finish_summary(2, "solve_failed")
                return 2
            round_info.update(result)
            round_info["status"] = "solved" if result["solved"] else "not_solved"
            self.summary["rounds"].append(round_info)
            self.summary["total_rounds"] = round_num
            self._save_summary()
            if result["solved"]:
                self.summary["solved"] = True
                self.summary["solved_round"] = round_num
                self._finish_summary(0, "solved")
                return 0
        self._finish_summary(1, "not_solved")
        return 1

    def run(self) -> int:
        """执行完整闭环。

        返回码: 0 = solved, 1 = 达到最大轮次未解决(正常结束), 2 = 步骤异常中断。
        """
        # 无 hint 基线模式: 跳过 hint 生成/压缩/review,只解题+评测
        if getattr(self.args, "no_hint_run", False):
            return self.run_baseline()

        log.info("#" * 60)
        log.info("启动 hint 反馈闭环: instance=%s run_name=%s max_rounds=%d",
                 self.instance_id, self.run_name, self.max_rounds)
        log.info("output_base=%s", self.output_base)
        log.info("#" * 60)

        if not self.args.dry_run:
            for p in [RUN_ONE_HINT_SH, COMPRESS_HINT_PY, RUN_ONE_LOOP_SH, REVIEW_HINT_TRAJ_PY]:
                if not p.is_file():
                    log.error("依赖脚本不存在: %s", p)
                    self._finish_summary(2, "missing_script")
                    return 2

        # ---- --continue 续跑预检 ----
        start_round = 1
        review_jsons: List[Path] = []  # 累计的 review json,供下轮压缩融合

        if self.args.continue_run:
            # 加载已有摘要的轮次记录(保留历史进度);新路径优先,回退旧路径兼容历史数据
            for sp in [self.summary_path, self._legacy_summary_path]:
                if not sp.is_file():
                    continue
                try:
                    prev = json.loads(sp.read_text(encoding="utf-8"))
                    prev_rounds = prev.get("rounds", [])
                    if prev_rounds:
                        self.summary["rounds"] = prev_rounds
                        log.info("[continue] 已加载历史摘要: %d 轮记录 (%s)",
                                 len(prev_rounds), sp)
                except (json.JSONDecodeError, OSError):
                    pass
                break

            scan = self._scan_existing_rounds()

            # 某轮已解决 → 补做泄漏审查(若缺失)后无需续跑
            if scan["solved_round"] is not None:
                sr = scan["solved_round"]
                log.info("[continue] 第 %d 轮已解决(reward=1)", sr)
                # 已解决轮次也需泄漏审查(供开发者复核),缺失则补做
                # (兼容旧路径:历史数据 review 可能写在无 instance_id 的旧目录)
                leakage_status = "done" if self._find_review_json(sr) is not None else "skipped"
                if self._find_review_json(sr) is None:
                    log.info("[continue] 第 %d 轮泄漏审查缺失,补做", sr)
                    leakage_status = "done" if self.step_review(sr, solved=True) else "failed"
                    if leakage_status == "failed":
                        log.warning("[continue] 补做泄漏审查失败,不影响 solved 结果")
                # 更新历史轮次记录中的泄漏审查状态
                for r in self.summary["rounds"]:
                    if r.get("round") == sr:
                        r["leakage_review"] = leakage_status
                        break
                self.summary["solved"] = True
                self.summary["solved_round"] = sr
                self.summary["total_rounds"] = sr
                self._finish_summary(0, "already_solved")
                return 0

            last = scan["last_complete_round"]
            if last == 0:
                log.error(
                    "[continue] 未找到任何完整轮次(需 trajs.json + eval_result.json 且未解决),"
                    "请去掉 --continue 从头运行"
                )
                self._finish_summary(2, "continue_no_complete_round")
                return 2

            start_round = last + 1
            if start_round > self.max_rounds:
                log.error(
                    "[continue] 完整轮次(%d)已达最大轮次 %d,无法续跑(可增大 --max_rounds)",
                    last, self.max_rounds,
                )
                self._finish_summary(2, "continue_max_rounds_reached")
                return 2

            log.info("[continue] 第 1~%d 轮完整(未解决),从第 %d 轮续跑", last, start_round)
            self.summary["continued_from_round"] = start_round

            # 恢复累计 review jsons(round_1..round_last),缺失则补做 review
            # (兼容旧路径:历史 review 可能写在无 instance_id 的旧目录,直接复用)
            for r in range(1, last + 1):
                rj = self._find_review_json(r)
                if rj is not None:
                    review_jsons.append(rj)
                else:
                    log.info("[continue] 第 %d 轮 review 缺失,补做 review", r)
                    if not self.step_review(r):
                        log.error("[continue] 补做第 %d 轮 review 失败,终止", r)
                        self._finish_summary(2, "continue_review_failed")
                        return 2
                    review_jsons.append(self._review_json_path(r))  # 补做的写入新路径
            log.info("[continue] 累计 %d 份 review 反馈", len(review_jsons))

            # 确认最新 hint(hint_compact_r{start_round}.md)是否就绪
            next_hint = self._hint_path_for_round(start_round)
            if next_hint.is_file():
                log.info("[continue] 最新 hint 已就绪: %s", next_hint)
            else:
                log.info(
                    "[continue] 最新 hint 缺失(%s),将在第 %d 轮压缩步骤中生成",
                    next_hint, start_round,
                )

        # ---- Round 0: 生成完整 hint(--continue 时已存在则自动跳过) ----
        if not self.step_get_hint():
            log.error("Round 0 hint 生成失败,闭环终止")
            self._finish_summary(2, "get_hint_failed")
            return 2

        # ---- 逐轮:压缩 → 解题 → (未解决)review ----
        final_status = "not_solved"    # 正常走完所有轮次仍未解决

        for round_num in range(start_round, self.max_rounds + 1):
            round_info: Dict[str, Any] = {
                "round": round_num,
                "hint_path": str(self._hint_path_for_round(round_num)),
                "solve_run_name": self._solve_run_name(round_num),
                "trajs_path": str(self._trajs_path(round_num)),
                "review_count": len(review_jsons),
                "status": None,
                "eval": None,
            }
            log.info("\n%s", "=" * 60)
            log.info(">>> Round %d / %d <<<", round_num, self.max_rounds)
            log.info("%s", "=" * 60)

            # 1. 压缩 hint(第 1 轮无 review,第 N 轮融合前 N-1 轮 review)
            #    --continue 时若本轮压缩 hint 已存在则复用,不重新压缩
            hint_path = self._hint_path_for_round(round_num)
            if self.args.continue_run and hint_path.is_file():
                log.info("[continue] 第 %d 轮压缩 hint 已存在,复用: %s", round_num, hint_path)
            elif not self.step_compress(round_num, review_jsons):
                round_info["status"] = "compress_failed"
                self.summary["rounds"].append(round_info)
                final_status = "compress_failed"
                break

            # 2. 解题 + 评测
            solve_result = self.step_solve(round_num)
            if solve_result is None:
                round_info["status"] = "solve_failed"
                self.summary["rounds"].append(round_info)
                final_status = "solve_failed"
                break
            round_info["eval"] = solve_result.get("eval")
            round_info["exit_code"] = solve_result.get("exit_code")
            self.summary["total_rounds"] = round_num

            # 3. 已解决 → 泄漏审查后提前结束
            #    即使已解决,仍审查 trajs.json 检查 hint 泄漏(行为泄漏+方案泄漏),
            #    供开发者复核;审查失败不阻断 solved 结果,仅记录警告
            if solve_result["solved"]:
                if self.step_review(round_num, solved=True):
                    round_info["leakage_review"] = "done"
                else:
                    round_info["leakage_review"] = "failed"
                    log.warning("Round %d 泄漏审查失败,不影响 solved 结果", round_num)
                round_info["status"] = "solved"
                self.summary["rounds"].append(round_info)
                self.summary["solved"] = True
                self.summary["solved_round"] = round_num
                final_status = "solved"
                log.info("Round %d 已解决!闭环提前结束。", round_num)
                break

            # 4. 未解决:最后一轮不再 review,直接结束
            if round_num == self.max_rounds:
                round_info["status"] = "not_solved"
                self.summary["rounds"].append(round_info)
                final_status = "not_solved"
                log.info("已达最大轮次(%d),题目仍未解决。", self.max_rounds)
                break

            # 5. review 失败轨迹,产出 corrective_hint 供下轮累计压缩
            if not self.step_review(round_num):
                round_info["status"] = "review_failed"
                self.summary["rounds"].append(round_info)
                final_status = "review_failed"
                break
            review_jsons.append(self._review_json_path(round_num))
            round_info["status"] = "review_done"
            self.summary["rounds"].append(round_info)
            log.info("Round %d review 完成,累计 %d 份反馈,进入下一轮。",
                     round_num, len(review_jsons))

            # 每轮落盘一次摘要(中途异常也能保留进度)
            self._save_summary()

        exit_code = 0 if self.summary["solved"] else (1 if final_status == "not_solved" else 2)
        self._finish_summary(exit_code, final_status)
        return exit_code

    def _finish_summary(self, exit_code: int, final_status: str):
        """收尾:汇总每轮关键路径,落盘 loop_summary.json。"""
        self.summary["final_status"] = final_status
        self.summary["exit_code"] = exit_code
        self.summary["end_time"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._save_summary()

        log.info("#" * 60)
        log.info("闭环结束: %s (exit=%d)", final_status, exit_code)
        log.info("  总轮次:     %d", self.summary["total_rounds"])
        log.info("  是否解决:   %s", self.summary["solved"])
        if self.summary["solved_round"]:
            log.info("  解决轮次:   %d", self.summary["solved_round"])
        log.info("  摘要文件:   %s", self.summary_path)
        log.info("  步骤日志目录: %s", self.logs_dir)
        log.info("#" * 60)


# ==================== 多 task 编排器 ====================

class MultiTaskLoopOrchestrator:
    """多 task 编排器: 同一 run_name 下顺序处理 parquet 中的所有 task。

    --instance_id all 时启用。每个 task 启动独立的 HintLoopOrchestrator,
    产物按 instance_id 隔离(reviews/logs/summary 互不覆盖)。
    单个 task 异常不中断后续 task,每跑完一个落盘汇总(loop_summary_all.json)。

    退出码: 0 = 全部 solved, 1 = 有未 solved 但无异常, 2 = 有异常/parquet 加载失败,
            130 = Ctrl+C 中断。
    """

    def __init__(self, args):
        self.args = args
        self.run_name = args.run_name
        self.max_rounds = args.max_rounds
        self.output_base = Path(args.output_base)
        self.parquet_file = Path(args.parquet_file)
        self.summary_path = self.output_base / self.run_name / "loop_summary_all.json"

    def _load_instance_ids(self) -> List[str]:
        """从 parquet 读取所有 instance_id(按文件行序)。"""
        try:
            import pandas as pd
        except ImportError as e:
            raise RuntimeError("多 task 模式需要 pandas + pyarrow: pip install pandas pyarrow") from e
        df = pd.read_parquet(self.parquet_file)
        if "instance_id" not in df.columns:
            raise ValueError(f"parquet 缺少 instance_id 列: {self.parquet_file}")
        return df["instance_id"].astype(str).tolist()

    def _save_summary(self, results: List[Dict[str, Any]], status: str = "running"):
        """落盘多 task 汇总摘要。"""
        summary = {
            "mode": "no_hint_baseline" if getattr(self.args, "no_hint_run", False) else "all",
            "run_name": self.run_name,
            "max_rounds": self.max_rounds,
            "total_tasks": len(results),
            "solved_tasks": sum(1 for r in results if r.get("solved")),
            "status": status,
            "tasks": results,
            "update_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self.summary_path.parent.mkdir(parents=True, exist_ok=True)
        self.summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def run(self) -> int:
        """顺序执行所有 task,汇总结果。

        返回码: 0 = 全部 solved, 1 = 有未 solved 但无异常, 2 = 有异常, 130 = Ctrl+C。
        """
        try:
            ids = self._load_instance_ids()
        except Exception as e:
            log.error("加载 parquet 失败: %s (%s)", self.parquet_file, e)
            return 2

        if not ids:
            log.error("parquet 中无 task: %s", self.parquet_file)
            return 2

        log.info("#" * 60)
        log.info("多 task 模式: 共 %d 个 task (run_name=%s)", len(ids), self.run_name)
        for i, iid in enumerate(ids, 1):
            log.info("  [%d/%d] %s", i, len(ids), iid)
        log.info("#" * 60)

        # all 模式下 --golden_diff_file 不适用(单文件无法匹配多 task),忽略并警告
        if self.args.golden_diff_file:
            log.warning(
                "all 模式忽略 --golden_diff_file(%s): 多 task 各自从 "
                "tasks_dir/{instance_id}/solution/solution.patch 获取 golden diff",
                self.args.golden_diff_file,
            )

        results: List[Dict[str, Any]] = []
        interrupted = False

        for idx, iid in enumerate(ids, 1):
            log.info("\n%s", "*" * 70)
            log.info("*** Task %d/%d: %s ***", idx, len(ids), iid)
            log.info("%s", "*" * 70)

            # 构造单 task args: 替换 instance_id,清空 golden_diff_file(按实例自行解析)
            task_args = argparse.Namespace(**vars(self.args))
            task_args.instance_id = iid
            task_args.golden_diff_file = ""

            task_result: Dict[str, Any] = {
                "instance_id": iid,
                "index": idx,
                "exit_code": None,
                "final_status": None,
                "solved": False,
                "solved_round": None,
                "total_rounds": 0,
                "summary_path": None,
            }

            try:
                orch = HintLoopOrchestrator(task_args)
                ec = orch.run()
                task_result["exit_code"] = ec
                task_result["final_status"] = orch.summary.get("final_status")
                task_result["solved"] = orch.summary.get("solved", False)
                task_result["solved_round"] = orch.summary.get("solved_round")
                task_result["total_rounds"] = orch.summary.get("total_rounds", 0)
                task_result["summary_path"] = str(orch.summary_path)
            except SystemExit as e:
                # _sigint_handler 触发 sys.exit(130) → Ctrl+C 中断,保存进度后退出
                if e.code == 130:
                    interrupted = True
                    task_result["final_status"] = "interrupted"
                    log.warning("Task %s 被 Ctrl+C 中断,停止后续 task", iid)
                    break
                raise  # 其他 SystemExit 重新抛出

            results.append(task_result)
            # 每跑完一个 task 落盘汇总(中途异常也能保留进度)
            self._save_summary(results)

            status_str = "solved" if task_result["solved"] else task_result["final_status"]
            log.info("*** Task %d/%d (%s) 完成: %s ***", idx, len(ids), iid, status_str)

        # ---- 汇总 ----
        if interrupted:
            self._save_summary(results, status="interrupted")
            log.info("多 task 运行被中断: 已完成 %d/%d", len(results), len(ids))
            return 130

        solved = sum(1 for r in results if r["solved"])
        failed = sum(1 for r in results if r["exit_code"] == 2)
        self._save_summary(results, status="done")

        log.info("#" * 60)
        log.info("多 task 运行结束: 共 %d 个 task", len(results))
        log.info("  已解决:   %d", solved)
        log.info("  未解决:   %d", len(results) - solved - failed)
        log.info("  异常:     %d", failed)
        log.info("  汇总文件: %s", self.summary_path)
        log.info("#" * 60)

        if failed:
            return 2
        return 0 if solved == len(results) else 1


# ==================== CLI ====================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="端到端 hint 反馈闭环编排: 生成→压缩→解题→review→累计压缩→... (最多 N 轮)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--instance_id", required=True,
                        help="任务实例 ID;设为 all 则顺序处理 parquet 中的所有 task")
    parser.add_argument("--run_name", required=True, help="实验名称(hint/review/日志归于此名下)")
    parser.add_argument("--max_rounds", type=int, default=5, help="最大解题轮次")
    parser.add_argument("--baseline_rounds", type=int, default=1,
                        help="Independent no-Hint attempts (original default: 1)")
    parser.add_argument("--codex_session", default="")
    parser.add_argument("--container_api_base", default="")
    parser.add_argument("--container_cpus", type=int, default=None)
    parser.add_argument("--teacher_state", default="")
    parser.add_argument("--teacher_codex_session", default="")
    parser.add_argument("--teacher_session_mode", choices=("fresh", "resume"), default="fresh")
    parser.add_argument("--keep_teacher", action="store_true")
    parser.add_argument("--teacher_progress_url", default="")
    parser.add_argument("--teacher_status_url", default="http://127.0.0.1:8766/experiment/status")
    parser.add_argument("--output_base", default=str(CC_RUN_DIR / "deepswe-output"),
                        help="输出根目录")
    parser.add_argument("--parquet_file", default=str(CC_RUN_DIR / "deep_swe_tasks.parquet"))
    parser.add_argument("--tasks_dir", default="/tmp/deep-swe-tasks/tasks")
    parser.add_argument("--model_name", default="Qwen3.6-35B-A3B")
    parser.add_argument("--api_base", default="http://hubrouter.jd.com")
    parser.add_argument("--api_key", default=os.environ.get("HUBROUTER_API_KEY", ""))
    parser.add_argument("--python_bin", default=sys.executable)
    parser.add_argument("--task_timeout", type=int, default=7200, help="解题容器超时(秒)")
    parser.add_argument("--capability_path", default=None,
                        help="Frozen cross-task capability text; independent of per-task Hint generation")
    parser.add_argument("--hint_task_timeout", type=int, default=3600, help="hint 生成容器超时(秒)")
    parser.add_argument("--monitor_interval", type=int, default=30, help="容器监控轮询间隔(秒,0=禁用)")
    parser.add_argument("--mem_limit", default="128g", help="容器内存限制")
    parser.add_argument("--proxy_max_tokens", type=int, default=65536)
    parser.add_argument("--golden_diff_file", default="", help="外部 golden diff 文件(留空自动提取)")
    parser.add_argument("--skip_hint_gen", action="store_true",
                        help="跳过 hint 生成(需已有 hint_output.md)")
    parser.add_argument("--no_hint_run", action="store_true",
                        help="无 hint 基线模式: 只解题+评测,不生成 hint/不压缩/不 review,"
                             "用于对比 hint 效果(每 task 仅跑 1 轮)")
    parser.add_argument("--continue", dest="continue_run", action="store_true",
                        help="续跑模式:扫描已有完整轮次(trajs.json+eval_result.json 且未解决),"
                             "从下一轮继续;自动复用已有 hint/补做缺失 review")
    parser.add_argument("--skip_docker_login", action="store_true")
    parser.add_argument("--dry_run", action="store_true", help="只打印命令不执行")
    return parser


def main():
    args = build_parser().parse_args()
    signal.signal(signal.SIGINT, _sigint_handler)
    if args.instance_id == "all":
        orch: Any = MultiTaskLoopOrchestrator(args)
    else:
        orch = HintLoopOrchestrator(args)
    exit_code = orch.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
