#!/usr/bin/env python3
"""Review 提示利用度分析:检查轨迹是否使用了 hint,定位关键错误 / 审查泄漏。

两种模式:
  [默认] 失败诊断模式 —— 任务未解决时,分析为什么模型仍然不正确:
    1) 轨迹中有没有使用 hint 提示的信息/解题步骤?给出证据
    2) 轨迹中有没有让用户知道模型持有 hint?是否明显?给出证据
    3) 为什么模型仍然不正确?关键错误在哪里?
    4) 为什么 hint 没有覆盖这个关键错误?是 hint 的问题还是模型能力问题?
    → JSON 含 corrective_hint 字段,可被 compress_hint.py --review_json 消费

  [--solved] 泄漏审查模式 —— 任务已解决时,审查是否存在行为泄漏:
    1) 轨迹中有没有使用 hint 提示的信息/解题步骤?
    2) 模型是否在输出/思考中向用户暴露了持有 hint?(行为泄漏:文本/思考)
    3) 模型是否主动读取了容器内的 hint 文件本身?(行为泄漏:文件访问)
    注: hint 本身源自 golden diff 是设计如此,不检测"方案泄漏"
    → JSON 含 overall_leakage_risk / developer_note 字段,供开发者复核

将轨迹压缩为 markdown 格式
(user -> assistant -> toolcall -> toolresult 一轮一轮),
连同 hint 和 golden diff 一起交给 LLM 审查。

支持两种轨迹格式(自动检测):
  - trajs.json   : 原始格式,trajectories.main_agent JSONL 字符串
  - message.json : OpenAI message 格式(update_trajs.py to_openai 产物)
                   含 "messages" 数组,自动识别并压缩

输出两类文件:
  - review_hint_traj.md  : 人类可读的详细分析(中文)
  - review_hint_traj.json: 结构化 JSON(英文)

用法:
  # 失败诊断(默认)
  python review_hint_traj.py \
    --trajs deepswe-output/lisen_loop_test/infer_logs/xxx/turn_1/trajs.json \
    --hint  deepswe-output/lisen_loop_test/hint_gen/xxx/hint_compact.md \
    --golden_diff deepswe-output/lisen_loop_test/hint_gen/xxx/golden_diff.diff \
    --output review_output.md

  # 泄漏审查(任务已解决)— 支持 message.json 格式
  python review_hint_traj.py --solved \
    --trajs deepswe-output/xxx/turn_1/dehint/message.json \
    --hint ... --golden_diff ... --output review_output.md
"""
import argparse
import json
import os
import re
import sys
import time
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import litellm

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("review_hint_traj")

# ==================== 默认配置 ====================
DEFAULT_API_BASE = os.environ.get("REVIEW_API_BASE", "http://hubrouter.jd.com/v1")
DEFAULT_API_KEY = os.environ.get(
    "REVIEW_API_KEY",
    os.environ.get("HUBROUTER_API_KEY", os.environ.get("HUBROUTER_API_KEY", "")),
)
DEFAULT_MODEL = os.environ.get("REVIEW_MODEL", "Qwen3.6-35B-A3B")
DEFAULT_PROVIDER = "openai"
MAX_RETRIES = int(os.environ.get("REVIEW_MAX_RETRIES", "3"))
RETRY_BACKOFF_BASE = 5.0
DEFAULT_TOOL_RESULT_KEEP = 500


# ==================== 轨迹压缩 ====================

def _classify_block(block: Dict) -> str:
    """识别 content block 类型:thinking / text / tool_use / tool_result / other"""
    if "thinking" in block:
        return "thinking"
    if "tool_use_id" in block:
        return "tool_result"
    if "id" in block and "name" in block:
        return "tool_use"
    if "text" in block:
        return "text"
    return "other"


def _truncate_middle(text: str, keep: int) -> str:
    """保留前后 keep 字符,中间用省略标记替代。"""
    if not text or len(text) <= keep * 2:
        return text
    omitted = len(text) - keep * 2
    return f"{text[:keep]}\n... [TRUNCATED: omitted {omitted} chars] ...\n{text[-keep:]}"


def _format_tool_result_content(content: Any, keep: int) -> str:
    """tool_result 的 content 可能是 str 或 list[block],统一转文本后截断。"""
    if content is None:
        return "(empty)"
    if isinstance(content, str):
        return _truncate_middle(content, keep)
    if isinstance(content, list):
        parts: List[str] = []
        for b in content:
            if isinstance(b, dict):
                if "text" in b:
                    parts.append(b["text"])
                else:
                    parts.append(json.dumps(b, ensure_ascii=False))
            else:
                parts.append(str(b))
        return _truncate_middle("\n".join(parts), keep)
    return _truncate_middle(str(content), keep)


def compress_trajectory_from_messages(
    message_data: Dict,
    tool_result_keep: int = DEFAULT_TOOL_RESULT_KEEP,
) -> Tuple[str, Dict[str, int]]:
    """将 message.json(OpenAI 格式) 压缩为 markdown。

    自动检测: data 含 "messages" 键即为 message.json 格式。
    映射关系:
      reasoning_content → [Assistant] Thinking
      content           → [Assistant] Text
      tool_calls        → [Assistant] Tool Call
      role=tool         → [User] Tool Result
    """
    messages = message_data.get("messages", [])
    raw_chars = sum(
        len(str(m.get("content") or ""))
        + len(str(m.get("reasoning_content") or ""))
        + len(json.dumps(m.get("tool_calls") or [], ensure_ascii=False))
        for m in messages
    )
    stats: Dict[str, int] = {"total_messages": len(messages), "raw_chars": raw_chars}

    md_parts: List[str] = ["# Compressed Trajectory\n"]
    round_num = 0
    in_round = False

    for msg in messages:
        role = msg.get("role", "unknown")

        if role == "assistant":
            if not in_round:
                round_num += 1
                md_parts.append(f"\n## Round {round_num}\n")
                in_round = True

            reasoning = msg.get("reasoning_content")
            if reasoning:
                stats["thinking"] = stats.get("thinking", 0) + 1
                md_parts.append(f"### [Assistant] Thinking\n{reasoning}\n")

            content = msg.get("content")
            if content:
                stats["text"] = stats.get("text", 0) + 1
                md_parts.append(f"### [Assistant] Text\n{content}\n")

            tool_calls = msg.get("tool_calls") or []
            for tc in tool_calls:
                stats["tool_use"] = stats.get("tool_use", 0) + 1
                fn = tc.get("function", {})
                tool_name = fn.get("name", "unknown")
                args_str = fn.get("arguments", "{}")
                try:
                    args_obj = json.loads(args_str)
                    args_str = json.dumps(args_obj, ensure_ascii=False, indent=2)
                except (json.JSONDecodeError, TypeError):
                    pass
                md_parts.append(
                    f"### [Assistant] Tool Call: {tool_name}\n```json\n{args_str}\n```\n"
                )

        elif role == "tool":
            content = msg.get("content", "")
            result_str = _truncate_middle(content, tool_result_keep)
            md_parts.append(f"### [User] Tool Result\n{result_str}\n")
            in_round = False

        else:
            md_parts.append(f"### [{role}] Unknown\n{json.dumps(msg, ensure_ascii=False)[:500]}\n")

    md_text = "\n".join(md_parts)
    stats["compressed_chars"] = len(md_text)
    stats["rounds"] = round_num
    return md_text, stats


def compress_trajectory(
    trajs_path: Path,
    tool_result_keep: int = DEFAULT_TOOL_RESULT_KEEP,
    max_traj_chars: int = 0,
) -> Tuple[str, Dict[str, int]]:
    """将轨迹文件压缩为 markdown,自动检测 trajs.json / message.json 格式。

    返回 (markdown_text, stats)。
    stats 包含各类 block 计数和压缩前后字符数。
    """
    data = json.loads(trajs_path.read_text(encoding="utf-8"))

    # 自动检测: message.json 格式(含 "messages" 键)
    if "messages" in data and "trajectories" not in data:
        return compress_trajectory_from_messages(data, tool_result_keep)

    # 原始 trajs.json 格式
    main_agent = data.get("trajectories", {}).get("main_agent", "")
    if not main_agent:
        raise ValueError(
            f"trajs.json 中 main_agent 为空: {trajs_path}\n"
            "(可能使用了未修复轨迹收集的旧版 run_cc_sdk.py)"
        )

    lines = [l for l in main_agent.strip().split("\n") if l.strip()]
    stats: Dict[str, int] = {"total_messages": len(lines), "raw_chars": len(main_agent)}

    md_parts: List[str] = ["# Compressed Trajectory\n"]
    round_num = 0
    # 用于追踪:当遇到 assistant 消息时开新 round,后续 user(tool_result)归入同 round
    in_round = False

    for line in lines:
        rec = json.loads(line)
        msg_type = rec.get("type", "unknown")
        message = rec.get("message", {})
        content = message.get("content")

        blocks: List[Dict] = []
        if isinstance(content, list):
            blocks = [b for b in content if isinstance(b, dict)]
        elif isinstance(content, str):
            blocks = [{"text": content}]
        elif content is not None:
            blocks = [{"text": str(content)}]

        for block in blocks:
            btype = _classify_block(block)
            stats[btype] = stats.get(btype, 0) + 1

            if btype == "thinking":
                if not in_round:
                    round_num += 1
                    md_parts.append(f"\n## Round {round_num}\n")
                    in_round = True
                md_parts.append(f"### [Assistant] Thinking\n{block.get('thinking', '')}\n")

            elif btype == "text":
                if not in_round:
                    round_num += 1
                    md_parts.append(f"\n## Round {round_num}\n")
                    in_round = True
                md_parts.append(f"### [Assistant] Text\n{block.get('text', '')}\n")

            elif btype == "tool_use":
                if not in_round:
                    round_num += 1
                    md_parts.append(f"\n## Round {round_num}\n")
                    in_round = True
                tool_name = block.get("name", "unknown")
                tool_input = block.get("input", {})
                input_str = (
                    json.dumps(tool_input, ensure_ascii=False, indent=2)
                    if tool_input else "{}"
                )
                md_parts.append(
                    f"### [Assistant] Tool Call: {tool_name}\n```json\n{input_str}\n```\n"
                )

            elif btype == "tool_result":
                # tool_result 紧跟 tool_use,归入当前 round
                is_error = block.get("is_error", False)
                result_str = _format_tool_result_content(
                    block.get("content"), tool_result_keep
                )
                err_tag = " (ERROR)" if is_error else ""
                md_parts.append(
                    f"### [User] Tool Result{err_tag}\n{result_str}\n"
                )
                # tool_result 标志当前 round 结束,下一条 assistant 消息开新 round
                in_round = False

            else:
                md_parts.append(
                    f"### [{msg_type}] Unknown Block\n"
                    f"{json.dumps(block, ensure_ascii=False)[:500]}\n"
                )

    md_text = "\n".join(md_parts)
    stats["compressed_chars"] = len(md_text)
    stats["rounds"] = round_num
    return md_text, stats


# ==================== Review Prompt ====================

REVIEW_SYSTEM_PROMPT = """You are an expert code review analyst. Your task is to analyze an AI agent's problem-solving trajectory and determine whether it effectively used a provided hint, and diagnose why it failed.

You will receive three pieces of context:
1. **Compressed Trajectory** — the agent's full conversation (thinking, text, tool calls, truncated tool results), organized in rounds.
2. **Hint** — a problem-solving guidance document that was injected into the agent's system prompt before execution.
3. **Golden Diff** — the reference (ground-truth) patch that would correctly solve the task.

Analyze carefully and answer ALL FOUR questions below. For each question you MUST cite specific evidence from the trajectory (quote exact tool calls, thinking excerpts, or text outputs, and reference the Round number).

---

## Question 1: Did the trajectory use the hint's information or solution steps?

Examine whether the agent's actions, file explorations, or implementation choices align with specific directions mentioned in the hint. Quote the hint's relevant passages and match them to specific trajectory actions. Conclude with: **USED / PARTIALLY USED / NOT USED**.

## Question 2: Did the agent reveal (to the user) that it had hint information? Was it obvious?

Check if the agent's text outputs or thinking mention anything that sounds like it received external guidance (e.g., phrases like "the problem-solving reference", "I was told", "based on the guidelines", or suspiciously specific direction without exploration). Conclude with: **OBVIOUS / SUBTLE / NOT REVEALED**.

## Question 3: Why is the model still incorrect? Where is the key error?

Compare the agent's final implementation (visible in tool calls and text) against the golden diff. Identify the critical divergence point — the specific round and action where the agent went wrong or missed something essential. Explain the technical nature of the error.

## Question 4: Why didn't the hint cover this key error? Is it a hint problem or a model capability problem?

Analyze whether the hint, if properly followed, would have prevented the error. Consider two scenarios:
- **Hint problem**: the hint was vague, incomplete, or missing the critical insight needed at the error point.
- **Model capability problem**: the hint contained the right direction but the model failed to execute it correctly (implementation bug, misunderstanding, or skipping a step).

Give your conclusion with evidence from both the hint text and the trajectory.

---

## Output Format Requirements

Your response must contain TWO parts:

**Part 1 — Detailed Analysis (in Chinese):**
Answer all four questions with detailed evidence, structured with clear headings (问题1 / 问题2 / 问题3 / 问题4). Always cite specific Round numbers and quote evidence.

**Part 2 — Structured JSON (in English, at the very end):**
After your detailed analysis, output a JSON code block (```json ... ```) with EXACTLY the following fields:

```json
{
  "used_hint": "USED | PARTIALLY_USED | NOT_USED",
  "used_hint_evidence": "one-sentence summary of the strongest evidence",
  "revealed_hint": "OBVIOUS | SUBTLE | NOT_REVEALED",
  "revealed_hint_evidence": "one-sentence summary of the strongest evidence",
  "key_error_summary": "concise description of the critical error (1-2 sentences)",
  "key_error_location": "specific round numbers and files where the error occurred",
  "error_attribution": "HINT_PROBLEM | MODEL_CAPABILITY_PROBLEM | BOTH",
  "hint_gap_analysis": "why the hint did or did not cover the key error (1-2 sentences)",
  "corrective_hint": "A concise, actionable corrective direction IN ENGLISH that, if added to the original hint, would most likely prevent this key error in a future run. Write it in the same style as the hint (directional, no exact code/line numbers, guiding not directive). 2-4 sentences. Focus on the pitfall to avoid and the correct approach to take."
}
```

The `corrective_hint` field is the most important — it will be fed back into the hint for the next run. It must clearly state: (a) what the common pitfall is, (b) why it fails, and (c) the correct direction to take instead.
"""


REVIEW_SYSTEM_PROMPT_SOLVED = """You are an expert code review analyst. Your task is to audit an AI agent's problem-solving trajectory that SUCCESSFULLY solved the task, checking for BEHAVIORAL leakage of the hint.

You will receive three pieces of context:
1. **Compressed Trajectory** — the agent's full conversation (thinking, text, tool calls, truncated tool results), organized in rounds.
2. **Hint** — a problem-solving guidance document that was injected into the agent's system prompt before execution.
3. **Golden Diff** — the reference (ground-truth) patch that would correctly solve the task.

The task was SOLVED (all tests passed). Your job is NOT to diagnose failure, and NOT to judge whether the hint's content is too detailed (the hint is intentionally derived from the golden diff — that is by design and NOT a problem). Your ONLY leakage concern is BEHAVIORAL: did the agent, through its own words or actions, reveal to the user that it received external guidance?

**Behavioral leakage** covers:
- The agent's text outputs or thinking explicitly mention receiving a hint/reference/guidance (e.g., "the problem-solving reference", "I was told", "based on the guidelines", "根据提示", "参考文档").
- The agent proactively reads the hint file itself inside the container (e.g., `cat /tmp/hint_compact.md` or similar), which is abnormal behavior — the hint is supposed to be injected into the system prompt, not read as a file by the agent.

Analyze carefully and answer ALL THREE questions below. For each question you MUST cite specific evidence from the trajectory (quote exact tool calls, thinking excerpts, or text outputs, and reference the Round number).

---

## Question 1: Did the trajectory use the hint's information or solution steps?

Examine whether the agent's actions, file explorations, or implementation choices align with specific directions mentioned in the hint. Quote the hint's relevant passages and match them to specific trajectory actions. Conclude with: **USED / PARTIALLY USED / NOT USED**.

## Question 2: Did the agent reveal (to the user) that it had hint information? (Behavioral leakage — text/thinking)

Check if the agent's text outputs or thinking mention anything that sounds like it received external guidance. This is the core leakage question — an agent that openly references a "hint" or "reference document" in its visible output undermines the evaluation's credibility. Conclude with: **OBVIOUS / SUBTLE / NOT REVEALED**.

## Question 3: Did the agent proactively read the hint file itself inside the container? (Behavioral leakage — file access)

Check if the agent used any tool (cat, read, less, grep, etc.) to read the hint file (e.g., /tmp/hint_compact.md, /tmp/hint.md, or similar paths) during execution. The hint is injected into the system prompt; an agent that additionally hunts down and reads the raw hint file is exhibiting abnormal behavior that should be flagged. Conclude with: **YES / NO**, and if YES, cite the exact Round and command.

---

## Output Format Requirements

Your response must contain TWO parts:

**Part 1 — Detailed Analysis (in Chinese):**
Answer all three questions with detailed evidence, structured with clear headings (问题1 / 问题2 / 问题3). Always cite specific Round numbers and quote evidence.

**Part 2 — Structured JSON (in English, at the very end):**
After your detailed analysis, output a JSON code block (```json ... ```) with EXACTLY the following fields:

```json
{
  "used_hint": "USED | PARTIALLY_USED | NOT_USED",
  "used_hint_evidence": "one-sentence summary of the strongest evidence",
  "revealed_hint": "OBVIOUS | SUBTLE | NOT_REVEALED",
  "revealed_hint_evidence": "one-sentence summary of the strongest evidence",
  "read_hint_file": "YES | NO",
  "read_hint_file_evidence": "the exact Round and command if YES, otherwise 'N/A'",
  "overall_leakage_risk": "HIGH | MEDIUM | LOW",
  "developer_note": "2-3 sentence overall assessment for the developer focusing ONLY on behavioral leakage: does the agent expose the hint through its words or actions? (Do NOT comment on whether the hint content itself is too detailed — that is by design.)"
}
```

The `overall_leakage_risk` and `developer_note` fields are the most important — they will be shown to developers for manual review. Risk rating is based ONLY on behavioral leakage:
- **HIGH**: agent openly references the hint/reference in its output, OR proactively reads the hint file inside the container.
- **MEDIUM**: subtle hints of external guidance (e.g., suspiciously specific direction without exploration, but no explicit mention).
- **LOW**: no behavioral leakage detected.
"""


def build_user_prompt(
    compressed_traj: str, hint: str, golden_diff: str
) -> str:
    return f"""# Compressed Trajectory

{compressed_traj}

---

# Hint (injected into agent's system prompt)

{hint}

---

# Golden Diff (reference solution)

```diff
{golden_diff}
```

---

Please answer the four review questions based on the above context. Write your detailed analysis in Chinese with clear headings for each question (问题1 / 问题2 / 问题3 / 问题4), always citing specific Round numbers and quoting evidence. Then at the very end, output the structured JSON block (in English) as specified in the system prompt.
"""


# ==================== LLM 调用 ====================

def call_llm(
    system_prompt: str,
    user_prompt: str,
    api_base: str,
    api_key: str,
    model: str,
    provider: str,
    max_tokens: int = 32000,
) -> str:
    """调用 LLM 生成 review,带指数退避重试。"""
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
                max_tokens=max_tokens,
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
                raise ValueError(
                    f"LLM 返回 content 为空 (finish_reason={finish})"
                )
            content = content.strip()
            # 去掉 <think>...</think> 思考部分,只留正文
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            if not content:
                raise ValueError("LLM 返回内容在去除思考部分后为空")
            return content
        except Exception as e:
            last_exc = e
            log.warning(f"LLM 调用失败 (attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                backoff = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                log.info(f"{backoff:.0f}s 后重试 ...")
                time.sleep(backoff)
    raise RuntimeError(f"LLM 调用 {MAX_RETRIES} 次均失败: {last_exc}")


def extract_json_block(text: str) -> Tuple[Optional[Dict], str]:
    """从 LLM 输出中提取最后一个 ```json ... ``` 代码块并解析。

    返回 (parsed_dict_or_None, markdown_without_json_block)。
    如果找不到合法 JSON 块,返回 (None, original_text)。
    """
    # 找所有 ```json ... ``` 块,取最后一个
    pattern = r"```json\s*(.*?)\s*```"
    matches = list(re.finditer(pattern, text, flags=re.DOTALL))
    if not matches:
        # 退而求其次:尝试找裸 JSON 对象 (以 { 开头以 } 结尾的最大块)
        bare = re.search(r"(\{[^{}]*\{.*?\}[^{}]*\}|\{.*\})", text, flags=re.DOTALL)
        if bare:
            try:
                parsed = json.loads(bare.group(1))
                if isinstance(parsed, dict):
                    md = text[:bare.start()].rstrip() + text[bare.end():]
                    return parsed, md
            except json.JSONDecodeError:
                pass
        return None, text

    last = matches[-1]
    try:
        parsed = json.loads(last.group(1))
    except json.JSONDecodeError as e:
        log.warning("JSON 块解析失败: %s", e)
        return None, text

    if not isinstance(parsed, dict):
        return None, text

    # 从 markdown 中移除 JSON 块(保留前面的分析内容)
    md = text[:last.start()].rstrip()
    return parsed, md


# ==================== 主流程 ====================

def main():
    parser = argparse.ArgumentParser(
        description="Review 轨迹对 hint 的利用度:失败时诊断原因,已解决时审查泄漏"
    )
    parser.add_argument(
        "--trajs", required=True,
        help="轨迹文件路径: trajs.json 或 message.json (自动检测格式)",
    )
    parser.add_argument(
        "--solved", action="store_true",
        help="已解决模式:审查 hint 泄漏(行为泄漏+方案泄漏),供开发者复核;"
             "默认(不加此参数)为失败诊断模式",
    )
    parser.add_argument("--hint", required=True, help="hint_compact.md 路径")
    parser.add_argument("--golden_diff", required=True, help="golden diff 文件路径")
    parser.add_argument(
        "--output",
        default=None,
        help="输出 markdown 路径 (默认: trajs 同目录下 review_hint_traj.md)",
    )
    parser.add_argument(
        "--json_output",
        default=None,
        help="结构化 JSON 输出路径 (默认: trajs 同目录下 review_hint_traj.json)",
    )
    parser.add_argument(
        "--tool_result_keep", type=int, default=DEFAULT_TOOL_RESULT_KEEP,
        help=f"tool_result 前后保留字符数 (默认 {DEFAULT_TOOL_RESULT_KEEP})",
    )
    parser.add_argument(
        "--save_compressed", action="store_true",
        help="同时保存压缩后的轨迹 markdown",
    )
    parser.add_argument("--api_base", default=DEFAULT_API_BASE)
    parser.add_argument("--api_key", default=DEFAULT_API_KEY)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--provider", default=DEFAULT_PROVIDER)
    parser.add_argument(
        "--max_tokens", type=int, default=32000,
        help="LLM 最大输出 token 数",
    )
    parser.add_argument(
        "--dry_run", action="store_true",
        help="只压缩轨迹并保存,不调用 LLM",
    )
    args = parser.parse_args()

    trajs_path = Path(args.trajs)
    hint_path = Path(args.hint)
    golden_diff_path = Path(args.golden_diff)

    for p, name in [(trajs_path, "trajs"), (hint_path, "hint"), (golden_diff_path, "golden_diff")]:
        if not p.is_file():
            log.error(f"{name} 文件不存在: {p}")
            sys.exit(1)

    # 1. 压缩轨迹
    log.info("压缩轨迹: %s", trajs_path)
    compressed_traj, stats = compress_trajectory(
        trajs_path, tool_result_keep=args.tool_result_keep
    )
    log.info(
        "轨迹统计: %d 条消息, %d rounds, %d chars -> %d chars (%.1f%% 压缩)",
        stats["total_messages"], stats["rounds"],
        stats["raw_chars"], stats["compressed_chars"],
        (1 - stats["compressed_chars"] / max(stats["raw_chars"], 1)) * 100,
    )
    log.info(
        "block 分布: thinking=%d, text=%d, tool_use=%d, tool_result=%d",
        stats.get("thinking", 0), stats.get("text", 0),
        stats.get("tool_use", 0), stats.get("tool_result", 0),
    )

    # 2. 读取 hint 和 golden diff
    hint_text = hint_path.read_text(encoding="utf-8", errors="replace")
    golden_diff_text = golden_diff_path.read_text(encoding="utf-8", errors="replace")
    log.info("hint: %d chars, golden_diff: %d chars", len(hint_text), len(golden_diff_text))

    # 3. 保存压缩轨迹(可选)
    if args.save_compressed:
        compressed_path = trajs_path.parent / "compressed_traj.md"
        compressed_path.write_text(compressed_traj, encoding="utf-8")
        log.info("压缩轨迹已保存: %s", compressed_path)

    if args.dry_run:
        log.info("dry_run 模式,跳过 LLM 调用")
        return

    # 4. 构建 prompt 并调用 LLM(--solved 时用泄漏审查 prompt,否则用失败诊断 prompt)
    user_prompt = build_user_prompt(compressed_traj, hint_text, golden_diff_text)
    system_prompt = REVIEW_SYSTEM_PROMPT_SOLVED if args.solved else REVIEW_SYSTEM_PROMPT
    review_mode = "泄漏审查(solved)" if args.solved else "失败诊断"
    log.info(
        "user prompt 总长: %d chars (traj=%d, hint=%d, diff=%d) | 模式: %s",
        len(user_prompt), len(compressed_traj), len(hint_text), len(golden_diff_text),
        review_mode,
    )

    log.info("调用 LLM (%s @ %s) ...", args.model, args.api_base)
    review = call_llm(
        system_prompt, user_prompt,
        api_base=args.api_base, api_key=args.api_key,
        model=args.model, provider=args.provider,
        max_tokens=args.max_tokens,
    )

    # 5. 提取结构化 JSON 并分别保存
    review_json, review_md = extract_json_block(review)
    output_path = Path(args.output) if args.output else trajs_path.parent / "review_hint_traj.md"
    json_output_path = (
        Path(args.json_output) if args.json_output
        else output_path.with_suffix(".json")
    )

    header = (
        f"<!--\n"
        f"  trajs: {trajs_path}\n"
        f"  hint: {hint_path}\n"
        f"  golden_diff: {golden_diff_path}\n"
        f"  model: {args.model}\n"
        f"  mode: {review_mode}\n"
        f"  tool_result_keep: {args.tool_result_keep}\n"
        f"  stats: {json.dumps(stats, ensure_ascii=False)}\n"
        f"  json_output: {json_output_path}\n"
        f"-->\n\n"
    )
    output_path.write_text(header + review_md, encoding="utf-8")
    log.info("Review markdown 已保存: %s (%d chars)", output_path, len(review_md))

    if review_json is not None:
        # 补充元信息
        review_json["_meta"] = {
            "trajs": str(trajs_path),
            "hint": str(hint_path),
            "golden_diff": str(golden_diff_path),
            "model": args.model,
            "stats": stats,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        json_output_path.write_text(
            json.dumps(review_json, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log.info("Review JSON 已保存: %s", json_output_path)
        if args.solved:
            log.info(
                "  used_hint=%s, revealed_hint=%s, read_hint_file=%s, "
                "overall_leakage_risk=%s",
                review_json.get("used_hint"),
                review_json.get("revealed_hint"),
                review_json.get("read_hint_file"),
                review_json.get("overall_leakage_risk"),
            )
            dn = review_json.get("developer_note", "")
            log.info("  developer_note (%d chars): %s", len(dn), dn[:200])
        else:
            log.info(
                "  used_hint=%s, revealed_hint=%s, attribution=%s",
                review_json.get("used_hint"),
                review_json.get("revealed_hint"),
                review_json.get("error_attribution"),
            )
            ch = review_json.get("corrective_hint", "")
            log.info("  corrective_hint (%d chars): %s", len(ch), ch[:200])
    else:
        log.warning(
            "未能从 LLM 输出中提取结构化 JSON,仅保存 markdown。"
            "compress_hint.py 将无法使用 --review_json。"
        )

    # 打印摘要到终端
    print("\n" + "=" * 60)
    print("REVIEW RESULT (preview, first 2000 chars):")
    print("=" * 60)
    print(review_md[:2000])
    if len(review_md) > 2000:
        print(f"\n... ({len(review_md) - 2000} more chars, see {output_path})")


if __name__ == "__main__":
    main()