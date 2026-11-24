#!/usr/bin/env python3
"""Small configuration/preflight wrapper; delegates all experiment logic to cc-run."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

PACKAGE = Path(__file__).resolve().parents[1]
ENTRY = PACKAGE / "source/benchmark/deepswe/run_loop_by_hint.py"
MODULES = ("docker", "pandas", "numpy", "yaml", "litellm", "anyio",
           "claude_agent_sdk", "tqdm", "pyarrow")
FIELDS = {"mode", "instance_id", "run_name", "model_name", "api_base", "api_key_env",
          "parquet_file", "tasks_dir", "output_base", "golden_diff_file", "max_rounds",
          "task_timeout", "hint_task_timeout", "monitor_interval", "mem_limit",
          "proxy_max_tokens", "http_proxy", "no_proxy"}


def package_path(value: str) -> Path:
    path = Path(os.path.expandvars(os.path.expanduser(value)))
    return path.resolve() if path.is_absolute() else (PACKAGE / path).resolve()


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Hint 实验交接包运行入口；不改变上游实验算法")
    p.add_argument("--config", default=str(PACKAGE / "config/run.local.json"))
    p.add_argument("--mode", choices=("hint", "baseline"))
    p.add_argument("--instance-id")
    p.add_argument("--run-name")
    p.add_argument("--output-base")
    p.add_argument("--max-rounds", type=int)
    p.add_argument("--dry-run", action="store_true", help="打印完整链路，不读数据、不启动 Docker、不调用模型")
    p.add_argument("--preflight-only", action="store_true", help="检查本机依赖、任务数据、模型配置和 Docker 后退出")
    p.add_argument("--continue", dest="continue_run", action="store_true", help="复用已有轮次继续外层循环")
    p.add_argument("--skip-hint-gen", action="store_true", help="复用已有完整 Hint")
    return p


def validate(cfg: dict) -> None:
    unknown = set(cfg) - FIELDS
    if unknown:
        raise ValueError("未知配置字段：" + ", ".join(sorted(unknown)))
    if cfg["mode"] not in ("hint", "baseline"):
        raise ValueError("mode 应为 hint 或 baseline")
    for field in ("instance_id", "run_name"):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", cfg[field]) or cfg[field] in (".", ".."):
            raise ValueError(field + " 仅支持字母、数字、下划线、点和连字符")
    for field in ("max_rounds", "task_timeout", "hint_task_timeout", "proxy_max_tokens"):
        if type(cfg[field]) is not int or cfg[field] < 1:
            raise ValueError(field + " 应为正整数")
    if type(cfg["monitor_interval"]) is not int or cfg["monitor_interval"] < 0:
        raise ValueError("monitor_interval 应为非负整数")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", cfg["api_key_env"]):
        raise ValueError("api_key_env 应为环境变量名")
    if not re.fullmatch(r"\d+(?:\.\d+)?[bkmgBKMG]?", cfg["mem_limit"]):
        raise ValueError("mem_limit 示例：32g、128g")


def preflight(cfg: dict, args: argparse.Namespace, paths: dict, key: str) -> None:
    if sys.version_info < (3, 12):
        raise ValueError("建议并要求本入口使用 Python 3.12 或更新版本；容器内仍由上游脚本安装 Python 3.12")
    if not cfg["model_name"] or cfg["model_name"].startswith("REPLACE_"):
        raise ValueError("请在 config/run.local.json 中填写可用的 model_name")
    if not cfg["api_base"].startswith(("http://", "https://")):
        raise ValueError("api_base 必须是 HTTP(S) 模型服务地址")
    if not key:
        raise ValueError("请设置环境变量 " + cfg["api_key_env"])
    if not ENTRY.is_file():
        raise ValueError("缺少上游实验入口")
    missing = [m for m in MODULES if importlib.util.find_spec(m) is None]
    if missing:
        raise ValueError("缺少 Python 依赖：" + ", ".join(missing) + "；请 pip install -r requirements.txt")
    for cmd in ("bash", "docker"):
        if shutil.which(cmd) is None:
            raise ValueError("找不到命令：" + cmd)
    if not paths["parquet_file"].is_file():
        raise ValueError("Parquet 不存在：" + str(paths["parquet_file"]))
    if not paths["tasks_dir"].is_dir():
        raise ValueError("tasks_dir 不存在：" + str(paths["tasks_dir"]))

    import pandas as pd
    df = pd.read_parquet(paths["parquet_file"])
    required = {"instance_id", "problem_statement", "base_commit", "image_name"}
    if required - set(df.columns):
        raise ValueError("Parquet 缺少列：" + ", ".join(sorted(required - set(df.columns))))
    if df["instance_id"].duplicated().any():
        raise ValueError("Parquet 的 instance_id 有重复，请先整理数据")
    selected = df if cfg["instance_id"] == "all" else df[df["instance_id"] == cfg["instance_id"]]
    if selected.empty:
        raise ValueError("Parquet 找不到任务：" + cfg["instance_id"])
    for row in selected.to_dict(orient="records"):
        iid = row["instance_id"]
        if not isinstance(iid, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", iid) or iid in (".", ".."):
            raise ValueError("Parquet 含不支持的 instance_id")
        for field in ("problem_statement", "base_commit", "image_name"):
            if not isinstance(row[field], str) or not row[field].strip():
                raise ValueError(iid + " 缺少有效的 " + field)
        task = paths["tasks_dir"] / iid
        for rel in ("task.toml", "tests/Dockerfile", "tests/test.sh"):
            if not (task / rel).is_file():
                raise ValueError("任务文件不存在：" + str(task / rel))
        if cfg["mode"] == "hint":
            generated = paths["output_base"] / cfg["run_name"] / "hint_gen" / iid
            if args.skip_hint_gen:
                for rel in ("hint_output.md", "golden_diff.diff"):
                    if not (generated / rel).is_file():
                        raise ValueError("跳过生成需要已有文件：" + str(generated / rel))
            else:
                explicit = paths.get("golden_diff_file") if cfg["instance_id"] != "all" else None
                patch = row.get("patch")
                if not ((explicit and explicit.is_file()) or
                        (task / "solution/solution.patch").is_file() or
                        (isinstance(patch, str) and patch.strip())):
                    raise ValueError(iid + " 缺少 Golden Diff")
    checked = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"],
                             capture_output=True, text=True, timeout=30)
    if checked.returncode:
        raise ValueError("无法连接 Docker daemon；请检查 Docker 服务与当前用户权限")
    print(f"预检通过：{len(selected)} 道题，Python {sys.version.split()[0]}，Docker {checked.stdout.strip()}")
    print("预检检查本地配置与数据；镜像可拉取、端点可用和测试能运行，需实际实验验证。")


def main() -> int:
    args = parser().parse_args()
    try:
        template = json.loads((PACKAGE / "config/run.example.json").read_text(encoding="utf-8"))
        config = Path(args.config).expanduser().resolve()
        if config.is_file():
            local = json.loads(config.read_text(encoding="utf-8"))
            if not isinstance(local, dict):
                raise ValueError("配置应为 JSON 对象")
            cfg = {**template, **local}
        elif args.dry_run:
            cfg = template
        else:
            raise ValueError("本地配置不存在，请复制 config/run.example.json 为 config/run.local.json")
        for field, value in (("mode", args.mode), ("instance_id", args.instance_id),
                             ("run_name", args.run_name), ("output_base", args.output_base),
                             ("max_rounds", args.max_rounds)):
            if value is not None:
                cfg[field] = value
        validate(cfg)
        if args.dry_run and cfg["instance_id"] == "all":
            raise ValueError("dry-run 请指定具体任务 ID；all 模式需要读取外部 Parquet")
        paths = {field: package_path(cfg[field]) for field in
                 ("parquet_file", "tasks_dir", "output_base")}
        if cfg["golden_diff_file"]:
            paths["golden_diff_file"] = package_path(cfg["golden_diff_file"])
        key = "DRY_RUN_NO_CREDENTIAL" if args.dry_run else os.environ.get(cfg["api_key_env"], "")
        if not args.dry_run:
            preflight(cfg, args, paths, key)
        if args.preflight_only:
            return 0
        env = dict(os.environ)
        env.update({"HUBROUTER_API_KEY": key, "API_KEY": key,
                    "PYTHON_BIN": sys.executable, "SKIP_DOCKER_LOGIN": "true",
                    "HTTP_PROXY": cfg["http_proxy"], "HTTPS_PROXY": cfg["http_proxy"],
                    "NO_PROXY": cfg["no_proxy"], "http_proxy": cfg["http_proxy"],
                    "https_proxy": cfg["http_proxy"], "no_proxy": cfg["no_proxy"]})
        cmd = [sys.executable, str(ENTRY), "--instance_id", cfg["instance_id"],
               "--run_name", cfg["run_name"], "--model_name", cfg["model_name"],
               "--api_base", cfg["api_base"], "--api_key", key,
               "--python_bin", sys.executable, "--skip_docker_login"]
        for field in ("parquet_file", "tasks_dir", "output_base"):
            cmd += ["--" + field, str(paths[field])]
        for field in ("max_rounds", "task_timeout", "hint_task_timeout", "monitor_interval",
                      "mem_limit", "proxy_max_tokens"):
            cmd += ["--" + field, str(cfg[field])]
        if "golden_diff_file" in paths:
            cmd += ["--golden_diff_file", str(paths["golden_diff_file"])]
        if cfg["mode"] == "baseline":
            cmd.append("--no_hint_run")
        if args.dry_run:
            cmd.append("--dry_run")
        if args.continue_run:
            cmd.append("--continue")
        if args.skip_hint_gen:
            cmd.append("--skip_hint_gen")
        print(f"模式={cfg['mode']} 任务={cfg['instance_id']} 实验={cfg['run_name']}", flush=True)
        result = subprocess.run(cmd, env=env, cwd=PACKAGE / "source", check=False)
        if args.dry_run:
            if result.returncode in (0, 1):
                print("dry-run 完成；只生成链路日志，不代表任务通过。", flush=True)
                return 0
            print(f"dry-run 出错：退出码 {result.returncode}。", file=sys.stderr)
        elif result.returncode == 0:
            print("实验结束：测试通过。")
        elif result.returncode == 1:
            print("实验结束：未解出；这是正常评测结果。")
        else:
            print(f"实验中断：退出码 {result.returncode}，请检查步骤日志。", file=sys.stderr)
        return result.returncode
    except (ValueError, KeyError, OSError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print("配置/预检错误：" + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
