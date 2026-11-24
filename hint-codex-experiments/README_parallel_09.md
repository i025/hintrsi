# 09 重测前审计：尚未达到原 API 等价要求

2026-11-22，09 正式实验没有启动。用户要求既检查 CLI 接入与并行兼容，也核对最原始 API key 框架的一致性。当前结论是：若干传输故障已有通过验证的修复，但不能把当前 CLI 接入称为原 API 的等价替换。

## 原 API 与当前 CLI 的差异

| 检查项 | 原始 API 框架 | 当前 CLI 接入 | 结论 |
|---|---|---|---|
| 模型输入历史 | 每次请求携带 SDK 当前完整消息 | 主要向持久 native 会话追加新用户输入和工具结果；后续 system/assistant 改写不完整同步 | 不等价 |
| 长会话压缩 | SDK 摘要后发送替换后的消息历史 | SDK 与 Codex 管理两份历史；SDK 压缩后可能分裂会话或中止 M 教师 | 未解决 |
| 采样与输出参数 | 原代码发送 temperature、top_p、max_tokens 等参数 | 桥没有将这些字段映射给 CLI，仅固定 Terra/low | 不等价 |
| 工具实际执行 | Claude SDK 在题目容器执行 | 同一 SDK 执行路径；实际代理链路的读写、失败回执和续聊已验证 | 已验证局部一致 |
| 模型工具调度 | 一次模型响应给出工具调用，SDK 执行后发下一次请求 | Codex Code Mode 还会调用内部 exec/wait；按待处理队列分批交付外部请求 | 调度边界不同 |
| 取消及晚回执 | API 响应中的操作由 SDK 执行后回传 | 修复可接回被 native 提前取消的结果，但可能增加一次 native 继续生成 | 兼容补救，不是完全等价 |
| 系统提示与工具呈现 | 每次请求传递 SDK 系统提示；原代码未关闭延迟工具发现 | 初次建立 native 指令并附加桥接说明；工具提前展示已获用户同意；native 调度说明仍存在 | 不能称逐字/逐项一致 |
| 用量统计 | API 返回每次请求的 usage | 使用 native 累计增量；模拟 native 压缩的 usage 未进入累计事件 | 不声称涵盖全部压缩推理成本 |
| 历史版本 | 交接包依赖表不是历史版本锁文件 | 当前 SDK 0.2.186、捆绑 CLI 2.1.329、Codex 0.163.0 | 历史运行版本不能倒推 |

08 的 777 个真实请求均仍携带采样字段：temperature 为 1.0（759 次）或 0.3（18 次），top_p=0.95 出现 759 次，max_tokens 分别为 65536/16384/2048/1024/32000。字段存在不代表 CLI 已采用，也不能据此证明历史 API 服务确实采用了每一个参数；可以确认当前桥没有映射它们。

关闭 SDK 自动压缩、改由 Codex 单独压缩的方案**没有采用**。默认 SDK 的自动压缩已在禁网假 API 下复现；关闭开关会改变原行为，不能作为等价修复。每次 SDK 请求重建 native 上下文也是尚未验证的替代设计，不能先用来重跑九题。

用户已明确授权的实验扩展——Terra、英文提示、B 最多五次、M/I、新的 H/M 共用首轮、六路运行和静态工具呈现——单独作为已知协议变化记录。这些授权不意味着其他输入、采样或会话差异可以省略。

## 已完成的故障修复与验证

独立候选为 `source_parallel_09_checked/`，只合并桥接层修改，未部署到正式服务；最原始交接目录和此前冻结的 `source_parallel_09/` 保持不变。

- 多工具 SSE 分块修复，避免转换器把不同操作的参数拼接。
- SDK 重发同一请求时重放原响应，恢复遗漏交付的工具，不重复执行、不重复累计 token。
- 正确处理 Codex 的 `willRetry=true` 通知；真正失败和额度停止仍保留原逻辑。
- 用实际工具回执接回被 native 取消的等待，并记录恢复事件；这可能增加 native 轮次及用量。
- 禁用意外附加的宿主机内置技能说明。没有修改用户全局配置，没有新增哈希验证或通用防御框架。

合并后 **143 项检查通过**（8.43 秒），所有生产模块实际从 checked 候选加载。另用真实 Codex 进程、本机模拟响应通过 6 个独立会话、12 个 native turn、36 个外部工具请求的隔离检查；这项探针使用直接动态工具模式，Code Mode 取消场景另有真实 CLI 探针。实际完整 LiteLLM CLI→原 streaming_fix→SDK 的 9 次工具调用、失败回执和同会话恢复也已验证，但该检查用的是初始09 SSE候选，并非最终合并候选的完整双 SDK 并发验证。

这些通过项证明其各自覆盖范围，**不代表原 API 等价验收通过**。合并候选的完整双 SDK 并发检查暂缓；先解决当前实验协议的差异。全部本轮审计调用均为本机模拟响应，真实实验模型调用为 **0**，模拟 usage 不写入正式实验账本。

历史桥日志共107,221行，精确扫描未发现 native 压缩开始或完成事件，08也为0。压缩 usage 未进入累计的现象来自本轮模拟探针，不能据此推断旧实验漏记了多少 token。原79,067,226仍是现有实验与早期CLI探针账本记录的合计，不是费用账单。最终状态核查：09运行目录不存在，未部署候选进程，六套VM内运行容器均为0；既有停止容器和结果继续保留。

## 证据与下一步边界

- [完整原 API 对照与审计状态](reports/parallel_09_api_equivalence.json)
- [143 项合并检查及实际模块路径](preflight/parallel_09_combined_audit/continuation/all_tests.json)
- [六路真实 CLI 隔离检查](preflight/parallel_09_combined_audit/native_bridge/result.json)
- [SDK 压缩实证与原版源码对照](preflight/parallel_09_compaction_audit/audit.json)
- [native 压缩与统计边界](preflight/parallel_09_native_compaction_audit/result.json)
- [合并桥接差异](preflight/parallel_09_combined_audit/bridge.diff)

在历史、采样、压缩和工具协议差异解决或被明确接受为新的实验条件前，09 不具备按“原 API 等价替换”启动的条件。没有更换为另一个后端，也没有开始正式重测。

---

## 以下是追加审计前的 09 候选冻结说明（未执行）

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
