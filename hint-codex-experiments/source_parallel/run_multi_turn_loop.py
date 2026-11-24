

#!/usr/bin/env python3
"""多轮反馈 loop 编排脚本(单实例)。

流程:
  1. 从 parquet 加载任务,启动容器,注入文件,安装+重置
  2. Turn 1: agent 解题(新会话) → 收集产物 → eval
  3. 未解决 → 归档 turn_N/ → 生成 hint → resume 会话进入 Turn N+1
  4. 最多 max_turns 轮(默认 1=单轮),无论成功与否最终删除容器

用法:
  python run_multi_turn_loop.py \
    --instance_id go-genai-streamed-function-args \
    --run_name lisen_loop_test \
    --parquet_file deep_swe_tasks.parquet \
    --tasks_dir /tmp/deep-swe-tasks/tasks \
    --config /tmp/run_config.yaml \
    --output_base deepswe-output \
    --max_turns 1
"""

import argparse
import io
import json
import logging
import os
import shlex
import shutil
import sys
import tarfile
import threading
import time
import uuid
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

import docker
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR / "benchmark" / "deepswe"))

from constant_zhy import (  # noqa: E402
    INSTALL_SCRIPT, render_proxy_config,
    INSTANCE_ID, IMAGE_NAME, PROBLEM_STATEMENT,
    INSTALLATION_COMMAND, BASE_COMMIT,
)
from runtime_config import load_run_config  # noqa: E402
from eval_deep_swe import evaluate_task  # noqa: E402
import gen_review_hint  # noqa: E402

# ==================== 常量 ====================
TASK_TIMEOUT_SEC = int(os.getenv("TASK_TIMEOUT_SEC", "7200"))
INSTALL_TIMEOUT_SEC = int(os.getenv("INSTALL_TIMEOUT_SEC", "3600"))
DOCKER_CLIENT_TIMEOUT_SEC = int(
    os.getenv("DOCKER_CLIENT_TIMEOUT_SEC", str(max(TASK_TIMEOUT_SEC + 300, 600)))
)
CONTAINER_MEM_LIMIT = os.getenv("CONTAINER_MEM_LIMIT", "128g")

SDK_SCRIPT_LOG_PATH = "/tmp/sdk_script.log"
TRAJS_FILE_PATH = "/tmp/trajs.json"
PATCH_DIFF_PATH = "/tmp/patch.diff"
ANTICHEAT_BLOCKS_LOG_PATH = "/tmp/anticheat_blocks.log"
ANTICHEAT_FIREWALL_LOG_PATH = "/tmp/anticheat_firewall.log"
ANTICHEAT_SCRUB_LOG_PATH = "/tmp/anticheat_scrub.log"
# system prompt 日志(proxy 捕获实际请求中的 system prompt + sdk_script 记录启动前配置)
SYSTEM_PROMPT_ACTUAL_LOG_PATH = "/tmp/system_prompt_actual.json"
SYSTEM_PROMPT_CONFIG_LOG_PATH = "/tmp/system_prompt_config.json"

# 实时监控参数(移植自 get_hint_by_task.py):
# exec_run 阻塞期间后台线程周期轮询容器内日志增量打印到控制台
MONITOR_INTERVAL_SEC = int(os.getenv("LOOP_MONITOR_INTERVAL_SEC", "30"))
MONITOR_LINE_TRUNCATE = int(os.getenv("LOOP_MONITOR_LINE_TRUNCATE", "300"))
# 噪声过滤:这些子串命中的日志行不逐条打印,只统计跳过数量
# (thinking_tokens 是 SDK 每 token delta 一条的计数更新,每秒数十条,纯噪声)
MONITOR_LOG_FILTERS = ("thinking_tokens",)

# USER_PROMPT(与 run_cc_trajs_swe_pro.py 一致)
_prompt_file = os.getenv("USER_PROMPT_FILE_PATH", "prompts/user_prompt.md")
_prompt_path = Path(_prompt_file)
if not _prompt_path.is_absolute():
    _prompt_path = SCRIPT_DIR / _prompt_file
if not _prompt_path.is_file():
    raise FileNotFoundError(f"无法找到 Prompt 文件: {_prompt_path}")
USER_PROMPT = _prompt_path.read_text(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("multi_turn_loop")


# ==================== 工具函数 ====================

def _monitor_container(
    container_name: str,
    interval: int,
    stop_event: threading.Event,
    log_file: Optional[Path] = None,
    watch_files: Optional[Dict[str, str]] = None,
    sdk_log_path: str = SDK_SCRIPT_LOG_PATH,
    start_line: int = 0,
) -> threading.Thread:
    """启动容器实时监控线程(移植自 get_hint_by_task.py,适配多轮 loop)。

    exec_run 阻塞期间无任何输出,此线程每隔 interval 秒通过独立 docker client
    执行一次轻量 exec_run,采集容器内实时状态:
      - sdk_script.log 行数 + 自上次轮询以来的新增行
        (run_cc_sdk.py 每收到一条 Claude Code message 都会 logger.info,是最直接的进度信号)
      - proxy.log 大小(LLM 调用活跃度)
      - watch_files 中各文件生成状态(如 turn_N/trajs.json、turn_N/patch.diff)

    输出双通道:
      - 控制台:只打印关键信息(状态摘要 + 过滤噪声 + 截断长行)
      - log_file:完整信息实时落盘(不截断、不过滤),事后排查用;
        若容器 OOM/被删导致事后拷贝失败,monitor.log 仍有运行期完整记录

    使用独立 docker client,避免与主线程共享 requests.Session 的线程安全问题。
    start_line: sdk_script.log 起始行号(多轮 loop 中跳过前轮累积日志,只显示本轮新增)。
    """
    watch_files = watch_files or {}

    def _poll_once(mon_container, last_line: int, fh=None) -> int:
        """执行一次轮询:完整信息写文件,关键信息打印控制台,返回新的 last_line。"""
        # 构建统计赋值命令: sdk_script.log 行数 + proxy.log 大小 + watch_files 各文件大小
        assigns = [f"L=$(wc -l < {shlex.quote(sdk_log_path)} 2>/dev/null || echo 0)"]
        for i, wpath in enumerate(watch_files.values()):
            assigns.append(f"W{i}=$(stat -c %s {shlex.quote(wpath)} 2>/dev/null || echo -1)")
        assigns.append(f"P=$(stat -c %s /tmp/proxy.log 2>/dev/null || echo 0)")
        stat_keys = ["L", "P"] + [f"W{i}" for i in range(len(watch_files))]
        printf_fmt = "===STATS " + " ".join(f"{k}=%s" for k in stat_keys)
        printf_args = " ".join(f'"${k}"' for k in stat_keys)
        cmd = (
            f"{'; '.join(assigns)}; "
            f'printf "{printf_fmt}\\n" {printf_args}; '
            f'if [ "$L" -gt {last_line} ]; then '
            f"echo ===NEWLOG; "
            f"sed -n '{last_line + 1},$p' {shlex.quote(sdk_log_path)} 2>/dev/null; "
            f"echo ===ENDLOG; fi"
        )
        ec, out = mon_container.exec_run(["/bin/bash", "-c", cmd])
        if ec != 0:
            log.warning("[monitor] 轮询命令失败 exit=%s", ec)
            return last_line
        text = out.decode("utf-8", errors="replace") if out else ""

        cur_lines = last_line
        proxy_size = 0
        watch_sizes: Dict[str, int] = {name: -1 for name in watch_files}
        new_log_lines: list = []
        in_new = False
        for line in text.splitlines():
            if line.startswith("===STATS "):
                kv = {}
                for part in line.split()[1:]:
                    if "=" in part:
                        k, v = part.split("=", 1)
                        kv[k] = v
                try:
                    cur_lines = int(kv.get("L", last_line))
                    proxy_size = int(kv.get("P", 0))
                    for i, name in enumerate(watch_files):
                        watch_sizes[name] = int(kv.get(f"W{i}", -1))
                except ValueError:
                    pass
            elif line == "===NEWLOG":
                in_new = True
            elif line == "===ENDLOG":
                in_new = False
            elif in_new:
                new_log_lines.append(line)

        now = time.strftime("%Y-%m-%d %H:%M:%S")
        watch_str = " | ".join(
            f"{name}: {'已生成(%dB)' % sz if sz >= 0 else '无'}"
            for name, sz in watch_sizes.items()
        )
        stats_line = (
            f"sdk_log: {last_line}→{cur_lines} 行(+{cur_lines - last_line}) | "
            f"proxy: {proxy_size / 1048576:.2f}MB"
            + (f" | {watch_str}" if watch_str else "")
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
                fh.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] [STATS] "
                         f"===== 监控开始: {container_name} (起始行 {start_line}) =====\n")
            except Exception as e:
                log.warning("[monitor] 打开日志文件失败 %s: %s", log_file, e)

        last_line = start_line
        try:
            while not stop_event.is_set():
                if stop_event.wait(timeout=interval):
                    break
                try:
                    last_line = _poll_once(mon_container, last_line, fh)
                except docker.errors.NotFound:
                    log.error("[monitor] 容器已消失(可能 OOM 或被手动删除),监控退出")
                    if fh:
                        fh.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [STATS] "
                                 f"===== 容器消失,监控退出 =====\n")
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

    t = threading.Thread(target=_loop, daemon=True, name="loop-monitor")
    t.start()
    return t


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


def extract_session_id(trajs_path: Path) -> Optional[str]:
    """从 trajs.json 提取 ResultMessage.session_id。"""
    try:
        data = json.loads(trajs_path.read_text(encoding="utf-8"))
        return data.get("metadata", {}).get("ResultMessage", {}).get("session_id")
    except Exception as e:
        log.warning("提取 session_id 失败: %s", e)
        return None


def get_turn_error_info(trajs_path: Path) -> Dict[str, Any]:
    """提取 trajs.json 中 ResultMessage 的错误与产出信息。

    run_cc_sdk.py 在 API 错误时仍以 exit 0 退出并写出 trajs.json,
    仅在 metadata.ResultMessage.is_error 中标记,需显式检测。

    返回:
      is_error: bool — ResultMessage.is_error
      error_msg: str — 错误摘要(截断)
      output_tokens: int — 本轮模型产出 token 数(0 表示模型完全没工作)
    """
    empty = {"is_error": False, "error_msg": "", "output_tokens": -1}
    try:
        data = json.loads(trajs_path.read_text(encoding="utf-8"))
        metadata = data.get("metadata", {})
        rm = metadata.get("ResultMessage", {}) or {}
        usage = rm.get("usage") or {}
        out_tok = int(usage.get("output_tokens") or 0)
        return {
            "is_error": bool(rm.get("is_error")) or metadata.get("status") == "incomplete",
            "error_msg": str(metadata.get("error_log") or rm.get("result") or "")[:500],
            "output_tokens": out_tok,
        }
    except Exception:
        return empty


def flatten_eval_result(eval_path: Path) -> Optional[Dict[str, Any]]:
    """读取 eval_result.json 并将 reward 嵌套字段展平到顶层。

    eval_deep_swe.py 输出格式为 {"reward": {"reward": 0, "f2p_total": 6, ...}, ...},
    而 gen_review_hint.analyze_eval 期望顶层有 f2p_passed 等字段。
    展平后 reward 键变为数字(0/1),便于判断是否解决。
    """
    try:
        raw = json.loads(eval_path.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("读取 eval_result.json 失败: %s", e)
        return None
    reward_dict = raw.pop("reward", None) or {}
    flat = {**raw, **reward_dict}
    # 写回展平版本,供 gen_review_hint 和后续轮次使用
    eval_path.write_text(json.dumps(flat, ensure_ascii=False, indent=2), encoding="utf-8")
    return flat


def is_solved(eval_flat: Optional[Dict[str, Any]]) -> bool:
    if not eval_flat:
        return False
    return eval_flat.get("reward") == 1


# ==================== 主编排类 ====================
class MultiTurnLoopRunner:
    def __init__(self, args):
        self.args = args
        self.instance_id = args.instance_id
        self.run_name = args.run_name
        self.max_turns = args.max_turns
        self.parquet_file = args.parquet_file
        self.tasks_dir = Path(args.tasks_dir)
        self.config_path = args.config
        self.output_base = args.output_base

        # 输出目录
        self.run_dir = Path(self.output_base) / self.run_name
        self.infer_dir = self.run_dir / "infer_logs" / self.instance_id
        self.eval_dir = self.run_dir / "eval_output" / self.instance_id
        self.hints_dir = self.run_dir / "review_hints" / self.instance_id
        self.infer_dir.mkdir(parents=True, exist_ok=True)
        self.eval_dir.mkdir(parents=True, exist_ok=True)
        self.hints_dir.mkdir(parents=True, exist_ok=True)

        # 资源文件路径
        self.sdk_script_path = SCRIPT_DIR / "run_cc_sdk.py"
        self.logging_utils_path = SCRIPT_DIR / "logging_utils.py"
        self.litellm_callbacks_path = SCRIPT_DIR / "litellm_proxy" / "claude_code_proxy.py"
        self.streaming_fix_path = SCRIPT_DIR / "litellm_proxy" / "streaming_fix.py"

        self.docker_client = None
        self.container = None
        self.container_name = None

        self.base_commit: Optional[str] = None
        self.task_row: Optional[Dict[str, Any]] = None
        self.session_id: Optional[str] = None  # 当前(最新)会话 ID

        # 压缩 hint(以 system-reminder 形式 append 到 system prompt,turn 1 新会话生效)
        self.compact_hint_path = self._resolve_hint_path(args.hint_path)

        # 实时监控间隔(秒):exec_run 阻塞期间后台线程周期打印容器内日志增量;0=禁用
        self.monitor_interval = getattr(args, "monitor_interval", MONITOR_INTERVAL_SEC)

        # rounds_meta.json 记录
        self.rounds_meta: Dict[str, Any] = {"rounds": []}
        self.execution_status: Dict[str, Any] = {}

    def _resolve_hint_path(self, explicit: Optional[str]) -> Optional[Path]:
        """解析压缩 hint 路径:显式指定优先,否则自动查找约定路径。

        约定路径: {output_base}/{run_name}/hint_gen/{instance_id}/hint_compact.md
        """
        if explicit:
            p = Path(explicit)
            if p.is_file():
                log.info("使用指定 hint: %s", p)
                return p
            log.warning("hint_path 指定但文件不存在: %s,忽略", p)
            return None
        auto = Path(self.output_base) / self.run_name / "hint_gen" / self.instance_id / "hint_compact.md"
        if auto.is_file():
            log.info("自动发现 hint: %s", auto)
            return auto
        log.info("未找到压缩 hint(查找过 %s),turn 1 将不注入 system prompt append", auto)
        return None

    # ---------- 任务加载 ----------
    def load_task_row(self):
        df = pd.read_parquet(self.parquet_file)
        row = df[df["instance_id"] == self.instance_id]
        if row.empty:
            raise ValueError(f"parquet 中找不到 instance_id: {self.instance_id}")
        self.task_row = row.iloc[0].to_dict()
        self.base_commit = self.task_row.get(BASE_COMMIT) or self.task_row.get("base_commit")
        if not self.base_commit:
            raise ValueError("parquet 中缺少 base_commit")
        log.info("任务加载完成: %s (base_commit=%s)", self.instance_id, self.base_commit)

    # ---------- 容器管理 ----------
    def start_container(self):
        image_name = self.task_row.get(IMAGE_NAME) or self.task_row.get("image_name")
        if not image_name:
            raise ValueError("parquet 中缺少 image_name")
        image_base = image_name.split("/")[-1].split(":")[0]
        self.container_name = f"cc-{image_base}-{uuid.uuid4().hex[:8]}"
        self.docker_client = docker.from_env(timeout=DOCKER_CLIENT_TIMEOUT_SEC)
        log.info("启动容器 %s (镜像 %s)", self.container_name, image_name)
        resource_options = {"mem_limit": self.args.container_memory}
        if self.args.container_cpus is not None:
            resource_options["nano_cpus"] = int(self.args.container_cpus * 1_000_000_000)
        if os.getenv("HINT_EXPERIMENT_NAME"):
            resource_options["labels"] = {"hint.experiment_name": os.environ["HINT_EXPERIMENT_NAME"]}
        runtime_path = os.getenv("HINT_CODEX_RUNTIME")
        if runtime_path:
            resource_options["volumes"] = {
                runtime_path: {"bind": "/opt/python3.12-tmp", "mode": "ro"}}
            resource_options["environment"] = {
                "HINT_PREINSTALLED_RUNTIME": "1", "PYTHONDONTWRITEBYTECODE": "1"}
        self.container = self.docker_client.containers.run(
            image_name, name=self.container_name,
            entrypoint="", command="tail -f /dev/null",
            detach=True, privileged=True, **resource_options,
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
        problem_statement = self.task_row.get(PROBLEM_STATEMENT) or self.task_row.get("problem_statement", "")
        # ps.txt 存格式化后的完整 prompt(与 run_cc_trajs_swe_pro.py 一致)
        full_prompt = USER_PROMPT.replace("{{issue_description}}", problem_statement)
        api_base = self.args.api_base
        if self.args.experiment_session:
            session = urllib.parse.quote(self.args.experiment_session, safe="")
            api_base = f"{api_base.rstrip('/')}/sessions/{session}/student/solve/v1"
        proxy_config = render_proxy_config(
            provider=self.args.provider, model=self.args.model,
            api_key=self.args.api_key, api_base=api_base,
            callbacks_path="/tmp/litellm_call_backs.proxy_handler_instance",
            reasoning_effort=self.args.reasoning_effort,
            max_tokens=self.args.proxy_max_tokens,
        )
        files = {
            "/tmp/install.sh": (INSTALL_SCRIPT, 0o755),
            "/tmp/ps.txt": (full_prompt, 0o644),
            "/tmp/sdk_script.py": (self.sdk_script_path.read_bytes(), 0o755),
            "/tmp/logging_utils.py": (self.logging_utils_path.read_bytes(), 0o644),
            "/tmp/litellm_call_backs.py": (self.litellm_callbacks_path.read_bytes(), 0o644),
            "/tmp/streaming_fix.py": (self.streaming_fix_path.read_bytes(), 0o644),
            "/tmp/config.yaml": (proxy_config, 0o644),
        }
        # 可选注入: skills.tar.gz
        if self.args.skills_path and Path(self.args.skills_path).is_file():
            files["/tmp/skills.tar.gz"] = (Path(self.args.skills_path).read_bytes(), 0o644)
        # 可选注入: system_prompt.md
        if self.args.system_prompt_path and Path(self.args.system_prompt_path).is_file():
            files["/tmp/system_prompt.md"] = (Path(self.args.system_prompt_path).read_text(encoding="utf-8"), 0o644)
        # 可选注入: 压缩 hint(供 sdk_script 以 append 方式注入 system prompt)
        if self.compact_hint_path:
            files["/tmp/hint_compact.md"] = (self.compact_hint_path.read_text(encoding="utf-8"), 0o644)

        log.info("注入 %d 个文件到容器", len(files))
        for dest_path, (content, mode) in files.items():
            inject_file_to_container(self.container, content if isinstance(content, bytes) else str(content).encode("utf-8"), dest_path)
        # 解压 skills
        if self.args.skills_path and Path(self.args.skills_path).is_file():
            self.container.exec_run("bash -c 'mkdir -p /root/.claude/skills && tar -xzf /tmp/skills.tar.gz -C /root/.claude/skills'")

    # ---------- 安装与重置 ----------
    def install_and_reset(self, task_config):
        base_commit = self.base_commit
        run_env = {**(task_config.container_env if task_config else {}),
                   **(task_config.claude_env if task_config else {}),
                   # proxy 在 install.sh 中启动,须在启动时注入 clamp 变量
                   "PROXY_MAX_TOKENS_CLAMP": str(self.args.proxy_max_tokens)}

        # 1. 运行 install.sh(含 litellm proxy 启动)
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

        # 3. anticheat scrub
        git_scrub_command = self.task_row.get("git_scrub_command") or ""
        if git_scrub_command:
            log.info("执行 anticheat scrub")
            ec, out = self.container.exec_run(
                f"bash -c {shlex.quote(f'cd /app && {git_scrub_command} > /tmp/anticheat_scrub.log 2>&1 || true')}"
            )

        # 4. checkout base_commit
        log.info("checkout base_commit: %s", base_commit)
        ec, out = self.container.exec_run(
            f"bash -c {shlex.quote(f'cd /app && git checkout {base_commit}')}"
        )
        if ec != 0:
            log.error("checkout 失败:\n%s", out.decode("utf-8", errors="replace") if out else "")
            raise RuntimeError(f"git checkout {base_commit} 失败")

        # 5. installation_command
        installation_command = self.task_row.get(INSTALLATION_COMMAND) or self.task_row.get("installation_command") or ""
        if installation_command:
            log.info("执行 installation_command")
            inner_cmd = f"cd /app && timeout {INSTALL_TIMEOUT_SEC} bash -c {json.dumps(installation_command)}"
            ec, out = self.container.exec_run(
                f"bash -c {shlex.quote(inner_cmd)}",
                environment=run_env,
            )
            if ec != 0:
                log.warning("installation_command exit=%s", ec)

    # ---------- 执行一轮 ----------
    def execute_turn(self, turn: int, task_config, hint: Optional[str] = None) -> bool:
        """执行一轮 agent 任务。turn=1 为新会话,turn>1 为 resume 会话。"""
        run_env = {**(task_config.container_env if task_config else {}),
                   **(task_config.claude_env if task_config else {})}
        if self.args.experiment_session:
            run_env.update({
                "EXPERIMENT_SESSION": self.args.experiment_session,
                "EXPERIMENT_TASK": self.instance_id,
                "ANTHROPIC_MODEL": self.args.model,
                "ANTHROPIC_DEFAULT_OPUS_MODEL": self.args.model,
                "ANTHROPIC_DEFAULT_SONNET_MODEL": self.args.model,
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": self.args.model,
            })
        if self.args.teacher_progress_url:
            run_env["TEACHER_PROGRESS_URL"] = self.args.teacher_progress_url
        # 通过 append 机制将压缩 hint 注入 system prompt(新会话与 resume 均生效)
        if self.compact_hint_path:
            run_env["APPEND_SYSTEM_PROMPT_FILE"] = "/tmp/hint_compact.md"

        output_dir_in_container = f"/tmp/turn_{turn}"
        self.container.exec_run(f"mkdir -p {output_dir_in_container}")

        # 构造命令(与 run_cc_trajs_swe_pro.py 一致: bash -c 包裹, 长文本用 $(cat ...) 读取)
        cmd_parts = [
            "/opt/python3.12-tmp/bin/python3 /tmp/sdk_script.py",
            "--cwd /app",
            f"--base_commit {self.base_commit}",
            f"--log_path {SDK_SCRIPT_LOG_PATH}",
            f"--output_dir {output_dir_in_container}",
        ]
        if turn == 1:
            # ps.txt 在 inject_files 中已写入格式化后的完整 prompt
            cmd_parts.append('--problem_statement "$(cat /tmp/ps.txt)"')
            if self.args.first_init:
                cmd_parts.append("--init")
        else:
            # resume 模式: 注入 hint 文件,传 resume_session_id + extra_message
            hint_path = f"/tmp/hint_turn_{turn}.txt"
            inject_file_to_container(self.container, (hint or "").encode("utf-8"), hint_path)
            cmd_parts.append(f"--resume_session_id {self.session_id}")
            cmd_parts.append(f'--extra_message "$(cat {hint_path})"')
            log.info("Turn %d: resume 会话 %s", turn, self.session_id)

        cmd_str = " ".join(cmd_parts)
        log.info("Turn %d: 执行 sdk_script (timeout=%ds)", turn, TASK_TIMEOUT_SEC)

        result_holder = {}

        def _run():
            try:
                ec, out = self.container.exec_run(
                    f"/bin/bash -c '{cmd_str}'",
                    workdir="/app",
                    environment=run_env,
                )
                result_holder["exit_code"] = ec
                result_holder["output"] = out.decode("utf-8", errors="replace") if out else ""
            except Exception as e:
                result_holder["exit_code"] = -1
                result_holder["output"] = str(e)

        thread = threading.Thread(target=_run, daemon=True)
        started = time.monotonic()
        thread.start()

        # 启动实时监控线程(移植自 get_hint_by_task.py):
        # exec_run 阻塞期间后台线程周期打印容器内 sdk_script.log 增量,
        # 双通道输出:控制台摘要 + monitor.log 完整落盘
        monitor_stop = threading.Event()
        monitor_thread = None
        if self.monitor_interval > 0:
            # 获取 sdk_script.log 当前行数作为起始 offset
            # (多轮 loop 中 sdk_script.log 追加写入,跳过前轮累积日志只显示本轮新增)
            start_line = 0
            try:
                ec_s, out_s = self.container.exec_run(
                    f"wc -l < {SDK_SCRIPT_LOG_PATH} 2>/dev/null || echo 0")
                if ec_s == 0 and out_s:
                    start_line = int(out_s.decode("utf-8", errors="replace").strip() or 0)
            except Exception:
                pass
            monitor_log_path = self.infer_dir / "monitor.log"
            watch_files = {
                "trajs.json": f"/tmp/turn_{turn}/trajs.json",
                "patch.diff": f"/tmp/turn_{turn}/patch.diff",
            }
            log.info("Turn %d: 实时监控已启动(间隔 %ds,起始行 %d),完整日志: %s",
                     turn, self.monitor_interval, start_line, monitor_log_path)
            monitor_thread = _monitor_container(
                self.container.name, self.monitor_interval, monitor_stop,
                log_file=monitor_log_path,
                watch_files=watch_files,
                start_line=start_line,
            )
        else:
            log.info("Turn %d: 实时监控已禁用(monitor_interval=0)", turn)

        if self.args.experiment_session:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            while thread.is_alive():
                status = {"teacher_wait_seconds": 0.0, "stopped": False}
                if self.args.teacher_status_url:
                    query = urllib.parse.urlencode({"session": self.args.experiment_session})
                    try:
                        with opener.open(self.args.teacher_status_url + "?" + query,
                                         timeout=5) as response:
                            status = json.load(response)
                    except Exception as exc:
                        status = {"teacher_wait_seconds": 0.0, "stopped": True,
                                  "stop_reason": "teacher_status_error: " + str(exc)}
                wall_seconds = time.monotonic() - started
                teacher_wait = status["teacher_wait_seconds"]
                self.execution_status = {
                    "wall_seconds": wall_seconds,
                    "teacher_wait_seconds": teacher_wait,
                    "effective_seconds": wall_seconds - teacher_wait,
                }
                if status.get("stopped") or wall_seconds - teacher_wait >= TASK_TIMEOUT_SEC:
                    self.execution_status["stop_reason"] = (
                        status.get("stop_reason") or "student_timeout"
                    )
                    self.container.exec_run(
                        ["/bin/bash", "-c", "pkill -INT -f '^/opt/python3.12-tmp/bin/python3 /tmp/sdk_script.py' || true"]
                    )
                    thread.join(timeout=30)
                    break
                thread.join(timeout=1)
        else:
            thread.join(timeout=TASK_TIMEOUT_SEC + 120)

        # 通知监控线程退出(它会最后拉一次补齐剩余日志)
        monitor_stop.set()
        if monitor_thread:
            monitor_thread.join(timeout=15)

        if thread.is_alive() or self.execution_status.get("stop_reason"):
            log.error("Turn %d: 执行超时 (%ds)", turn, TASK_TIMEOUT_SEC)
            return False

        ec = result_holder.get("exit_code", -1)
        output = result_holder.get("output", "")
        if ec != 0:
            log.error("Turn %d: sdk_script exit=%s\n%s", turn, ec, output[-3000:])
            return False
        log.info("Turn %d: sdk_script 执行完成", turn)
        return True

    # ---------- 收集产物 ----------
    def collect_artifacts(self, turn: int):
        """从容器拷出本轮产物到顶层 infer_dir。

        - /tmp/turn_{turn}/ 下的 patch.diff / trajs.json(由 --output_dir 控制)
        - /tmp/ 下的 sdk_script.log / anticheat_*.log
        - proxy.log 在容器内 tail 截断后拷出(避免 1GB+ 全量拷贝)
        """
        turn_out = f"/tmp/turn_{turn}"
        # 核心产物
        for name in ["patch.diff", "trajs.json", "online_teacher_state.json", "online_teacher_events.json"]:
            copy_from_container(self.container, f"{turn_out}/{name}", self.infer_dir)
        # 日志类
        copy_from_container(self.container, SDK_SCRIPT_LOG_PATH, self.infer_dir)
        for p in [ANTICHEAT_BLOCKS_LOG_PATH, ANTICHEAT_FIREWALL_LOG_PATH, ANTICHEAT_SCRUB_LOG_PATH]:
            copy_from_container(self.container, p, self.infer_dir)
        # system prompt 日志(验证 hint 是否真正进入 system prompt)
        #   system_prompt_actual.json  — proxy 捕获的 API 请求中实际 system prompt
        #   system_prompt_config.json — sdk_script 启动前记录的 system prompt 配置
        copy_from_container(self.container, SYSTEM_PROMPT_ACTUAL_LOG_PATH, self.infer_dir)
        copy_from_container(self.container, SYSTEM_PROMPT_CONFIG_LOG_PATH, self.infer_dir)
        # 摘要日志:直接在 runner 日志中显示 hint 加载验证结果
        actual_sp = self.infer_dir / "system_prompt_actual.json"
        if actual_sp.is_file():
            try:
                rec = json.loads(actual_sp.read_text(encoding="utf-8"))
                has_reminder = rec.get("contains_system_reminder", False)
                n_chars = rec.get("char_count", 0)
                if has_reminder:
                    log.info("Turn %d: system prompt 验证通过 — hint 已加载 "
                             "(actual %d chars, contains <system-reminder>)", turn, n_chars)
                else:
                    log.warning("Turn %d: system prompt 中未检测到 <system-reminder> "
                                "(actual %d chars) — hint 可能未加载", turn, n_chars)
            except Exception as e:
                log.warning("Turn %d: 解析 system_prompt_actual.json 失败: %s", turn, e)
        else:
            log.warning("Turn %d: 未找到 system_prompt_actual.json "
                        "(proxy 可能未捕获到请求)", turn)
        # proxy.log 截断拷出
        self.container.exec_run("bash -c 'tail -c 1000000 /tmp/proxy.log > /tmp/proxy_tail.log 2>/dev/null || true'")
        copy_from_container(self.container, "/tmp/proxy_tail.log", self.infer_dir)
        proxy_dst = self.infer_dir / "proxy_tail.log"
        if proxy_dst.exists():
            proxy_dst.rename(self.infer_dir / "proxy.log")
        log.info("Turn %d: 产物已收集到 %s", turn, self.infer_dir)

    # ---------- 归档 ----------
    def archive_turn(self, turn: int):
        """将顶层 infer_dir 产物归档到 turn_{turn}/ 子目录,清空顶层供下一轮使用。"""
        turn_dir = self.infer_dir / f"turn_{turn}"
        turn_dir.mkdir(parents=True, exist_ok=True)
        names = ["patch.diff", "trajs.json", "sdk_script.log", "proxy.log",
                 "anticheat_blocks.log", "anticheat_firewall.log", "anticheat_scrub.log",
                 "system_prompt_actual.json", "system_prompt_config.json",
                 "monitor.log", "online_teacher_state.json", "online_teacher_events.json"]
        for name in names:
            src = self.infer_dir / name
            if src.exists():
                shutil.move(str(src), str(turn_dir / name))
        # eval 结果也复制一份到归档
        eval_src = self.eval_dir / "eval_result.json"
        if eval_src.exists():
            shutil.copy2(str(eval_src), str(turn_dir / "eval_result.json"))
        log.info("Turn %d: 产物已归档到 %s", turn, turn_dir)

    # ---------- 评测 ----------
    def run_eval(self) -> Optional[Dict[str, Any]]:
        """评测顶层 patch.diff,返回展平后的 eval 结果。"""
        task_dir = self.tasks_dir / self.instance_id
        if not task_dir.is_dir():
            log.error("任务目录不存在: %s", task_dir)
            return None
        patches_dir = self.run_dir / "infer_logs"
        log.info("评测中: patches_dir=%s", patches_dir)
        try:
            result = evaluate_task(
                task_dir=task_dir,
                task_id=self.instance_id,
                patches_dir=patches_dir,
                output_dir=self.eval_dir.parent,
                delete_image=True,
            )
        except Exception as e:
            log.exception("评测异常: %s", e)
            return None
        eval_path = self.eval_dir / "eval_result.json"
        if not eval_path.exists():
            log.error("评测完成但未生成 eval_result.json")
            return None
        return flatten_eval_result(eval_path)

    # ---------- 生成 hint ----------
    def _extract_model_summary_from_trajs(self, trajs_path: Path) -> str:
        """从 trajs.json 的 metadata.ResultMessage.result 提取模型最终总结。"""
        if not trajs_path.exists():
            return "(未找到 trajs.json)"
        try:
            data = json.loads(trajs_path.read_text(encoding="utf-8"))
            result = data.get("metadata", {}).get("ResultMessage", {}).get("result", "")
            if result and len(result.strip()) > 10:
                return result.strip()[:2000]
            return "(未找到有效总结)"
        except Exception as e:
            return f"(读取轨迹失败: {e})"

    def generate_hint(self, turn: int) -> str:
        """基于 turn_{turn}/ 归档产物 + eval 结果,调用 LLM 生成下一轮 hint。

        复用 gen_review_hint 的 analyze_patch / analyze_eval / call_llm / 模板。
        """
        grh = gen_review_hint
        turn_dir = self.infer_dir / f"turn_{turn}"
        problem_statement = (
            self.task_row.get(PROBLEM_STATEMENT)
            or self.task_row.get("problem_statement", "")
        )
        patch_summary = grh.analyze_patch(turn_dir / "patch.diff")
        eval_summary = grh.analyze_eval(self.eval_dir / "eval_result.json")
        model_summary = self._extract_model_summary_from_trajs(turn_dir / "trajs.json")

        # 构建前轮 hint 历史，让 reviewer 避免重复、逐轮聚焦
        prev_hints = []
        for r in self.rounds_meta.get("rounds", []):
            h = r.get("hint_used")
            if h:
                prev_hints.append(f"Your feedback after round {r['turn']}: {h}")
        previous_hints = "\n\n".join(prev_hints) if prev_hints else "No previous feedback."

        user_prompt = grh.USER_PROMPT_TEMPLATE.format(
            problem_statement=problem_statement,
            patch_summary=patch_summary,
            eval_summary=eval_summary,
            model_summary=model_summary,
            previous_hints=previous_hints,
        )
        log.info("调用 LLM (%s) 生成 hint (round %d) ...", self.args.model, turn)
        # litellm.completion 的 base_url 需带 /v1(proxy 配置用的 api_base 可不带)
        hint_api_base = self.args.api_base.rstrip("/")
        if not hint_api_base.endswith("/v1"):
            hint_api_base += "/v1"
        hint = grh.call_llm(
            grh.SYSTEM_PROMPT, user_prompt,
            hint_api_base, self.args.api_key, self.args.model, self.args.provider,
        )
        # 保存 hint 记录
        record = {
            "instance_id": self.instance_id,
            "round": turn,
            "hint": hint,
            "context": {
                "patch_summary": patch_summary,
                "eval_summary_lines": eval_summary.split("\n")[:5],
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        out_path = self.hints_dir / f"round_{turn}.json"
        out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("hint 已保存: %s", out_path)
        return hint

    # ---------- rounds_meta ----------
    def _save_rounds_meta(self):
        meta_path = self.infer_dir / "rounds_meta.json"
        meta_path.write_text(
            json.dumps(self.rounds_meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ---------- 主 loop ----------
    def run(self) -> int:
        log.info("=" * 60)
        log.info("多轮反馈 Loop 启动: %s (max_turns=%d)", self.instance_id, self.max_turns)
        log.info("输出目录: %s", self.run_dir)
        if self.compact_hint_path:
            log.info("压缩 hint: %s (将 append 到 system prompt)", self.compact_hint_path)
        else:
            log.info("压缩 hint: 无 (system prompt 使用默认 preset)")
        log.info("=" * 60)

        # 0. 加载任务
        self.load_task_row()

        # 1. 加载配置
        run_config = load_run_config(self.config_path)
        task_config = run_config.resolve_task()
        log.info("配置加载完成 (provider=%s, model=%s)",
                 self.args.provider, self.args.model)

        # 2. 启动容器
        self.start_container()

        solved = False
        self.current_hint: Optional[str] = None
        try:
            # 3. 注入文件 + 安装重置
            self.inject_files(task_config)
            self.install_and_reset(task_config)

            # 4. 多轮 loop
            for turn in range(1, self.max_turns + 1):
                log.info("")
                log.info("=" * 60)
                log.info("===== Turn %d / %d =====", turn, self.max_turns)
                log.info("=" * 60)

                hint = self.current_hint if turn > 1 else None
                exec_ok = self.execute_turn(turn, task_config, hint=hint)

                # 收集产物
                self.collect_artifacts(turn)

                # 提取 session_id(供下一轮 resume)
                trajs_path = self.infer_dir / "trajs.json"
                if trajs_path.exists():
                    sid = extract_session_id(trajs_path)
                    if sid:
                        self.session_id = sid
                        log.info("Turn %d: session_id=%s", turn, sid)

                # 检测 API 级错误与模型产出(如 proxy 未启动/上下文超限)
                err_info = get_turn_error_info(trajs_path) if trajs_path.exists() else {}
                api_error = err_info.get("is_error", False)
                output_tokens = err_info.get("output_tokens", -1)
                if api_error:
                    log.error("Turn %d: 检测到 API 错误: %s", turn, err_info.get("error_msg", ""))

                if not exec_ok:
                    log.warning("Turn %d: 执行未正常完成,仍尝试评测", turn)

                # API 错误且模型本轮无产出(output_tokens==0): resume 同一会话只会
                # 重复同样错误(如 ContextWindowExceeded),中止 loop 避免空转到 max_turns
                if (api_error and output_tokens == 0) or (
                    self.args.experiment_session and (api_error or not exec_ok)
                ):
                    err_msg = err_info.get("error_msg", "")
                    if self.execution_status.get("stop_reason"):
                        abort_reason = self.execution_status["stop_reason"]
                    elif not exec_ok:
                        abort_reason = "student_execution_error"
                    elif "ContextWindowExceeded" in err_msg:
                        abort_reason = "context_window_exceeded"
                        log.error("Turn %d: 上下文窗口超限,后续 resume 会同样失败,中止 loop", turn)
                        log.error("提示: 可尝试降低 --proxy_max_tokens 或减少 --max_turns")
                    else:
                        abort_reason = "api_error_no_output"
                        log.error("Turn %d: API 错误且模型无产出,中止多轮 loop 避免空转", turn)
                    self.rounds_meta["rounds"].append({
                        "turn": turn,
                        "session_id": self.session_id,
                        "exec_ok": exec_ok,
                        "api_error": api_error,
                        "error_msg": err_msg,
                        "reward": None,
                        "f2p_passed": None, "f2p_total": None,
                        "p2p_passed": None, "p2p_total": None,
                        "partial": None,
                        "hint_used": hint,
                        "execution": self.execution_status,
                    })
                    self.rounds_meta["solved"] = False
                    self.rounds_meta["aborted"] = abort_reason
                    self._save_rounds_meta()
                    self.archive_turn(turn)
                    break

                # 评测
                eval_flat = self.run_eval()
                reward = eval_flat.get("reward") if eval_flat else None
                f2p = f"{eval_flat.get('f2p_passed')}/{eval_flat.get('f2p_total')}" if eval_flat else "?"
                log.info("Turn %d: eval reward=%s, f2p=%s", turn, reward, f2p)

                # 记录 rounds_meta
                round_rec = {
                    "turn": turn,
                    "session_id": self.session_id,
                    "exec_ok": exec_ok,
                    "api_error": api_error,
                    "reward": reward,
                    "f2p_passed": eval_flat.get("f2p_passed") if eval_flat else None,
                    "f2p_total": eval_flat.get("f2p_total") if eval_flat else None,
                    "p2p_passed": eval_flat.get("p2p_passed") if eval_flat else None,
                    "p2p_total": eval_flat.get("p2p_total") if eval_flat else None,
                    "partial": eval_flat.get("partial") if eval_flat else None,
                    "hint_used": hint,
                    "execution": self.execution_status,
                }
                if api_error:
                    round_rec["error_msg"] = err_info.get("error_msg", "")
                self.rounds_meta["rounds"].append(round_rec)
                self.rounds_meta["solved"] = False
                self._save_rounds_meta()

                # 判断是否解决
                if is_solved(eval_flat):
                    solved = True
                    log.info("Turn %d: 题目已解决 (reward=1)!", turn)
                    self.archive_turn(turn)
                    break

                # 未解决:归档当前轮
                self.archive_turn(turn)

                # 生成下一轮 hint
                if turn < self.max_turns:
                    log.info("Turn %d: 未解决,生成 review hint ...", turn)
                    try:
                        self.current_hint = self.generate_hint(turn)
                        log.info("===== Hint (将用于 Turn %d) =====", turn + 1)
                        log.info("%s", self.current_hint[:800])
                        log.info("=" * 40)
                    except Exception as e:
                        log.error("生成 hint 失败: %s,使用默认 hint", e)
                        self.current_hint = (
                            "The acceptance tests still fail. Recheck how data flows from input "
                            "to the public interface, and verify that the intended code paths run."
                        )
                else:
                    log.info("Turn %d: 达到最大轮次,不再生成 hint", turn)

            # 最终状态
            self.rounds_meta["solved"] = solved
            self.rounds_meta["total_turns"] = len(self.rounds_meta["rounds"])
            self._save_rounds_meta()
            log.info("")
            log.info("=" * 60)
            if solved:
                log.info("Loop 完成: 题目已解决 (共 %d 轮)", len(self.rounds_meta["rounds"]))
            else:
                log.info("Loop 完成: %d 轮后仍未解决", self.max_turns)
            log.info("rounds_meta: %s", self.infer_dir / "rounds_meta.json")
            log.info("=" * 60)
        finally:
            # 5. 无论成功与否,删除容器
            log.info("清理容器 ...")
            self.stop_and_remove_container()

        return 0 if solved else 1


# ==================== CLI ====================
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="多轮反馈 Loop(单实例)")
    parser.add_argument("--instance_id", required=True, help="任务 ID")
    parser.add_argument("--run_name", required=True, help="实验名称")
    parser.add_argument("--parquet_file", default="deep_swe_tasks.parquet")
    parser.add_argument("--tasks_dir", default="/tmp/deep-swe-tasks/tasks")
    parser.add_argument("--config", required=True, help="run_config YAML 路径")
    parser.add_argument("--output_base", default="deepswe-output")
    parser.add_argument("--max_turns", type=int, default=1, help="最大轮次(默认 1,单轮模式;>1 开启多轮反馈 loop)")
    # 模型/proxy 参数(用于 render_proxy_config 与 hint 生成)
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--model", default="Qwen3.6-35B-A3B")
    parser.add_argument("--api_base", default="http://hubrouter.jd.com/v1")
    parser.add_argument("--api_key", default=os.environ.get("HUBROUTER_API_KEY", ""))
    parser.add_argument("--reasoning_effort", default=None)
    parser.add_argument("--experiment_session", default=None,
                        help="Session identifier for Codex bridge routing")
    parser.add_argument("--teacher_progress_url", default=None,
                        help="Local teacher progress endpoint; omitted disables online guidance")
    parser.add_argument("--teacher_status_url", default=os.getenv("TEACHER_STATUS_URL"),
                        help="Host-side teacher status endpoint for paused-time accounting")
    parser.add_argument("--container_cpus", type=float, default=None,
                        help="Container CPU count; omitted preserves the original Docker default")
    parser.add_argument("--container_memory", default=CONTAINER_MEM_LIMIT,
                        help="Container memory limit")
    parser.add_argument("--proxy_max_tokens", type=int, default=65536,
                        help="proxy 强制 clamp 的 max_tokens(多轮 resume 时 input 累积,"
                             "需压低 output 预留以防超出上下文窗口;默认 65536)")
    parser.add_argument("--first_init", action="store_true", help="Turn 1 先执行 /init")
    # 可选注入
    parser.add_argument("--skills_path", default=None, help="skills.tar.gz 路径")
    parser.add_argument("--system_prompt_path", default=None, help="system_prompt.md 路径")
    parser.add_argument("--hint_path", default=None,
                        help="压缩 hint(hint_compact.md)路径;未指定时自动查找 "
                             "{output_base}/{run_name}/hint_gen/{instance_id}/hint_compact.md")
    parser.add_argument("--monitor_interval", type=int, default=MONITOR_INTERVAL_SEC,
                        help="实时监控轮询间隔秒数:exec_run 阻塞期间后台线程周期打印"
                             "容器内 sdk_script.log 增量(0=禁用,默认 30)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runner = MultiTurnLoopRunner(args)
    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
