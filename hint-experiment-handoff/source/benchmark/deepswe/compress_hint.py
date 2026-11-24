#!/usr/bin/env python3
"""
压缩完整 hint 为精简版，用于嵌入 system prompt。

读取 hint_gen/{instance_id}/hint_output.md（完整解题指导），
请求 LLM 压缩为精简的方向性提示，再拼接固定的"提示使用规范"，
输出 hint_compact.md 可直接嵌入 agent 的 system prompt。

设计要点：
- 使用规范（先验证再引用、第一人称措辞、不暴露 hint 存在）是固定文本，
  由脚本拼接，不交给 LLM 生成，确保每实例一致。
- LLM 只负责内容压缩：保留问题分析/建议方向/关键文件线索，
  删除代码片段、精确行号、逐步实现细节。
- 输出语言为英文，与 cc harness 的 claude_code preset system prompt 保持一致。
- 可选 --review_json（支持多个，累计缺陷融合）：读取一或多个
  review_hint_traj.py 产出的结构化 review JSON，将历轮失败分析的纠正方向
  （corrective_hint）按时间顺序全部融入压缩后的 hint，新增 "## Critical Warnings"
  段落并强化相关 Suggested Directions。多轮 loop 中第 N 轮传入前 N-1 轮的 review。
- 可选 --output：指定 hint_compact.md 输出路径（多轮 loop 中用独立文件名
  如 hint_compact_r2.md 避免覆盖前轮产物）。

用法:
  # 首轮压缩(无 review)
  python compress_hint.py \
    --instance_id go-genai-streamed-function-args \
    --run_name lisen_full_loop \
    --output deepswe-output/lisen_full_loop/hint_gen/xxx/hint_compact_r1.md

  # 第 3 轮压缩(累计融合前 2 轮 review)
  python compress_hint.py \
    --instance_id go-genai-streamed-function-args \
    --run_name lisen_full_loop \
    --output deepswe-output/lisen_full_loop/hint_gen/xxx/hint_compact_r3.md \
    --review_json deepswe-output/lisen_full_loop/reviews/round_1/review_hint_traj.json \
                  deepswe-output/lisen_full_loop/reviews/round_2/review_hint_traj.json
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
from typing import Dict, List, Optional

import litellm

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ==================== 默认配置 ====================
DEFAULT_API_BASE = os.environ.get("HINT_API_BASE", "http://hubrouter.jd.com/v1")
DEFAULT_API_KEY = os.environ.get("HINT_API_KEY", os.environ.get("HUBROUTER_API_KEY", ""))
DEFAULT_MODEL = os.environ.get("HINT_MODEL", "Qwen3.6-35B-A3B")
DEFAULT_PROVIDER = "openai"
MAX_RETRIES = int(os.environ.get("HINT_MAX_RETRIES", "3"))
RETRY_BACKOFF_BASE = 5.0

# ==================== 固定的提示使用规范 ====================
# 这段文本会拼接在压缩后的 hint 前面，作为 agent 使用 hint 的行为约束。
# 不交给 LLM 生成，保证每个实例的规范措辞完全一致。
USAGE_GUIDELINES = """[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.
"""

# ==================== 压缩 Prompt ====================

COMPRESS_SYSTEM_PROMPT = """You are a problem-solving hint compressor. Your task is to compress a detailed problem-solving guide into a concise directional hint, to serve as internal reference in the system prompt of another AI coding assistant. Output must be in English.

[Compression Principles]
1. Keep three types of core information:
   - Problem analysis: what the problem essentially is and why it occurs (2-3 sentences)
   - Suggested directions: the thinking steps for solving the problem (directional, not implementation-level)
   - Key location clues: the file names involved and their approximate roles
2. Must remove:
   - Specific code snippets, function signatures, type definitions, import lists
   - Exact line numbers (remove all references like "around line 217", "lines 46-49")
   - Step-by-step implementation details (how to write each function, how to handle boundary conditions, state lifecycle management details)
   - Data flow diagrams, call chains, merge strategy details
3. Wording style — hints, not answers:
   - Use guiding phrases like "may need attention", "suggest first understanding", "the core lies in", "worth noting"
   - Do not use directive phrases like "must modify", "add at line X", "create the following function", "change to the following code"
   - For new file suggestions, use soft expressions like "the core logic may need to live in a separate file" rather than giving the file name directly
   - Present file locations as "clues": file name + one-sentence role description, no line numbers
4. Length: keep it concise, typically no more than 500 words.

[Output Format]
## Problem Analysis
(2-3 sentences describing the essence of the problem)

## Suggested Directions
(3-6 bullet points, one sentence each, describing thinking direction not implementation details)

## Key Location Clues
(List the file names involved, one sentence per file describing its possible role, no line numbers)

Output the above content directly, without any opening remarks, explanations, or closing remarks."""

COMPRESS_USER_TEMPLATE = """## Full Problem-Solving Guide (original content to compress)
{full_hint}

Please compress the above full problem-solving guide into a concise directional hint. Remember: keep only the problem analysis, suggested directions, and key file clues; remove all specific code, line numbers, and implementation details. The output is a hint, not an answer. Output in English."""

# ==================== Review Feedback 融合 ====================
# 当提供 --review_json 时,追加到 system prompt,指示 LLM 将纠正方向融入 hint
REVIEW_FEEDBACK_SYSTEM_ADDENDUM = """

[Review Feedback Integration — when Review Feedback section is present]
One or more "Review Feedback from Previous Attempt" sections are provided in the user message. They contain corrective directions derived from analyzing previous failed runs that used earlier versions of this hint, ordered from earliest to latest attempt. You MUST incorporate ALL of them:

1. Add a new output section "## Critical Warnings" AFTER "Key Location Clues".
2. Translate the corrective directions into concise warning bullet points in the same directional hint style (no exact code, no line numbers, guiding not directive). Consolidate overlapping pitfalls into one bullet; keep distinct pitfalls as separate bullets.
3. Each warning must clearly state: the pitfall to avoid, why it fails, and the correct direction instead.
4. If any corrective direction reveals the original guide was insufficient or misleading in some area, also strengthen the corresponding "Suggested Directions" bullet points.
5. The "Critical Warnings" section must not exceed 200 words total (stay concise even with multiple attempts — merge related pitfalls).

[Updated Output Format when Review Feedback is present]
## Problem Analysis
(2-3 sentences)

## Suggested Directions
(3-6 bullet points, strengthened with review feedback where relevant)

## Key Location Clues
(file names + one-sentence role descriptions)

## Critical Warnings
(2-5 bullet points translated from the accumulated review feedback: pitfall → why it fails → correct direction; consolidate overlapping pitfalls)

Output the above content directly, without any opening remarks, explanations, or closing remarks."""


def build_review_feedback_user_section(feedbacks: List[Dict]) -> str:
    """构建累计 review feedback 的 user prompt 段落(多轮按时间顺序排列)。

    累计缺陷模式:第 N 轮压缩时传入前 N-1 轮的 review JSON,
    所有有效的 corrective_hint 按轮次顺序展示,让 LLM 全部融入新 hint。
    """
    parts = ["\n\n## Review Feedback from Previous Attempt(s)"]
    if len(feedbacks) == 1:
        parts.append(
            "A previous run using an earlier version of this hint failed. "
            "Post-run analysis produced the following corrective direction that MUST be "
            "incorporated into the new compressed hint:\n"
        )
    else:
        parts.append(
            f"{len(feedbacks)} previous runs using earlier versions of this hint all failed. "
            "Post-run analyses produced the following corrective directions "
            "(ordered from earliest to latest attempt) that MUST ALL be incorporated "
            "into the new compressed hint:\n"
        )

    for i, fb in enumerate(feedbacks, 1):
        parts.append(f"### Attempt {i}")
        parts.append(f"- Key error: {fb.get('key_error_summary', '(unknown)')}")
        parts.append(f"- Error location: {fb.get('key_error_location', '(unknown)')}")
        parts.append(f"- Attribution: {fb.get('error_attribution', '(unknown)')}")
        parts.append(f"- Hint gap analysis: {fb.get('hint_gap_analysis', '(unknown)')}")
        parts.append(f"- Corrective direction: {fb.get('corrective_hint', '')}")
        parts.append("")

    parts.append(
        "Incorporate ALL the above corrective directions into the compressed hint as "
        "instructed in the system prompt (add a \"## Critical Warnings\" section "
        "consolidating all pitfalls, and strengthen relevant \"Suggested Directions\" "
        "if the original guide was insufficient)."
    )
    return "\n".join(parts)


# ==================== LLM 调用 ====================

def call_llm(system_prompt: str, user_prompt: str,
             api_base: str, api_key: str, model: str, provider: str) -> str:
    """调用 LLM 压缩 hint，带指数退避重试。"""
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
                temperature=0.3,
                max_tokens=16384,
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
            if not content:
                raise ValueError("LLM 返回内容去除思考段后为空")
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

def load_review_feedbacks(review_json_paths: Optional[List[str]]) -> List[Dict]:
    """读取多个 review_hint_traj.json,按传入顺序返回有效的反馈列表。

    累计缺陷模式:第 N 轮压缩时传入前 N-1 轮的 review JSON 路径,
    所有有效的 corrective_hint 都会融入新 hint 的 Critical Warnings。

    单个路径时行为与旧版 load_review_feedback 一致。
    """
    if not review_json_paths:
        return []
    feedbacks: List[Dict] = []
    for raw_path in review_json_paths:
        p = Path(raw_path)
        if not p.is_file():
            log.warning(f"review_json 文件不存在,跳过: {p}")
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            log.warning(f"review_json 解析失败,跳过: {p} ({e})")
            continue
        corrective = (data.get("corrective_hint") or "").strip()
        if not corrective:
            log.warning(f"review_json 中 corrective_hint 为空,跳过: {p}")
            continue
        log.info(
            "读取 review feedback: %s (attribution=%s, corrective_hint=%d chars)",
            p, data.get("error_attribution"), len(corrective),
        )
        feedbacks.append(data)
    return feedbacks


def main():
    parser = argparse.ArgumentParser(description="压缩完整 hint 为精简版 system prompt 提示")
    parser.add_argument("--instance_id", required=True)
    parser.add_argument("--run_name", required=True)
    parser.add_argument("--output_base", default=str(Path(__file__).resolve().parents[2] / "deepswe-output"))
    parser.add_argument(
        "--review_json", nargs="+", default=None,
        help="可选: 一个或多个 review_hint_traj.json 路径(按轮次顺序传入,累计融合所有纠正方向)。"
             "如第 3 轮: --review_json r1.json r2.json",
    )
    parser.add_argument(
        "--output", default=None,
        help="hint_compact.md 输出路径 (默认: {output_base}/{run_name}/hint_gen/{instance_id}/hint_compact.md)。"
             "多轮 loop 中建议指定独立文件名如 hint_compact_r2.md 避免覆盖",
    )
    parser.add_argument("--api_base", default=DEFAULT_API_BASE)
    parser.add_argument("--api_key", default=DEFAULT_API_KEY)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--provider", default=DEFAULT_PROVIDER)
    args = parser.parse_args()

    hint_dir = Path(args.output_base) / args.run_name / "hint_gen" / args.instance_id
    full_hint_path = hint_dir / "hint_output.md"

    if not full_hint_path.exists():
        log.error(f"未找到完整 hint: {full_hint_path}")
        return 1

    full_hint = full_hint_path.read_text(encoding="utf-8")
    log.info(f"读取完整 hint: {full_hint_path} ({len(full_hint)} 字符)")

    # 读取 review feedback (可选,支持多个累计)
    review_feedbacks = load_review_feedbacks(args.review_json)

    # 构建 prompt:有 review feedback 时追加 addendum
    system_prompt = COMPRESS_SYSTEM_PROMPT
    user_prompt = COMPRESS_USER_TEMPLATE.format(full_hint=full_hint)
    if review_feedbacks:
        system_prompt = COMPRESS_SYSTEM_PROMPT + REVIEW_FEEDBACK_SYSTEM_ADDENDUM
        user_prompt += build_review_feedback_user_section(review_feedbacks)
        log.info(
            "已附加 %d 份 review feedback,将生成含累计 Critical Warnings 的 hint",
            len(review_feedbacks),
        )

    # 调用 LLM 压缩
    log.info(f"调用 LLM ({args.model}) 压缩 hint ...")
    compressed = call_llm(system_prompt, user_prompt,
                          args.api_base, args.api_key, args.model, args.provider)

    log.info(f"压缩完成: {len(compressed)} 字符 (原始 {len(full_hint)} 字符, 压缩率 {len(compressed)/len(full_hint)*100:.0f}%)")

    # 拼接固定的使用规范 + 压缩后的内容
    final_hint = USAGE_GUIDELINES.rstrip() + "\n\n---\n\n" + compressed.strip() + "\n"

    # 保存(支持 --output 指定独立文件名,多轮 loop 中避免覆盖)
    out_path = Path(args.output) if args.output else hint_dir / "hint_compact.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(final_hint, encoding="utf-8")
    log.info(f"已保存精简 hint: {out_path}")

    # 保存元数据(meta 文件名跟随 output: hint_compact_r2.md → hint_compact_r2_meta.json)
    meta_path = out_path.with_name(out_path.stem + "_meta.json")
    meta = {
        "instance_id": args.instance_id,
        "run_name": args.run_name,
        "model": args.model,
        "provider": args.provider,
        "full_hint_chars": len(full_hint),
        "compressed_chars": len(compressed),
        "final_chars": len(final_hint),
        "compression_ratio": round(len(compressed) / len(full_hint), 3),
        "source": str(full_hint_path),
        "has_review_feedback": bool(review_feedbacks),
        "review_count": len(review_feedbacks),
        "review_jsons": [str(p) for p in (args.review_json or [])],
        "review_error_attributions": [
            fb.get("error_attribution") for fb in review_feedbacks
        ],
        "output": str(out_path),
        "timestamp": datetime.now().isoformat(),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"已保存元数据: {meta_path}")

    # 打印结果
    print("\n" + "=" * 60)
    print(f"COMPACT HINT ({len(compressed)} chars, 压缩率 {len(compressed)/len(full_hint)*100:.0f}%)")
    print("=" * 60)
    print(final_hint)
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())