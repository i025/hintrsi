# 九题六路并行实验 09：修正多工具传输

> 当前暂停启动：用户要求扩大正式重测前的接入与并行检查。下文是原09候选的冻结说明；最终候选、检查结果和是否启动将另行更新。原09还未运行正式题目。

2026-11-22，用户已同意保存并停止 08，统一应用已经离线验证的多工具传输修复，再重新运行 Anko 之外的九题。准备和验证阶段不启动正式模型、实验服务或容器；主线程完成旧批保存及最后核查后启动。

## 唯一生产变化

`source_parallel_09/` 直接复制 `source_parallel_08_static/`，只替换 `codex_cli_bridge.py` 的 `_sse`。08 将多个工具调用放在同一个数据块，实际 LiteLLM 1.81.8 转换器会把多个工具的参数拼到首个工具中。09 分别发送正文，并让每个工具调用独占一个数据块；工具顺序、ID、名称、参数、finish 和 usage 保持不变。

全部 18 个 SDK 工具从首次请求起展示的设置继续保留。没有修改 Prompt、工具 schema、模型、GT、评分、预算或资源，也没有使用另行准备的 `source_parallel_08/` 恢复实现。此次修复仅处理多工具 SSE 拼接。08 已观察到：原生学生主动调用 `wait(terminate=true)` 取消工具等待后，SDK 命令可能继续运行，晚到的回执没有进入原生模型历史。09 没有修改这一行为，应随轨迹注明，不能声称与原 API 的所有工具等待和取消语义完全相同；这不是固定 300 秒超时，也不因此修改模型或 Prompt。

## 控制变量

- 全部角色使用 `gpt-6.1-terra`、推理强度 `low`；题目与模型 Prompt 沿用 08。
- 六套既有 VM，每套 8 vCPU / 144 GiB，共 48 vCPU；学生和教师仍为 8 CPU / 128 GiB，评测容器 8 GiB。
- 固定队列：lane0 Claude Code → Termenv；lane1 Igel → Textual；lane2 Ink → Valibot；lane3 Kea；lane4 Obsidian Linter；lane5 SQLfmt。
- B、H、M、I 各最多 5 轮，通过后停止。H/M 共用一次实际首轮；共同失败后 H 使用新教师复盘，M 使用本批初始教师同一会话复盘；后续学生仍从新环境和新会话开始。
- I 每 20 次主要工具调用检查一次，最多 3 次，每条指导最多 100 词。学生有效时限 7200 秒、教师 3600 秒、单次轮内教师检查 600 秒。
- SDK、CLI、JIT、工具执行位置、网络限制、教师代码只读设置、题内组顺序及额度停止规则均保持原设定。

## 结果和费用边界

09 九题重新生成 Hint 和学生尝试，不导入 08 的成绩、补丁或教师会话。08 正常完成评测继续作为带有已知传输限制的观察结果保留；技术中断单列。旧结果不会被新结果覆盖。Anko 继续保留 03/04 的 7 次完成评测，属于早期过渡条件，不声称与 09 九题条件完全一致。

07 的 Ink I1 仅补评测结果仍单列：F2P 0/25，P2P 49/49，未解出；不纳入 09 新九题。其他旧批的成绩和消耗同样保留。08 的三份已导出补丁仅补评测，汇总另见 `runs/codex_parallel_08_eval_recovery/summary.json`，不导入 09 九题成绩。

09 正式输出为 `runs/codex_parallel_09/`。原 `logs/bridge/token_usage.jsonl` 继续追加；09 新增 token 与之前累计量分别记录。08 停止后历史累计为 79,067,226 token，其中桥账本 79,054,655、独立早期 CLI 验证 12,571；08 自身新增 39,160,506，不重复累加继承的 Anko；模拟测试和实施对话不算实验模型用量。

## 验证及冻结材料

- 原 106 项离线测试全部通过（6.688 秒）：`preflight/offline_tests_parallel_09.json`。
- 六路九题编排演练通过（15.68 秒）：`preflight/parallel_09_dryrun_result.json`；占位成绩不纳入实验。
- 已完成的实际 LiteLLM + 原 streaming_fix 验证：`preflight/parallel_08_multitool_fix/result.json`，覆盖正文、单工具、三工具、正文加工具、Unicode/转义参数、usage 和 finish；7 种用例通过。另有 25 项相关回归通过。原转换器对纯空正文的既有关闭行为记录为限制，本次不扩大修复。
- 真实 SDK 多工具禁网模拟验证通过：`preflight/parallel_09_sdk_multitool_gate/attempt_03/`。容器内直接 HTTP 入口实时调用实际 LiteLLM 转换器和原 streaming_fix，再交给真正 SDK 执行；初始及同会话恢复阶段共 6 个工具成功，正文、参数和写入内容正确，18 项工具定义稳定，容器已删除。没有使用预转换响应替代，没有真实模型调用。此验证不包含完整代理 CLI 的启动；`attempt_01/02` 的代理 CLI 冷启动失败记录保留。最终规范结果见该目录的 `result.json` 与 `host_result.json`。
- 配置与差异：`reports/parallel_09_config.json`、`reports/parallel_09_source_changes.diff`、`reports/parallel_09_changed_files.json`。
- 源码及操作归档：`reports/parallel_09_snapshot.json`，不使用哈希。
- 启动入口：`preflight/launch_parallel_09.py`；旧服务关闭前证据在 `preflight/parallel_09_service_shutdown/`，启动器先另存再创建新服务。

所有验证均为零真实模型调用。本文描述冻结前准备状态，正式启动时间以 `logs/codex_parallel_09_process.json` 为准。
