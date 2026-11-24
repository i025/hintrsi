#!/usr/bin/env python3
"""通过容器探索生成解题 hint。

与 gen_review_hint.py(单轮 LLM 请求,仅基于 eval 结果 + patch 概况)不同,
本脚本启动容器,让 agent 通过 search/terminal 等工具实际探索代码库,
结合 golden diff 和题目需求,生成更准确的 hint、思路和解题步骤。

流程:
  1. 从 parquet 加载任务(problem_statement / patch(golden diff) / base_commit 等)
  2. 启动容器 → 注入文件 → 安装+重置到 base_commit
  3. 注入 golden diff + hint 生成 prompt(system prompt + user prompt)
  4. 运行 SDK agent 探索容器代码库,生成解题指导文档
  5. 收集 hint(优先 /tmp/hint_output.md,兜底 trajs.json ResultMessage)
  6. 删除容器

用法:
  python benchmark/deepswe/get_hint_by_task.py \
    --instance_id go-genai-streamed-function-args \
    --run_name lisen_hint_test \
    --parquet_file deep_swe_tasks.parquet \
    --tasks_dir /tmp/deep-swe-tasks/tasks \
    --config /tmp/run_config.yaml \
    --output_base deepswe-output
"""

import argparse
import gzip
import io
import json
import logging
import os
import shlex
import sys
import tarfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import docker
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # benchmark/deepswe/ -> 项目根目录
sys.path.insert(0, str(PROJECT_ROOT))

from constant_zhy import (  # noqa: E402
    INSTALL_SCRIPT, render_proxy_config,
    INSTANCE_ID, IMAGE_NAME, PROBLEM_STATEMENT,
    INSTALLATION_COMMAND, BASE_COMMIT,
)
from runtime_config import load_run_config  # noqa: E402

# ==================== 常量 ====================
HINT_TASK_TIMEOUT_SEC = int(os.getenv("HINT_TASK_TIMEOUT_SEC", "3600"))
INSTALL_TIMEOUT_SEC = int(os.getenv("INSTALL_TIMEOUT_SEC", "3600"))
DOCKER_CLIENT_TIMEOUT_SEC = int(
    os.getenv("DOCKER_CLIENT_TIMEOUT_SEC", str(max(HINT_TASK_TIMEOUT_SEC + 300, 600)))
)
CONTAINER_MEM_LIMIT = os.getenv("CONTAINER_MEM_LIMIT", "128g")

# 实时监控参数(exec_run 阻塞期间,后台线程周期轮询容器内日志增量打印到控制台)
MONITOR_INTERVAL_SEC = int(os.getenv("HINT_MONITOR_INTERVAL_SEC", "30"))
MONITOR_LINE_TRUNCATE = int(os.getenv("HINT_MONITOR_LINE_TRUNCATE", "300"))
# 噪声过滤:这些子串命中的日志行不逐条打印,只统计跳过数量
# (thinking_tokens 是 SDK 每 token delta 一条的计数更新,每秒数十条,纯噪声)
MONITOR_LOG_FILTERS = ("thinking_tokens",)

# 容器内路径
SDK_SCRIPT_LOG_PATH = "/tmp/sdk_script.log"
GOLDEN_DIFF_CONTAINER_PATH = "/tmp/golden_diff.diff"
HINT_OUTPUT_CONTAINER_PATH = "/tmp/hint_output.md"
HINT_SYSTEM_PROMPT_CONTAINER_PATH = "/tmp/hint_system_prompt.md"
HINT_PS_CONTAINER_PATH = "/tmp/ps.txt"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("get_hint_by_task")

# ==================== Prompt 模板 ====================

HINT_AGENT_SYSTEM_PROMPT = """You are an expert code reviewer and technical teacher. Help a coding student solve the task independently using the task description, the fixed reference patch, repository inspection, and the student's recorded work.

[Shared Working Principles]
- Use the available file-reading, search, and terminal tools to inspect the actual repository before drawing conclusions.
- The repository and reference patch are read-only. Do not edit source files or run checkout, reset, commit, or other repository-changing commands. You may write requested analysis artifacts under /tmp only.
- Base conclusions on inspected code and recorded tool results, and distinguish observations from hypotheses.
- Never execute the reference patch or repair the student's code yourself.
- All generated guidance and analysis must be in English. Preserve original source, patch, and tool-output quotations verbatim.
- Your role covers both initial guidance and later reviews. Follow the stage-specific output instructions in the user message.
- Initial guidance may identify relevant existing files and explain implementation directions, but must not paste a complete solution.
- A progress reminder must not reveal code, exact edits, a complete solution sequence, hidden-test content, or reference-only identifiers that the student has not discovered.
"""

HINT_AGENT_USER_PROMPT = """## Stage: Initial Guidance

The fixed reference patch is available at {golden_diff_path}.

## Original Issue

{problem_statement}

## Workflow

1. Read the reference patch and understand the affected files and intended behavior.
2. Inspect the actual repository, related calls, types, interfaces, and data flow. Explain why the initial implementation fails.
3. Produce a detailed Markdown guide with these sections:
   - Problem Essence: explain the root cause in two or three sentences.
   - Key Files and Locations: cover every file affected by the reference patch and explain its role.
   - Solution Approach: explain the design and the relationships between the changes.
   - Implementation Directions: describe where to investigate, what logic needs attention, and why, without complete replacement code.
   - Pitfalls and Edge Cases: explain related changes that are easy to miss and relevant boundary conditions.
4. Write the complete guide to {hint_output_path} and include it in your final response.

Begin by reading the reference patch, then inspect the repository.
"""


# ==================== 工具函数 ====================

def inject_file_to_container(container, content: bytes, container_path: str):
    """注入单个文件到容器。"""
    dir_path = str(Path(container_path).parent)
    container.exec_run(f"mkdir -p {dir_path}")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo(name=Path(container_path).name)
        info.size = len(content)
        info.mtime = time.time()
        tar.addfile(info, io.BytesIO(content))
    buf.seek(0)
    container.put_archive(dir_path, buf)


def copy_from_container(container, src_path: str, dest_dir: Path) -> bool:
    """从容器拷出单个文件到 dest_dir(覆盖同名)。"""
    temp_tar = dest_dir / f"temp_extract_{Path(src_path).name}.tar"
    try:
        bits, _ = container.get_archive(src_path)
        with open(temp_tar, "wb") as f:
            for chunk in bits:
                f.write(chunk)
        with tarfile.open(temp_tar) as tar:
            tar.extractall(path=dest_dir)
        return True
    except Exception as e:
        log.warning("拷出产物失败 %s -> %s: %s", src_path, dest_dir, e)
        return False
    finally:
        try:
            if temp_tar.exists():
                temp_tar.unlink()
        except Exception:
            pass


def extract_hint_from_trajs(trajs_path: Path) -> str:
    """从 trajs.json 的 ResultMessage.result 提取 agent 最终输出(兜底)。"""
    if not trajs_path.exists():
        return ""
    try:
        data = json.loads(trajs_path.read_text(encoding="utf-8"))
        result = data.get("metadata", {}).get("ResultMessage", {}).get("result", "")
        return result.strip() if result else ""
    except Exception as e:
        log.warning("从 trajs.json 提取 hint 失败: %s", e)
        return ""


# ==================== 主类 ====================

def _monitor_container(
    container_name: str,
    interval: int,
    stop_event: threading.Event,
    log_file: Optional[Path] = None,
) -> threading.Thread:
    """启动容器实时监控线程。

    exec_run 阻塞期间无任何输出,此线程每隔 interval 秒通过独立 docker client
    执行一次轻量 exec_run,采集容器内实时状态:
      - sdk_script.log 行数 + 自上次轮询以来的新增行
        (run_cc_sdk.py 每收到一条 Claude Code message 都会 logger.info,是最直接的进度信号)
      - proxy.log 大小(LLM 调用活跃度)
      - hint_output.md / trajs.json 生成状态

    输出双通道:
      - 控制台:只打印关键信息(状态摘要 + 过滤噪声 + 截断长行)
      - log_file:完整信息实时落盘(不截断、不过滤),事后排查用;
        若容器 OOM/被删导致事后拷贝失败,monitor.log 仍有运行期完整记录

    使用独立 docker client,避免与主线程共享 requests.Session 的线程安全问题。
    """

    def _poll_once(mon_container, last_line: int, fh=None) -> int:
        """执行一次轮询:完整信息写文件,关键信息打印控制台,返回新的 last_line。"""
        cmd = (
            f"L=$(wc -l < {SDK_SCRIPT_LOG_PATH} 2>/dev/null || echo 0); "
            f"H=$(stat -c %s {HINT_OUTPUT_CONTAINER_PATH} 2>/dev/null || echo -1); "
            f"P=$(stat -c %s /tmp/proxy.log 2>/dev/null || echo 0); "
            f"T=$(stat -c %s /tmp/hint_agent_out/trajs.json 2>/dev/null || echo -1); "
            f'printf "===STATS %s %s %s %s\\n" "$L" "$H" "$P" "$T"; '
            f'if [ "$L" -gt {last_line} ]; then '
            f"echo ===NEWLOG; "
            f"sed -n '{last_line + 1},$p' {SDK_SCRIPT_LOG_PATH} 2>/dev/null; "
            f"echo ===ENDLOG; fi"
        )
        ec, out = mon_container.exec_run(["/bin/bash", "-c", cmd])
        if ec != 0:
            log.warning("[monitor] 轮询命令失败 exit=%s", ec)
            return last_line
        text = out.decode("utf-8", errors="replace") if out else ""

        cur_lines = last_line
        hint_size, proxy_size, trajs_size = -1, 0, -1
        new_log_lines: list = []
        in_new = False
        for line in text.splitlines():
            if line.startswith("===STATS "):
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        cur_lines = int(parts[1])
                        hint_size = int(parts[2])
                        proxy_size = int(parts[3])
                        trajs_size = int(parts[4])
                    except ValueError:
                        pass
            elif line == "===NEWLOG":
                in_new = True
            elif line == "===ENDLOG":
                in_new = False
            elif in_new:
                new_log_lines.append(line)

        now = time.strftime("%Y-%m-%d %H:%M:%S")
        hint_str = f"已生成({hint_size}B)" if hint_size >= 0 else "未生成"
        trajs_str = "已生成" if trajs_size >= 0 else "无"
        stats_line = (
            f"sdk_log: {last_line}→{cur_lines} 行(+{cur_lines - last_line}) | "
            f"proxy: {proxy_size / 1048576:.2f}MB | hint_output.md: {hint_str} | trajs: {trajs_str}"
        )
        # 控制台:状态摘要(每次轮询一行)
        log.info("[monitor] %s", stats_line)
        # 文件:完整状态摘要(带时间戳)
        if fh:
            fh.write(f"[{now}] [STATS] {stats_line}\n")

        # 增量日志处理:文件写完整行,控制台只打印过滤+截断后的关键行
        skipped = 0
        for line in new_log_lines:
            if not line.strip():
                continue
            # 文件:完整写入(不截断、不过滤)
            if fh:
                fh.write(f"[{now}] [LOG] {line}\n")
            # 控制台:噪声行只计数
            if any(f in line for f in MONITOR_LOG_FILTERS):
                skipped += 1
                continue
            display = line[:MONITOR_LINE_TRUNCATE] + (
                "…" if len(line) > MONITOR_LINE_TRUNCATE else ""
            )
            print(f"  [sdk] {display}", flush=True)
        if skipped:
            skip_msg = f"(跳过 {skipped} 条噪声日志,完整内容见 monitor.log)"
            print(f"  [sdk] {skip_msg}", flush=True)
            if fh:
                fh.write(f"[{now}] [STATS] {skip_msg}\n")
        if fh:
            fh.flush()
        return cur_lines

    def _loop():
        try:
            mon_client = docker.from_env(timeout=60)
            mon_container = mon_client.containers.get(container_name)
        except Exception as e:
            log.warning("[monitor] 初始化失败,本次运行无实时监控: %s", e)
            return

        fh = None
        if log_file:
            try:
                log_file.parent.mkdir(parents=True, exist_ok=True)
                fh = open(log_file, "a", encoding="utf-8")
                fh.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] [STATS] ===== 监控开始: {container_name} =====\n")
            except Exception as e:
                log.warning("[monitor] 打开日志文件失败 %s: %s", log_file, e)

        last_line = 0
        try:
            while not stop_event.is_set():
                if stop_event.wait(timeout=interval):
                    break
                try:
                    last_line = _poll_once(mon_container, last_line, fh)
                except docker.errors.NotFound:
                    log.error("[monitor] 容器已消失(可能 OOM 或被手动删除),监控退出")
                    if fh:
                        fh.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [STATS] ===== 容器消失,监控退出 =====\n")
                    return
                except Exception as e:
                    # 偶发网络抖动等,下轮重试
                    log.warning("[monitor] 轮询异常(将重试): %s", e)
            # 收尾:主流程结束后最后拉一次,补齐剩余日志
            try:
                _poll_once(mon_container, last_line, fh)
            except Exception:
                pass
            if fh:
                fh.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [STATS] ===== 监控结束 =====\n")
        finally:
            if fh:
                try:
                    fh.close()
                except Exception:
                    pass
            try:
                mon_client.close()
            except Exception:
                pass

    t = threading.Thread(target=_loop, daemon=True, name="hint-monitor")
    t.start()
    return t


class ContainerHintGenerator:
    """启动容器,让 agent 探索代码库并生成解题 hint。"""

    def __init__(self, args):
        self.args = args
        self.instance_id = args.instance_id
        self.run_name = args.run_name
        self.parquet_file = args.parquet_file
        self.output_base = args.output_base
        self.tasks_dir = args.tasks_dir

        # 输出目录: {output_base}/{run_name}/hint_gen/{instance_id}/
        self.out_dir = Path(self.output_base) / self.run_name / "hint_gen" / self.instance_id
        self.out_dir = Path(getattr(args, "teacher_output_dir", None) or self.out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)

        # 资源文件路径(注入容器用)——位于项目根目录
        self.sdk_script_path = PROJECT_ROOT / "run_cc_sdk.py"
        self.logging_utils_path = PROJECT_ROOT / "logging_utils.py"
        self.litellm_callbacks_path = PROJECT_ROOT / "litellm_proxy" / "claude_code_proxy.py"
        self.streaming_fix_path = PROJECT_ROOT / "litellm_proxy" / "streaming_fix.py"

        self.monitor_interval = getattr(args, "monitor_interval", MONITOR_INTERVAL_SEC)

        self.docker_client = None
        self.container = None
        self.container_name = None

        self.base_commit: Optional[str] = None
        self.task_row: Optional[Dict[str, Any]] = None
        self.golden_diff: Optional[str] = None

    # ---------- 任务加载 ----------
    def load_task_row(self):
        """从 parquet 加载任务信息,含 golden diff(patch 列)。"""
        df = pd.read_parquet(self.parquet_file)
        row = df[df["instance_id"] == self.instance_id]
        if row.empty:
            raise ValueError(f"parquet 中找不到 instance_id: {self.instance_id}")
        self.task_row = row.iloc[0].to_dict()
        self.base_commit = self.task_row.get(BASE_COMMIT) or self.task_row.get("base_commit")
        if not self.base_commit:
            raise ValueError("parquet 中缺少 base_commit")

        # golden diff 优先级: --golden_diff_file > tasks_dir/solution/solution.patch > parquet patch 列
        if self.args.golden_diff_file and Path(self.args.golden_diff_file).is_file():
            self.golden_diff = Path(self.args.golden_diff_file).read_text(encoding="utf-8", errors="replace")
            log.info("golden diff 来自文件: %s (%d 字符)", self.args.golden_diff_file, len(self.golden_diff))
        elif self.args.tasks_dir:
            solution_patch = Path(self.args.tasks_dir) / self.instance_id / "solution" / "solution.patch"
            if solution_patch.is_file():
                self.golden_diff = solution_patch.read_text(encoding="utf-8", errors="replace")
                log.info("golden diff 来自 tasks_dir: %s (%d 字符)", solution_patch, len(self.golden_diff))
        if not self.golden_diff:
            self.golden_diff = self.task_row.get("patch") or ""
            if not self.golden_diff:
                raise ValueError(
                    "未找到 golden diff: 请指定 --golden_diff_file 或 --tasks_dir,"
                    "或 parquet 需包含 patch 列"
                )
            log.info("golden diff 来自 parquet patch 列 (%d 字符)", len(self.golden_diff))

        log.info("任务加载完成: %s (base_commit=%s)", self.instance_id, self.base_commit)

    # ---------- 容器管理 ----------
    def start_container(self):
        image_name = self.task_row.get(IMAGE_NAME) or self.task_row.get("image_name")
        if not image_name:
            raise ValueError("parquet 中缺少 image_name")
        image_base = image_name.split("/")[-1].split(":")[0]
        self.container_name = f"hint-{image_base}-{uuid.uuid4().hex[:8]}"
        self.docker_client = docker.from_env(timeout=DOCKER_CLIENT_TIMEOUT_SEC)
        log.info("启动容器 %s (镜像 %s)", self.container_name, image_name)
        runtime_options = {}
        if os.getenv("HINT_EXPERIMENT_NAME"):
            runtime_options["labels"] = {"hint.experiment_name": os.environ["HINT_EXPERIMENT_NAME"]}
        runtime_path = os.getenv("HINT_CODEX_RUNTIME")
        if runtime_path:
            runtime_options["volumes"] = {
                runtime_path: {"bind": "/opt/python3.12-tmp", "mode": "ro"}}
            runtime_options["environment"] = {
                "HINT_PREINSTALLED_RUNTIME": "1", "PYTHONDONTWRITEBYTECODE": "1"}
        self.container = self.docker_client.containers.run(
            image_name, name=self.container_name,
            entrypoint="", command="tail -f /dev/null",
            detach=True, mem_limit=CONTAINER_MEM_LIMIT, privileged=True,
            nano_cpus=int(getattr(self.args, "cpus", 0) * 1_000_000_000),
            **runtime_options,
        )
        log.info("容器已启动: %s", self.container_name)

    def stop_and_remove_container(self):
        if self.container is not None:
            try:
                self.container.stop(timeout=10)
            except Exception:
                pass
            try:
                self.container.remove(force=True)
            except Exception as e:
                log.warning("删除容器失败: %s", e)
            log.info("容器已删除: %s", self.container_name)
            self.container = None

    # ---------- 文件注入 ----------
    def inject_files(self, task_config):
        """注入运行所需文件 + golden diff + hint 生成 prompt。"""
        problem_statement = (
            self.task_row.get(PROBLEM_STATEMENT)
            or self.task_row.get("problem_statement", "")
        )
        # hint agent 的 user prompt
        hint_user_prompt = HINT_AGENT_USER_PROMPT.format(
            golden_diff_path=GOLDEN_DIFF_CONTAINER_PATH,
            problem_statement=problem_statement,
            hint_output_path=HINT_OUTPUT_CONTAINER_PATH,
        )
        proxy_config = render_proxy_config(
            provider=self.args.provider, model=self.args.model,
            api_key=self.args.api_key, api_base=self.args.api_base,
            callbacks_path="/tmp/litellm_call_backs.proxy_handler_instance",
            reasoning_effort=self.args.reasoning_effort,
            max_tokens=self.args.proxy_max_tokens,
        )
        files = {
            "/tmp/install.sh": (INSTALL_SCRIPT, 0o755),
            "/tmp/sdk_script.py": (self.sdk_script_path.read_bytes(), 0o755),
            "/tmp/logging_utils.py": (self.logging_utils_path.read_bytes(), 0o644),
            "/tmp/litellm_call_backs.py": (self.litellm_callbacks_path.read_bytes(), 0o644),
            "/tmp/streaming_fix.py": (self.streaming_fix_path.read_bytes(), 0o644),
            "/tmp/config.yaml": (proxy_config, 0o644),
            # hint 专用文件
            GOLDEN_DIFF_CONTAINER_PATH: (self.golden_diff, 0o644),
            HINT_PS_CONTAINER_PATH: (hint_user_prompt, 0o644),
            HINT_SYSTEM_PROMPT_CONTAINER_PATH: (HINT_AGENT_SYSTEM_PROMPT, 0o644),
        }
        # 可选注入: skills.tar.gz
        if self.args.skills_path and Path(self.args.skills_path).is_file():
            files["/tmp/skills.tar.gz"] = (Path(self.args.skills_path).read_bytes(), 0o644)

        log.info("注入 %d 个文件到容器", len(files))
        for dest_path, (content, _mode) in files.items():
            inject_file_to_container(
                self.container,
                content if isinstance(content, bytes) else str(content).encode("utf-8"),
                dest_path,
            )
        # 解压 skills
        if self.args.skills_path and Path(self.args.skills_path).is_file():
            self.container.exec_run(
                "bash -c 'mkdir -p /root/.claude/skills && tar -xzf /tmp/skills.tar.gz -C /root/.claude/skills'"
            )

    # ---------- 安装与重置 ----------
    def install_and_reset(self, task_config):
        """运行 install.sh(含 proxy 启动)+ git 重置到 base_commit。"""
        run_env = {
            **(task_config.container_env if task_config else {}),
            **(task_config.claude_env if task_config else {}),
            "PROXY_MAX_TOKENS_CLAMP": str(self.args.proxy_max_tokens),
        }
        # 1. install.sh
        log.info("运行 install.sh (timeout=%ds)", INSTALL_TIMEOUT_SEC)
        ec, out = self.container.exec_run(
            f"timeout {INSTALL_TIMEOUT_SEC} bash /tmp/install.sh",
            environment=run_env,
        )
        output = out.decode("utf-8", errors="replace") if out else ""
        if ec != 0:
            log.error("install.sh 失败(exit=%s):\n%s", ec, output[-3000:])
            raise RuntimeError("install.sh 执行失败")
        log.info("install.sh 完成")

        # 2. git reset + clean
        self.container.exec_run("bash -c 'git reset --hard && git clean -fd'", workdir="/app")

        # 3. anticheat scrub(与解题环境一致)
        git_scrub_command = self.task_row.get("git_scrub_command") or ""
        if git_scrub_command:
            log.info("执行 anticheat scrub")
            self.container.exec_run(
                f"bash -c {shlex.quote(f'cd /app && {git_scrub_command} > /tmp/anticheat_scrub.log 2>&1 || true')}"
            )

        # 4. checkout base_commit
        log.info("checkout base_commit: %s", self.base_commit)
        ec, out = self.container.exec_run(
            f"bash -c {shlex.quote(f'cd /app && git checkout {self.base_commit}')}"
        )
        if ec != 0:
            log.error("checkout 失败:\n%s", out.decode("utf-8", errors="replace") if out else "")
            raise RuntimeError(f"git checkout {self.base_commit} 失败")

        # 5. installation_command
        installation_command = (
            self.task_row.get(INSTALLATION_COMMAND)
            or self.task_row.get("installation_command")
            or ""
        )
        if installation_command:
            log.info("执行 installation_command")
            inner_cmd = f"cd /app && timeout {INSTALL_TIMEOUT_SEC} bash -c {json.dumps(installation_command)}"
            ec, out = self.container.exec_run(
                f"bash -c {shlex.quote(inner_cmd)}",
                environment=run_env,
            )
            if ec != 0:
                log.warning("installation_command exit=%s", ec)

    # ---------- 运行 hint agent ----------
    def run_hint_agent(self, task_config, user_prompt=None,
                       output_dir_in_container="/tmp/hint_agent_out",
                       resume_session_id=None) -> bool:
        """在容器内运行 SDK agent,使用 hint 生成 prompt 探索代码库。

        复用 run_cc_sdk.py:hint user prompt 作为 problem_statement,
        hint system prompt 通过 SYSTEM_PROMPT_FILE 环境变量注入。
        """
        run_env = {
            **(task_config.container_env if task_config else {}),
            **(task_config.claude_env if task_config else {}),
            # 关键:让 run_cc_sdk.py 加载 hint 专用 system prompt
            "SYSTEM_PROMPT_FILE": HINT_SYSTEM_PROMPT_CONTAINER_PATH,
            "TEACHER_MODE": "1",
            "EXPERIMENT_ROLE": "teacher",
        }
        if user_prompt is not None:
            inject_file_to_container(self.container, user_prompt.encode("utf-8"), HINT_PS_CONTAINER_PATH)
        self.container.exec_run(f"mkdir -p {output_dir_in_container}")

        cmd_parts = [
            "/opt/python3.12-tmp/bin/python3 /tmp/sdk_script.py",
            "--cwd /app",
            f"--base_commit {self.base_commit}",
            f"--log_path {SDK_SCRIPT_LOG_PATH}",
            f"--output_dir {output_dir_in_container}",
            f"--problem_statement_file {HINT_PS_CONTAINER_PATH}",
        ]
        if resume_session_id:
            cmd_parts += [f"--resume_session_id {shlex.quote(resume_session_id)}",
                          f"--extra_message_file {HINT_PS_CONTAINER_PATH}"]
        cmd_str = " ".join(cmd_parts)
        log.info("运行 hint agent (timeout=%ds)", HINT_TASK_TIMEOUT_SEC)
        log.info("命令: %s", cmd_str[:300])

        result_holder = {}

        def _run():
            try:
                ec, out = self.container.exec_run(
                    ["timeout", "-s", "INT", "-k", "30", str(HINT_TASK_TIMEOUT_SEC),
                     "/bin/bash", "-c", cmd_str],
                    workdir="/app",
                    environment=run_env,
                )
                result_holder["exit_code"] = ec
                result_holder["output"] = out.decode("utf-8", errors="replace") if out else ""
            except Exception as e:
                result_holder["exit_code"] = -1
                result_holder["output"] = str(e)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        # 启动实时监控线程:exec_run 阻塞期间增量打印容器内日志到控制台
        # 双通道输出:完整信息写入 monitor.log,控制台只显示关键信息
        monitor_stop = threading.Event()
        monitor_thread = None
        if self.monitor_interval > 0:
            monitor_log_path = self.out_dir / "monitor.log"
            log.info("完整监控日志将写入: %s", monitor_log_path)
            monitor_thread = _monitor_container(
                self.container.name, self.monitor_interval, monitor_stop,
                log_file=monitor_log_path,
            )
        else:
            log.info("实时监控已禁用(monitor_interval=0)")

        thread.join(timeout=HINT_TASK_TIMEOUT_SEC + 120)

        # 通知监控线程退出(它会最后拉一次补齐剩余日志)
        monitor_stop.set()
        if monitor_thread:
            monitor_thread.join(timeout=15)

        if thread.is_alive():
            log.error("hint agent 执行超时 (%ds)", HINT_TASK_TIMEOUT_SEC)
            return False

        ec = result_holder.get("exit_code", -1)
        output = result_holder.get("output", "")
        copied = copy_from_container(
            self.container, f"{output_dir_in_container}/trajs.json", self.out_dir)
        if ec != 0:
            log.error("hint agent exit=%s\n%s", ec, output[-3000:])
            return False
        if not copied:
            log.error("Teacher SDK trajectory was not saved")
            return False
        metadata = json.loads((self.out_dir / "trajs.json").read_text(encoding="utf-8"))["metadata"]
        result = metadata.get("ResultMessage")
        if metadata.get("status") != "completed" or not result or result.get("is_error"):
            log.error("Teacher SDK did not complete successfully")
            return False
        log.info("hint agent 执行完成")
        return True

    def make_repository_read_only(self):
        """Keep the same read-only repository permissions in both teacher conditions."""
        ec, out = self.container.exec_run(
            ["bash", "-c", "mount --bind /app /app && mount -o remount,bind,ro /app"]
        )
        if ec != 0:
            raise RuntimeError(out.decode("utf-8", errors="replace"))

    def clear_stage_files(self):
        """Remove file-based stage memory while preserving the SDK session directory."""
        self.container.exec_run([
            "bash", "-c",
            "rm -rf /tmp/hint_agent_out /tmp/teacher_review_out "
            "/tmp/hint_output.md /tmp/review_output.md /tmp/ps.txt "
            "/tmp/sdk_script.log /tmp/proxy_tail.log /tmp/base_commit.txt; "
            "truncate -s 0 /tmp/proxy.log",
        ])

    def save_sdk_session(self):
        """Export SDK conversation files before releasing a teacher container."""
        target = self.out_dir / "teacher_sdk_projects.tar.gz"
        temporary = target.with_suffix(".tmp")
        try:
            chunks, _ = self.container.get_archive("/root/.claude/projects")
        except docker.errors.NotFound:
            return None
        with gzip.open(temporary, "wb") as stream:
            for chunk in chunks:
                stream.write(chunk)
        temporary.replace(target)
        return str(target)

    def save_teacher_state(self, state_path, trajs_path=None):
        trajs_path = Path(trajs_path or self.out_dir / "trajs.json")
        metadata = json.loads(trajs_path.read_text(encoding="utf-8"))["metadata"]
        session_id = metadata.get("ResultMessage", {}).get("session_id")
        if not session_id:
            session_id = metadata.get("SystemMessage", {}).get("data", {}).get("session_id")
        if not session_id:
            raise ValueError("The teacher did not return an SDK session ID")
        arguments = dict(vars(self.args))
        arguments.pop("api_key", None)
        config_path = self.out_dir / "teacher_run_config.yaml"
        config_path.write_text(Path(self.args.config).read_text(encoding="utf-8"), encoding="utf-8")
        arguments["config"] = str(config_path)
        arguments["keep_teacher"] = False
        arguments["teacher_output_dir"] = None
        archive = self.save_sdk_session()
        if archive is None:
            raise RuntimeError("The completed teacher SDK session could not be exported")
        state = {
            "sdk_projects_archive": archive,
            "container_name": self.container.name,
            "session_id": session_id,
            "base_commit": self.base_commit,
            "initial_artifacts": str(self.out_dir),
            "arguments": arguments,
        }
        Path(state_path).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return state

    def refresh_proxy(self, task_config):
        proxy_config = render_proxy_config(
            provider=self.args.provider, model=self.args.model,
            api_key=self.args.api_key, api_base=self.args.api_base,
            callbacks_path="/tmp/litellm_call_backs.proxy_handler_instance",
            reasoning_effort=self.args.reasoning_effort,
            max_tokens=self.args.proxy_max_tokens,
        )
        inject_file_to_container(self.container, proxy_config.encode("utf-8"), "/tmp/config.yaml")
        ready_seconds = 600 if os.getenv("HINT_CODEX_RUNTIME") else 60
        command = (
            "pkill -f '^/opt/python3.12-tmp/bin/.*litellm --config /tmp/config.yaml' || true; "
            "PYTHONPATH=/tmp LITELLM_LOG=DEBUG nohup /opt/python3.12-tmp/bin/litellm "
            "--config /tmp/config.yaml > /tmp/proxy.log 2>&1 & "
            f"for i in $(seq 1 {ready_seconds}); do "
            "curl -sf http://127.0.0.1:4000/health/liveliness >/dev/null && exit 0; sleep 1; done; exit 1"
        )
        ec, out = self.container.exec_run(
            ["bash", "-c", command], environment=task_config.container_env,
        )
        if ec != 0:
            raise RuntimeError("Could not restart the teacher proxy")

    # ---------- 收集 hint ----------
    def collect_hint(self) -> str:
        """收集 hint:优先 /tmp/hint_output.md,兜底 trajs.json ResultMessage。"""
        # 1. 拷出 agent 写入的 hint 文件
        copied = copy_from_container(self.container, HINT_OUTPUT_CONTAINER_PATH, self.out_dir)
        hint = ""
        hint_file = self.out_dir / Path(HINT_OUTPUT_CONTAINER_PATH).name  # hint_output.md
        if copied and hint_file.exists():
            hint = hint_file.read_text(encoding="utf-8", errors="replace").strip()
            if hint:
                log.info("hint 来自 %s (%d 字符)", HINT_OUTPUT_CONTAINER_PATH, len(hint))

        # 2. 兜底:从 trajs.json 提取
        if not hint:
            turn_out = "/tmp/hint_agent_out"
            copy_from_container(self.container, f"{turn_out}/trajs.json", self.out_dir)
            trajs_path = self.out_dir / "trajs.json"
            hint = extract_hint_from_trajs(trajs_path)
            if hint:
                log.info("hint 来自 trajs.json ResultMessage (%d 字符)", len(hint))

        # 3. 拷出日志(调试用)
        copy_from_container(self.container, SDK_SCRIPT_LOG_PATH, self.out_dir)
        self.container.exec_run(
            "bash -c 'tail -c 500000 /tmp/proxy.log > /tmp/proxy_tail.log 2>/dev/null || true'"
        )
        copy_from_container(self.container, "/tmp/proxy_tail.log", self.out_dir)
        proxy_dst = self.out_dir / "proxy_tail.log"
        if proxy_dst.exists():
            proxy_dst.rename(self.out_dir / "proxy.log")

        # 4. 确保 trajs.json 一定拷出(即使 hint 来自文件)
        trajs_dst = self.out_dir / "trajs.json"
        if not trajs_dst.exists():
            copy_from_container(self.container, "/tmp/hint_agent_out/trajs.json", self.out_dir)

        return hint

    # ---------- 保存结果 ----------
    def save_hint(self, hint: str):
        """保存 hint.md + hint_meta.json。"""
        # hint.md
        hint_md = self.out_dir / "hint.md"
        hint_md.write_text(hint, encoding="utf-8")
        log.info("hint 已保存: %s", hint_md)

        # golden diff 副本(便于追溯)
        golden_copy = self.out_dir / "golden_diff.diff"
        golden_copy.write_text(self.golden_diff or "", encoding="utf-8")

        # hint_meta.json
        meta = {
            "instance_id": self.instance_id,
            "run_name": self.run_name,
            "base_commit": self.base_commit,
            "model": self.args.model,
            "provider": self.args.provider,
            "golden_diff_chars": len(self.golden_diff or ""),
            "hint_chars": len(hint),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        meta_path = self.out_dir / "hint_meta.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("meta 已保存: %s", meta_path)

    # ---------- 主流程 ----------
    def run(self) -> int:
        log.info("=" * 60)
        log.info("Hint 生成(容器探索模式): %s", self.instance_id)
        log.info("输出目录: %s", self.out_dir)
        log.info("=" * 60)

        # 1. 加载任务
        self.load_task_row()

        # 2. 加载配置
        run_config = load_run_config(self.args.config)
        task_config = run_config.resolve_task()
        log.info("配置加载完成 (provider=%s, model=%s)", self.args.provider, self.args.model)

        # 3. 启动容器
        self.start_container()

        hint = ""
        completed = False
        try:
            # 4. 注入文件 + 安装重置
            self.inject_files(task_config)
            self.install_and_reset(task_config)
            self.make_repository_read_only()

            # 5. 运行 hint agent 探索容器
            exec_ok = self.run_hint_agent(task_config)
            if not exec_ok:
                log.warning("hint agent 未正常完成,仍尝试收集输出")

            # 6. 收集 hint
            hint = self.collect_hint()
            if hint:
                self.save_hint(hint)
            if not exec_ok:
                log.error("Teacher execution failed; partial output is retained only for inspection")
                return 1
            if not hint:
                log.error("未能收集到 hint(agent 可能未产出有效内容)")
                return 1

            # 7. 保存
            state_path = self.args.teacher_state or str(self.out_dir / "teacher_state.json")
            self.save_teacher_state(state_path)
            self.clear_stage_files()
            completed = True

            # 打印 hint 摘要
            log.info("")
            log.info("=" * 60)
            log.info("HINT 生成完成 (%d 字符),前 800 字符预览:", len(hint))
            log.info("%s", hint[:800])
            log.info("=" * 60)
            return 0
        finally:
            # 8. 清理容器
            log.info("清理容器 ...")
            if not completed:
                self.save_sdk_session()
                self.container.stop(timeout=10)
            elif not self.args.keep_teacher:
                self.stop_and_remove_container()


def run_teacher_review(state_path, user_prompt, output_dir, resume=False,
                       api_base=None, api_key="", model=None, provider=None):
    """Run a review with the same SDK, tools, initial repository, and teacher role."""
    state_path = Path(state_path)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    values = dict(state["arguments"])
    values.update(api_key=api_key, teacher_output_dir=str(output_dir), keep_teacher=False)
    for name, value in (("api_base", api_base), ("model", model), ("provider", provider)):
        if value is not None:
            values[name] = value
    args = argparse.Namespace(**values)
    generator = ContainerHintGenerator(args)
    generator.load_task_row()
    task_config = load_run_config(args.config).resolve_task()
    if resume:
        generator.docker_client = docker.from_env(timeout=DOCKER_CLIENT_TIMEOUT_SEC)
        generator.container = generator.docker_client.containers.get(state["container_name"])
        generator.container_name = generator.container.name
        generator.clear_stage_files()
        generator.refresh_proxy(task_config)
    else:
        generator.start_container()
    completed = False
    try:
        if not resume:
            generator.inject_files(task_config)
            generator.install_and_reset(task_config)
            generator.make_repository_read_only()
        stage_prompt = user_prompt + "\n\nWrite your complete review to /tmp/review_output.md and include it in your final response."
        ok = generator.run_hint_agent(
            task_config, user_prompt=stage_prompt,
            output_dir_in_container="/tmp/teacher_review_out",
            resume_session_id=state["session_id"] if resume else None,
        )
        copy_from_container(generator.container, "/tmp/teacher_review_out/trajs.json", generator.out_dir)
        copy_from_container(generator.container, SDK_SCRIPT_LOG_PATH, generator.out_dir)
        copy_from_container(generator.container, "/tmp/proxy.log", generator.out_dir)
        if not ok:
            raise RuntimeError("Teacher review execution failed; see the stage logs")
        review_path = generator.out_dir / "review_output.md"
        copied = copy_from_container(generator.container, "/tmp/review_output.md", generator.out_dir)
        review = review_path.read_text(encoding="utf-8").strip() if copied else ""
        if not review:
            review = extract_hint_from_trajs(generator.out_dir / "trajs.json")
        if not review:
            raise ValueError("The teacher returned an empty review")
        generator.save_teacher_state(generator.out_dir / "teacher_state.json")
        if resume:
            generator.save_teacher_state(state_path)
        generator.clear_stage_files()
        completed = True
        return review
    finally:
        if not completed:
            generator.save_sdk_session()
            generator.container.stop(timeout=10)
        elif not resume:
            generator.stop_and_remove_container()


# ==================== CLI ====================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="通过容器探索生成解题 hint(启动容器,agent 用 search/terminal 工具探索代码库)"
    )
    parser.add_argument("--instance_id", required=True, help="任务 ID")
    parser.add_argument("--run_name", required=True, help="实验名称")
    parser.add_argument("--parquet_file", default="deep_swe_tasks.parquet",
                        help="任务 parquet 文件(含 problem_statement/patch/base_commit 等)")
    parser.add_argument("--tasks_dir", default=None,
                        help="DeepSWE tasks 目录(golden diff 取自 {tasks_dir}/{instance_id}/solution/solution.patch)")
    parser.add_argument("--config", required=True, help="run_config YAML 路径")
    parser.add_argument("--output_base", default="deepswe-output", help="输出根目录")
    parser.add_argument("--golden_diff_file", default=None,
                        help="golden diff 文件路径(优先于 parquet patch 列)")
    # 模型/proxy 参数
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--model", default="gpt-6.1-terra")
    parser.add_argument("--api_base", default="http://127.0.0.1:8765/v1")
    parser.add_argument("--api_key", default=os.environ.get("HUBROUTER_API_KEY", ""))
    parser.add_argument("--reasoning_effort", default="low")
    parser.add_argument("--container_cpus", "--cpus", dest="cpus", type=float, default=0)
    parser.add_argument("--teacher_state", default=None)
    parser.add_argument("--keep_teacher", action="store_true")
    parser.add_argument("--teacher_output_dir", default=None)
    parser.add_argument("--proxy_max_tokens", type=int, default=65536,
                        help="proxy 强制 clamp 的 max_tokens(默认 65536)")
    # 可选注入
    parser.add_argument("--skills_path", default=None, help="skills.tar.gz 路径")
    # 实时监控
    parser.add_argument("--monitor_interval", type=int, default=MONITOR_INTERVAL_SEC,
                        help="实时监控轮询间隔秒数:exec_run 阻塞期间后台线程周期打印容器内日志增量(0=禁用,默认 30)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generator = ContainerHintGenerator(args)
    return generator.run()


if __name__ == "__main__":
    sys.exit(main())
