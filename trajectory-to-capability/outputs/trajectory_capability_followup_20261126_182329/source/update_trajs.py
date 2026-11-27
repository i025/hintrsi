#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""update_trajs.py - 轨迹后处理流水线

对最终生成的解题轨迹(trajs.json)执行一系列转换动作。

动作列表(按需扩展):
  1. to_openai  : 将 trajs.json 转换为标准 OpenAI message 格式,输出 message.json
  2. dehint     : 检测并改写轨迹中的 hint 泄漏,输出到 dehint/ 子目录

用法:
  # 单文件
  python update_trajs.py --input deepswe-output/xxx_r1/infer_logs/iid/turn_1/trajs.json
  # 目录(递归查找所有 trajs.json)
  python update_trajs.py --input deepswe-output/xxx_r1/infer_logs/
  # 指定动作 + 覆盖已有产物
  python update_trajs.py --input <path> --actions to_openai --force
  # dehint: 检测+改写 hint 泄漏
  python update_trajs.py --input <trajs.json> --actions dehint
  python update_trajs.py --input <trajs.json> --actions dehint --force

trajs.json 结构:
  {
    "trajectories": {
      "main_agent": "<JSONL 字符串,每行一个消息对象>",
      "sub_agent": [...]   # 当前数据均为空
    },
    "metadata": {...}
  }
  JSONL 每行: {"type": "assistant"|"user", "message": {"content": [...], ...}}
  assistant content 项: {"text": ...} | {"thinking": ..., "signature": ...} | {"id": ..., "name": ..., "input": {...}}
  user content 项:     {"tool_use_id": ..., "content": ..., "is_error": bool}

OpenAI message 格式映射:
  assistant text     → {"role": "assistant", "content": "text"}
  assistant thinking → reasoning_content 字段(DeepSeek/o1 等推理模型标准扩展)
  assistant tool_use → {"role": "assistant", "tool_calls": [{"id", "type": "function", "function": {"name", "arguments"}}]}
  user tool_result   → {"role": "tool", "tool_call_id": "...", "content": "..."}
  同 message_id 且相邻的 assistant 行合并为一条消息(text/thinking/tool_calls 合并)
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

# 立即刷新输出,避免管道缓冲(| tail / | grep)导致运行中看不到进度
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except AttributeError:
    pass  # Python < 3.7 无 reconfigure

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("update_trajs")


# ==================== 通用工具 ====================

def parse_jsonl(jsonl_str: str) -> List[Dict[str, Any]]:
    """解析 JSONL 字符串为对象列表(跳过空行,坏行打警告)。"""
    items = []
    for lineno, line in enumerate(jsonl_str.strip().split("\n"), 1):
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"  [warn] 第 {lineno} 行 JSON 解析失败,跳过: {e}", file=sys.stderr)
    return items


def find_trajs_files(input_path: Path) -> List[Path]:
    """收集所有 trajs.json: 单文件直接返回,目录递归查找。"""
    if input_path.is_file():
        return [input_path] if input_path.name == "trajs.json" else [input_path]
    if input_path.is_dir():
        return sorted(input_path.rglob("trajs.json"))
    raise FileNotFoundError(f"路径不存在: {input_path}")


# ==================== 动作 1: trajs.json → message.json ====================

def _classify_content_item(c: Dict[str, Any]) -> str:
    """识别 assistant content 项类型。"""
    if "thinking" in c:
        return "thinking"
    if "text" in c:
        return "text"
    if "name" in c and "id" in c:
        return "tool_use"
    return "unknown"


def _group_lines(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """将 JSONL 行分组: 同 message_id 且连续的 assistant 行合并为一组。

    规则: assistant 行若与前一行同为 assistant 且 message_id 相同,并入同组;
          user 行或 message_id 变化则另起新组。
    """
    groups: List[Dict[str, Any]] = []
    for obj in lines:
        otype = obj.get("type", "unknown")
        if otype == "assistant":
            mid = obj.get("message", {}).get("message_id")
            if (groups and groups[-1]["gtype"] == "assistant"
                    and groups[-1]["mid"] == mid):
                groups[-1]["items"].append(obj)
            else:
                groups.append({"gtype": "assistant", "mid": mid, "items": [obj]})
        else:
            groups.append({"gtype": otype, "mid": None, "items": [obj]})
    return groups


def _merge_assistant_group(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """将同组 assistant 行合并为一条 OpenAI assistant 消息。"""
    msg: Dict[str, Any] = {"role": "assistant"}
    reasoning_parts: List[str] = []
    text_parts: List[str] = []
    tool_calls: List[Dict[str, Any]] = []

    for obj in items:
        content = obj.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for c in content:
            if not isinstance(c, dict):
                continue
            kind = _classify_content_item(c)
            if kind == "thinking":
                reasoning_parts.append(c.get("thinking", ""))
            elif kind == "text":
                text_parts.append(c.get("text", ""))
            elif kind == "tool_use":
                tool_calls.append({
                    "id": c.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": c.get("name", ""),
                        "arguments": json.dumps(c.get("input", {}),
                                                ensure_ascii=False),
                    },
                })

    if reasoning_parts:
        msg["reasoning_content"] = "\n".join(reasoning_parts)
    # content: 有文本则拼接; 仅有 tool_calls 则为 null(OpenAI 标准)
    msg["content"] = "\n".join(text_parts) if text_parts else None
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return msg


def _convert_user_group(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """将 user 行(tool_result)转换为 OpenAI tool 消息(每项一条)。"""
    out: List[Dict[str, Any]] = []
    for obj in items:
        content = obj.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for c in content:
            if not isinstance(c, dict) or "tool_use_id" not in c:
                continue
            out.append({
                "role": "tool",
                "tool_call_id": c.get("tool_use_id", ""),
                "content": c.get("content", ""),
            })
    return out


def convert_trajs_to_openai(trajs_data: Dict[str, Any]) -> Dict[str, Any]:
    """将 trajs.json 完整数据转换为 OpenAI message 格式。"""
    trajectories = trajs_data.get("trajectories", {})
    main_agent = trajectories.get("main_agent", "")
    if not isinstance(main_agent, str) or not main_agent.strip():
        raise ValueError("trajectories.main_agent 为空或非字符串")

    lines = parse_jsonl(main_agent)
    groups = _group_lines(lines)

    messages: List[Dict[str, Any]] = []
    for g in groups:
        if g["gtype"] == "assistant":
            messages.append(_merge_assistant_group(g["items"]))
        else:  # user / 其他 → 尝试按 tool_result 解析
            messages.extend(_convert_user_group(g["items"]))

    result: Dict[str, Any] = {"messages": messages}
    # 保留元数据(不影响 messages 标准 格式)
    metadata = trajs_data.get("metadata")
    if metadata is not None:
        result["metadata"] = metadata
    return result


def action_to_openai(trajs_path: Path, force: bool = False) -> Optional[Path]:
    """动作 1: trajs.json → message.json (标准 OpenAI message 格式)。

    返回输出路径; 失败返回 None。
    """
    out_path = trajs_path.parent / "message.json"
    if out_path.exists() and not force:
        print(f"  [skip] 已存在 {out_path} (--force 覆盖)")
        return out_path

    try:
        trajs_data = json.loads(trajs_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [error] 读取失败 {trajs_path}: {e}", file=sys.stderr)
        return None

    try:
        result = convert_trajs_to_openai(trajs_data)
    except Exception as e:
        print(f"  [error] 转换失败 {trajs_path}: {e}", file=sys.stderr)
        return None

    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    n_msgs = len(result["messages"])
    n_tool = sum(1 for m in result["messages"] if m["role"] == "tool")
    print(f"  [ok] {trajs_path.parent.name}/message.json  "
          f"({n_msgs} 条消息, 含 {n_tool} 条 tool 结果)")
    return out_path


# ==================== 动作 2: dehint (泄漏检测+改写) ====================

# ---- dehint 配置 ----
DEHINT_API_BASE = os.environ.get("DEHINT_API_BASE", "http://127.0.0.1:8765/v1")
DEHINT_API_KEY = os.environ.get("DEHINT_API_KEY", os.environ.get("HUBROUTER_API_KEY", ""))
DEHINT_MODEL = os.environ.get("DEHINT_MODEL", "gpt-6.1-terra")
DEHINT_MAX_RETRIES = int(os.environ.get("DEHINT_MAX_RETRIES", "3"))
DEHINT_RETRY_BACKOFF = 5.0
DEHINT_BATCH_TOKENS = 64_000  # 每批 token 上限(64k, 减小批量提升 LLM 检测彻底度)
DEHINT_CHARS_PER_TOKEN = 2      # 换算: 2 chars = 1 token
DEHINT_BATCH_CHARS = DEHINT_BATCH_TOKENS * DEHINT_CHARS_PER_TOKEN  # ~128k chars
DEHINT_MAX_FIXUP_ROUNDS = int(os.environ.get("DEHINT_MAX_FIXUP_ROUNDS", "3"))  # 替换失败后最大修复轮次

# (LEAK_REGEX 已移除: 泄漏检测完全由 LLM 判断, 不做预先正则过滤)


_LLM_STATS = {"calls": 0, "ok": 0, "fail": 0, "total_time": 0.0}


def _log_llm_stats(prefix: str = ""):
    """输出 LLM 调用累计统计(请求级)。"""
    s = _LLM_STATS
    if s["calls"]:
        log.info("%sLLM 调用统计: 共 %d 次请求 (成功 %d, 失败 %d), LLM 累计耗时 %.1fs",
                 prefix, s["calls"], s["ok"], s["fail"], s["total_time"])


def _http_chat_completion(system_prompt: str, user_prompt: str,
                           max_tokens: int, temperature: float,
                           enable_thinking: bool,
                           request_timeout: int = 600) -> Dict[str, Any]:
    """直接 HTTP 调用 OpenAI 兼容 /chat/completions 接口(标准库 urllib,无第三方依赖)。

    使用 daemon 线程 + join 实现请求级硬超时(socket timeout 对慢速流式响应无效)。
    """
    import urllib.request
    import urllib.error
    import threading
    url = f"{DEHINT_API_BASE.rstrip('/')}/chat/completions"
    payload = {
        "model": DEHINT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {
            "enable_thinking": enable_thinking,
            "clear_thinking": False,
        },
        "allow_external": True,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEHINT_API_KEY}",
        },
    )
    result: Dict[str, Any] = {}

    def _worker():
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                result["data"] = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            result["error"] = e

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(request_timeout)
    if t.is_alive():
        raise TimeoutError(f"HTTP 请求超时 ({request_timeout}s),线程已放弃")
    if "error" in result:
        raise result["error"]
    return result["data"]


def _dehint_call_llm(system_prompt: str, user_prompt: str,
                     max_tokens: int = 131072, temperature: float = 0.3,
                     tag: str = "LLM", enable_thinking: bool = False,
                     finish_reason_out: Optional[list] = None) -> str:
    """调用 LLM(dehint 专用),带指数退避重试。

    tag 用于日志标识调用来源(如 dehint-batch1)。
    enable_thinking 默认关闭: dehint 为抽取型任务,思考会耗尽 max_tokens
                             导致 content 为空(finish_reason=length)。
    finish_reason_out: 若提供 list, 成功返回时将 finish_reason append 进去,
                       供调用方检测输出截断(length)并做自适应拆分。
    """
    last_exc = None
    prompt_chars = len(system_prompt) + len(user_prompt)
    for attempt in range(1, DEHINT_MAX_RETRIES + 1):
        t0 = time.time()
        _LLM_STATS["calls"] += 1
        log.info("[%s] 请求发出: model=%s, prompt=%d chars, max_tokens=%d "
                 "(第 %d/%d 次尝试)", tag, DEHINT_MODEL, prompt_chars, max_tokens,
                 attempt, DEHINT_MAX_RETRIES)
        try:
            body = _http_chat_completion(system_prompt, user_prompt,
                                         max_tokens, temperature, enable_thinking)
            elapsed = time.time() - t0
            choice = body["choices"][0]
            content = choice["message"].get("content") or ""
            finish = choice.get("finish_reason", "unknown")
            usage = body.get("usage", {}) or {}
            tok_in = usage.get("prompt_tokens")
            tok_out = usage.get("completion_tokens")
            log.info("[%s] 响应收到: %.1fs, %d chars, finish=%s%s", tag, elapsed,
                     len(content), finish,
                     f", tokens(in={tok_in}, out={tok_out})" if tok_in is not None else "")
            if not content:
                raise ValueError(f"LLM 返回 content 为空 (finish_reason={finish})")
            content = content.strip()
            # 去掉 <think>...</think> 思考部分
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            if not content:
                raise ValueError("LLM 返回内容去除思考段后为空")
            _LLM_STATS["ok"] += 1
            _LLM_STATS["total_time"] += elapsed
            if finish_reason_out is not None:
                finish_reason_out.append(finish)
            return content
        except Exception as e:
            elapsed = time.time() - t0
            _LLM_STATS["fail"] += 1
            last_exc = e
            log.warning("[%s] 调用失败 (%.1fs, 第 %d/%d 次): %s", tag, elapsed,
                        attempt, DEHINT_MAX_RETRIES, e)
            if attempt < DEHINT_MAX_RETRIES:
                wait = DEHINT_RETRY_BACKOFF * (2 ** (attempt - 1))
                log.info("[%s] %ds 后重试...", tag, int(wait))
                time.sleep(wait)
    raise RuntimeError(f"dehint LLM 调用 {DEHINT_MAX_RETRIES} 次均失败: {last_exc}")


# ---- 块提取 (thinking + text → block) ----

def _extract_blocks(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """从 JSONL 行提取所有 thinking/text 块,附带轮次和类型属性。

    返回: [{"block_id": int, "turn": int, "type": "thinking"|"text",
            "line_idx": int, "content_idx": int, "content": str}]
    turn = assistant 段序号(1-based), 与 leak_review 的 Round 编号一致:
    每当 assistant 行出现在非 assistant 行之后, turn += 1。
    (同一 message_id 可能跨多个 tool_result 段, 不能按 message_id 分组,
     否则 turn 编号会与 leak_review 的 Round 编号错位。)
    """
    blocks: List[Dict[str, Any]] = []
    block_id = 0
    turn = 0
    prev_type: Optional[str] = None
    for line_idx, obj in enumerate(lines):
        otype = obj.get("type", "")
        if otype == "assistant":
            if prev_type != "assistant":
                turn += 1
            prev_type = "assistant"
        elif otype == "user":
            prev_type = "user"
        else:
            continue
        content = obj.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for content_idx, c in enumerate(content):
            if not isinstance(c, dict):
                continue
            for field in ("thinking", "text"):
                text = c.get(field, "")
                if isinstance(text, str) and text.strip():
                    blocks.append({
                        "block_id": block_id, "turn": turn, "type": field,
                        "line_idx": line_idx, "content_idx": content_idx,
                        "content": text,
                    })
                    block_id += 1
    return blocks


# (无预先正则过滤: 泄漏检测完全由 LLM 基于"行为泄漏"理念判断)


# ---- dehint 系统提示词 (检测+改写一体, 基于 review 行为泄漏理念, 单次请求返回 old→new 替换列表) ----

DEHINT_SYSTEM_PROMPT = """You are an expert trajectory sanitization analyst. Your job is to find and rewrite ALL behavioral leakage in an AI agent's problem-solving conversation trace. Be AGGRESSIVE and THOROUGH — missing a leak is far worse than a false positive.

## Background
The agent was secretly given a problem-solving hint (derived from a reference solution) in its system prompt before executing a coding task on a benchmark. The agent must NOT reveal — through its words or thinking — that it received external guidance or that it knows it is being evaluated. Any such revelation is behavioral leakage and MUST be rewritten.

You will receive:
1. The actual Hint text — use it to detect quoted/paraphrased content
2. Text blocks from the agent's conversation trace (thinking and text outputs)

## What counts as a leak — ZERO TOLERANCE

### Category 1: Explicit attribution to external guidance (MUST catch ALL)
ANY sentence mentioning "hint", "reference", "guidance", "guidelines", "clue", "warning", "note", "instruction" as an external information source:
- "the hint says/tells/mentions/states/suggests/implies/provides/indicates ..."
- "the hint's phrasing/wording/guidance/content/statement/mention ..."
- "the reference says/tells/notes/describes/specifies/approach ..."
- "based on the hint/reference/guidelines", "according to the hint", "from the hint", "per hint", "per the hint"
- "That matches the hint", "as the hint suggests", "the hint explicitly mentions ..."
- "the hint was auto-generated", "the hint doc", "hint file", "reference file", "evaluation internals"
- "The task says don't look for the reference file" (mentions reference file)
- Attribution in any language should be treated by the same rule.
RULE: If the word "hint" or "reference" (as external guidance) appears anywhere, it IS a leak. No exceptions.

### Category 2: Evaluation/benchmark awareness (MUST catch ALL)
ANY mention of evaluation infrastructure or benchmark mechanics:
- "hidden tests", "test patch", "hidden test patch", "the tests will be added later"
- "gold patch", "golden diff", "reference solution", "reference implementation"
- "SWE-bench", "benchmark task", "this benchmark", "benchmark author", "benchmark artifacts"
- "derived from a PR", "actual PR", "real upstream commit", "upstream fix"
- "synthetic reference", "synthetic tests", "auto-generated from the diff"
- "the hint is our only source", "evaluation internals"
- "The commits seem artificial (future)" — reveals awareness of benchmark construction
- "Could I inspect the hidden test patch?" — reveals awareness of hidden tests
RULE: If the agent discusses benchmark/evaluation mechanics, it IS a leak.

### Category 3: Quoting or closely paraphrasing hint content (compare against the Hint text!)
You have the actual Hint text. Compare each block against it. Any sentence or distinctive phrase in a block that also appears in the Hint (verbatim or near-verbatim paraphrase) is a leak:
- Verbatim quotes: the agent copied hint sentences word-for-word into its thinking
- Close paraphrases: same technical prescription with minor word changes
- Hint section titles: "Key Location Clues", "Suggested Directions", etc.
- Distinctive technical prescriptions that match the hint but the agent didn't discover through its own code exploration (e.g., exact error message wording, specific design patterns, boundary behavior specifications)
RULE: If content overlaps with the Hint text, it IS a leak. When unsure whether a phrase came from the hint, FLAG IT.

## What is NOT a leak (do NOT rewrite)
- Technical reasoning that the agent derived from its own code exploration ("I found that the parser needs modification", "After examining the code, I believe the error should be fatal")
- Normal code exploration conclusions ("The Parse function is the entry point")
- Generic first-person reasoning ("I believe...", "Let me consider...", "Perhaps...")
- Normal TDD thinking about existing tests in the repo
- The agent's own implementation decisions

## Rewriting principles
For each leak, produce an old→new replacement:

**Category 1 (explicit attribution):** Strip the attribution, keep the technical content:
- "The hint says we should use X" → "Using X is appropriate here"
- "Based on the hint, the error message must be exact" → "The error message must be exact"
- "That matches the hint. Fine — not required." → "" (delete, no technical value)
- "According to the reference, the parser needs changes" → "The parser needs changes"

**Category 2 (evaluation awareness):** Remove the evaluation framing, keep any technical reasoning:
- "The hidden tests will check the error message" → "The error message should be clear and consistent"
- "This benchmark task is derived from a PR" → "" (delete)
- "The hint was likely auto-generated from the diff" → "" (delete)
- "Could I inspect the hidden test patch? Not allowed." → "" (delete)

**Category 3 (hint content quotes):** Repackage as the agent's OWN inference from context and experience. The technical content stays, but it must read as the agent's own deduction, NOT something read from an external document:
- "bind each parameter with var (to create function-local bindings and avoid overwriting outer variables)" → "Based on the code structure, I think we should bind each parameter with var so they're function-local and don't shadow outer variables"
- "errors must be *parser.Error with Fatal=true and the canonical message" → "From my experience with this codebase, the errors should probably be *parser.Error with Fatal=true and use a canonical message"
- "an empty original function body means the last prologue statement becomes the implicit return value — consider a harmless trailing expression statement to preserve nil return" → "Looking at the semantics, an empty function body likely means the last prologue statement becomes the implicit return value, so adding a harmless trailing expression to preserve nil return seems reasonable"
- For long verbatim quotes: wrap with "Based on the context and my experience with similar patterns, ..." or "From what I can infer from the codebase, ..."
- Short technical terms that happen to match (function names, file paths) are NOT leaks — only sentences/prescriptions that were clearly copied from the hint

**General rules:**
- Preserve ALL technical content — only remove the leakage aspect
- Pure-leak sentences with no technical content → "new": "" (empty string, delete)
- Multiple separate leaks in one block → multiple entries with the same block_id
- NEVER alter text that is not a leak
- When in doubt about whether something is a leak, FLAG IT — over-flagging is much better than missing

## Input format
You receive the Hint text first, then text blocks in XML:
<hint>
...the actual hint content, for your reference...
</hint>

<block id="0" turn="1" type="thinking">
...content...
</block>

## Output format
Output ONLY a JSON array — no markdown fences, no explanation, no other text:
[
  {"block_id": 0, "old": "exact text to replace", "new": "replacement text"},
  {"block_id": 3, "old": "...", "new": "..."}
]
"old" MUST be copied character-for-character from the block content (including whitespace). Keep it focused: just the leaking phrase or sentence, not the whole block.
Blocks with NO leak must NOT appear in the output. If no block has any leak, output: []
"""

DEHINT_FIXUP_SYSTEM_PROMPT = """You are an expert trajectory sanitization analyst. Your previous replacement attempts FAILED because the "old" strings were NOT exact substrings of the block content (whitespace, punctuation, or wording differences).

## Leak categories you are fixing (zero tolerance — same as before)
1. Explicit attribution to external guidance: ANY mention of "hint", "reference", "guidance", "guidelines" as external source ("the hint says", "per hint" ...)
2. Evaluation/benchmark awareness: hidden tests, test patch, gold patch, SWE-bench, benchmark, upstream fix, reference solution, "derived from a PR", "evaluation internals" ...
3. Quoting/paraphrasing hint content: sentences that match the provided Hint text (verbatim or near-verbatim) — repackage as the agent's own inference ("Based on the context and my experience, ...")

You also receive the actual Hint text for comparison — use it to identify Category 3 leaks.

## Your task
For each block below, a list of FAILED replacements is attached. Each failed "old" indicates approximately where the leak is, but it does NOT match the block text exactly.

You must:
1. Locate the actual leak text in the block content (use the failed "old" as a rough guide)
2. Copy the EXACT substring from the block content as the new "old" — character-for-character, including all whitespace, newlines, and punctuation
3. Provide the "new" replacement:
   - Category 1/2: strip attribution/evaluation-framing, keep technical content; pure-leak → ""
   - Category 3: repackage as the agent's own inference from context and experience ("Based on the code structure, I think ...", "From my experience with similar patterns, ...")

## CRITICAL rules for "old"
- MUST be an exact substring of the block content — verify character-by-character before outputting
- If the leak spans a newline, include the newline in "old"
- Keep it focused: just the leaking phrase or sentence
- Do NOT paraphrase or "clean up" the text — copy it verbatim

## Output format
Output ONLY a JSON array:
[
  {"block_id": 0, "old": "exact text copied verbatim from block", "new": "replacement"}
]
"""


# ---- 批处理工具 ----

def _make_batches(blocks: List[Dict[str, Any]], max_chars: int) -> List[List[Dict[str, Any]]]:
    """将 blocks 按字符上限分批(每块额外计 100 chars 的 XML 标签开销)。"""
    batches: List[List[Dict[str, Any]]] = []
    cur: List[Dict[str, Any]] = []
    cur_chars = 0
    for b in blocks:
        b_chars = len(b["content"]) + 100
        if cur and cur_chars + b_chars > max_chars:
            batches.append(cur)
            cur, cur_chars = [], 0
        cur.append(b)
        cur_chars += b_chars
    if cur:
        batches.append(cur)
    return batches


def _format_blocks_xml(blocks: List[Dict[str, Any]]) -> str:
    """将 blocks 格式化为 XML 文本(LLM 输入)。"""
    parts: List[str] = []
    for b in blocks:
        parts.append(f'<block id="{b["block_id"]}" turn="{b["turn"]}" type="{b["type"]}">')
        parts.append(b["content"])
        parts.append("</block>")
    return "\n".join(parts)


def _extract_json_from_text(text: str) -> List[Dict[str, Any]]:
    """从 LLM 响应文本中提取 JSON 数组(容忍 markdown 代码围栏和多余文本)。"""
    text = text.strip()
    # 去掉 markdown 代码围栏
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()
    # 直接解析
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    # 括号配对提取第一个完整 JSON 数组
    start = text.find("[")
    if start < 0:
        return []
    depth, in_str, escape = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                try:
                    data = json.loads(text[start:i + 1])
                    if isinstance(data, list):
                        return data
                except json.JSONDecodeError:
                    return []
    return []


# ---- 替换校验与执行 ----

def _validate_replacements(reps: Any, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """校验 LLM 返回的 replacements 结构, 过滤非法项。"""
    valid: List[Dict[str, Any]] = []
    valid_ids = {b["block_id"] for b in batch}
    for rep in (reps if isinstance(reps, list) else []):
        if not isinstance(rep, dict):
            continue
        bid = rep.get("block_id")
        old = rep.get("old")
        new = rep.get("new")
        if bid not in valid_ids:
            log.warning("[dehint] 未知 block_id=%s, 跳过", bid)
            continue
        if not isinstance(old, str) or not old.strip():
            log.warning("[dehint] block_id=%s old 为空, 跳过", bid)
            continue
        if not isinstance(new, str):
            new = str(new) if new is not None else ""
        valid.append({"block_id": bid, "old": old, "new": new})
    return valid


def _apply_replacement(content: str, old: str, new: str) -> Tuple[str, int]:
    """在 content 中将 old 替换为 new, 返回 (新内容, 替换次数)。

    匹配策略(逐级放宽): 精确匹配 → strip 匹配 → 空白归一化模糊匹配。
    """
    # 1. 精确匹配
    if old in content:
        return content.replace(old, new), content.count(old)
    # 2. strip 后匹配
    old_s = old.strip()
    if old_s and old_s in content:
        return content.replace(old_s, new), content.count(old_s)
    # 3. 空白归一化模糊匹配(old 中连续空白可匹配原文任意空白)
    norm_old = re.sub(r"\s+", " ", old_s).strip()
    if norm_old:
        escaped = re.escape(norm_old)
        pattern = escaped.replace("\\ ", " ").replace(" ", "\\s+")
        matches = list(re.finditer(pattern, content))
        if matches:
            result = content
            for m in reversed(matches):
                result = result[:m.start()] + new + result[m.end():]
            return result, len(matches)
    return content, 0


def _dehint_batch(batch: List[Dict[str, Any]], batch_idx: int,
                  n_batches: int, hint_text: str = "",
                  depth: int = 0, side: str = "",
                  debug_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """单批 dehint: 调用 LLM 获取 replacements 列表, 带自适应拆分重试。

    hint_text: hint 原文, 嵌入 <hint> 段供 LLM 对照检测逐字引用(Category 3)。
    depth: 拆分深度(拆半重试时递增, 用于日志 tag)。
    debug_dir: 调试目录, 若提供则保存每批 prompt/response 原文供排查。

    自适应拆分: 当 LLM 调用失败或输出被截断(finish_reason=length)时,
    将批次拆半重试, 避免大批量因输出超限导致整批泄漏被遗漏。
    """
    hint_section = f"<hint>\n{hint_text}\n</hint>\n\n" if hint_text else ""
    user_prompt = hint_section + _format_blocks_xml(batch)
    tag = f"dehint-batch{batch_idx + 1}/{n_batches}"
    if depth:
        tag += f"-sub{depth}"
    turns = [b["turn"] for b in batch]
    dbg_name = f"batch{batch_idx + 1}" + (f"_sub{depth}{side}" if depth else "")
    log.info("[%s] %d 个 block, %d chars (hint=%d chars), turn %d-%d, block_id %d-%d",
             tag, len(batch), len(user_prompt), len(hint_text),
             min(turns), max(turns), batch[0]["block_id"], batch[-1]["block_id"])

    # 保存调试文件: block 清单 + 完整 prompt
    if debug_dir is not None:
        debug_dir.mkdir(parents=True, exist_ok=True)
        block_list = "\n".join(
            f"  block_id={b['block_id']} turn={b['turn']} type={b['type']} "
            f"chars={len(b['content'])}" for b in batch)
        (debug_dir / f"{dbg_name}_blocks.txt").write_text(
            f"# {tag}: {len(batch)} blocks, turn {min(turns)}-{max(turns)}\n"
            f"{block_list}\n", encoding="utf-8")
        (debug_dir / f"{dbg_name}_prompt.txt").write_text(user_prompt, encoding="utf-8")
        log.info("[%s] 调试文件: %s/{%s_blocks.txt, %s_prompt.txt}",
                 tag, debug_dir, dbg_name, dbg_name)

    fr_holder: List[str] = []
    resp: Optional[str] = None
    try:
        resp = _dehint_call_llm(DEHINT_SYSTEM_PROMPT, user_prompt,
                                max_tokens=131072, temperature=0.3,
                                tag=tag, enable_thinking=False,
                                finish_reason_out=fr_holder)
    except Exception as e:
        log.warning("[%s] LLM 调用失败: %s", tag, e)

    # 保存调试文件: LLM 原始响应
    if debug_dir is not None and resp is not None:
        (debug_dir / f"{dbg_name}_response.txt").write_text(resp, encoding="utf-8")

    truncated = bool(fr_holder) and fr_holder[0] == "length"
    valid: List[Dict[str, Any]] = []

    if resp is not None:
        reps = _extract_json_from_text(resp)
        valid = _validate_replacements(reps, batch)
        log.info("[%s] LLM 返回 %d 条 replacement, 校验通过 %d 条%s",
                 tag, len(reps), len(valid),
                 " [输出截断!]" if truncated else "")
        if not truncated:
            return valid  # 正常完成(可能为空 = 真没泄漏)
        if valid:
            log.info("[%s] 截断但已解析 %d 条, 仍拆半重试确保完整", tag, len(valid))

    # LLM 调用失败 或 输出截断 → 拆半重试
    if len(batch) <= 1:
        log.warning("[%s] 单 block 仍无法完成(%s), 放弃该 block",
                    tag, "输出截断" if truncated else "调用失败")
        return []
    mid = len(batch) // 2
    log.info("[%s] 拆分为 %d + %d 个 block 重试", tag, mid, len(batch) - mid)
    left = _dehint_batch(batch[:mid], batch_idx, n_batches, hint_text, depth + 1,
                         "L", debug_dir)
    right = _dehint_batch(batch[mid:], batch_idx, n_batches, hint_text, depth + 1,
                          "R", debug_dir)
    return left + right


def _dehint_fixup(failed: Dict[int, List[Dict[str, str]]],
                  block_by_id: Dict[int, Dict[str, Any]],
                  lines: List[Dict[str, Any]],
                  round_idx: int,
                  hint_text: str = "", depth: int = 0, side: str = "",
                  debug_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """修复轮: 将匹配失败的 block 连同当前内容 + 失败记录重新发给 LLM, 带自适应拆分。

    failed: {block_id: [{"old": ..., "new": ...}, ...]} 匹配失败的替换
    hint_text: hint 原文, 嵌入 <hint> 段供 LLM 对照。
    depth: 拆分深度(拆半重试时递增)。
    返回: 新的 replacements 列表(已校验)。
    """
    parts: List[str] = []
    fixup_batch: List[Dict[str, Any]] = []
    if hint_text:
        parts.append(f"<hint>\n{hint_text}\n</hint>")
    for bid, fails in failed.items():
        block = block_by_id[bid]
        try:
            c = lines[block["line_idx"]]["message"]["content"][block["content_idx"]]
            content = c.get(block["type"], "")
        except (IndexError, KeyError, TypeError):
            log.warning("[fixup-r%d] block_id=%s 无法读取当前内容, 跳过",
                        round_idx, bid)
            continue
        parts.append(f'<block id="{bid}" turn="{block["turn"]}" type="{block["type"]}">')
        parts.append(content)
        parts.append("</block>")
        parts.append(f'<failed_attempts for_block="{bid}">')
        for f_item in fails:
            parts.append(f'- old (NOT FOUND in block): '
                         f'{json.dumps(f_item["old"], ensure_ascii=False)}')
        parts.append("</failed_attempts>")
        fixup_batch.append(block)

    if not fixup_batch:
        return []

    user_prompt = "\n".join(parts)
    tag = f"dehint-fixup-r{round_idx}"
    if depth:
        tag += f"-sub{depth}{side}"
    dbg_name = f"fixup_r{round_idx}" + (f"_sub{depth}{side}" if depth else "")
    log.info("[%s] %d 个 block 待修复, %d chars", tag, len(fixup_batch), len(user_prompt))

    # 保存调试文件: block 清单 + 完整 prompt
    if debug_dir is not None:
        debug_dir.mkdir(parents=True, exist_ok=True)
        block_list = "\n".join(
            f"  block_id={b['block_id']} turn={b['turn']} type={b['type']} "
            f"chars={len(b['content'])}" for b in fixup_batch)
        (debug_dir / f"{dbg_name}_blocks.txt").write_text(
            f"# {tag}: {len(fixup_batch)} blocks\n{block_list}\n",
            encoding="utf-8")
        (debug_dir / f"{dbg_name}_prompt.txt").write_text(user_prompt, encoding="utf-8")
        log.info("[%s] 调试文件: %s/{%s_blocks.txt, %s_prompt.txt}",
                 tag, debug_dir, dbg_name, dbg_name)

    fr_holder: List[str] = []
    resp: Optional[str] = None
    try:
        resp = _dehint_call_llm(DEHINT_FIXUP_SYSTEM_PROMPT, user_prompt,
                                max_tokens=131072, temperature=0.3,
                                tag=tag, enable_thinking=False,
                                finish_reason_out=fr_holder)
    except Exception as e:
        log.warning("[%s] LLM 调用失败: %s", tag, e)

    # 保存调试文件: LLM 原始响应
    if debug_dir is not None and resp is not None:
        (debug_dir / f"{dbg_name}_response.txt").write_text(resp, encoding="utf-8")

    truncated = bool(fr_holder) and fr_holder[0] == "length"
    valid: List[Dict[str, Any]] = []

    if resp is not None:
        reps = _extract_json_from_text(resp)
        valid = _validate_replacements(reps, fixup_batch)
        log.info("[%s] LLM 返回 %d 条, 校验通过 %d 条%s",
                 tag, len(reps), len(valid),
                 " [输出截断!]" if truncated else "")
        if not truncated:
            return valid

    # 截断或失败 → 拆半重试
    if len(failed) <= 1:
        log.warning("[%s] 单 block 仍无法完成(%s), 放弃",
                    tag, "输出截断" if truncated else "调用失败")
        return valid
    items = list(failed.items())
    mid = len(items) // 2
    log.info("[%s] 拆分为 %d + %d 个 block 重试", tag, mid, len(items) - mid)
    left = _dehint_fixup(dict(items[:mid]), block_by_id, lines, round_idx,
                         hint_text, depth + 1, "L", debug_dir)
    right = _dehint_fixup(dict(items[mid:]), block_by_id, lines, round_idx,
                          hint_text, depth + 1, "R", debug_dir)
    return left + right


# ---- 后置泄漏审查 (dehint 后验证改写效果) ----

DEHINT_REVIEW_SYSTEM_PROMPT = """You are an expert code review analyst. Your task is to audit an AI agent's problem-solving trajectory that has been SANITIZED to remove hint references, checking for any REMAINING behavioral leakage of the hint.

You will receive three pieces of context:
1. **Compressed Trajectory** — the agent's full conversation (thinking, text, tool calls, truncated tool results), organized in rounds. This trajectory has already been processed to remove explicit hint references, but some may have been missed.
2. **Hint** — a problem-solving guidance document that was injected into the agent's system prompt before execution.
3. **Golden Diff** — the reference (ground-truth) patch that would correctly solve the task.

The hint is intentionally derived from the golden diff — that is by design and NOT a problem. Your ONLY concern is BEHAVIORAL leakage: does the agent, through its own words or actions, still reveal that it received external guidance?

**Behavioral leakage** covers:
- The agent's text outputs or thinking explicitly mention receiving a hint/reference/guidance (e.g., "the hint says", "the reference tells me", "based on the guidelines", "the clue says", "the warning says", "the note says", "the instruction says", "the task says", "as suggested", "per the hint", "gold patch", "test patches", "hidden tests", "SWE benchmark").
- The agent proactively reads the hint file itself inside the container (e.g., `cat /tmp/hint_compact.md`).
- The agent quotes hint content verbatim with attribution to an external source.

NOT a leak: technical reasoning that aligns with the hint direction; normal code analysis; generic first-person reasoning.

Analyze carefully and answer ALL THREE questions below. For each question you MUST cite specific evidence from the trajectory (quote exact thinking excerpts or text outputs, and reference the Round number).

---

## Question 1: Did the trajectory use the hint's information or solution steps?

Examine whether the agent's actions align with specific directions mentioned in the hint. Conclude with: **USED / PARTIALLY USED / NOT USED**.

## Question 2: Does the agent still reveal (to the user) that it had hint information? (Behavioral leakage — text/thinking)

Check if ANY text output or thinking still mentions external guidance. This is the core question — even one remaining hint reference means the sanitization failed. Conclude with: **OBVIOUS / SUBTLE / NOT_REVEALED**.

## Question 3: Did the agent proactively read the hint file itself inside the container? (Behavioral leakage — file access)

Check if the agent used any tool to read the hint file. Conclude with: **YES / NO**.

---

## Output Format Requirements

Your response must contain TWO parts:

**Part 1 — Detailed Analysis (in English):**
Answer all three questions with detailed evidence, structured with clear headings (Question 1 / Question 2 / Question 3). Always cite specific Round numbers and quote evidence. For Question 2, list EVERY remaining hint reference you find with its exact text and Round number.

**Part 2 — Structured JSON (in English, at the very end):**
After your detailed analysis, output a JSON code block (```json ... ```) with EXACTLY the following fields:

```json
{
  "used_hint": "USED | PARTIALLY_USED | NOT_USED",
  "used_hint_evidence": "one-sentence summary of the strongest evidence",
  "revealed_hint": "OBVIOUS | SUBTLE | NOT_REVEALED",
  "revealed_hint_evidence": "one-sentence summary of the strongest evidence, or 'No leakage found' if NOT_REVEALED",
  "read_hint_file": "YES | NO",
  "read_hint_file_evidence": "the exact Round and command if YES, otherwise 'N/A'",
  "overall_leakage_risk": "HIGH | MEDIUM | LOW",
  "remaining_leaks": [{"round": 1, "text": "exact quote of remaining leak", "type": "thinking|text"}],
  "developer_note": "2-3 sentence overall assessment for the developer: does the sanitization successfully remove all hint references? List any remaining issues."
}
```

The `remaining_leaks` array must contain EVERY remaining hint reference found (empty array if none). The `overall_leakage_risk` is:
- **HIGH**: remaining OBVIOUS leaks exist (explicit hint/reference mentions).
- **MEDIUM**: only SUBTLE leaks remain (suspicious patterns but no explicit mention).
- **LOW**: no behavioral leakage detected.
"""


def _truncate_middle(text: str, keep: int) -> str:
    """保留前后 keep 字符, 中间用省略标记替代。"""
    if not text or len(text) <= keep * 2:
        return text
    omitted = len(text) - keep * 2
    return f"{text[:keep]}\n... [TRUNCATED: omitted {omitted} chars] ...\n{text[-keep:]}"


def _compress_messages_for_review(result: Dict[str, Any],
                                  tool_result_keep: int = 500) -> Tuple[str, Dict[str, int]]:
    """将 OpenAI message 格式(改写后)压缩为 markdown, 供泄漏审查 LLM 输入。"""
    messages = result.get("messages", [])
    stats: Dict[str, int] = {"total_messages": len(messages)}
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
            for tc in (msg.get("tool_calls") or []):
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
                    f"### [Assistant] Tool Call: {tool_name}\n```json\n{args_str}\n```\n")
        elif role == "tool":
            content = msg.get("content", "")
            result_str = _truncate_middle(content, tool_result_keep)
            md_parts.append(f"### [User] Tool Result\n{result_str}\n")
            in_round = False
        else:
            md_parts.append(
                f"### [{role}] Unknown\n{json.dumps(msg, ensure_ascii=False)[:500]}\n")

    md_text = "\n".join(md_parts)
    stats["rounds"] = round_num
    stats["compressed_chars"] = len(md_text)
    return md_text, stats


def _extract_review_json(text: str) -> Tuple[Optional[Dict], str]:
    """从 LLM 输出中提取最后一个 ```json ... ``` 代码块并解析。

    返回 (parsed_dict_or_None, markdown_without_json_block)。
    """
    pattern = r"```json\s*(.*?)\s*```"
    matches = list(re.finditer(pattern, text, flags=re.DOTALL))
    if not matches:
        bare = re.search(r"(\{.*\})", text, flags=re.DOTALL)
        if bare:
            try:
                parsed = json.loads(bare.group(1))
                if isinstance(parsed, dict):
                    return parsed, text[:bare.start()].rstrip()
            except json.JSONDecodeError:
                pass
        return None, text
    last = matches[-1]
    try:
        parsed = json.loads(last.group(1))
    except json.JSONDecodeError as e:
        log.warning("[leak-review] JSON 块解析失败: %s", e)
        return None, text
    if not isinstance(parsed, dict):
        return None, text
    return parsed, text[:last.start()].rstrip()


def _find_hint_files(trajs_path: Path) -> Tuple[Optional[Path], Optional[Path]]:
    """从 trajs.json 路径推导 hint .md 和 golden_diff.diff 路径。

    路径模式:
      trajs: .../{xxxx_r{y}}/infer_logs/{instance_id}/turn_{turn}/trajs.json
      hint:  .../{xxxx}/hint_gen/{instance_id}/hint_compact_r{y}.md (优先) 或 hint.md
      diff:  .../{xxxx}/hint_gen/{instance_id}/golden_diff.diff

    run_name 带 _r{y} 后缀时, hint 在去掉后缀的外层 xxxx 目录的 hint_gen 中;
    无后缀时在 run_name 自身目录的 hint_gen 中找。
    """
    turn_dir = trajs_path.parent            # turn_N/
    instance_dir = turn_dir.parent           # {instance_id}/
    infer_logs_dir = instance_dir.parent     # infer_logs/
    run_name_dir = infer_logs_dir.parent     # {xxxx_r{y}}/
    output_dir = run_name_dir.parent         # deepswe-output/
    instance_id = instance_dir.name
    run_name = run_name_dir.name

    # 解析 run_name: "lisen_hard_by_hint_r1" → base="lisen_hard_by_hint", round=1
    m = re.match(r"^(.+?)_r(\d+)$", run_name)
    if m:
        base_name, round_num = m.group(1), int(m.group(2))
        hint_base_dir = output_dir / base_name
    else:
        base_name, round_num = run_name, None
        hint_base_dir = run_name_dir

    hint_gen_dir = hint_base_dir / "hint_gen" / instance_id
    if not hint_gen_dir.is_dir():
        log.warning("[leak-review] hint_gen 目录不存在: %s", hint_gen_dir)
        return None, None

    # 查找 hint .md (优先级: hint_compact_r{y}.md > hint_compact.md > hint.md > 任意 hint*.md)
    hint_path = None
    candidates: List[Path] = []
    if round_num is not None:
        candidates.append(hint_gen_dir / f"hint_compact_r{round_num}.md")
    candidates.extend([
        hint_gen_dir / "hint_compact.md",
        hint_gen_dir / "hint.md",
    ])
    for c in candidates:
        if c.is_file():
            hint_path = c
            break
    if hint_path is None:
        for md in sorted(hint_gen_dir.glob("hint*.md")):
            if "output" not in md.name.lower() and "meta" not in md.name.lower():
                hint_path = md
                break
    if hint_path is None:
        log.warning("[leak-review] 未找到 hint .md 文件: %s", hint_gen_dir)
        return None, None

    diff_path = hint_gen_dir / "golden_diff.diff"
    diff = diff_path if diff_path.is_file() else None
    return hint_path, diff


def _run_leak_review(result: Dict[str, Any], trajs_path: Path,
                     out_dir: Path) -> Optional[Dict[str, Any]]:
    """dehint 后置泄漏审查: 压缩改写后轨迹 + hint + golden diff → LLM 审查残留泄漏。

    输出 leak_review.md / leak_review.json 到 out_dir。
    返回 review_json (失败返回 None)。
    """
    hint_path, diff_path = _find_hint_files(trajs_path)
    if hint_path is None:
        log.warning("[leak-review] 跳过: 未找到 hint .md 文件")
        return None

    # 1. 压缩轨迹
    compressed, stats = _compress_messages_for_review(result)
    log.info("[leak-review] 轨迹压缩: %d rounds, %d chars",
             stats.get("rounds", 0), len(compressed))

    # 2. 读取 hint 和 golden diff (diff 缺失时用空串, 不跳过审查)
    hint_text = hint_path.read_text(encoding="utf-8", errors="replace")
    diff_text = (diff_path.read_text(encoding="utf-8", errors="replace")
                 if diff_path else "")
    if diff_path is None:
        log.warning("[leak-review] golden_diff.diff 未找到, 审查将继续(无 diff 对照)")

    # 3. 构建 prompt
    user_prompt = (
        f"# Compressed Trajectory\n\n{compressed}\n\n---\n\n"
        f"# Hint (injected into agent's system prompt)\n\n{hint_text}\n\n---\n\n"
        f"# Golden Diff (reference solution)\n\n```diff\n{diff_text}\n```\n\n---\n\n"
        f"Please answer the three review questions based on the above context. "
        f"Write your detailed analysis in English with clear headings "
        f"(Question 1 / Question 2 / Question 3), always citing specific Round numbers and "
        f"quoting evidence. Then at the very end, output the structured JSON "
        f"block as specified in the system prompt."
    )
    log.info("[leak-review] prompt 总长: %d chars (traj=%d, hint=%d, diff=%d)",
             len(user_prompt), len(compressed), len(hint_text), len(diff_text))

    # 4. 调用 LLM
    resp = _dehint_call_llm(DEHINT_REVIEW_SYSTEM_PROMPT, user_prompt,
                            max_tokens=32000, temperature=0.3,
                            tag="leak-review", enable_thinking=False)

    # 5. 提取 JSON
    review_json, review_md = _extract_review_json(resp)

    # 6. 写出
    md_path = out_dir / "leak_review.md"
    json_path = out_dir / "leak_review.json"
    reviewed_path = out_dir / "message.json"  # 实际审查的是改写后的 message.json
    header = (
        f"<!--\n"
        f"  reviewed: {reviewed_path}  (改写后轨迹, 实际审查对象)\n"
        f"  source_trajs: {trajs_path}  (原始轨迹, 仅用于定位 hint)\n"
        f"  hint: {hint_path}\n"
        f"  golden_diff: {diff_path}\n"
        f"  model: {DEHINT_MODEL}\n"
        f"  mode: post-dehint leak review\n"
        f"  stats: {json.dumps(stats, ensure_ascii=False)}\n"
        f"-->\n\n"
    )
    md_path.write_text(header + review_md, encoding="utf-8")
    log.info("[leak-review] 写出 %s (%d chars)", md_path, len(review_md))

    if review_json is not None:
        review_json["_meta"] = {
            "reviewed": str(reviewed_path),
            "source_trajs": str(trajs_path),
            "hint": str(hint_path),
            "golden_diff": str(diff_path),
            "model": DEHINT_MODEL,
            "stats": stats,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        json_path.write_text(
            json.dumps(review_json, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("[leak-review] 写出 %s", json_path)
        log.info("[leak-review] revealed_hint=%s, overall_leakage_risk=%s, "
                 "remaining_leaks=%d",
                 review_json.get("revealed_hint"),
                 review_json.get("overall_leakage_risk"),
                 len(review_json.get("remaining_leaks", [])))
    else:
        log.warning("[leak-review] 未能提取结构化 JSON, 仅保存 markdown")
    return review_json


def action_dehint(trajs_path: Path, force: bool = False) -> Optional[Path]:
    """动作 2: dehint — 检测并改写轨迹中的 hint 泄漏, 输出到 dehint/ 子目录。

    新方案流程:
      1. 提取所有 thinking/text 为 XML block(带 block_id/turn/type 属性)
      1.5 读取 hint 原文, 嵌入每批 prompt 供 LLM 对照检测逐字引用
      2. 按 64k token 上限(≈192k chars)分批
      3. 每批单次 LLM 请求(含 hint 原文), 返回 old→new 替换列表(JSON, 无泄漏的 block 不出现)
      4. 脚本根据返回执行精确替换, 匹配失败时发起修复轮重新请求 LLM
      5. 后置泄漏审查: LLM 审查改写后轨迹的残留泄漏

    输出(dehint/ 子目录):
      - message.json      : 改写后轨迹的 OpenAI message 格式
      - dehint_report.json: 改写明细(含 leak_review 摘要)
      - leak_review.md    : 后置泄漏审查详细分析(中文)
      - leak_review.json  : 后置泄漏审查结构化结果(英文)

    不加 --force 时: 若 message.json 已存在, 跳过替换步骤, 直接运行泄漏审查。
    返回 dehint 目录路径; 失败返回 None。
    """
    out_dir = trajs_path.parent / "dehint"
    report_path = out_dir / "dehint_report.json"
    msg_path = out_dir / "message.json"

    # 已有 message.json 且不加 --force → 跳过替换, 直接运行泄漏审查
    if msg_path.exists() and not force:
        print(f"  [skip] 已存在 {msg_path}, 跳过替换, 直接运行泄漏审查 (--force 重新替换)")
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            result = json.loads(msg_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [error] 读取已有 message.json 失败: {e}", file=sys.stderr)
            return None
        try:
            review_json = _run_leak_review(result, trajs_path, out_dir)
            if review_json is not None and report_path.exists():
                report = json.loads(report_path.read_text(encoding="utf-8"))
                report["leak_review"] = {
                    "revealed_hint": review_json.get("revealed_hint"),
                    "overall_leakage_risk": review_json.get("overall_leakage_risk"),
                    "remaining_leaks_count": len(review_json.get("remaining_leaks", [])),
                }
                report_path.write_text(
                    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            log.warning("[leak-review] 审查失败: %s", e)
        return out_dir

    dehint_t0 = time.time()
    log.info("dehint 开始: %s", trajs_path)
    log.info("dehint 配置: model=%s, base=%s, 批量上限=%d tokens (≈%d chars)",
             DEHINT_MODEL, DEHINT_API_BASE, DEHINT_BATCH_TOKENS, DEHINT_BATCH_CHARS)

    # 1. 读取并解析 trajs
    try:
        trajs_data = json.loads(trajs_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [error] 读取失败 {trajs_path}: {e}", file=sys.stderr)
        return None
    main_agent = trajs_data.get("trajectories", {}).get("main_agent", "")
    if not isinstance(main_agent, str) or not main_agent.strip():
        print(f"  [error] trajectories.main_agent 为空: {trajs_path}", file=sys.stderr)
        return None
    lines = parse_jsonl(main_agent)

    # 1.5 读取 hint 原文 (供 LLM 对照检测逐字引用)
    hint_path, _ = _find_hint_files(trajs_path)
    hint_text = ""
    if hint_path:
        try:
            hint_text = hint_path.read_text(encoding="utf-8", errors="replace")
            log.info("hint 原文: %s (%d chars), 将嵌入每批 prompt 供 LLM 对照",
                     hint_path, len(hint_text))
        except Exception as e:
            log.warning("读取 hint 失败 (%s): %s, Category 3 检测将降级", hint_path, e)
    else:
        log.warning("未找到 hint 文件, Category 3 (逐字引用) 检测将降级为纯语义判断")

    # 2. 提取 blocks
    blocks = _extract_blocks(lines)
    if not blocks:
        log.warning("未提取到任何 thinking/text block, 跳过 dehint")
        return None
    total_chars = sum(len(b["content"]) for b in blocks)
    log.info("提取 %d 个 block (thinking=%d, text=%d), 共 %d chars",
             len(blocks),
             sum(1 for b in blocks if b["type"] == "thinking"),
             sum(1 for b in blocks if b["type"] == "text"),
             total_chars)

    # 2.5 创建调试目录, 记录全局 block 清单 (block_id → turn/type/chars 映射)
    debug_dir = out_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    all_blocks_txt = "\n".join(
        f"  block_id={b['block_id']} turn={b['turn']} type={b['type']} "
        f"chars={len(b['content'])} line_idx={b['line_idx']} content_idx={b['content_idx']}"
        for b in blocks)
    (debug_dir / "all_blocks.txt").write_text(
        f"# 全部 {len(blocks)} 个 block (共 {total_chars} chars)\n"
        f"# block_id → turn/type/chars/line_idx/content_idx 映射\n"
        f"{all_blocks_txt}\n", encoding="utf-8")
    log.info("调试目录: %s (全局 block 清单 all_blocks.txt + 每批 prompt/response)",
             debug_dir)

    # 3. 分批
    batches = _make_batches(blocks, DEHINT_BATCH_CHARS)
    log.info("分为 %d 批 (批量上限 %d chars)", len(batches), DEHINT_BATCH_CHARS)

    # 4. 逐批调用 LLM 获取 replacements
    all_reps: List[Dict[str, Any]] = []
    for i, batch in enumerate(batches):
        try:
            reps = _dehint_batch(batch, i, len(batches), hint_text=hint_text,
                                 debug_dir=debug_dir)
            all_reps.extend(reps)
        except Exception as e:
            log.error("[dehint-batch%d/%d] 失败, 跳过该批: %s",
                      i + 1, len(batches), e)

    if not all_reps:
        log.info("未发现任何 hint 泄漏 (LLM 返回 0 条 replacement)")
    else:
        log.info("共获取 %d 条 replacement", len(all_reps))

    # 5. 执行替换 + 失败修复循环(匹配失败不跳过, 重新请求 LLM 给出精确 old)
    block_by_id = {b["block_id"]: b for b in blocks}
    applied, failed = 0, 0
    block_changes: Dict[int, List[Dict[str, Any]]] = {}   # bid -> [{old,new,round,status}]
    block_applied_count: Dict[int, int] = {}               # bid -> 累计成功次数

    # pending: {block_id: [{"old":..., "new":...}, ...]} 当前待应用的替换
    pending: Dict[int, List[Dict[str, str]]] = {}
    for rep in all_reps:
        pending.setdefault(rep["block_id"], []).append(
            {"old": rep["old"], "new": rep["new"]})

    round_idx = 0
    while pending:
        next_pending: Dict[int, List[Dict[str, str]]] = {}
        for bid, reps in pending.items():
            block = block_by_id[bid]
            line_idx, content_idx = block["line_idx"], block["content_idx"]
            field = block["type"]
            try:
                c = lines[line_idx]["message"]["content"][content_idx]
            except (IndexError, KeyError, TypeError):
                log.warning("[dehint] block_id=%s 定位失败 (line=%s, idx=%s)",
                            bid, line_idx, content_idx)
                failed += len(reps)
                continue
            modified = c.get(field, "")
            block_applied = 0
            remaining: List[Dict[str, str]] = []
            for r in reps:
                modified, n = _apply_replacement(modified, r["old"], r["new"])
                status = "applied" if n > 0 else "failed"
                block_changes.setdefault(bid, []).append(
                    {"old": r["old"], "new": r["new"],
                     "round": round_idx, "status": status})
                if n > 0:
                    applied += n
                    block_applied += n
                else:
                    remaining.append(r)
            if block_applied > 0:
                c[field] = modified
                block_applied_count[bid] = block_applied_count.get(bid, 0) + block_applied
            if remaining:
                next_pending[bid] = remaining

        pending = next_pending
        round_idx += 1

        if not pending:
            break

        failed_count = sum(len(v) for v in pending.values())
        if round_idx > DEHINT_MAX_FIXUP_ROUNDS:
            log.warning("修复已达上限 %d 轮, 仍有 %d 条替换未匹配, 放弃",
                        DEHINT_MAX_FIXUP_ROUNDS, failed_count)
            failed += failed_count
            break

        log.info("第 %d 轮替换后仍有 %d 个 block 的 %d 条替换未匹配, 发起修复请求...",
                 round_idx, len(pending), failed_count)
        try:
            fixup_reps = _dehint_fixup(pending, block_by_id, lines, round_idx,
                                       hint_text=hint_text, debug_dir=debug_dir)
            if not fixup_reps:
                log.warning("[fixup-r%d] LLM 未返回有效替换, 放弃剩余 %d 条",
                            round_idx, failed_count)
                failed += failed_count
                break
            pending = {}
            for rep in fixup_reps:
                pending.setdefault(rep["block_id"], []).append(
                    {"old": rep["old"], "new": rep["new"]})
        except Exception as e:
            log.error("[fixup-r%d] 修复请求失败: %s, 放弃剩余 %d 条",
                      round_idx, e, failed_count)
            failed += failed_count
            break

    log.info("替换完成: 成功 %d 处, 失败 %d 处 (共 %d 轮, 含 %d 轮修复)",
             applied, failed, round_idx, max(0, round_idx - 1))

    # 5.5 保存替换汇总: 每个 block 的处理状态 (方便从 leak_review round 反查)
    summary_lines: List[str] = [
        f"# 替换汇总: {len(blocks)} blocks, {len(block_changes)} 有泄漏, "
        f"applied={applied} failed={failed}"]
    for b in blocks:
        bid = b["block_id"]
        if bid in block_changes:
            n_req = len(block_changes[bid])
            n_app = block_applied_count.get(bid, 0)
            status = "applied" if n_app >= n_req else f"partial({n_app}/{n_req})"
            summary_lines.append(
                f"  block_id={bid} turn={b['turn']} type={b['type']} "
                f"status={status} n_requested={n_req} n_applied={n_app}")
        else:
            summary_lines.append(
                f"  block_id={bid} turn={b['turn']} type={b['type']} "
                f"status=no_replacement (LLM 未检出泄漏)")
    (debug_dir / "replacements_summary.txt").write_text(
        "\n".join(summary_lines) + "\n", encoding="utf-8")
    log.info("替换汇总: %s/replacements_summary.txt", debug_dir)

    # 构建 details
    details: List[Dict[str, Any]] = []
    for bid, changes in block_changes.items():
        block = block_by_id[bid]
        details.append({
            "block_id": bid, "turn": block["turn"], "type": block["type"],
            "n_requested": len(changes),
            "n_applied": block_applied_count.get(bid, 0),
            "changes": changes,
        })

    # 6. 重建 JSONL 并更新 trajs_data
    new_jsonl = "\n".join(json.dumps(obj, ensure_ascii=False) for obj in lines)
    trajs_data["trajectories"]["main_agent"] = new_jsonl

    # 7. 转换为 OpenAI 格式 → dehint/message.json
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = convert_trajs_to_openai(trajs_data)
    except Exception as e:
        print(f"  [error] 转换 OpenAI 格式失败: {e}", file=sys.stderr)
        return None
    msg_path = out_dir / "message.json"
    msg_path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    log.info("写出 %s (%d 条消息)", msg_path, len(result["messages"]))

    # 8. 写 dehint_report.json
    elapsed = time.time() - dehint_t0
    report = {
        "source": str(trajs_path),
        "model": DEHINT_MODEL,
        "blocks_total": len(blocks),
        "blocks_with_leaks": len(block_changes),
        "replacements_requested": applied + failed,
        "replacements_applied": applied,
        "replacements_failed": failed,
        "fixup_rounds": max(0, round_idx - 1),
        "batches": len(batches),
        "elapsed_seconds": round(elapsed, 1),
        "details": details,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    # 9. 后置泄漏审查 (改写后轨迹 → LLM 审查残留泄漏, 输出 leak_review.md/json)
    try:
        review_json = _run_leak_review(result, trajs_path, out_dir)
        if review_json is not None:
            report["leak_review"] = {
                "revealed_hint": review_json.get("revealed_hint"),
                "overall_leakage_risk": review_json.get("overall_leakage_risk"),
                "remaining_leaks_count": len(review_json.get("remaining_leaks", [])),
            }
            report_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log.warning("[leak-review] 审查失败(不影响 dehint 产物): %s", e)

    _log_llm_stats()
    print(f"  [ok] {trajs_path.parent.name}/dehint/  "
          f"({len(blocks)} blocks, {len(block_changes)} 有泄漏, "
          f"{applied} 处替换, {failed} 失败, {elapsed:.0f}s)")
    return out_dir


# ==================== 动作注册表 ====================

ACTIONS = {
    "to_openai": action_to_openai,
    "dehint": action_dehint,
}


# ==================== 主流程 ====================

def process_file(trajs_path: Path, actions: List[str], force: bool) -> bool:
    """对单个 trajs.json 依次执行动作。"""
    print(f"[process] {trajs_path}")
    ok = True
    for act_name in actions:
        fn = ACTIONS.get(act_name)
        if fn is None:
            print(f"  [error] 未知动作: {act_name} (可用: {', '.join(ACTIONS)})",
                  file=sys.stderr)
            ok = False
            continue
        ret = fn(trajs_path, force=force)
        if ret is None:
            ok = False
    return ok


def main():
    parser = argparse.ArgumentParser(
        description="轨迹后处理流水线: 对 trajs.json 执行一系列转换动作",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", required=True,
                        help="trajs.json 文件路径,或包含 trajs.json 的目录(递归)")
    parser.add_argument("--actions", default="to_openai",
                        help=f"执行动作,逗号分隔 (可用: {', '.join(ACTIONS)})")
    parser.add_argument("--force", action="store_true",
                        help="覆盖已存在的输出文件")
    args = parser.parse_args()

    input_path = Path(args.input)
    try:
        trajs_files = find_trajs_files(input_path)
    except FileNotFoundError as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(2)

    if not trajs_files:
        print(f"[error] 未找到 trajs.json: {input_path}", file=sys.stderr)
        sys.exit(2)

    actions = [a.strip() for a in args.actions.split(",") if a.strip()]
    print(f"共 {len(trajs_files)} 个 trajs.json, 动作: {actions}")

    succeeded = 0
    for tf in trajs_files:
        if process_file(tf, actions, args.force):
            succeeded += 1

    _log_llm_stats("全局 ")
    print(f"\n完成: {succeeded}/{len(trajs_files)} 成功")
    sys.exit(0 if succeeded == len(trajs_files) else 1)


if __name__ == "__main__":
    main()