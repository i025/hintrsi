# Codex Hint 正式实验报告

更新时间：2026-11-22 16:12:12（北京时间）。
状态：stopped；模型：gpt-6.1-terra；思考强度：low。

## 解题结果

各组首轮与累计结果分开统计。未完成和未跑满轮次不等同正常失败。

| 组别 | 协议题数 | 已尝试题数 | 首轮通过 | 累计通过 | 跑满仍失败题数 | 未完成尝试 | 尚未结束题数 |
|---|---:|---:|---:|---:|---:|---:|---:|
| B | 10 | 7 | 1 | 1 | 1 | 3 | 8 |
| H | 9 | 6 | 1 | 1 | 0 | 2 | 8 |
| M | 9 | 6 | 1 | 1 | 0 | 1 | 8 |
| I | 10 | 7 | 1 | 1 | 0 | 0 | 9 |

B：无指导；H：原框架对齐版；M：教师会话连续；I：增加轮内指导。

| 组别 | 第1轮累计 | 第2轮累计 | 第3轮累计 | 第4轮累计 | 第5轮累计 |
|---|---:|---:|---:|---:|---:|
| B | 1 | 1 | 1 | 1 | 1 |
| H | 1 | 1 | 1 | 1 | 1 |
| M | 1 | 1 | 1 | 1 | 1 |
| I | 1 | 1 | 1 | 1 | 1 |

进行中或因额度停止时，累计通过是已观察到的数量；尚未执行的尝试不计为失败。每轮覆盖题数见 metrics.json。

## 共同首轮与失败后分支

H/M 策略指标引用同一个共同首轮，结果相关，不是两个独立样本。共同首轮占各自最多5轮中的第1轮；实际学生执行和费用仅计一次，不生成独立M1记录。

| v2计划题数 | 实际共同学生执行 | 已正式评测 | 首轮通过 | 首轮未解出 | 未完成 | 尚未评测 |
|---:|---:|---:|---:|---:|---:|---:|
| 9 | 6 | 5 | 1 | 4 | 1 | 4 |

共同首轮通过后，保留一次H成功轨迹审查作为共享诊断，H/M均停止；M教师记忆机制未触发。首轮未解出时，H新教师与M原教师复盘同一轨迹，后续学生从第2轮各自独立执行。

以下分支统计仅以共同首轮正常未解出的题为条件，不包含共同首轮通过、未完成或尚未执行的题。

| 分支 | 可进入题数 | 已执行后续尝试 | 已尝试题数 | 后续通过题数 | 跑满仍失败 | 未完成尝试 | 尚未结束 |
|---|---:|---:|---:|---:|---:|---:|---:|
| H | 4 | 1 | 1 | 0 | 0 | 1 | 4 |
| M | 4 | 0 | 0 | 0 | 0 | 0 | 4 |

v1过渡题（anko-default-function-arguments）保留真实历史结果，排除在上述v2 H/M策略及条件分支统计之外；B/I仍按其真实尝试统计。

旧批用户取消的1次尝试单列在 excluded_prior_attempt_metrics.csv，没有正式成绩，不计正常失败，也不充当共同首轮。

## 实际 Token 与模型请求耗时

缓存输入包含在输入内，推理输出包含在输出内；总量采用模型返回的 totalTokens，不重复相加。

| 归属 | 输入 | 缓存输入 | 输出 | 推理输出 | 总 Token | 请求耗时（秒） | 请求错误数 |
|---|---:|---:|---:|---:|---:|---:|---:|
| B | 13005824 | 12561152 | 46406 | 9334 | 13052230 | 1323.52 | 0 |
| H | 2883018 | 2660608 | 23068 | 1058 | 2906086 | 567.08 | 2 |
| H/M共同首轮及共享成功审查（仅计一次） | 13210358 | 12885120 | 40910 | 5726 | 13251268 | 1167.52 | 0 |
| I | 14286880 | 12046208 | 64602 | 5346 | 14351482 | 1688.45 | 0 |
| M | 651627 | 538368 | 11329 | 71 | 662956 | 218.67 | 0 |
| 旧批用户取消尝试（仅计费用） | 1257198 | 1211904 | 4797 | 830 | 1261995 | 115.03 | 0 |
| 共享初始教师与首轮压缩（仅计一次） | 1697523 | 1394560 | 23675 | 58 | 1721198 | 563.02 | 0 |

本次报告覆盖的实际总量：47207215 Token；模型请求耗时合计 5643.28 秒。
共享初始产物只计一次；M 后续复盘归 M。分摊表若启用，仅供比较，不再加入实际总量。
请求耗时是各请求耗时之和，不能当作系统墙钟；Codex 轮次耗时包含工具等待，不能当作纯推理时间。
学生整次流程墙钟、SDK 解题墙钟、教师等待和扣除等待后的时间分列在 attempt_metrics.csv；缺失数据保留为空。

## 阶段与数据边界

各任务、组别、角色、阶段的明细见 token_usage_by_stage.csv；每次教师决定见原始 progress.jsonl。
预检、联调和正式实验的 Token 分开列在 metrics.json.bridge_scope_totals；成绩仅使用当前状态中的真实尝试及明确引用的共同首轮。

续接批次按原始 experiment/session 归集，源批与当前批各计一次；导入成绩保留 origin_experiment，轨迹与轮内检查按原会话读取。

| 实际调用来源 | 总Token |
|---|---:|
| codex_formal_03 | 5136005 |
| codex_formal_04 | 2910704 |
| codex_parallel_08 | 0 |
| codex_parallel_08_lane0 | 8188611 |
| codex_parallel_08_lane1 | 7709745 |
| codex_parallel_08_lane2 | 6625609 |
| codex_parallel_08_lane3 | 4871887 |
| codex_parallel_08_lane4 | 6250434 |
| codex_parallel_08_lane5 | 5514220 |
旧批用户取消尝试的 1261995 Token 已包含在上述实际总量内，不计入成绩。
v1/v2的费用归属另见 metrics.json.protocol_group_totals，避免将过渡题费用用于v2分支效果比较。

## 按题并行与来源

本次按题固定分配6路，每路独立运行原有题内流程；实际学生与教师仍为8CPU/128GiB。Anko保留旧批已完成结果，其余九题各执行一次，不跨路复用学生代码。
本并行段新增实际用量：39160506 Token。上文报告总量还覆盖明确承接的历史来源，不能再次与旧批总量相加。
各路共用账户额度和宿主机；整批墙钟、每次SDK/有效时间、教师等待须分别解释，不能把并行墙钟当作纯模型提速。

| 路 | 实验 | 固定题目 | 状态 |
|---:|---|---|---|
| 0 | codex_parallel_08_lane0 | claude-code-by-agents-recursive-delegation, termenv-preserve-ansi-resets | stopped |
| 1 | codex_parallel_08_lane1 | igel-persist-feature-schema, textual-kitty-key-phases | stopped |
| 2 | codex_parallel_08_lane2 | ink-grid-box-layout, valibot-recursive-schema-composition | stopped |
| 3 | codex_parallel_08_lane3 | kea-atomic-signal-selectors | stopped |
| 4 | codex_parallel_08_lane4 | obsidian-linter-auto-table-of-contents | stopped |
| 5 | codex_parallel_08_lane5 | sqlfmt-create-table-ddl-formatting | stopped |
独立 CLI 预检另记录 12571 Token、8.555451058782637 秒，未计入本实验总量。
未提供可核对的货币账单，因此不换算美元费用。

停止原因：User authorized preserving and stopping parallel08, then restarting all nine tasks with the verified multi-tool SSE compatibility fix. Preserve all observations, interrupted artifacts, teacher sessions and usage separately.
