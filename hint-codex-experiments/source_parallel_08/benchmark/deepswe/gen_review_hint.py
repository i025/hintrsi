#!/usr/bin/env python3
"""
生成"用户口吻"的 review 提示，用于多轮反馈 loop。

从 eval 结果 + 题目需求 + patch 概况中提取信息，
请求 LLM 以用户/需求方口吻给出不泄露测试细节的思路性提示。

用法:
  python gen_review_hint.py \
    --instance_id go-genai-streamed-function-args \
    --run_name lisen_rollout_test_1019 \
    --output_base /mnt/joyai/lisen.173/cc-run/deepswe-output \
    --parquet_file /mnt/joyai/lisen.173/cc-run/deep_swe_tasks.parquet \
    --round 1
"""
import argparse
import json
import os
import re
import sys
import time
import logging
from datetime import datetime
from pathlib import Path

import litellm

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ==================== 默认配置 ====================
DEFAULT_API_BASE = os.environ.get("HINT_API_BASE", "http://127.0.0.1:8765/v1")
DEFAULT_API_KEY = os.environ.get("HINT_API_KEY", os.environ.get("HUBROUTER_API_KEY", ""))
DEFAULT_MODEL = os.environ.get("HINT_MODEL", "gpt-6.1-terra")
DEFAULT_PROVIDER = "openai"
MAX_RETRIES = int(os.environ.get("HINT_MAX_RETRIES", "3"))
RETRY_BACKOFF_BASE = 5.0

# ==================== Prompt 模板 ====================

SYSTEM_PROMPT = """You are the user who requested a software change and has just run acceptance checks. Write a short, natural chat message to the developer about the remaining incorrect behavior.

Use English throughout. Write three to eight connected conversational sentences with no headings, numbered lists, Markdown, code, opening remarks, or formal overall assessment. Describe the failing behavior concretely in your own words and ask a focused diagnostic question when useful.

Never reveal test function names, exact test inputs, expected values, or assertion source. Those are private analysis material. Explain which feature or scenario still fails without quoting test details. Help the developer locate the cause independently; do not give a repair implementation or code answer.

Use earlier feedback to avoid repeating yourself. Narrow the diagnosis when the new evidence supports it, and revise earlier hypotheses when the evidence contradicts them. Output only the chat message.
"""

USER_PROMPT_TEMPLATE = """## Original Requirement
{problem_statement}

## Submitted Patch Summary
{patch_summary}

## Acceptance Results (private analysis context)
{eval_summary}

## Developer's Final Summary
{model_summary}

## Earlier Feedback Messages
{previous_hints}

Write a short English chat message that describes the remaining behavior specifically, without exposing test identifiers, exact data, or expected answers. Make it more focused than earlier feedback when the evidence permits.
"""


# ==================== 上下文收集 ====================

def analyze_patch(patch_path: Path) -> str:
    """分析 patch.diff，提取新建/修改文件列表及规模。"""
    if not patch_path.exists():
        return "(patch.diff was not found)"

    text = patch_path.read_text(encoding="utf-8", errors="replace")
    file_blocks = re.split(r"^diff --git ", text, flags=re.MULTILINE)
    new_files, modified_files = [], []
    for block in file_blocks[1:]:
        header = block.split("\n", 1)[0]  # e.g. "a/foo.go b/foo.go"
        paths = header.split(" ")
        if len(paths) >= 2:
            b_path = paths[1].lstrip("b/")
        else:
            b_path = header
        added = len(re.findall(r"^\+[^+]", block, flags=re.MULTILINE))
        removed = len(re.findall(r"^-[^-]", block, flags=re.MULTILINE))
        is_new = "\nnew file mode" in block[:300]
        entry = f"{b_path} (+{added}/-{removed})"
        if is_new:
            new_files.append(entry)
        else:
            modified_files.append(entry)

    lines = []
    if new_files:
        lines.append("New files:")
        for f in new_files:
            lines.append(f"  - {f}")
    if modified_files:
        lines.append("Modified existing files:")
        for f in modified_files:
            lines.append(f"  - {f}")
    if not modified_files:
        lines.append("Modified existing files: none")
    return "\n".join(lines) if lines else "(The patch is empty)"


def extract_failure_blocks(stdout: str) -> str:
    """从测试 stdout 中提取全部失败块 + 总结行，而非仅截取尾部。

    测试输出格式为 `[verifier] ✗ [f2p] ...` 开头的分段，每段含完整失败详情。
    仅取尾部 2000 字符会丢失前面的失败，导致 reviewer 看不到全部失败模式。
    """
    if not stdout:
        return ""
    # 按 [verifier] 行首标记分段，保留含 ✗ 的失败段
    parts = re.split(r"(?=^\[verifier\])", stdout, flags=re.MULTILINE)
    fail_parts = [p.strip() for p in parts if "✗" in p]
    # 提取总结行（P2P ... F2P ... PARTIAL ... BINARY）
    summary = ""
    for line in stdout.split("\n"):
        if "PARTIAL" in line and "BINARY" in line:
            summary = line.strip()
            break
    result = "\n\n".join(fail_parts)
    if summary:
        result = (result + "\n\n" + summary) if result else summary
    # 兜底：如果没提取到失败块，退回尾部 4000 字符
    return result if result else stdout[-4000:]


def analyze_eval(eval_path: Path) -> str:
    """分析 eval_result.json，提取通过率和失败模式。"""
    if not eval_path.exists():
        return "(eval_result.json was not found)"

    data = json.loads(eval_path.read_text(encoding="utf-8"))
    lines = []
    lines.append(f"Feature tests (f2p): {data.get('f2p_passed', '?')}/{data.get('f2p_total', '?')} passed")
    lines.append(f"Regression tests (p2p): {data.get('p2p_passed', '?')}/{data.get('p2p_total', '?')} passed")
    if "partial" in data:
        lines.append(f"Partial score: {data.get('partial')}")
    if "reward" in data:
        lines.append(f"Reward: {data.get('reward')}")

    # 提取全部失败块供 reviewer 分析失败模式（reviewer 会将其翻译为行为方向，不直接透露测试标识）
    stdout_tail = data.get("stdout_tail", "")
    if stdout_tail:
        fail_blocks = extract_failure_blocks(stdout_tail)
        if fail_blocks:
            lines.append("\nFailure details for private analysis only; do not quote test names, literal data, or expected values:")
            lines.append("```\n" + fail_blocks + "\n```")
    return "\n".join(lines)


def load_problem_statement(parquet_path: Path, instance_id: str) -> str:
    """从 parquet 加载题目原文。"""
    import pandas as pd
    df = pd.read_parquet(parquet_path)
    matches = df[df["instance_id"] == instance_id]
    if matches.empty:
        return f"({instance_id} was not found in {parquet_path})"
    return str(matches.iloc[0]["problem_statement"])


def extract_model_summary(trajs_path: Path) -> str:
    """从 extracted_trajs.json 提取模型最终总结。"""
    if not trajs_path.exists():
        return "(extracted_trajs.json was not found)"
    try:
        data = json.loads(trajs_path.read_text(encoding="utf-8"))
        # 结构: main_agent 列表，取最后一条的 result_msg / message
        main = data.get("main_agent", [])
        if not main:
            return "(No main-agent records were found)"
        for item in reversed(main):
            msg = item.get("result_msg") or item.get("message") or ""
            if msg and len(msg.strip()) > 10:
                return msg.strip()[:2000]
        return "(No usable final summary was found)"
    except Exception as e:
        return f"(Could not read the trajectory: {e})"


# ==================== LLM 调用 ====================

def call_llm(system_prompt: str, user_prompt: str,
             api_base: str, api_key: str, model: str, provider: str) -> str:
    """调用 LLM 生成 review hint，带指数退避重试。"""
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = litellm.completion(
                model=f"{provider}/{model}",
                base_url=api_base,
                api_key=api_key,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=256000,
                verbose=False,
                extra_body={
                    "chat_template_kwargs": {
                        "enable_thinking": True,
                        "clear_thinking": False,
                    },
                    "allow_external": True,
                },
            )
            content = response.choices[0].message.content
            if not content:
                finish = getattr(response.choices[0], "finish_reason", "unknown")
                raise ValueError(f"LLM 返回 content 为空 (finish_reason={finish})，可能思考过程耗尽 token 预算")
            content = content.strip()
            # 思考型模型可能输出 <think>...</think>，去掉思考部分只留正文
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            return content
        except Exception as e:
            last_exc = e
            log.warning(f"LLM 调用失败 (attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                backoff = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                log.info(f"{backoff:.0f}s 后重试 ...")
                time.sleep(backoff)
    raise RuntimeError(f"LLM 调用 {MAX_RETRIES} 次均失败: {last_exc}")


# ==================== 主流程 ====================

def main():
    parser = argparse.ArgumentParser(description="生成用户口吻的 review 提示")
    parser.add_argument("--instance_id", required=True)
    parser.add_argument("--run_name", required=True)
    parser.add_argument("--output_base", default=str(Path(__file__).resolve().parents[2] / "deepswe-output"))
    parser.add_argument("--parquet_file", default=str(Path(__file__).resolve().parents[2] / "deep_swe_tasks.parquet"))
    parser.add_argument("--round", type=int, default=1, help="当前反馈轮次")
    parser.add_argument("--api_base", default=DEFAULT_API_BASE)
    parser.add_argument("--api_key", default=DEFAULT_API_KEY)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--provider", default=DEFAULT_PROVIDER)
    parser.add_argument("--save", action="store_true", help="保存 hint 到 JSON 文件")
    args = parser.parse_args()

    run_dir = Path(args.output_base) / args.run_name
    infer_dir = run_dir / "infer_logs" / args.instance_id
    eval_dir = run_dir / "eval_output" / args.instance_id

    # 收集上下文
    log.info("收集上下文 ...")
    problem_statement = load_problem_statement(Path(args.parquet_file), args.instance_id)
    patch_summary = analyze_patch(infer_dir / "patch.diff")
    eval_summary = analyze_eval(eval_dir / "eval_result.json")
    model_summary = extract_model_summary(infer_dir / "extracted_trajs.json")

    log.info(f"题目需求: {len(problem_statement)} 字符")
    log.info(f"Patch 概况:\n{patch_summary}")
    log.info(f"Eval 概况: f2p/p2p 见 eval_summary")

    # 构建 prompt
    user_prompt = USER_PROMPT_TEMPLATE.format(
        problem_statement=problem_statement,
        patch_summary=patch_summary,
        eval_summary=eval_summary,
        model_summary=model_summary,
        previous_hints="(Standalone invocation; no earlier feedback)" if args.round <= 1
                       else f"(Standalone invocation at round {args.round}; earlier feedback was not supplied)",
    )

    # 调用 LLM
    log.info(f"调用 LLM ({args.model}) 生成 review hint (round {args.round}) ...")
    hint = call_llm(SYSTEM_PROMPT, user_prompt,
                    args.api_base, args.api_key, args.model, args.provider)

    print("\n" + "=" * 60)
    print(f"REVIEW HINT (round {args.round})")
    print("=" * 60)
    print(hint)
    print("=" * 60)

    # 保存
    if args.save:
        hint_dir = run_dir / "review_hints" / args.instance_id
        hint_dir.mkdir(parents=True, exist_ok=True)
        out_path = hint_dir / f"round_{args.round}.json"
        record = {
            "instance_id": args.instance_id,
            "round": args.round,
            "hint": hint,
            "context": {
                "patch_summary": patch_summary,
                "eval_summary_lines": eval_summary.split("\n")[:5],
            },
            "timestamp": datetime.now().isoformat(),
        }
        out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info(f"已保存: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())