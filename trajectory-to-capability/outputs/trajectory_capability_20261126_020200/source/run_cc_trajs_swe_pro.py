import pandas as pd
import docker
import logging
import io
import tarfile
import os
import re
import signal
import time
import json
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
import random
import hashlib
import uuid
from typing import Dict, Any, Set, Tuple, Optional
from collections import OrderedDict
import shutil
import argparse
import threading
from skills_manager import SkillManager, load_swe_useful_skills
from utils import save_json, safe_to_list, LLMUtils, ImageGarbageCollector, shard_dataframe, ImagePrefetcher, ImagePullFailedError, safe_cmd, git_scrub_command, ANTICHEAT_SCRUB_LOG_PATH
from constant_zhy import INSTALL_SCRIPT, render_proxy_config, INSTANCE_ID, IMAGE_NAME, PROBLEM_STATEMENT, INTERFACE, INSTALLATION_COMMAND, BASE_COMMIT, TEST_PATCH, FAIL_TO_PASS, PASS_TO_PASS
from runtime_config import ResolvedTaskConfig, RunConfig, load_run_config  # pyright: ignore[reportMissingImports]
import tqdm
from logging_utils import setup_logging  # pyright: ignore[reportMissingImports]


# 环境变量读取的结果是字符串，超时时间需要转换为 int
TASK_TIMEOUT_SEC = int(os.getenv("TASK_TIMEOUT_SEC", "7200"))
INSTALL_TIMEOUT_SEC = int(os.getenv("INSTALL_TIMEOUT_SEC", "3600"))
DOCKER_CLIENT_TIMEOUT_SEC = int(
    os.getenv("DOCKER_CLIENT_TIMEOUT_SEC", str(max(TASK_TIMEOUT_SEC + 300, 600)))
)
CONTAINER_MEM_LIMIT = os.getenv("CONTAINER_MEM_LIMIT", "128g")
SDK_SCRIPT_LOG_PATH = "/tmp/sdk_script.log"
LITELLM_PROXY_LOG_PATH = "/tmp/proxy.log"
TRAJS_FILE_PATH = "/tmp/trajs.json"
PATCH_DIFF_PATH = "/tmp/patch.diff"
TEST_COMMANDS_DETAIL_PATH = "/tmp/test_commands_detail.jsonl"
LITELLM_REQUESTS_PATH = "/tmp/litellm_requests.jsonl"
ANTICHEAT_BLOCKS_LOG_PATH = "/tmp/anticheat_blocks.log"
ANTICHEAT_FIREWALL_LOG_PATH = "/tmp/anticheat_firewall.log"


prompt_file_path = os.getenv("USER_PROMPT_FILE_PATH", "prompts/user_prompt.md")
prompt_path = Path(prompt_file_path)
if prompt_path.is_absolute():
    USER_PROMPT_PATH = prompt_path
else:
    USER_PROMPT_PATH = Path(__file__).resolve().parent / prompt_path
# 检查路径是否存在且为文件，如果不存在则抛出异常
if not USER_PROMPT_PATH.is_file():
    raise FileNotFoundError(f"无法找到 Prompt 文件，请检查路径: {USER_PROMPT_PATH}")

USER_PROMPT = USER_PROMPT_PATH.read_text(encoding="utf-8")

# 系统 prompt：如果设置了 SYSTEM_PROMPT_FILE_PATH 则使用自定义 system prompt，否则为 None（使用 claude_code 默认）
system_prompt_file_path = os.getenv("SYSTEM_PROMPT_FILE_PATH")
SYSTEM_PROMPT_CONTENT: Optional[str] = None
if system_prompt_file_path:
    sp_path = Path(system_prompt_file_path)
    if not sp_path.is_absolute():
        sp_path = Path(__file__).resolve().parent / sp_path
    if not sp_path.is_file():
        raise FileNotFoundError(f"无法找到 System Prompt 文件，请检查路径: {sp_path}")
    SYSTEM_PROMPT_CONTENT = sp_path.read_text(encoding="utf-8")


@dataclass
class TaskRunResult:
    index: int
    instance_id: Optional[str]
    model_name: str
    image: Optional[str]
    patch: str = ""
    finished: bool = False
    validated: bool = False
    exit_code: Optional[int] = None
    output: str = ""
    attempt: int = 1
    use_init: bool = False
    status: Optional[str] = None
    resolved_config: Optional[Dict[str, Any]] = None

    def update(self, values: Dict[str, Any]) -> None:
        for key, value in values.items():
            setattr(self, key, value)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TaskContext:
    index: int
    row: Any
    instance_id: str
    image_name: str
    problem_statement: str
    install_bash_cmds: str
    base_commit: str
    test_patch: Any
    output_dir: Path
    should_validate: bool
    max_attempts: int
    start_attempt: int = 0


@dataclass
class RunnerResources:
    client: Any = None
    container: Any = None
    skip_final_container_cleanup: bool = False
    timeout_cleanup_action: str = "none"


@dataclass
class AttemptOutcome:
    action: str
    result: Optional[Dict[str, Any]] = None


class DockerTaskRunner:
    def __init__(self, output_base_path: Path, run_config: RunConfig, resource_paths: Dict[str, Path],
                 skill_pool: Dict[str, Path] = None, num_skills: int = 10,
                 max_validation_retries: int = 1, skill_strategy: str = "none",
                 force_remove_container: bool = False,
                 stop_container: bool = False,
                 remove_finished_images: bool = True,
                 enable_validation: bool = True,
                 image_prefetcher: Optional[ImagePrefetcher] = None):
        self.output_base_path = output_base_path
        self.run_config = run_config
        self.resource_paths = resource_paths
        self.skill_manager = SkillManager(
            skill_pool=skill_pool,
            num_skills=num_skills,
            strategy=skill_strategy,
        )
        self.max_validation_retries = max_validation_retries
        self.force_remove_container = force_remove_container
        self.stop_container = stop_container
        self.remove_finished_images = remove_finished_images
        self.enable_validation = enable_validation
        self.image_prefetcher = image_prefetcher
        self._container_start_lock = threading.Lock()
        self._sdk_script_content = self._read_text(resource_paths["sdk_script"])
        self._logging_utils_content = self._read_text(resource_paths["logging_utils"])
        self._litellm_callbacks_content = self._read_text(resource_paths["litellm_callbacks"])
        self._streaming_fix_content = self._read_text(resource_paths["streaming_fix"])
        self._system_prompt_content = SYSTEM_PROMPT_CONTENT

    @staticmethod
    def _build_run_container_env(task_config: ResolvedTaskConfig) -> Dict[str, str]:
        env = {**task_config.container_env, "TMP": "xx"}
        log_level = os.getenv("LOG_LEVEL")
        if log_level:
            env["LOG_LEVEL"] = log_level
        # Go module settings — sensible China-mirror defaults so
        # `GOTOOLCHAIN=auto` can fetch missing minor versions (Go 1.21+
        # refuses to fetch anything when GOSUMDB=off; proxy.golang.org
        # is often unreachable from the internal build hosts). Overridable
        # per host by exporting GOSUMDB= / GOPROXY= before launch.
        env.setdefault("GOSUMDB", os.getenv("GOSUMDB", "sum.golang.google.cn"))
        env.setdefault("GOPROXY", os.getenv("GOPROXY", "https://goproxy.cn,direct"))
        return env

    @staticmethod
    def _read_text(path: Path) -> str:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    @staticmethod
    def _create_tar_archive(files_dict: Dict[str, Tuple[Any, int]]) -> io.BytesIO:
        fileobj = io.BytesIO()
        with tarfile.open(fileobj=fileobj, mode='w') as tar:
            for filename, (content, mode) in files_dict.items():
                content_bytes = str(content or "").encode('utf-8') if isinstance(content, str) else content
                info = tarfile.TarInfo(name=filename)
                info.size = len(content_bytes)
                info.mtime = time.time()
                info.mode = mode
                tar.addfile(info, io.BytesIO(content_bytes))
        fileobj.seek(0)
        return fileobj

    @staticmethod
    def _copy_from_container(container, src_path: str, dest_dir: Path) -> bool:
        temp_tar = dest_dir / f"temp_extract_{Path(src_path).name}.tar"
        try:
            logging.info(
                "[%s] Copying artifact from container: %s -> %s",
                container.name,
                src_path,
                dest_dir,
            )
            DockerTaskRunner._write_event(
                dest_dir,
                "artifact_copy_start",
                container_id=container.id,
                container_name=container.name,
                src_path=src_path,
                dest_dir=str(dest_dir),
            )
            bits, stat = container.get_archive(src_path)
            with open(temp_tar, 'wb') as f:
                for chunk in bits:
                    f.write(chunk)
            with tarfile.open(temp_tar) as tar:
                tar.extractall(path=dest_dir)
            copied_file = dest_dir / Path(src_path).name
            copied_size = copied_file.stat().st_size if copied_file.exists() else None
            logging.info(
                "[%s] Copied artifact: %s size=%s archive_stat=%s",
                container.name,
                copied_file,
                copied_size,
                stat,
            )
            DockerTaskRunner._write_event(
                dest_dir,
                "artifact_copy_success",
                container_id=container.id,
                container_name=container.name,
                src_path=src_path,
                dest_path=str(copied_file),
                copied_size=copied_size,
                archive_stat=stat,
            )
            return True
        except Exception as e:
            logging.exception(
                "[%s] Failed to copy artifact from container: %s -> %s",
                getattr(container, "name", "unknown"),
                src_path,
                dest_dir,
            )
            DockerTaskRunner._write_event(
                dest_dir,
                "artifact_copy_failed",
                container_id=getattr(container, "id", None),
                container_name=getattr(container, "name", None),
                src_path=src_path,
                dest_dir=str(dest_dir),
                error=repr(e),
                error_type=type(e).__name__,
            )
            return False
        finally:
            try:
                if temp_tar.exists():
                    temp_tar.unlink()
            except Exception as e:
                logging.warning("Failed to remove temp artifact tar %s: %s", temp_tar, e)

    @staticmethod
    def _write_event(output_dir: Path, event: str, **fields: Any) -> None:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "epoch": time.time(),
            "pid": os.getpid(),
            "event": event,
            **fields,
        }
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            with open(output_dir / "runner_events.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            logging.warning("Failed to write runner event %s to %s: %s", event, output_dir, e)

    @staticmethod
    def _container_state(container) -> Dict[str, Any]:
        try:
            container.reload()
            state = container.attrs.get("State", {})
            return {
                "id": container.id,
                "name": container.name,
                "status": container.status,
                "running": state.get("Running"),
                "exit_code": state.get("ExitCode"),
                "oom_killed": state.get("OOMKilled"),
                "error": state.get("Error"),
                "started_at": state.get("StartedAt"),
                "finished_at": state.get("FinishedAt"),
            }
        except Exception as e:
            return {"error": repr(e), "error_type": type(e).__name__}

    def _start_container(self, image_name: str, container_env: Dict[str, str]):
        client = docker.from_env(timeout=DOCKER_CLIENT_TIMEOUT_SEC)

        base_name = image_name.split('/')[-1].replace(':', '_')
        container_name = f"cc-{base_name}-{uuid.uuid4().hex[:8]}"

        # Best-effort: remove any stale container with the same name (shouldn't
        # happen due to uuid suffix, but defensive against extremely unlucky
        # collisions or leftover containers from a previous abnormal exit).
        try:
            existing = client.containers.get(container_name)
            logging.warning(
                "Removing stale container with name=%s id=%s before run",
                container_name,
                existing.id,
            )
            existing.remove(force=True)
        except docker.errors.NotFound:
            pass
        except Exception as e:
            logging.warning(
                "Failed to inspect/remove stale container %s: %s", container_name, e
            )

        container = client.containers.run(
            image=image_name,
            name=container_name,
            entrypoint="",
            command="tail -f /dev/null",
            detach=True,
            mem_limit=CONTAINER_MEM_LIMIT,
            privileged=True,
            environment=container_env,
        )

        return client, container

    def _sample_skills_archive(self) -> Optional[bytes]:
        """Build the skill archive using the configured selection strategy."""
        return self.skill_manager.build_archive()

    def _inject_files(self, container, problem_statement: str, task_config: ResolvedTaskConfig):
        proxy_config = render_proxy_config(
            provider=task_config.execution_backend.provider,
            model=task_config.execution_backend.model,
            api_key=task_config.execution_backend.api_key,
            api_base=task_config.execution_backend.api_base,
            callbacks_path=task_config.proxy.callbacks_path,
            reasoning_effort=os.getenv("REASONING_EFFORT", ""),
        )
        skills_archive = self._sample_skills_archive()
        files = {
            "install.sh": (INSTALL_SCRIPT, 0o755),
            "ps.txt": (problem_statement, 0o644),
            "sdk_script.py": (self._sdk_script_content, 0o644),
            "logging_utils.py": (self._logging_utils_content, 0o644),
            "config.yaml": (proxy_config, 0o644),
            "litellm_call_backs.py": (self._litellm_callbacks_content, 0o644),
            "streaming_fix.py": (self._streaming_fix_content, 0o644),
        }
        if skills_archive is not None:
            files["skills.tar.gz"] = (skills_archive, 0o644)
        if self._system_prompt_content is not None:
            files["system_prompt.md"] = (self._system_prompt_content, 0o644)
        container.put_archive("/tmp", self._create_tar_archive(files))

    def _install_and_reset(
        self,
        container,
        base_commit: str,
        install_bash_cmds: str,
        run_env: Dict[str, str],
    ) -> Tuple[bool, str]:
        max_try_install_times = 3
        for i in range(max_try_install_times):
            exec_res = container.exec_run(
                f"timeout {INSTALL_TIMEOUT_SEC} bash /tmp/install.sh",
                workdir="/tmp",
                environment=run_env,
            )
            if exec_res.exit_code == 0:
                break
            elif i == max_try_install_times - 1:
                return False, exec_res.output.decode('utf-8', errors='replace')

        reset_res = container.exec_run(
            f"git reset --hard {base_commit}", workdir="/app", environment=run_env
        )
        if reset_res.exit_code != 0:
            return False, (
                f"git reset --hard {base_commit} failed (exit={reset_res.exit_code}): "
                + reset_res.output.decode('utf-8', errors='replace')
            )

        clean_res = container.exec_run("git clean -fd", workdir="/app", environment=run_env)
        if clean_res.exit_code != 0:
            return False, (
                f"git clean -fd failed (exit={clean_res.exit_code}): "
                + clean_res.output.decode('utf-8', errors='replace')
            )

        # Anti-cheat: strip anything in the local git repo that could point
        # the agent at the upstream fix commit -- remotes, remote-tracking
        # refs, tags, PR refs, reflog, and unreachable objects reachable by
        # SHA. Implementation lives in utils.git_scrub_command; it logs
        # progress and post-condition assertions to /tmp/anticheat_scrub.log.
        scrub_res = container.exec_run(
            ["/bin/bash", "-c", git_scrub_command(base_commit, work_dir="/app")],
            workdir="/app", environment=run_env,
        )
        if scrub_res.exit_code != 0:
            logging.warning(
                "anti-cheat scrub verification FAILED (exit=%s). "
                "Check anticheat_scrub.log. Output tail: %s",
                scrub_res.exit_code,
                (scrub_res.output or b"").decode("utf-8", errors="replace")[-500:],
            )

        if install_bash_cmds:
            install_res = container.exec_run(
                ["/bin/bash", "-c", install_bash_cmds], workdir="/app", environment=run_env
            )
            if install_res.exit_code != 0:
                return False, (
                    f"installation_command failed (exit={install_res.exit_code}): "
                    + install_res.output.decode('utf-8', errors='replace')
                )
        return True, ""

    def _cleanup_timeout_container(
        self,
        container,
        instance_id: str,
        output_dir: Optional[Path] = None,
    ) -> str:
        if self.force_remove_container or self.remove_finished_images:
            cleanup_action = "remove"
        elif self.stop_container:
            cleanup_action = "stop"
        else:
            # On timeout we always force-stop the container to release the
            # blocked exec_run thread, even if the global config asks to
            # retain finished containers. Retaining a runaway container makes
            # no sense and would leak threads/sockets at high concurrency.
            cleanup_action = "stop"

        try:
            if cleanup_action == "remove":
                container.remove(force=True)
                container_state = None
            else:
                container.stop()
                container_state = self._container_state(container)

            if output_dir is not None:
                self._write_event(
                    output_dir,
                    "execute_task_timeout_cleanup_done",
                    instance_id=instance_id,
                    cleanup_action=cleanup_action,
                    container=container_state,
                )
            return cleanup_action
        except Exception as e:
            logging.error(
                "[%s] Error during timeout cleanup (%s): %s",
                instance_id,
                cleanup_action,
                e,
            )
            if output_dir is not None:
                self._write_event(
                    output_dir,
                    "execute_task_timeout_cleanup_failed",
                    instance_id=instance_id,
                    cleanup_action=cleanup_action,
                    error=repr(e),
                    error_type=type(e).__name__,
                )
            return "failed"

    def _execute_task(self, container, instance_id: str, base_commit: str,
                      claude_env: Dict[str, str], use_init: bool = False,
                      output_dir: Optional[Path] = None) -> Tuple[str, str, int, str]:
        """Returns (status, output, exit_code, timeout_cleanup_action)."""
        if self._system_prompt_content is not None:
            claude_env = {**claude_env, "SYSTEM_PROMPT_FILE": "/tmp/system_prompt.md"}
        init_flag = "--init " if use_init else ""
        logging.info(f"[{instance_id}] use_init={use_init}")
        logging.info(f"[{instance_id}] SYSTEM_PROMPT_FILE in claude_env: {'SYSTEM_PROMPT_FILE' in claude_env}")
        start_cmd = (
            f'ls -la /tmp/system_prompt.md 2>&1; echo "SYSTEM_PROMPT_FILE=$SYSTEM_PROMPT_FILE"; '
            f'/opt/python3.12-tmp/bin/python3 /tmp/sdk_script.py '
            f'--cwd /app --base_commit {base_commit} {init_flag}'
            f'--log_path {SDK_SCRIPT_LOG_PATH} --output_dir /tmp '
            f'--problem_statement_file /tmp/ps.txt'
        )
        logging.info(f"[{instance_id}] Starting task execution...")
        if output_dir is not None:
            self._write_event(
                output_dir,
                "execute_task_start",
                instance_id=instance_id,
                timeout_sec=TASK_TIMEOUT_SEC,
                use_init=use_init,
                container=self._container_state(container),
                command=start_cmd,
            )

        # Use a plain Thread instead of ThreadPoolExecutor: on timeout we
        # force-stop the container which unblocks exec_run, and we then
        # join() the worker thread so no half-released docker socket lingers.
        result_holder: Dict[str, Any] = {}

        def _run_exec():
            try:
                result_holder["res"] = container.exec_run(
                    f"/bin/bash -c '{start_cmd}'",
                    workdir="/app",
                    environment=claude_env,
                )
            except Exception as exc:  # noqa: BLE001
                result_holder["err"] = exc

        worker = threading.Thread(
            target=_run_exec,
            name=f"exec-{instance_id}",
            daemon=True,
        )
        worker.start()
        worker.join(timeout=TASK_TIMEOUT_SEC)

        if worker.is_alive():
            logging.error(f"[{instance_id}] TIMEOUT after {TASK_TIMEOUT_SEC}s.")
            if output_dir is not None:
                self._write_event(
                    output_dir,
                    "execute_task_timeout",
                    instance_id=instance_id,
                    timeout_sec=TASK_TIMEOUT_SEC,
                    container=self._container_state(container),
                )
            timeout_cleanup_action = self._cleanup_timeout_container(
                container,
                instance_id,
                output_dir,
            )
            # Wait for the exec thread to actually unwind so its docker
            # socket / connection is released before we return.
            worker.join(timeout=30)
            if worker.is_alive():
                logging.warning(
                    "[%s] exec worker thread still alive 30s after container cleanup",
                    instance_id,
                )
                if output_dir is not None:
                    self._write_event(
                        output_dir,
                        "execute_task_worker_thread_leak",
                        instance_id=instance_id,
                        cleanup_action=timeout_cleanup_action,
                    )
            return "timeout", "TIMEOUT", -1, timeout_cleanup_action

        if "err" in result_holder:
            err = result_holder["err"]
            logging.exception(
                "[%s] Docker exec failed before artifact collection: %r",
                instance_id,
                err,
            )
            if output_dir is not None:
                self._write_event(
                    output_dir,
                    "execute_task_error",
                    instance_id=instance_id,
                    error=repr(err),
                    error_type=type(err).__name__,
                    container=self._container_state(container),
                )
            raise err

        exec_res = result_holder["res"]
        raw_output = exec_res.output or b""
        if isinstance(raw_output, bytes):
            output_size = len(raw_output)
            output = raw_output.decode('utf-8', errors='replace').strip()
        else:
            output = str(raw_output).strip()
            output_size = len(output.encode('utf-8', errors='replace'))
        exit_code = exec_res.exit_code
        status = "success" if exit_code == 0 else "execution_failed"
        logging.info(
            "[%s] Task execution returned: status=%s exit_code=%s output_bytes=%s",
            instance_id,
            status,
            exit_code,
            output_size,
        )
        if output_dir is not None:
            self._write_event(
                output_dir,
                "execute_task_returned",
                instance_id=instance_id,
                status=status,
                exit_code=exit_code,
                output_bytes=output_size,
                container=self._container_state(container),
            )
        return status, output, exit_code, "none"

    @staticmethod
    def _get_session_key(line: dict) -> str:
        msgs = line.get("Messages", [])
        for m in msgs:
            if m.get("role") == "user":
                raw = json.dumps(m, sort_keys=True, ensure_ascii=False)
                return hashlib.md5(raw.encode()).hexdigest()
        raw = json.dumps(msgs, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(raw.encode()).hexdigest()

    def _collect_artifacts(self, container, output_dir: Path) -> Tuple[str, str]:
        """Copy patch/litellm_requests from container, extract result from main agent traj.
        Returns (patch_content, result_message)."""
        self._write_event(
            output_dir,
            "collect_artifacts_start",
            container=self._container_state(container),
        )
        copy_results = {
            PATCH_DIFF_PATH: self._copy_from_container(container, PATCH_DIFF_PATH, output_dir),
            LITELLM_REQUESTS_PATH: self._copy_from_container(container, LITELLM_REQUESTS_PATH, output_dir),
            TRAJS_FILE_PATH: self._copy_from_container(container, TRAJS_FILE_PATH, output_dir),
            LITELLM_PROXY_LOG_PATH: self._copy_from_container(container, LITELLM_PROXY_LOG_PATH, output_dir),
            SDK_SCRIPT_LOG_PATH: self._copy_from_container(container, SDK_SCRIPT_LOG_PATH, output_dir),
            # Anti-cheat observability. These files may not exist (hook never
            # fired / iptables not available); _copy_from_container returns
            # False and logs, which is fine.
            ANTICHEAT_BLOCKS_LOG_PATH: self._copy_from_container(container, ANTICHEAT_BLOCKS_LOG_PATH, output_dir),
            ANTICHEAT_FIREWALL_LOG_PATH: self._copy_from_container(container, ANTICHEAT_FIREWALL_LOG_PATH, output_dir),
            ANTICHEAT_SCRUB_LOG_PATH: self._copy_from_container(container, ANTICHEAT_SCRUB_LOG_PATH, output_dir),
        }
        self._write_event(output_dir, "collect_artifacts_copied", copy_results=copy_results)

        patch_file = output_dir / "patch.diff"
        patch_content = patch_file.read_text(encoding='utf-8') if patch_file.exists() else ""

        result_msg = ""
        jsonl_file = output_dir / "litellm_requests.jsonl"
        if jsonl_file.exists():
            with open(jsonl_file, "r", encoding="utf-8") as f:
                lines = [json.loads(line) for line in f if line.strip()]

            if lines:
                groups: OrderedDict = OrderedDict()
                for i, line in enumerate(lines):
                    key = self._get_session_key(line)
                    if key not in groups:
                        groups[key] = []
                    groups[key].append(i)

                # 包含最后一行的会话为主 agent
                main_key = self._get_session_key(lines[-1])
                main_traj = lines[groups[main_key][-1]]

                # 提取出main agent最后一轮回复的content，用于判断是否finish
                try:
                    content = main_traj["Response"]["choices"][0]["message"]["content"]
                    if isinstance(content, list):
                        texts = [
                            b.get("text", "") for b in content
                            if isinstance(b, dict) and b.get("type") == "text"
                        ]
                        result_msg = " ".join(texts)
                    else:
                        result_msg = content or ""
                except (KeyError, IndexError, TypeError):
                    result_msg = ""

                # 保存提取的轨迹供后续使用
                sub_trajs = [
                    lines[indices[-1]]
                    for key, indices in groups.items()
                    if key != main_key
                ]
                extracted = {"main_agent": main_traj, "sub_agent": sub_trajs}
                with open(output_dir / "extracted_trajs.json", "w", encoding="utf-8") as f:
                    json.dump(extracted, f, ensure_ascii=False, indent=2)

        self._write_event(
            output_dir,
            "collect_artifacts_done",
            patch_size=len(patch_content),
            result_msg_size=len(result_msg),
            output_files={
                path.name: path.stat().st_size
                for path in output_dir.iterdir()
                if path.is_file()
            },
        )
        return patch_content, result_msg

    def _validate_patch(self, container, row: pd.Series, install_bash_cmds: str, run_env: Dict[str, str]) -> bool:
        instance_id = row.get(INSTANCE_ID)

        if install_bash_cmds:
            install_res = container.exec_run(["/bin/bash", "-c", install_bash_cmds], workdir="/app", environment=run_env)

            if install_res.exit_code != 0:
                logging.warning(
                        f"[{instance_id}] Failed to install at validate patch install_res: {install_res}"
                    )
                return False

        try:
            container.exec_run(f"rm -f {TEST_COMMANDS_DETAIL_PATH}")
        except:
            pass                                                                   
        test_results = []                                      

        f2ps = safe_to_list(row.get(FAIL_TO_PASS))
        for cmd in f2ps:
            res = container.exec_run(["/bin/bash", "-c", cmd], workdir="/app", environment=run_env)
            output = res.output.decode("utf-8", errors="replace") if res.output else ""
            test_results.append(json.dumps({
                "exit_code": res.exit_code,
                "output": output,
                "test_cmd": cmd,
                "test_cmd_type": "f2p",
            }, ensure_ascii=False))
            if res.exit_code != 0:
                self._write_test_results(container, test_results)
                return False

        p2ps = safe_to_list(row.get(PASS_TO_PASS))
        p2ps_sampled = random.sample(p2ps, min(50, len(p2ps)))
        for cmd in p2ps_sampled:
            res = container.exec_run(["/bin/bash", "-c", cmd], workdir="/app", environment=run_env)
            output = res.output.decode("utf-8", errors="replace") if res.output else ""
            test_results.append(json.dumps({
                "exit_code": res.exit_code,
                "output": output,
                "test_cmd": cmd,
                "test_cmd_type": "p2p",
            }, ensure_ascii=False))
            if res.exit_code != 0:
                self._write_test_results(container, test_results)
                return False
        
        self._write_test_results(container, test_results)
        return True
    

    @staticmethod
    def _write_test_results(container, test_results: list) -> None:
        content = "\n".join(test_results) + "\n"
        tar_buf = io.BytesIO()
        with tarfile.open(fileobj=tar_buf, mode="w") as tar:
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name="test_commands_detail.jsonl")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        tar_buf.seek(0)
        container.put_archive("/tmp", tar_buf)

    def _prepare_task_context(self, index: int, row: Dict) -> TaskContext:
        instance_id = row.get(INSTANCE_ID)
        image_name = safe_cmd(row.get(IMAGE_NAME))
        raw_ps = row.get(PROBLEM_STATEMENT)
        # Anti-cheat: `sanitize_problem_statement` used to redact upstream
        # URLs / PR#/SHA from the prompt. Once the SDK-tool / network / hook /
        # scrub layers were in place, sanitizing became redundant AND caused
        # false-positives on legitimate content (dependency URLs pinned to
        # a SHA, build/UUID hex strings in error logs). Keep the utils
        # helper for future need but no longer apply it by default.
        problem_statement = USER_PROMPT.replace("{{issue_description}}", raw_ps)
        install_bash_cmds = safe_cmd(row.get(INSTALLATION_COMMAND))
        base_commit = row.get(BASE_COMMIT)
        test_patch = row.get(TEST_PATCH)
        should_validate = self.enable_validation
        max_empty_patch_retries = 3
        max_attempts = max(max_empty_patch_retries, self.max_validation_retries) if should_validate else max_empty_patch_retries

        output_dir = self.output_base_path / "infer_logs" / instance_id
        start_attempt = 0
        prev_result_file = output_dir / "result.json"
        if should_validate and prev_result_file.exists():
            try:
                with open(prev_result_file, "r", encoding="utf-8") as f:
                    prev_data = json.load(f)
                if prev_data.get("finished") and not prev_data.get("validated"):
                    start_attempt = prev_data.get("attempt", 0)
                    logging.info(
                        f"[{instance_id}] Resuming from attempt {start_attempt + 1}/{max_attempts}"
                    )
            except Exception:
                start_attempt = 0
        if start_attempt == 0:
            if output_dir.exists():
                shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        self._write_event(
            output_dir,
            "task_start",
            instance_id=instance_id,
            index=index,
            image=image_name,
            pid=os.getpid(),
            max_attempts=max_attempts,
            should_validate=should_validate,
        )

        return TaskContext(
            index=index,
            row=row,
            instance_id=instance_id,
            image_name=image_name,
            problem_statement=problem_statement,
            install_bash_cmds=install_bash_cmds,
            base_commit=base_commit,
            test_patch=test_patch,
            output_dir=output_dir,
            should_validate=should_validate,
            max_attempts=max_attempts,
            start_attempt=start_attempt,
        )

    def _resolve_attempt_config(
        self,
        result: Optional[TaskRunResult] = None,
    ) -> Tuple[ResolvedTaskConfig, Dict[str, str]]:
        task_config = self.run_config.resolve_task()
        run_env = self._build_run_container_env(task_config)
        if result is not None:
            result.model_name = task_config.claude_env["ANTHROPIC_MODEL"]
            result.use_init = task_config.sdk.first_init
        return task_config, run_env

    def _wait_for_prefetched_image(self, context: TaskContext) -> None:
        if self.image_prefetcher is None:
            return
        logging.info(f"[{context.instance_id}] Waiting for prefetched image: {context.image_name}")
        self.image_prefetcher.wait_for(context.image_name)
        logging.info(f"[{context.instance_id}] Image ready: {context.image_name}")

    def _prepare_retry(
        self,
        context: TaskContext,
        attempt: int,
        resources: RunnerResources,
    ) -> None:
        failed_attempt = attempt
        attempt_dir = context.output_dir / f"attempt-{failed_attempt}"
        logging.info(
            f"[{context.instance_id}] Validation retry {attempt+1}/{context.max_attempts}: "
            f"removing container and re-executing from image..."
        )
        self._archive_attempt_outputs(context.output_dir, attempt_dir)

        if resources.container is not None:
            try:
                self._write_event(
                    attempt_dir,
                    "retry_collect_previous_artifacts_start",
                    instance_id=context.instance_id,
                    attempt=attempt + 1,
                    previous_attempt=failed_attempt,
                    container=self._container_state(resources.container),
                )
                self._collect_artifacts(resources.container, attempt_dir)
                self._write_event(
                    attempt_dir,
                    "retry_collect_previous_artifacts_done",
                    instance_id=context.instance_id,
                    attempt=attempt + 1,
                    previous_attempt=failed_attempt,
                )
            except Exception as e:
                logging.warning(
                    f"[{context.instance_id}] Failed to collect previous artifacts before retry "
                    f"{attempt+1}: {e}"
                )
                self._write_event(
                    attempt_dir,
                    "retry_collect_previous_artifacts_failed",
                    instance_id=context.instance_id,
                    attempt=attempt + 1,
                    previous_attempt=failed_attempt,
                    error=repr(e),
                    error_type=type(e).__name__,
                )

        if resources.container is not None:
            self._write_event(
                attempt_dir,
                "retry_container_remove_start",
                instance_id=context.instance_id,
                attempt=attempt + 1,
                container=self._container_state(resources.container),
            )
            try:
                resources.container.remove(force=True)
                self._write_event(
                    attempt_dir,
                    "retry_container_removed",
                    instance_id=context.instance_id,
                    attempt=attempt + 1,
                )
            except Exception as e:
                self._write_event(
                    attempt_dir,
                    "retry_container_remove_failed",
                    instance_id=context.instance_id,
                    attempt=attempt + 1,
                    error=repr(e),
                    error_type=type(e).__name__,
                )
                raise
            finally:
                resources.container = None

        if resources.client is not None:
            try:
                resources.client.close()
            except Exception:
                pass
            resources.client = None

    @staticmethod
    def _archive_attempt_outputs(output_dir: Path, attempt_dir: Path) -> None:
        if attempt_dir.exists():
            shutil.rmtree(attempt_dir)
        attempt_dir.mkdir(parents=True, exist_ok=True)

        for path in list(output_dir.iterdir()):
            if path == attempt_dir or path.name.startswith("attempt-"):
                continue
            shutil.move(str(path), str(attempt_dir / path.name))

    def _start_attempt(
        self,
        context: TaskContext,
        task_config: ResolvedTaskConfig,
        attempt: int,
        resources: RunnerResources,
    ) -> None:
        with self._container_start_lock:
            resources.client, resources.container = self._start_container(
                context.image_name,
                {**task_config.container_env, **task_config.claude_env},
            )
        logging.info(
            f"[{context.instance_id}] Started container id={resources.container.id} "
            f"name={resources.container.name} image={context.image_name} attempt={attempt+1}"
        )
        self._write_event(
            context.output_dir,
            "container_started",
            instance_id=context.instance_id,
            image=context.image_name,
            attempt=attempt + 1,
            container=self._container_state(resources.container),
        )
        self._inject_files(resources.container, context.problem_statement, task_config)
        self._write_event(context.output_dir, "files_injected", instance_id=context.instance_id, attempt=attempt + 1)
        save_json(context.output_dir, "resolved_task_config.json", task_config)
        self._write_event(context.output_dir, "resolved_config_saved", instance_id=context.instance_id, attempt=attempt + 1)

    def _run_attempt(
        self,
        context: TaskContext,
        result: TaskRunResult,
        task_config: ResolvedTaskConfig,
        run_env: Dict[str, str],
        attempt: int,
        resources: RunnerResources,
    ) -> AttemptOutcome:
        self._write_event(context.output_dir, "install_start", instance_id=context.instance_id, attempt=attempt + 1)
        ok, err_output = self._install_and_reset(
            resources.container,
            context.base_commit,
            context.install_bash_cmds,
            run_env,
        )
        self._write_event(
            context.output_dir,
            "install_done",
            instance_id=context.instance_id,
            attempt=attempt + 1,
            ok=ok,
            error_output_size=len(err_output or ""),
            container=self._container_state(resources.container),
        )
        if not ok:
            result.update({
                "status": "install_failed",
                "exit_code": -1,
                "output": err_output,
                "attempt": attempt + 1,
                "resolved_config": task_config.to_dict(),
            })
            save_json(context.output_dir, "result.json", result)
            self._write_event(context.output_dir, "task_return_install_failed", instance_id=context.instance_id, attempt=attempt + 1)
            return AttemptOutcome("continue")

        self._write_event(
            context.output_dir,
            "attempt_start",
            instance_id=context.instance_id,
            attempt=attempt + 1,
            container=self._container_state(resources.container),
        )
        status, exec_output, exit_code, resources.timeout_cleanup_action = self._execute_task(
            resources.container,
            context.instance_id,
            context.base_commit,
            task_config.claude_env,
            task_config.sdk.first_init,
            context.output_dir,
        )
        if status == "timeout":
            if resources.timeout_cleanup_action in {"remove", "stop"}:
                resources.skip_final_container_cleanup = True
                if resources.timeout_cleanup_action == "remove":
                    resources.container = None
            result.update({
                "status": "timeout",
                "output": exec_output,
                "attempt": attempt + 1,
                "resolved_config": task_config.to_dict(),
            })
            save_json(context.output_dir, "result.json", result)
            self._write_event(context.output_dir, "task_return_timeout", instance_id=context.instance_id, attempt=attempt + 1)
            return AttemptOutcome("continue")

        try:
            self._write_event(context.output_dir, "collect_artifacts_before_call", instance_id=context.instance_id, attempt=attempt + 1)
            patch_content, result_msg = self._collect_artifacts(resources.container, context.output_dir)
            logging.info(f"[{context.instance_id}] Collected artifacts: patch size={len(patch_content)}")
        except Exception as e:
            logging.warning(f"[{context.instance_id}] Failed to collect artifacts on attempt {attempt+1}: {e}")
            result.update({
                "status": status, "exit_code": exit_code,
                "output": exec_output, "attempt": attempt + 1,
            })
            self._write_event(
                context.output_dir,
                "collect_artifacts_exception",
                instance_id=context.instance_id,
                attempt=attempt + 1,
                error=repr(e),
                error_type=type(e).__name__,
            )
            return AttemptOutcome("continue")
        
        logging.warning(f"lisen.173:Debug: before is_text_a_summary result_msg={result_msg}")
        is_finished = LLMUtils.is_text_a_summary(text=result_msg, backend=task_config.verification_backend)
        logging.warning(f"lisen.173:Debug: after is_text_a_summary is_finished={is_finished}")

        is_validated = False
        if context.should_validate and is_finished and patch_content.strip():
            is_validated = self._validate_patch(resources.container, context.row, context.install_bash_cmds, run_env)
            self._copy_from_container(resources.container, TEST_COMMANDS_DETAIL_PATH, context.output_dir)
        
        result.update({
            "status": status,
            "exit_code": exit_code,
            "output": exec_output,
            "patch": patch_content,
            "finished": is_finished,
            "validated": is_validated,
            "attempt": attempt + 1,
            "resolved_config": task_config.to_dict(),
        })
        save_json(context.output_dir, "result.json", result)

        if is_validated:
            logging.info(f"[{context.instance_id}] Validated on attempt {attempt+1}/{context.max_attempts}.")
            return AttemptOutcome("break")

        if not context.should_validate:
            if not patch_content.strip():
                logging.warning(
                    f"[{context.instance_id}] Empty patch on attempt {attempt+1}/{context.max_attempts}, will retry."
                )
                return AttemptOutcome("continue")
            if not is_finished:
                logging.warning(
                    f"[{context.instance_id}] Not finished on attempt {attempt+1}/{context.max_attempts}, will retry."
                )
                return AttemptOutcome("continue")
            logging.info(f"[{context.instance_id}] Validation skipped by configuration.")
            return AttemptOutcome("break")

        logging.info(
            f"[{context.instance_id}] Not validated on attempt {attempt+1}/{context.max_attempts} "
            f"(finished={is_finished})."
        )
        return AttemptOutcome("continue")

    def _save_final_result(self, context: TaskContext, result: TaskRunResult) -> Dict[str, Any]:
        logging.info(
            f"[{context.instance_id}] Final: finished={result['finished']}, "
            f"validated={result['validated']}, attempts={result['attempt']}"
        )
        save_json(context.output_dir, "result.json", result)
        self._write_event(
            context.output_dir,
            "task_result_saved",
            instance_id=context.instance_id,
            status=result.status,
            finished=result.finished,
            validated=result.validated,
            attempt=result.attempt,
        )
        return result.to_dict()

    def _save_image_pull_failed(
        self,
        context: TaskContext,
        result: TaskRunResult,
        error: ImagePullFailedError,
    ) -> Dict[str, Any]:
        logging.error(
            f"[{context.instance_id}] Image pull failed for {context.image_name}: {error}"
        )
        result.update({
            "status": "image_pull_failed",
            "output": str(error),
        })
        try:
            save_json(context.output_dir, "result.json", result)
            self._write_event(
                context.output_dir,
                "task_image_pull_failed",
                instance_id=context.instance_id,
                image=context.image_name,
                error=repr(error),
                error_type=type(error).__name__,
            )
        except Exception:
            pass
        return result.to_dict()

    def _save_unexpected_error(
        self,
        context: TaskContext,
        result: TaskRunResult,
        error: Exception,
        resources: RunnerResources,
    ) -> Dict[str, Any]:
        logging.exception(f"[{context.instance_id}] Unexpected error: {error}")
        result.update({"status": "error", "output": str(error)})
        try:
            save_json(context.output_dir, "result.json", result)
            self._write_event(
                context.output_dir,
                "task_unexpected_error",
                instance_id=context.instance_id,
                error=repr(error),
                error_type=type(error).__name__,
                container=self._container_state(resources.container) if resources.container else None,
            )
        except Exception:
            pass
        return result.to_dict()

    def _cleanup_after_task(self, context: TaskContext, resources: RunnerResources) -> None:
        self._write_event(
            context.output_dir,
            "cleanup_start",
            instance_id=context.instance_id,
            force_remove_container=self.force_remove_container,
            stop_container=self.stop_container,
            remove_finished_images=self.remove_finished_images,
            skip_container_cleanup=resources.skip_final_container_cleanup,
            timeout_cleanup_action=resources.timeout_cleanup_action,
            container=self._container_state(resources.container) if resources.container else None,
        )
        if resources.skip_final_container_cleanup:
            self._write_event(
                context.output_dir,
                "cleanup_container_skipped",
                instance_id=context.instance_id,
                reason="already_cleaned_after_timeout",
                cleanup_action=resources.timeout_cleanup_action,
            )
        elif resources.container and (self.force_remove_container or self.remove_finished_images):
            try:
                resources.container.remove(force=True)
                resources.container = None
                self._write_event(context.output_dir, "container_removed", instance_id=context.instance_id)
            except Exception as e:
                logging.warning(f"[{context.instance_id}] Failed to remove container during cleanup: {e}")
                self._write_event(
                    context.output_dir,
                    "container_remove_failed",
                    instance_id=context.instance_id,
                    error=repr(e),
                    error_type=type(e).__name__,
                )
        elif resources.container and self.stop_container:
            try:
                resources.container.stop()
                self._write_event(
                    context.output_dir,
                    "container_stopped",
                    instance_id=context.instance_id,
                    container=self._container_state(resources.container),
                )
            except Exception as e:
                logging.warning(f"[{context.instance_id}] Failed to stop container during cleanup: {e}")
                self._write_event(
                    context.output_dir,
                    "container_stop_failed",
                    instance_id=context.instance_id,
                    error=repr(e),
                    error_type=type(e).__name__,
                )
        elif resources.container:
            try:
                resources.container.remove(force=True)
                resources.container = None
                self._write_event(context.output_dir, "container_removed_default", instance_id=context.instance_id)
            except Exception as e:
                logging.warning(f"[{context.instance_id}] Failed to remove container (default cleanup): {e}")
                self._write_event(
                    context.output_dir,
                    "container_remove_default_failed",
                    instance_id=context.instance_id,
                    error=repr(e),
                    error_type=type(e).__name__,
                )
        if self.remove_finished_images and context.image_name:
            try:
                ImageGarbageCollector.remove_image_if_unused(context.image_name)
            except Exception as e:
                logging.warning(f"[{context.instance_id}] Failed to remove image during cleanup: {e}")
        if resources.client:
            try:
                resources.client.close()
            except Exception:
                pass
        self._write_event(context.output_dir, "cleanup_done", instance_id=context.instance_id)

    def run(self, index: int, row: Dict) -> Dict[str, Any]:
        context = self._prepare_task_context(index, row)
        resources = RunnerResources()
        task_config, run_env = self._resolve_attempt_config()
        result = TaskRunResult(
            index=context.index,
            instance_id=context.instance_id,
            model_name=task_config.claude_env["ANTHROPIC_MODEL"],
            image=context.image_name,
            use_init=task_config.sdk.first_init,
        )
        try:
            self._wait_for_prefetched_image(context)

            for attempt in range(context.start_attempt, context.max_attempts):
                if attempt > 0:
                    self._prepare_retry(context, attempt, resources)
                    task_config, run_env = self._resolve_attempt_config(result)

                self._start_attempt(context, task_config, attempt, resources)
                outcome = self._run_attempt(context, result, task_config, run_env, attempt, resources)
                if outcome.action == "return":
                    return outcome.result
                if outcome.action == "break":
                    break

            return self._save_final_result(context, result)

        except ImagePullFailedError as e:
            return self._save_image_pull_failed(context, result, e)
        except Exception as e:
            return self._save_unexpected_error(context, result, e, resources)
        finally:
            self._cleanup_after_task(context, resources)


class BatchProcessor:
    def __init__(self, args):
        self.args = args
        self.output_path = Path(args.output_path)
        self.output_path.mkdir(parents=True, exist_ok=True)
        setup_logging(str(self.output_path / f"execution_volume_node{args.node_rank}.log"))
        resource_paths = {
            "sdk_script": Path(args.res_sdk_script),
            "logging_utils": Path(__file__).resolve().parent / "logging_utils.py",
            "litellm_callbacks": Path(args.res_litellm_callbacks),
            "streaming_fix": Path(args.res_litellm_callbacks).parent / "streaming_fix.py",
        }
        self.run_config = load_run_config(args.config)
        skill_pool = load_swe_useful_skills(args.swe_skills_jsonl)
        skills_enabled = bool(skill_pool) and args.skill_strategy != "none"
        prefetch_workers = max(1, args.prefetch_workers or args.max_workers)
        self.image_prefetcher = ImagePrefetcher(
            max_workers=prefetch_workers,
        )
        logging.info(
            f"Loaded {len(skill_pool)} swe_useful skills, strategy={args.skill_strategy}, "
            f"num_skills={args.num_skills}, enabled={skills_enabled}, "
            f"prefetch_workers={prefetch_workers}"
        )
        self.runner = DockerTaskRunner(
            self.output_path, self.run_config, resource_paths,
            skill_pool=skill_pool, num_skills=args.num_skills,
            max_validation_retries=args.max_validation_retries,
            skill_strategy=args.skill_strategy,
            force_remove_container=args.force_remove_container,
            stop_container=args.stop_container,
            remove_finished_images=args.remove_finished_images,
            enable_validation=args.enable_validation,
            image_prefetcher=self.image_prefetcher,
        )
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread = None

    def _write_heartbeat(self, status: str) -> None:
        heartbeat_path = self.output_path / f"runner_heartbeat_node{self.args.node_rank}.json"
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "epoch": time.time(),
            "pid": os.getpid(),
            "status": status,
            "node_rank": self.args.node_rank,
            "max_workers": self.args.max_workers,
            "active_threads": threading.active_count(),
        }
        try:
            with open(heartbeat_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            logging.warning("Failed to write runner heartbeat %s: %s", heartbeat_path, e)

    def _start_heartbeat(self) -> None:
        self._write_heartbeat("running")

        def loop():
            while not self._heartbeat_stop.wait(30):
                self._write_heartbeat("running")

        self._heartbeat_thread = threading.Thread(target=loop, name="runner-heartbeat", daemon=True)
        self._heartbeat_thread.start()

    def _stop_heartbeat(self) -> None:
        self._heartbeat_stop.set()
        self._write_heartbeat("stopped")

    def _prepare_output_dir(self):
        if self.args.selected_ids:
            target = self.output_path / "selected_instances"
            counter = 1
            while target.exists():
                target = self.output_path / f"selected_instances{counter}"
                counter += 1
            target.mkdir(parents=True)
            self.output_path = target
            self.runner.output_base_path = target
            setup_logging(str(target / f"execution_volume_node{self.args.node_rank}.log"))
            logging.info(f"Output directory adjusted to: {self.output_path}")
        else:
            self.output_path.mkdir(parents=True, exist_ok=True)

    def _load_completed(self, df: pd.DataFrame) -> Tuple[Dict[str, Any], Set[str]]:
        results = {}
        completed_ids = set()

        for instance_id in df[INSTANCE_ID]:
            log_dir = self.output_path / "infer_logs" / instance_id
            res_file = log_dir / "result.json"

            if res_file.exists():
                try:
                    with open(res_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    max_attempts = self.args.max_validation_retries
                    max_empty_patch_retries = 3
                    if data.get("validated"):
                        completed_ids.add(instance_id)
                        results[instance_id] = data
                    elif not data.get("patch", "").strip() and data.get("attempt", 1) < max_empty_patch_retries:      
                        pass  # empty patch, still has retries left 
                    elif data.get("finished") and (
                        not self.args.max_validation_retries
                        or data.get("attempt", 1) >= max_attempts
                    ):
                        completed_ids.add(instance_id)
                        results[instance_id] = data
                except Exception:
                    pass

        return results, completed_ids

    def run(self):
        node_rank = self.args.node_rank
        self._prepare_output_dir()
        self._start_heartbeat()
        try:
            logging.info("Runner process started: pid=%s node_rank=%s", os.getpid(), node_rank)
            logging.info(f"=== Distributed Mode: node_rank={node_rank}, world_size={self.args.world_size} ===")
            logging.info(f"Reading parquet: {self.args.parquet_file}")
            df = pd.read_parquet(self.args.parquet_file)

            if self.args.selected_ids:
                with open(self.args.selected_ids, 'r', encoding='utf-8') as f:
                    selected = set(json.load(f))
                df = df[df[INSTANCE_ID].isin(selected)]
                logging.info(f"Filtered to {len(df)} instances by selected_ids.")

            total_before_shard = len(df)
            df = shard_dataframe(df, self.args.world_size, node_rank)
            logging.info(
                f"Sharding: total={total_before_shard}, "
                f"this node (rank {node_rank}/{self.args.world_size}) gets {len(df)} instances."
            )

            if df.empty:
                logging.warning(f"Node {node_rank} has no instances to process. Exiting.")
                return

            final_output_file = self.output_path / f"outputs_node{node_rank}.jsonl"
            results, completed_ids = self._load_completed(df)
            logging.info(f"[Node {node_rank}] Found {len(completed_ids)} previously completed tasks.")

            current_df = df[~df[INSTANCE_ID].isin(completed_ids)]
            if current_df.empty:
                logging.info(f"[Node {node_rank}] All tasks completed.")
            else:
                # Prime prefetch in the exact order tasks will be submitted to
                # the ThreadPoolExecutor below (current_df.iterrows()), so
                # prefetch priority matches execution priority.
                submission_order_images = [
                    safe_cmd(row[IMAGE_NAME]) for _, row in current_df.iterrows()
                ]
                self.image_prefetcher.prime(submission_order_images, max_queued=self.args.max_workers * 2)
                logging.info(f"[Node {node_rank}] Processing {len(current_df)} tasks.")
                temp_output_file = self.output_path / f"outputs_node{node_rank}_running.jsonl"

                with open(temp_output_file, 'w', encoding='utf-8') as f_out:
                    for r in results.values():
                        f_out.write(json.dumps(r, ensure_ascii=False) + "\n")
                        f_out.flush()

                    with ThreadPoolExecutor(max_workers=self.args.max_workers) as executor:
                        future_to_idx = {
                            executor.submit(self.runner.run, idx, row): idx
                            for idx, row in current_df.iterrows()
                        }

                        desc = f"Node {node_rank}"
                        for future in tqdm.tqdm(as_completed(future_to_idx), total=len(current_df), desc=desc):
                            try:
                                res = future.result()
                                if not res:
                                    continue
                                results[res[INSTANCE_ID]] = res
                                f_out.write(json.dumps(res, ensure_ascii=False) + "\n")
                                f_out.flush()
                            except Exception as e:
                                logging.error(f"[Node {node_rank}] Error in batch loop: {e}")

            with open(final_output_file, 'w', encoding='utf-8') as f:
                for res in results.values():
                    f.write(json.dumps(res, ensure_ascii=False) + "\n")
            logging.info(f"[Node {node_rank}] Done. {len(results)} results saved to {final_output_file}")
        finally:
            self.image_prefetcher.close()
            self._stop_heartbeat()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Distributed Docker Volume Executor")

    parser.add_argument("--parquet_file", type=str,
        default="/public/data0/HOME/jdnlp1004/lamso/projects/JDClaudeCode/data/swe_bench_multilingual_test.parquet")
    parser.add_argument("--output_path", type=str,
        default="/public/data0/HOME/jdnlp1004/lamso/projects/JDClaudeCode/output/k2-1300b-sdk")
    parser.add_argument("--res_sdk_script", type=str,
        default="/public/data0/HOME/jdnlp1004/lamso/projects/JDClaudeCode/resources/run_sdk_in_container.py")
    parser.add_argument("--res_litellm_callbacks", type=str,
        default="/public/data0/HOME/jdnlp1004/lamso/projects/JDClaudeCode/resources/litellm_call_backs.py")
    parser.add_argument("--config", type=str,
        help="Path to unified runtime config file (JSON or YAML)")
    parser.add_argument("--swe_skills_jsonl", type=str,
        help="Optional path to swe_skills.jsonl; when omitted, no skills archive is built")
    parser.add_argument("--num_skills", type=int, default=10,
        help="Number of skills to select per task")
    parser.add_argument("--skill_strategy", type=str, default="none",
        choices=SkillManager.available_strategies(),
        help="Strategy used by SkillManager to choose task skills")
    parser.add_argument("--world_size", type=int, default=1,
        help="Total number of nodes (how many shards to split into)")
    parser.add_argument("--node_rank", type=int, default=0,
        help="Current node rank (0-indexed, range [0, world_size-1])")
    parser.add_argument("--max_workers", type=int, default=20)
    parser.add_argument("--prefetch_workers", type=int,
        help="Optional image prefetch concurrency; defaults to max_workers")
    parser.add_argument("--max_validation_retries", type=int, default=5,
        help="Per-task retries when validation fails (1=no retry)")
    parser.add_argument("--enable_validation", action="store_true", default=False,
        help="Enable patch validation after task execution; disabled by default")
    parser.add_argument("--selected_ids", type=str,
        help="Path to JSON file with selected instance IDs, List Type")
    parser.add_argument("--force_remove_container", action="store_true", default=False,
        help="Force remove container after task execution; if not set, container is kept")
    parser.add_argument("--stop_container", action="store_true", default=False,
        help="Stop the task container after execution without removing it; ignored if the container is removed")
    parser.add_argument(
        "--remove_finished_images",
        dest="remove_finished_images",
        action="store_true",
        help="Remove finished task images after cleanup; this also removes the task container before image deletion",
    )
    parser.set_defaults(remove_finished_images=False)

    args = parser.parse_args()
    processor = BatchProcessor(args)

    def _handle_runner_signal(signum, frame):
        logging.error("Runner received signal: %s", signum)
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, _handle_runner_signal)
    signal.signal(signal.SIGINT, _handle_runner_signal)
    processor.run()

