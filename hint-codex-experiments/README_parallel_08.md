# 九题六路并行实验 08：统一展示 SDK 工具

2026-11-22，用户已接受统一工具配置并重新运行 Anko 之外的九题。本批准备完成后由主线程启动；本文件生成时尚未启动正式实验。

07 因 SDK 在会话中通过 ToolSearch 增加工具定义而停止，已有原生线程不能直接加入这些新工具。08 将全部可用 SDK 工具从首次请求起统一提供，学生与教师使用相同设置。这会改变模型最初看见的工具列表，因此九题作为新批次重新采样，07 的结果和用量单独保留。

## 唯一生产代码变化

`source_parallel_08_static/` 直接复制冻结的 `source_parallel_07/`，只在 `run_cc_sdk.py::create_agent_options` 的既有 `env` 中添加 `"ENABLE_TOOL_SEARCH": "false"`。其余生产文件逐字节相同。真实 SDK 验证首次阶段及同会话后续阶段都提供相同的 18 个工具，没有延迟工具。

本候选不包含 `source_parallel_08/` 中另行准备的恢复代码。08 不复用 07 的初始 Hint、学生代码或 M 教师原生会话。07 的五个教师会话及备份继续保留，不把新会话描述为旧会话续接。

## 实验设置

- 模型：所有角色继续使用 `gpt-6.1-terra`、推理强度 `low`；题目、模型 Prompt、GT、评分程序均沿用 07。
- 六套原 VM，各 8 vCPU、144 GiB，共 48 vCPU；每套学生及教师仍为 8 CPU / 128 GiB，评测容器内存 8 GiB。
- 固定队列：lane0 Claude Code → Termenv；lane1 Igel → Textual；lane2 Ink → Valibot；lane3 Kea；lane4 Obsidian Linter；lane5 SQLfmt。
- 每路依次解题，不同路并行；题内各组顺序保留原全局题序轮换。
- B、H、M、I 最多各 5 轮，通过后停止该组。H/M 共用一次实际首轮；共同失败后 H 使用新教师复盘，M 使用本批初始教师同一会话复盘。后续学生使用新环境和新会话。
- I 每完成 20 次主要工具调用检查一次，最多 3 次，每条指导最多 100 词。学生有效时限 7200 秒、教师 3600 秒、单次轮内教师检查 600 秒。
- 原 SDK、CLI、JIT 设置、工具执行位置、网络限制和教师只读代码权限保持不变。只有 SDK 工具首次展示方式改变；直接压缩等无工具调用阶段沿用原方式。
- 额度或技术异常继续保存并停止，不自动改变模型、购买或重置额度。

## 旧数据与本批统计边界

Anko 沿用 03/04 的 7 次已完成评测，不重跑，仍作为 v1 过渡结果。Anko 没有采用本批统一工具展示条件，不用于宣称本批四组在十题上具有完全相同运行条件。

07 的 Ink I1 学生此前已经正常结束，后来仅补评测：F2P 为 0/25，P2P 为 49/49，未解出。该结果在 `runs/codex_parallel_07_eval_recovery/attempts.json` 单列，不导入 08 九题的成绩。07 其他五次学生技术中断也不计正常失败，不用 08 新结果覆盖。

正式输出为 `runs/codex_parallel_08/`。实际 token 继续追加到原账本，按批次/角色/阶段归集；08 新增用量与原历史总量分别记录，不把先前失败批次成本隐藏或重复相加。

## 已完成验证与启动材料

原 106 项离线测试全部通过；六路九题完整编排演练通过，没有真实模型调用。演练的占位成绩不计入实验。

真实 SDK 的禁网模拟验证使用候选 `create_agent_options` 内部配置，外部环境没有设置 `ENABLE_TOOL_SEARCH`；首次及同会话后续阶段执行 Read、Edit、Bash，工具列表保持 18 项一致。此测试使用模拟模型响应，用量不计入实验。

- 配置：`reports/parallel_08_config.json`
- 源码差异：`reports/parallel_08_source_changes.diff`
- 源码与操作归档：`reports/parallel_08_snapshot.json`
- 离线测试：`preflight/offline_tests_parallel_08_static.json`
- 编排演练：`preflight/parallel_08_dryrun_result.json`
- 真实 SDK 工具验证：`preflight/parallel_08_sdk_candidate_tools/result.json`
- 启动脚本：`preflight/launch_parallel_08.py`

旧 07 服务已经关闭，完整关闭前快照在 `preflight/parallel_08_service_shutdown/`。启动脚本先将这些记录复制到新启动记录目录，再创建新服务；不会要求旧服务仍然在线。主线程在最终检查账户额度及环境后执行启动脚本。

## 运行核查记录（2026-11-22，北京时间）

本批已于 15:00:34 启动。下述记录来自只读核查，没有改变运行中的源码、Prompt、配置、补丁或评分。

### M 同会话复盘

Claude Code 的首次 M 复盘于 15:28:54 正常完成，初始 Hint 生成与本次复盘使用相同教师容器、SDK 会话和 Codex 原生线程。随后 Igel、Kea、Obsidian 的首次 H/M 复盘也完成。SQLfmt 的共用首轮通过，因此 M 复盘未触发；不能将其作为 M 记忆机制生效的证据。

### 零补丁的正常结束尝试

Kea B1、Kea H/M 共用首轮和 Ink B1 均在复现后自行结束，未生成修改补丁。实际首请求包含原学生模板中明确要求实现修复的步骤；Edit/Write 可用，SDK 为 bypassPermissions，轨迹没有权限拒绝。现有证据不能确定学生提前结束的原因，也不支持将其归因于禁止写入。按正常结束后正式评分记录，不中途改 Prompt 或额外补跑。

证据：`logs/bridge/model_requests.jsonl` 第 1165、1453、1569 行；冻结模板 `source_parallel_08_static/benchmark/deepswe/prompts/deep_swe_user_prompt.md`；各次已保存的 SDK 轨迹和正式评分。

### Igel 两份 23/24 的失败原因

Igel H/M 共用首轮与 I1 都失败于 `test_fit_rejects_when_all_features_are_removed`。两份实现把可选的 `exclude=None` 提前判为非法配置，没有进入全部特征被移除的预期检查，因此错误信息断言失败。两次评测均完整执行 24 个目标测试及 2 个回归测试，属于实现失败，没有环境故障证据。

证据：`runs/codex_parallel_08/lanes/codex_parallel_08_lane1/codex_parallel_08_lane1_H_r1/eval_output/igel-persist-feature-schema/eval_result.json` 及对应 `I_r1` 文件。

### SQLfmt I1 工具取消与监控状态限制

SQLfmt I1 的一次提交请求于 15:43:31 被取消，TaskStop 和停止 pytest 的请求于 15:47:00 被取消，均没有 SDK 执行回执。原生日志给出的原因是 dynamic tool call was cancelled before receiving a response；没有 shell 返回码，不能解释为权限拒绝或命令本身失败。这三个请求出现在同一个模型四工具响应中，却不在导出的 SDK 主轨迹中，说明工具交付或回执存在缺口。

学生最终没有声称停止任务/pytest 已成功；代码提交则有后续独立工具调用的成功回执。原生会话于 15:47:00 正常完成，SDK 为 success/is_error=false/end_turn，保存了 11,367 字节补丁，并于 15:47:05 进入正式评测。现有证据不足以将整轮改标为技术中断；正式成绩保留，同时附上三次工具请求取消的限制，不声称全部工具往返均正常。

桥状态中的 active 落盘有延迟，pending 也可能保留已取消请求。监控应结合 worker 阶段日志、SDK 终态和已保存产物；最终成绩以正式 eval_result.json 为准，不能把 pending 列表等同于实际仍在执行。

证据：`logs/bridge/codex_events.jsonl` 第 94755、95985–95987 行；`logs/bridge/codex_stderr.log` 第 30–32 行；`logs/bridge/model_responses.jsonl` 第 1615 行；`runs/codex_parallel_08/lanes/codex_parallel_08_lane5/codex_parallel_08_lane5_I_r1/infer_logs/sqlfmt-create-table-ddl-formatting/` 的已保存轨迹与补丁（常规归档后位于 turn_1 子目录）。

### Obsidian I1：已确认的多工具转换错误与晚回执

16:00 左右的只读核查确认，多工具响应在转换层发生参数拼接错误：`logs/bridge/model_responses.jsonl:1777` 有三个合法 Bash 请求，`model_requests.jsonl:1783` 却把三段 JSON 拼进第一个请求的 `__unparsedToolInput`。原因是桥 `_sse` 将多工具放在同一数据块，而实际 LiteLLM 1.81.8 的 Anthropic 转换器只创建首个工具块、将所有参数相加。并非学生生成了非法 JSON。

另一个独立现象是长测试回执晚到。原生学生在 15:55:27 主动调用 `wait(cell_id="25", terminate=true)`，在约 278.56 秒后取消了等待，并非固定 300 秒超时；SDK 中的命令继续运行，于 15:57:41 返回 59/59 测试套件、1190/1190 测试通过。晚回执到达桥，但没有进入学生原生会话的可见历史。不能把 SDK 收到通过结果等同于学生已经看见通过结果。

该轮 SDK 正常结束并保存 11,403 字节补丁，正式评分为 F2P 0/41、P2P 1131/1131。成绩反映导出补丁的实际表现，但带有工具传输/回执限制，不能仅解释成教师策略差异。

多工具转换已用真实安装的 LiteLLM 与原 streaming_fix 离线复现，并准备最小候选 `preflight/parallel_08_multitool_fix/`：只拆分 `_sse` 数据块，保留正文、工具集合/顺序/ID/参数、finish 与 usage。7 种转换用例和 25 项相关回归通过，0 次模型调用、0 次网络连接。候选未部署；详情见该目录的 `README.md`、`candidate.diff` 和 `manifest.json`。这项修复不解决学生主动取消长调用的另一问题。

原生取消证据：`/srv/lab-disks/disk2/users/xymo/.codex/sessions/2026/11/22/rollout-2026-11-22T07-42-46-01a20235-2282-7c82-b6be-65f0271c1fb6.jsonl` 第 191、193、245–246 行；晚回执见 `logs/bridge/model_requests.jsonl:1782`。用户已选择保存停止本批，统一应用多工具传输修复后重跑九题；修复只用于新批次09，08运行条件及原始状态不回改。

## 最终停止与补评测

用户授权后，本批于北京时间16:12:09完成停止，旧bridge/progress服务随后关闭。14个容器退出后保留，最终bridge会话状态、恢复元数据、各lane状态、用量与日志边界快照保存在 `preflight/parallel_09_service_shutdown/`。所有旧结果和消耗单列，09重新生成教师Hint并重新采样九题，不复用08模型会话或学生补丁。

运行中已完成15份正式评分；另3份学生已正常完成的补丁，仅补评测后分别为：Igel B1 23/24、2/2；Ink H/M共用首轮24/25、49/49；SQLfmt B1 28/32、1269/1273。补评测模型调用为0，独立记录位于 `runs/codex_parallel_08_eval_recovery/summary.json`，原08状态与补丁没有修改。

合计18次实际评测，其中2次全通过（Claude Code B1、SQLfmt H/M共用首轮）。其余正常完成尝试未全通过；中断中的Claude Code H2、Obsidian B1不作为正常失败计入这18次。Termenv、Textual、Valibot尚未启动。H/M共用首轮不可重复计为两个独立样本。

本批实际用量39,160,506 token（含35,843,456缓存输入），运行墙钟约71分36秒。停止触发的桥错误单独解释为用户要求保存停止，不新增计作模型解题错误。
