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
DEFAULT_API_BASE = os.environ.get("HINT_API_BASE", "http://hubrouter.jd.com/v1")
DEFAULT_API_KEY = os.environ.get("HINT_API_KEY", os.environ.get("HUBROUTER_API_KEY", ""))
DEFAULT_MODEL = os.environ.get("HINT_MODEL", "Qwen3.6-35B-A3B")
DEFAULT_PROVIDER = "openai"
MAX_RETRIES = int(os.environ.get("HINT_MAX_RETRIES", "3"))
RETRY_BACKOFF_BASE = 5.0

# ==================== Prompt 模板 ====================

SYSTEM_PROMPT = """你是一个真实用户，刚跑完验收测试，正在聊天工具里给开发者发反馈消息。

【你的角色】
你就是提需求的人，你不懂代码细节，你只关心需求有没有被满足。你刚跑完验收测试，发现核心功能还是不行，有点失望也有点疑惑，随手在聊天里给开发者发了几句话。

【口吻要求——这是最重要的】
你要写得像微信/钉钉里随手敲的消息，不是正式文档。具体要求：
- 就是几句话连着说，想到哪说到哪，不要分点、不要编号、不要列表。
- 用口语表达，比如"我跑了下验收"、"还是不行啊"、"你看看是不是"、"感觉"、"好像"、"对了还有"、"我琢磨着"。
- 可以带点情绪和随意感，比如"有点奇怪"、"不太对劲"、"搞不懂为什么"。
- 可以用疑问句收尾，比如"是不是哪里没接上？"、"会不会是时机的问题？"。
- 句子之间不用逻辑连接词，不要"首先/其次/最后/总之"。

【绝对禁止的写法】
- 禁止出现"提示"、"建议"、"总体评价"、"验收结论"这类书面词。
- 禁止编号列表（1. 2. 3.）和任何 markdown 格式（加粗、标题、代码块）。
- 禁止"我建议你检查..."这种正式句式，改成"你看看..."、"会不会是..."。
- 禁止长篇大论，控制在 3-8 句话以内。

【内容红线——绝不能违反】
- 不能出现具体的测试用例标识：测试函数名、测试数据原文、期望值原文、断言代码原文。这些是你的内部信息。
- 可以（且应该）用你自己的话描述失败的行为方向，让开发者知道问题到底出在哪。比如：
  - 可以说："换个 id 重新发起请求的时候，第一段数据好像丢了，后面拼上去的是对的但前面那段没了"
  - 可以说："流式响应那个入口和 live 会话那个入口，读出来的参数也都是空的，不只是聊天那个入口"
  - 可以说："参数读出来是 nil，感觉压根没填充进去"
  - 不能说："TestXxx 期望 Args 包含 location 字段但实际是 nil"（这是测试细节原文）
- 如果某个功能面（比如某个入口、某个场景）测试全挂了，你应该明确告诉开发者那个功能面不行，不要笼统地说"还是不行"。
- 引导开发者自己定位根因，不要直接给修改方案或代码答案。
- 全部使用中文。

【与上一轮反馈的关系】
- 你之前已经给过反馈了（见下方"之前几轮的反馈"）。如果问题没变，不要重复上轮的原话，要往更具体的方向说。
- 如果上轮猜的方向被证明是对的/错的，你可以调整说法。比如上轮说"状态没清干净"，但这次发现其实是"清得太狠了把正常数据也清了"，就换一种说法。
- 每轮反馈都要比上轮更具体、更聚焦，帮助开发者缩小排查范围。

【输出格式】
直接输出消息内容，就是纯文本的几句话，不要加任何开头结尾、不要加格式。"""

USER_PROMPT_TEMPLATE = """## 任务需求（原始需求文档）
{problem_statement}

## 本次提交概况
{patch_summary}

## 验收测试结果
{eval_summary}

## 开发者的最终总结
{model_summary}

## 之前几轮的反馈（你之前发给开发者的消息）
{previous_hints}

请基于以上信息，像真实用户在聊天里那样给开发者发几句反馈。记住：不能透露测试函数名/数据原文/期望值原文，但要用你自己的话把失败的行为方向说清楚、说具体，不要笼统。如果之前几轮说过类似的话，这次要换个更具体的说法。"""


# ==================== 上下文收集 ====================

def analyze_patch(patch_path: Path) -> str:
    """分析 patch.diff，提取新建/修改文件列表及规模。"""
    if not patch_path.exists():
        return "(未找到 patch.diff)"

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
        lines.append("新建文件:")
        for f in new_files:
            lines.append(f"  - {f}")
    if modified_files:
        lines.append("修改的已有文件:")
        for f in modified_files:
            lines.append(f"  - {f}")
    if not modified_files:
        lines.append("修改的已有文件: 无")
    return "\n".join(lines) if lines else "(patch 为空)"


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
        return "(未找到 eval_result.json)"

    data = json.loads(eval_path.read_text(encoding="utf-8"))
    lines = []
    lines.append(f"核心功能测试 (f2p): {data.get('f2p_passed', '?')}/{data.get('f2p_total', '?')} 通过")
    lines.append(f"回归测试 (p2p): {data.get('p2p_passed', '?')}/{data.get('p2p_total', '?')} 通过")
    if "partial" in data:
        lines.append(f"部分得分: {data.get('partial')}")
    if "reward" in data:
        lines.append(f"总奖励: {data.get('reward')}")

    # 提取全部失败块供 reviewer 分析失败模式（reviewer 会将其翻译为行为方向，不直接透露测试标识）
    stdout_tail = data.get("stdout_tail", "")
    if stdout_tail:
        fail_blocks = extract_failure_blocks(stdout_tail)
        if fail_blocks:
            lines.append("\n测试失败详情（供你内部分析失败模式，输出提示时严禁直接引用测试函数名/数据原文/期望值原文）:")
            lines.append("```\n" + fail_blocks + "\n```")
    return "\n".join(lines)


def load_problem_statement(parquet_path: Path, instance_id: str) -> str:
    """从 parquet 加载题目原文。"""
    import pandas as pd
    df = pd.read_parquet(parquet_path)
    matches = df[df["instance_id"] == instance_id]
    if matches.empty:
        return f"(未在 {parquet_path} 中找到 {instance_id})"
    return str(matches.iloc[0]["problem_statement"])


def extract_model_summary(trajs_path: Path) -> str:
    """从 extracted_trajs.json 提取模型最终总结。"""
    if not trajs_path.exists():
        return "(未找到 extracted_trajs.json)"
    try:
        data = json.loads(trajs_path.read_text(encoding="utf-8"))
        # 结构: main_agent 列表，取最后一条的 result_msg / message
        main = data.get("main_agent", [])
        if not main:
            return "(轨迹中无 main_agent 记录)"
        for item in reversed(main):
            msg = item.get("result_msg") or item.get("message") or ""
            if msg and len(msg.strip()) > 10:
                return msg.strip()[:2000]
        return "(未找到有效总结)"
    except Exception as e:
        return f"(读取轨迹失败: {e})"


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
        previous_hints="(独立运行模式，无前轮反馈)" if args.round <= 1
                       else f"(独立运行模式，当前第 {args.round} 轮，前轮反馈未传入)",
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