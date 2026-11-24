#!/usr/bin/env python3
"""Offline syntax, dependency, document and manifest checks; no model/Docker calls."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

PACKAGE = Path(__file__).resolve().parents[1]
EXTERNAL = {"anyio", "claude_agent_sdk", "docker", "litellm", "numpy", "pandas",
            "tomli", "tqdm", "yaml"}
REQUIRED = ["benchmark/deepswe/run_loop_by_hint.py", "benchmark/deepswe/run_one_hint.sh",
            "benchmark/deepswe/get_hint_by_task.py", "benchmark/deepswe/compress_hint.py",
            "benchmark/deepswe/run_one_loop.sh", "benchmark/deepswe/review_hint_traj.py",
            "benchmark/deepswe/eval_deep_swe.py", "benchmark/deepswe/gen_review_hint.py",
            "run_multi_turn_loop.py", "run_cc_sdk.py", "run_cc_trajs_swe_pro.py",
            "anticheat.py", "constant_zhy.py", "logging_utils.py", "runtime_config.py",
            "skills_manager.py", "utils.py", "update_trajs.py",
            "litellm_proxy/claude_code_proxy.py", "litellm_proxy/streaming_fix.py",
            "benchmark/deepswe/prompts/deep_swe_user_prompt.md", "prompts/user_prompt.md"]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prose(markdown: str) -> str:
    lines, fence = [], None
    for line in markdown.splitlines():
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            mark = match[1]
            if fence is None:
                fence = mark
            elif mark[0] == fence[0] and len(mark) >= len(fence):
                fence = None
            continue
        if fence is None:
            lines.append(line)
    if fence:
        raise ValueError("未闭合的 Markdown 代码块")
    return "\n".join(lines)


def main() -> int:
    failures = []
    pyfiles = list((PACKAGE / "source").rglob("*.py")) + list((PACKAGE / "scripts").glob("*.py"))
    imports = set()
    for path in pyfiles:
        try:
            text = path.read_text(encoding="utf-8")
            compile(text, str(path), "exec")
            if PACKAGE / "source" in path.parents:
                for node in ast.walk(ast.parse(text)):
                    if isinstance(node, ast.Import):
                        imports.update(alias.name.split(".")[0] for alias in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                        imports.add(node.module.split(".")[0])
        except (SyntaxError, UnicodeError) as exc:
            failures.append(f"Python 语法：{path.relative_to(PACKAGE)} {exc}")
    local = {p.stem for p in (PACKAGE / "source").rglob("*.py")} | {"litellm_proxy"}
    missing_imports = imports - local - set(sys.stdlib_module_names) - EXTERNAL
    if missing_imports:
        failures.append("未声明/缺失的 import：" + ", ".join(sorted(missing_imports)))
    shfiles = list((PACKAGE / "source").rglob("*.sh"))
    for path in shfiles:
        result = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
        if result.returncode:
            failures.append("Shell 语法：" + str(path.relative_to(PACKAGE)))
    for name in REQUIRED:
        if not (PACKAGE / "source" / name).is_file():
            failures.append("缺少实验依赖文件：source/" + name)

    link_count = 0
    mdfiles = list(PACKAGE.rglob("*.md"))
    for path in mdfiles:
        try:
            visible = prose(path.read_text(encoding="utf-8"))
            for match in re.finditer(r"!?\[[^\]\n]*\]\(([^\n]+?)\)", visible):
                value = match[1].strip()
                if value.startswith("<"):
                    value = value[1:value.index(">")]
                elif ' "' in value:
                    value = value.split(' "', 1)[0]
                if urlsplit(value).scheme or value.startswith("#"):
                    continue
                value = unquote(value.split("#", 1)[0])
                target = (path.parent / value).resolve()
                if not target.is_relative_to(PACKAGE):
                    failures.append(f"链接越出包目录：{path.relative_to(PACKAGE)}")
                elif not target.exists():
                    failures.append(f"本地链接缺文件：{path.relative_to(PACKAGE)} → {value}")
                link_count += 1
        except ValueError as exc:
            failures.append(f"Markdown：{path.relative_to(PACKAGE)} {exc}")

    for path in PACKAGE.rglob("*.png"):
        if path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            failures.append("PNG 格式无效：" + str(path.relative_to(PACKAGE)))
    for path in PACKAGE.rglob("*.svg"):
        try:
            ET.fromstring(path.read_text())
        except ET.ParseError:
            failures.append("SVG 格式无效：" + str(path.relative_to(PACKAGE)))
    for path in PACKAGE.rglob("*"):
        if path.name in (".git", "__pycache__", "run.local.json", ".env"):
            failures.append("打包目录含本地/中间文件：" + str(path.relative_to(PACKAGE)))
        if path.is_file() and path.suffix in (".py", ".sh", ".md", ".json", ".yaml", ".yml"):
            text = path.read_text(encoding="utf-8")
            if re.search(r"sk-[A-Za-z0-9_-]{8,}", text):
                failures.append("存在疑似硬编码 Key：" + str(path.relative_to(PACKAGE)))
            if re.search(r"^\s*docker login .*?(?: -p | --password )", text, re.M):
                failures.append("存在 registry 明文登录：" + str(path.relative_to(PACKAGE)))
    provenance = json.loads((PACKAGE / "SOURCE_MANIFEST.json").read_text())
    for record in provenance["source_files"]:
        path = PACKAGE / record["path"]
        if not path.is_file() or digest(path) != record["packaged_sha256"]:
            failures.append("源码哈希不匹配：" + record["path"])
    results = json.loads((PACKAGE / "results/reported_results.json").read_text())
    rows, summary = results["tasks"], results["summary"]
    if len(rows) != 10 or len({r["instance_id"] for r in rows}) != 10:
        failures.append("历史结果任务数/唯一性不匹配")
    for mode in ("baseline", "hint"):
        if sum(r[mode]["status"] == "PASS" for r in rows) != summary[mode + "_solved"]:
            failures.append("历史结果汇总不匹配：" + mode)
    if (PACKAGE / "MANIFEST.sha256").exists():
        for line in (PACKAGE / "MANIFEST.sha256").read_text().splitlines():
            expected, name = line.split("  ", 1)
            path = PACKAGE / name
            if not path.is_file() or digest(path) != expected:
                failures.append("交付文件哈希不匹配：" + name)
    if failures:
        for failure in failures:
            print("FAIL: " + failure, file=sys.stderr)
        return 1
    print(f"检查通过：{len(pyfiles)} 个 Python 文件、{len(shfiles)} 个 Shell、"
          f"{len(mdfiles)} 个 Markdown、{link_count} 个本地链接；依赖/结果/凭据/哈希检查通过。")
    print("静态检查不会安装依赖、连接 Docker 或调用模型。")
    return 0


if __name__ == "__main__":
    if sys.version_info < (3, 12):
        print("请使用 Python 3.12 或更新版本运行本检查。", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main())
