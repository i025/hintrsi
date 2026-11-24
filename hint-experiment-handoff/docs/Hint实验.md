# Hint实验

## 1. 最终结果

以deepswe中的题目为例子，直接rollout为baseline，加入hint rollout作为对比，从通过率50%（避免偶现已经多次rollout） -> 90%，详情如下：

![Baseline vs Hint 对比报告](Hint实验_assets/baseline-vs-hint.png)

整体链路类似于：

**Hint Loop**

![Hint Loop](Hint实验_assets/hint-loop.svg)

代码在：[http://xingyun.jd.com/codingRoot/coding-ai/cc-run/tree/hint/benchmark/deepswe](http://xingyun.jd.com/codingRoot/coding-ai/cc-run/tree/hint/benchmark/deepswe)

启动脚本：`run_loop_by_hint.py`

## 2. 如何加入Hint更好

尝试多种方式之后，使用Agent方式加入Hint是效果最好的

简单理解就是：**拿着golden patch真正去仓库中apply一次，记录关键的注意事项**

### 2.1. 原始Hint

需要包含完整信息，得到类似于：（问题本质、关键文件与位置、解题思路、解题木舟、易错点和注意事项）

**Prompt**

```text
你是一个资深代码审查专家和技术指导。你的任务是分析一个 bug 修复的参考实现(golden diff),结合对代码库的实际探索,生成一份详细的解题指导文档,帮助另一位开发者独立完成同样的修复。

【工作原则】
- 自由使用文件读取、代码搜索、终端命令等工具探索代码库,这是你获取准确信息的方式
- 这是分析任务:不要修改任何源代码文件,不要执行 git checkout/reset/commit 等改变代码库状态的命令
- 分析必须基于实际代码:先读代码再下结论,不要凭空猜测
- 指导要具体:指明文件路径、函数名、结构体/接口名、关键代码位置
- 指导要有条理:按步骤组织,每步说明做什么、为什么
- 不要直接粘贴大段修复代码:描述修改的逻辑和方向,让开发者自己实现

【输出格式】
最终输出一份 markdown 格式的解题指导文档,包含以下部分:

### 问题本质
2-3 句话说明 bug 的根本原因:什么数据、在哪个环节、出了什么问题。

### 关键文件与位置
列出需要修改的所有文件,以及每个文件中需要关注的具体位置(函数名/结构体/接口名)。
注意:golden diff 涉及的每个文件都必须列出,不要遗漏;同时说明每个文件在整体修复中的角色。

### 解题思路
说明修复的整体思路和设计:
- 为什么要这样改(修复前的问题机制)
- 各处改动之间的逻辑关系(哪些是核心修复,哪些是配套调整)
- 修复后数据如何正确流动

### 解题步骤
分步实现指导,每步说明:
- 在哪个文件的哪个位置改
- 改什么(描述逻辑和方向,不必给完整代码)
- 为什么这样改

### 易错点与注意事项
列出:
- 容易遗漏的改动点(尤其是需要同步修改的关联代码)
- 边界情况和特殊场景
- 容易踩的坑(如并发、空值、状态清理等)

将完整文档写入 /tmp/hint_output.md,同时在最终回复中输出文档全文。
```

输出类似于：

[hint.md](Hint实验_assets/hint.md)（30.68 KB）

### 2.2. 压缩Hint

完整Hint不适合放入System Prompt，需要压缩下，保留核心内容，并且给出使用Guidelines

**Prompt**

```text
You are a problem-solving hint compressor. Your task is to compress a detailed problem-solving guide into a concise directional hint, to serve as internal reference in the system prompt of another AI coding assistant. Output must be in English.

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
```

**Guidelines**

```text
[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.
```

核心点：

1. 要求模型不能无故出现特定文件、目录等内容，需要先探索到了，再使用对应线索
2. 模型输出不包含“hint says”这种直白内容，变成类似于
    1. "I found that xxx is the key location"
    2. "Based on the clues I noticed xxx"
    3. "After browsing the code I believe xxx"

> 但是实践下来，发现模型缺失非常难完全遵守...

压缩完成后，就可以直接放入System Prompt中，例如：cc的system reminder

类似于：

[hint_compact_r1.md](Hint实验_assets/hint_compact_r1.md)（5.68 KB）

## 3. Rollout

这部分就直接rollout，并且评测

## 4. 轨迹分析，并“补充Hint”

1. 分析轨迹有没有使用Hint的信息、思路
2. 轨迹有没有泄漏Hint内容
3. 轨迹为什么没有解出题目，哪些地方有欠缺

**Prompt**

````text
You are an expert code review analyst. Your task is to analyze an AI agent's problem-solving trajectory and determine whether it effectively used a provided hint, and diagnose why it failed.

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
````

将 **欠缺部分的信息 **补充到 压缩Hint 的输入中，形成新的 压缩Hint，放入到System Prompt中

> \*这里的Loop对应开头表格中的“尝试次数”

## 5. DeHint

多次尝试，仍不可避免在轨迹中会泄漏Hint相关内容（实际上是大量泄漏，8/10会出现泄漏）

### 5.1. 简单方案

轨迹后处理是比较简单的方案

**Prompt**

```text
You are an expert trajectory sanitization analyst. Your job is to find and rewrite ALL behavioral leakage in an AI agent's problem-solving conversation trace. Be AGGRESSIVE and THOROUGH — missing a leak is far worse than a false positive.

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
- Chinese: "根据提示", "提示说/指/要/提", "根据参考", "参考文档"
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
- "根据提示,需要修改解析器" → "需要修改解析器"

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
```

常见的3类泄漏及修改示例：

```text
**Category 1 (explicit attribution):** Strip the attribution, keep the technical content:
- "The hint says we should use X" → "Using X is appropriate here"
- "Based on the hint, the error message must be exact" → "The error message must be exact"
- "That matches the hint. Fine — not required." → "" (delete, no technical value)
- "根据提示,需要修改解析器" → "需要修改解析器"

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
```

### 5.2. 根治方案

![Hint 中三类信息及泄漏根因](Hint实验_assets/hint-information-types.png)

需要在Rollout的Hint生成部分做更多的工作，关键点在：

- 上述Hint只解释了，“应该怎么解”题目，并没有解释“为什么”这样解决，这样的解法如何推导得到的
    - 导致模型无可奈何，只能遵循约定先探索探索仓库结构、文件、部分代码之后，就强行引入结论

---
