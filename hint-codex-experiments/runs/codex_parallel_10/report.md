# Codex Hint 正式实验报告

更新时间：2026-11-23 00:08:57（北京时间）。
状态：stopped；模型：gpt-6.1-terra；思考强度：low。

用量以桥接逐请求原始记录为准；SDK 汇总不重复相加。
未上报 token 的请求：4；这些请求的消耗未知。

## 解题结果

各组首轮与累计结果分开统计。未完成和未跑满轮次不等同正常失败。

| 组别 | 协议题数 | 已尝试题数 | 首轮通过 | 累计通过 | 跑满仍失败题数 | 未完成尝试 | 尚未结束题数 |
|---|---:|---:|---:|---:|---:|---:|---:|
| B | 10 | 2 | 0 | 0 | 1 | 1 | 9 |
| H | 9 | 0 | 0 | 0 | 0 | 0 | 9 |
| M | 9 | 0 | 0 | 0 | 0 | 0 | 9 |
| I | 10 | 1 | 1 | 1 | 0 | 0 | 9 |

B：无指导；H：原框架对齐版；M：教师会话连续；I：增加轮内指导。

| 组别 | 第1轮累计 | 第2轮累计 | 第3轮累计 | 第4轮累计 | 第5轮累计 |
|---|---:|---:|---:|---:|---:|
| B | 0 | 0 | 0 | 0 | 0 |
| H | 0 | 0 | 0 | 0 | 0 |
| M | 0 | 0 | 0 | 0 | 0 |
| I | 1 | 1 | 1 | 1 | 1 |

进行中或因额度停止时，累计通过是已观察到的数量；尚未执行的尝试不计为失败。每轮覆盖题数见 metrics.json。

## 共同首轮与失败后分支

H/M 策略指标引用同一个共同首轮，结果相关，不是两个独立样本。共同首轮占各自最多5轮中的第1轮；实际学生执行和费用仅计一次，不生成独立M1记录。

| v2计划题数 | 实际共同学生执行 | 已正式评测 | 首轮通过 | 首轮未解出 | 未完成 | 尚未评测 |
|---:|---:|---:|---:|---:|---:|---:|
| 9 | 0 | 0 | 0 | 0 | 0 | 9 |

共同首轮通过后，保留一次H成功轨迹审查作为共享诊断，H/M均停止；M教师记忆机制未触发。首轮未解出时，H新教师与M原教师复盘同一轨迹，后续学生从第2轮各自独立执行。

以下分支统计仅以共同首轮正常未解出的题为条件，不包含共同首轮通过、未完成或尚未执行的题。

| 分支 | 可进入题数 | 已执行后续尝试 | 已尝试题数 | 后续通过题数 | 跑满仍失败 | 未完成尝试 | 尚未结束 |
|---|---:|---:|---:|---:|---:|---:|---:|
| H | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| M | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

v1过渡题（anko-default-function-arguments）保留真实历史结果，排除在上述v2 H/M策略及条件分支统计之外；B/I仍按其真实尝试统计。

旧批用户取消的1次尝试单列在 excluded_prior_attempt_metrics.csv，没有正式成绩，不计正常失败，也不充当共同首轮。

## 实际 Token 与模型请求耗时

缓存输入包含在输入内，推理输出包含在输出内；总量采用模型返回的 totalTokens，不重复相加。

| 归属 | 输入 | 缓存输入 | 输出 | 推理输出 | 总 Token | 请求耗时（秒） | 请求错误数 |
|---|---:|---:|---:|---:|---:|---:|---:|
| B | 25709 | 0 | 86 | 0 | 25795 | 12.51 | 0 |
| 共享初始教师与首轮压缩（仅计一次） | 1402993 | 155008 | 12016 | 101 | 1415009 | 542.49 | 11 |

本次报告覆盖的实际总量：1440804 Token；模型请求耗时合计 555.00 秒。
共享初始产物只计一次；M 后续复盘归 M。分摊表若启用，仅供比较，不再加入实际总量。
请求耗时是各请求耗时之和，不能当作系统墙钟。Codex exec 耗时包含进程启动和一次决策，不含原 SDK 在两次请求之间执行工具的时间。
学生整次流程墙钟、SDK 解题墙钟、教师等待和扣除等待后的时间分列在 attempt_metrics.csv；缺失数据保留为空。

## 阶段与数据边界

各任务、组别、角色、阶段的明细见 token_usage_by_stage.csv；每次教师决定见原始 progress.jsonl。
预检、联调和正式实验的 Token 分开列在 metrics.json.bridge_scope_totals；成绩仅使用当前状态中的真实尝试及明确引用的共同首轮。

用量按指定桥接目录中的 experiment/session 归集；导入成绩保留 origin_experiment。新批日志不含旧调用时，下表不补记旧批费用，旧费用须查看原日志。

| 实际调用来源 | 总Token |
|---|---:|
| codex_parallel_10 | 0 |
| codex_parallel_10_lane0 | 535079 |
| codex_parallel_10_lane1 | 221998 |
| codex_parallel_10_lane2 | 204840 |
| codex_parallel_10_lane3 | 25795 |
| codex_parallel_10_lane4 | 162577 |
| codex_parallel_10_lane5 | 290515 |
当前日志中归属于旧批用户取消尝试的 0 Token 已包含在上述实际总量内，不计入成绩；原日志中的历史总额另存。
v1/v2的费用归属另见 metrics.json.protocol_group_totals，避免将过渡题费用用于v2分支效果比较。

## 按题并行与来源

本次按题固定分配6路，每路独立运行原有题内流程；实际学生与教师仍为8CPU/128GiB。Anko保留旧批已完成结果，其余九题各执行一次，不跨路复用学生代码。
本并行段新增实际用量：1440804 Token。本版只汇总指定桥接目录中的调用；Anko 等历史观察的费用保留在旧日志，不自动并入新批用量。
各路共用账户额度和宿主机；整批墙钟、每次SDK/有效时间、教师等待须分别解释，不能把并行墙钟当作纯模型提速。

| 路 | 实验 | 固定题目 | 状态 |
|---:|---|---|---|
| 0 | codex_parallel_10_lane0 | claude-code-by-agents-recursive-delegation, termenv-preserve-ansi-resets | stopped |
| 1 | codex_parallel_10_lane1 | igel-persist-feature-schema, textual-kitty-key-phases | stopped |
| 2 | codex_parallel_10_lane2 | ink-grid-box-layout, valibot-recursive-schema-composition | running |
| 3 | codex_parallel_10_lane3 | kea-atomic-signal-selectors | stopped |
| 4 | codex_parallel_10_lane4 | obsidian-linter-auto-table-of-contents | stopped |
| 5 | codex_parallel_10_lane5 | sqlfmt-create-table-ddl-formatting | stopped |
未提供可核对的货币账单，因此不换算美元费用。

停止原因：Save and stop parallel10 startup: structured action arguments contain invalid nested JSON escapes. No live code edits or automatic rerun; preserve traces and observed costs for diagnosis.
