# 最新状态：第二路线原型小规模验证通过，正式九题未启动

2026-11-22，用户接受先试“原SDK保存上下文、每次独立codex exec返回结构化操作请求”的第二路线。17项接口回归、六路真实CLI模拟门禁及真实SDK工具/手动压缩/续聊闭环均通过。真实Terra记忆小样本3次调用通过，报告19031 token、30.77秒，独立记账，Ofox调用0；该小样本工具读取由fixture执行，未将不同门禁说成同一条全真实链路。完整机制、限制及证据见[第二路线原型说明](../preflight/exec_action_probe/README.md)。原型尚未部署进正式实验，也未声称严格API等价。六路测试容器均已清理。

---

# 当前状态：08已保存停止，09未启动；原 API 等价检查未通过

2026-11-22，追加审计已完成合并候选的143项检查与六路真实CLI隔离验证，但确认当前CLI并非原始API的等价替换：完整历史同步、采样参数、自动压缩及工具调度仍有差异。关闭SDK自动压缩的方案未采用，正式九题继续暂缓。修复只保存在独立候选中，原文件、旧成绩和消耗保留。本轮审计真实模型调用0。完整结论与证据见[09审计说明](../README_parallel_09.md)及[API对照记录](parallel_09_api_equivalence.json)。

08共保留18次实际评测：15次运行中完成，加3次学生已正常结束后的独立补评测；其中2次全部通过，分别为Claude Code B1与SQLfmt H/M共用首轮。H/M共用首轮只算一次实际观察。不能把这18次成绩解释成不受兼容问题影响的完整对照实验，也不导入09的新九题成绩。

- [08评分与用量报告（运行中完成的15次）](../runs/codex_parallel_08/report.md)
- [08独立补评测（3次，新增模型调用0）](../runs/codex_parallel_08_eval_recovery/summary.json)
- [08运行问题、核查及保存说明](../README_parallel_08.md)
- [09最小生产差异](parallel_09_source_changes.diff)
- [09固定配置与统计边界](parallel_09_config.json)

08新增实际用量39,160,506 token，含缓存输入；此前Codex实验和模型预检账本累计39,906,720 token，合计79,067,226。此处不包含实现/监控对话用量，也不是美元费用。离线修复验证和补评测的模型调用为0。

---

# 历史记录：08启动时的配置说明（该批次现已停止）

2026-11-22北京时间15:00:34已启动codex_parallel_08，六路工作进程已运行，Anko沿用原成绩。完整工具从首次会话提供的变更已获用户确认；首次/同会话续聊的真实SDK隔离验证、106项离线测试和六路九题调度演练通过，准备期间无模型调用。

- [持续更新的08结果、Token和耗时](../runs/codex_parallel_08/report.md)
- [08完整运行状态](../runs/codex_parallel_08/experiment_state.json)
- [08固定配置](parallel_08_config.json)
- [08代码冻结清单](parallel_08_snapshot.json)
- [08唯一生产改动](parallel_08_source_changes.diff)

下面说明07停止情况与08承接边界。

07停止原因已定位：SQLfmt的H/M共同首轮通过工具搜索新增Monitor，SDK工具定义从12项变为13项，而该Codex原生线程无法中途增加执行工具。不是模型额度停止。五个教师会话和原容器都已保存；已在不推理的情况下恢复同一原生线程ID，但这不代表它们能直接转入新的18工具配置。[停止核对记录](../preflight/parallel_07_stop_result_audit.json)

| 07已获得的产物 | 当前结果 |
|---|---|
| 五题初始完整Hint及压缩Hint | 已完成、保留 |
| Ink I1 | 学生正常结束；仅补评测后F2P 0/25、P2P 49/49，未解出 |
| Claude Code、Igel、Kea、Obsidian、SQLfmt首轮学生 | 技术中断，未完成，不当作正常失败 |
| Termenv、Textual、Valibot | 尚未开始 |

Ink补评测耗时269.75秒，没有重跑学生或调用模型；原07状态不改，独立结果保留在[评测恢复记录](../runs/codex_parallel_07_eval_recovery/summary.json)。07新增实际用量为6,295,460 Token，包含缓存输入；不是美元费用，也不是本次监控对话的Token。

本次获批的变更只有SDK工具呈现方式：关闭延迟工具搜索，初始一次性提供18个可用工具；各组一致使用。模型Terra/low、原解题和教师提示词、最多五轮、H/M共同首轮、轮内指导参数和六路资源设置保持原配置。由于旧教师原生线程无法注册这套完整工具，新批次重建初始教师；Ink I1也将重跑，旧恢复成绩不混入新批次。

| 路 | 首题 | 后续题 |
|---|---|---|
| 0 | Claude Code递归委派 | Termenv |
| 1 | Igel | Textual |
| 2 | Ink | Valibot |
| 3 | Kea | — |
| 4 | Obsidian Linter | — |
| 5 | SQLfmt | — |

每套VM 8vCPU/144GiB，学生/教师容器8CPU/128GiB，评测8GiB。旧05结果、07结果及技术中断消耗均单列。08已启动；各题实际解题和评分进度以顶部实时报告为准。

- [07停止时的报告](../runs/codex_parallel_07/report.md)
- [07原始状态](../runs/codex_parallel_07/experiment_state.json)
- [旧教师原生会话只读恢复验证](../preflight/parallel_08_teacher_native_resume_verified/result.json)

以下是旧批次结果，不能当作新批次实时状态。

---

# 实验进展总览

更新：2026-11-22 04:59:15 UTC。**并行05已技术停止；原8次正式结果加2次独立恢复评测，共10次尝试有成绩，均未解出；完整十题对照尚未完成。** 05在2026-11-22 04:43:35 UTC因Claude Code I1教师复盘参数过长退出126而停止，非额度停止。原状态、源码、配置、归档和成绩不改；恢复方案仍待选择，未重启模型服务或启动新批。[停止审计](../preflight/parallel_05_stop_result_audit.json) · [原状态](../runs/codex_parallel_05/experiment_state.json) · [独立评测恢复](../runs/codex_parallel_05_eval_recovery/summary.json)

## 并行05停止结果

实际运行2678.886563秒（约44分39秒）。失败复盘的提示长202,118字符，经命令行传给Python时触发`Argument list too long`，该次教师模型没有启动、账本无其模型请求。lane0保存“Teacher review failed”，其他五路保存“Interrupted”；总清理错误为空，原状态不改。[故障日志与逐项核对](../preflight/parallel_05_stop_result_audit.json)

| 已正式评测的尝试 | F2P通过 | P2P通过 | 工作流秒 | SDK学生墙钟秒 |
|---|---:|---:|---:|---:|
| Claude Code，H/M共同r1 | 6/7 | 31/31 | 737.301 | 436.233 |
| Claude Code，I1 | 6/7 | 31/31 | 781.401 | 490.005 |
| Igel，H/M共同r1 | 23/24 | 2/2 | 858.587 | 532.428 |
| Ink，I1 | 19/25 | 41/49 | 1428.122 | 963.409 |
| Kea，B1 | 2/12 | 139/139 | 1412.047 | 1058.035 |
| Obsidian Linter，H/M共同r1 | 37/41 | 1060/1131 | 1288.757 | 603.891 |
| SQLfmt，H/M共同r1 | 20/32 | 1273/1273 | 1066.927 | 510.489 |
| SQLfmt，I1 | 0/32 | 1273/1273 | 622.239 | 67.718 |

8次均reward=0。其中Claude Code I1和SQLfmt I1在全局停止前已完成正式评测，不能归为中断；SQLfmt I1为0/32、P2P1273/1273，结果原样保留。

| 停止时未取得正式成绩 | 学生状态与补丁 | 处理 |
|---|---|---|
| Igel I1 | 学生completed，11,895字节 | 原评测中断；独立恢复评测已完成，结果见下表，不回填05 |
| Kea H/M共同r1 | 学生completed，0字节 | 原评测中断；独立恢复评测已完成，结果见下表，不回填05 |
| Ink B1 | 学生incomplete，10,608字节 | 中断、未评分，不评测未完成学生，不算失败 |
| Obsidian I1 | 学生incomplete，9,256字节 | 中断、未评分，不评测未完成学生，不算失败 |

原05状态中的四条仍为`running`，保留这一历史事实，不修改旧状态。随后只对已完成学生的Igel/Kea使用保存的原补丁和原verifier隔离恢复评测，不重跑学生、不新增模型调用；结果写在单独目录，不冒充停止前已有成绩。

| 独立恢复评测 | F2P通过 | P2P通过 | reward | 仅恢复评测秒 |
|---|---:|---:|---:|---:|
| Igel I1 | 23/24 | 2/2 | 0 | 125.564 |
| Kea H/M共同r1 | 0/12 | 139/139 | 0 | 148.615 |

因此目前是“原05的8次正式结果＋2次独立恢复结果”，不是原05自动变为10次已完成，更不是十道题全部完成。Ink B1与Obsidian I1仍是未完成学生、没有评测成绩，不当作失败；Termenv、Textual和Valibot没有开始模型实验。[恢复来源与结果](../runs/codex_parallel_05_eval_recovery/summary.json)

新副本已准备可选的“只运行从未开始题目”入口，保留原分路与旧观察；10项专项模拟检查通过。约234.7k字节长Prompt的新文件传递入口也通过真实SDK、禁网假接口检查：fresh/resume均完整收到Prompt、保持同一SDK会话，实际执行6次Read/Edit/Bash；旧命令退出126，新入口退出0。以上新增模型调用0、模拟用量不计账，尚不代表新批已启动。[长Prompt检查](../preflight/parallel_06_prompt_file_gate/result.json) · [禁网主机记录](../preflight/parallel_06_prompt_file_gate/host_result.json)

Ink I1的P2P41/49中，其余8项是报告缺失，不是8个已确认的断言失败；现有保留产物不能确定缺失原因。学生AVA测试exit133/V8 `IsNativeContext`及另一次超时，不足以证明正式8项缺失的原因。Obsidian P2P71项未通过也不直接归因为新代码；原grade不改、学生重跑0次。Ink两条Hint服务耗时合计40.433663秒，学生侧等待40.830821秒，口径分别保留。

Claude Code与Igel的M复盘已实际验证延续初始原生线程、SDK会话和教师容器；这不证明效果，尚无H2/M2正式结果。容器清理后原SDK会话JSONL未导出，只有teacher_state中的会话ID不能保证直接续聊。[续会话审查](../preflight/parallel_05_teacher_resume_audit.json)

最近记录的共享账户七日窗口在04:31:59 UTC已用70%；它不是本实验独占额度或美元账单，本次停止由命令参数限制触发。

## 已完成：Anko过渡题

Anko的B1—B5均已正常评测失败（F2P 0/2）；H1与I1通过，旧独立M1取消、成绩NA。B5正式结果为F2P 0/2、P2P 119/119，补丁0字节，工作流641.171568秒。这是跑满五次后的正常未解出，不是技术未完成；已有H/I不重跑。[B5正式结果](../runs/codex_formal_04/codex_formal_04_B_r5/eval_output/anko-default-function-arguments/eval_result.json)

I1正式评测 **F2P 2/2、P2P 119/119**，提交补丁5,757字节。学生执行28个主工具，发生1次轮内教师检查，实际收到1条Hint；本次完成了真实阶段指导流程。[正式结果](../runs/codex_formal_04/codex_formal_04_I_r1/eval_output/anko-default-function-arguments/eval_result.json) · [耗时明细](../runs/codex_formal_04/attempt_metrics.csv)

| 耗时口径 | 秒 |
|---|---:|
| 整次工作流墙钟 | 1,079.0948 |
| SDK学生墙钟 | 620.907985 |
| 其中教师等待 | 16.225550 |
| 扣除等待后的学生时间 | 604.682435 |

成功后的新教师会话复盘已完成，给出`USED / NOT_REVEALED / LOW`标签；这是教师对已保存可见轨迹的判定，不是独立泄漏证明，也不能用这一次通过证明轮内Hint带来提升。B2—B5均已取得F2P 0/2、P2P 119/119的正式结果，补丁均0字节。第三批B1的失败记录原样承接，合计五次；不再执行第六次，也不新增M尝试。

## 已保存结果与第四批承接

第三批Anko B1正式未解出（F2P 0/2），H1正式通过（2/2）。M1学生已完成并保存5,077字节补丁，但用户在正式评测完成前取消，**没有正式成绩，记为NA**；不能算失败，也不能借H1记作独立M成功。M1实际消耗 **1,261,995 tokens**，已包含在第三批总量中。第三批I未执行，第四批已独立完成I1并通过。第三批停止原因是用户修改实验协议，属于主动取消，不是新的技术故障。[取消记录](../preflight/formal_03_user_protocol_change/M1_cancellation.json) · [第三批事实与用量](../preflight/formal_03_user_protocol_change/protocol_audit/final_cost_and_provenance.json)

第四批保留原十题，只读承接第三批Anko B1/H1及完整、压缩初始Hint，**不重跑B1/H1**；承接后已完成B2—B5，I独立执行I1且通过，Anko不补跑M。Anko作为观察H1成功后的v1过渡题，排除在其余九题的v2 H/M比较之外，不能据此宣称共享首轮或教师记忆有因果收益。[协议修订](protocol_v2_amendment.md) · [第四批配置](formal_04_config.json)

其余九题固定采用共享首轮v2：实际H首轮同时供H/M使用，并计入两者最多五轮的第1轮。共同首轮成功时两策略停止，保留一次H成功轨迹诊断复盘，跳过M学生及M续会话复盘，明确“M记忆机制未触发”。共同首轮失败时，H新教师和M原初始教师复盘同一轨迹与正式结果，之后H2/M2各自从干净代码、新学生会话开始。比较后续H/M效果时，只用共同首轮正常失败的同一题集，列出分母；共同成功是一次相关观测，不能当作两个独立样本。B与I仍独立尝试。[说明](../README.md)

## 六路配置与已保留冻结记录

用户已授权在共享主机约一半CPU预算内并行。规模由可用内存约束，为 **6台VM各8vCPU/144GiB，合计48vCPU、864GiB**；48vCPU低于256逻辑CPU主机的128CPU预算，TCG虚拟核仍不等于独占物理核。学生/教师每容器保持8CPU/128GiB，评测8GiB。六路环境检查已于 **03:52:32 UTC** 就绪；原第四批的Anko成绩和所有轨迹保留。[六路环境清单](../preflight/parallel_runtime/runtime_manifest.json)

Root在Anko B/H/I自然结束、成功复盘结束后于03:54:36 UTC在整题边界停止第四批。原始停止原因保留`Interrupted`，规范解释为“用户授权并行交接”，不是新技术故障或额度停止。证据确认下一题模型请求为0、下一题Token为0、活跃模型会话为0，没有打断学生；旧03/04标签容器已清理，七个历史已退出预检容器保留。[交接核实](../preflight/parallel_handoff/verified.json)

并行副本revision2的 **94项离线测试通过（1.049秒、真实模型调用0）**，源码归档冻结为46个文件、237,059字节；环境准备/交接辅助脚本另归档8个文件、11,420字节。共享服务在03:56 UTC重新启动，bridge PID2398156、progress PID2398157；最终健康检查03:57:32 UTC通过，配置于03:58:32 UTC冻结，随后实际启动六个worker。04:00:36 UTC的启动核实确认每路仍为8CPU/128GiB容器，使用独立socket与本批精确标签。[94项检查](../preflight/offline_tests_parallel_05_revision2.log) · [源码快照](parallel_05_snapshot.json) · [辅助脚本归档](parallel_05_operations.json) · [最终健康](../preflight/parallel_05_prelaunch_health.json) · [冻结配置](parallel_05_config.json) · [并行代码变更](parallel_code_changes.md)

固定分配为：lane0 recursive delegation/Termenv，lane1 Igel/Textual，lane2 Ink/Valibot，lane3 Kea，lane4 Obsidian Linter，lane5 SQLfmt。原计划九题各执行一次、保留原全局题序与题内流程；实际仅六题进入实验，三题未开始，不把原计划当作已完成。H/M共同首轮通过不证明M记忆有效，后续比较仍以共同首轮失败题集配对。跨路共用账户额度、服务和宿主机，不承诺固定倍数提速或Token不变。[并行说明](../README_parallel.md) · [协议](parallel_protocol.md) · [配置](parallel_05_config.json)

## 固定条件与验证

统一 **gpt-6.1-terra / low**，Codex CLI返回工具请求，原Claude Agent SDK执行。H/M/I每题共享一次初始GT Hint生成与压缩；除上述共同首轮外，每次学生尝试从原代码和新会话开始，每策略最多五次，通过即停止。学生/教师8CPU；学生有效时限7200秒，教师SDK阶段3600秒。I每20次主工具且批次结束后检查，最多三次、每次最多100英文词/600秒。额度或技术异常保存后停止。

第四批revision2启动前 **80项离线测试通过，耗时1.127秒**；运行环境健康检查通过，8vCPU和内存配置保持。实际第三批产物承接检查通过，确认原状态未修改、完整/压缩Hint文本相同。重新冻结的源码归档为43个文件、230,439字节。启动前健康与服务准备记录中的空容器、零模型会话仅描述当时状态；这些准备没有真实模型调用。[80项检查](../preflight/offline_tests_formal_04.log) · [实际承接检查](../preflight/formal_04_continuation_actual_probe.json) · [冻结快照](formal_04_snapshot.json) · [环境健康](../preflight/formal_04_prelaunch_health.json) · [服务准备](../preflight/formal_04_service_restart/result.json)

此前第四批构造阶段曾因取消清单路径多保留`codex_`前缀而退出，尚未保存初始状态、未发起模型请求，实际模型Token为0。原冻结文件、日志和启动记录已另存，修正命名并新增回归检查后重新冻结revision2，再实际启动；不改写第三批，也不把这次启动前错误当作正式解题失败。[启动前错误记录](../preflight/formal_04_constructor_failure/failure.json)

SDK0.2.186、捆绑CLI2.1.329及共同 `BUN_JSC_useJIT=0` 设置沿用第三批，并采集stderr；变量会传入工具子进程。既有无模型SDK启动检查26/26和完整Anko环境检查通过。**原SIGSEGV未复现，不能证明JIT是根因或长期稳定。** 实际SDK读写、续接、子代理及提醒投递已有兼容验证；这些验证不等同于完整实验取得效果。[SDK检查](../preflight/sdk_sigsegv_diagnosis/summary.md) · [运行恢复](runtime_recovery.md)

## 更早批次单列

| 批次 | 正式评测 | 技术未完成 |
|---|---|---|
| Formal01 | Anko首轮H/M为2/2通过，B/I为0/2未通过；P2P均119/119 | B2来宾内核崩溃 |
| Formal02 | Anko B1为F2P0/2、P2P119/119，正常未解出 | H1 SDK启动exit -11，首请求前退出；M/I未执行 |

第一、二批结果不承接，也不与第四批拼接成绩。Formal01 I1检查0次，不能作为轮内Hint实际生效的证据。本阶段没有训练，也没有完成DeHint或去教师后的泛化验证。[第一批说明](formal_01_interruption.md) · [第二批说明](formal_02_interruption.md)

## 实际消耗与存储清理

| 范围 | 实际总Token |
|---|---:|
| 正式前预检与联调（含独立CLI） | 1,751,919 |
| Formal01 | 4,709,961 |
| Formal02 | 1,627,587 |
| Formal03（含取消M1） | 5,136,005 |
| **第四批启动前历史累计快照** | **13,225,472** |
| Formal04实际新增调用（自然交接完成） | 2,910,704 |
| **并行启动前历史累计快照** | **16,136,176** |
| 并行05实际新增Token（停止后核对） | 17,475,084 |
| **历史加并行05累计** | **33,611,260** |

第四批总量直接累加原始账本92条实际Token增量：输入2,895,307（其中缓存2,500,608）、输出15,397（其中推理4,073），总量2,910,704。I1学生与轮内教师合计1,559,530、成功复盘93,065已包含在其中，其余包括B2—B5；不再额外相加。13,225,472是第四批启动前历史快照，加第四批实际新增2,910,704，得到并行启动前历史累计16,136,176。并行05停止后原始账本422条实际增量合计17,475,084 tokens：输入17,367,238（缓存15,094,400）、输出107,846（推理6,911）；加启动前历史16,136,176，得到33,611,260。只加05新增来源，不重复加03/04。模型请求/响应各441条，模型错误记录为0；这次是模型启动前的本地命令错误。HTTP请求耗时合计2499.961321秒、原生已记录turn耗时合计7482.882秒，后者含工具等待，均不当作纯模型计算时间或整批墙钟。后续新增用量见[并行实时报告](../runs/codex_parallel_05/report.md)与[明细](../runs/codex_parallel_05/metrics.json)，不把历史快照冒充未来实时总量；第四批记录见[实时报告](../runs/codex_formal_04/report.md)与[用量明细](../runs/codex_formal_04/metrics.json)。第四批实时报告按实际调用来源分别展示第三批与第四批，各计一次；其覆盖的第三批用量已在历史快照内，不能将整份实时报告总量再直接加到历史快照。引用旧成绩、Hint不新增费用，取消M1用量已包含，不能再加一遍。未来共同学生首轮、共同成功诊断复盘及初始教师/压缩均只计实际调用一次。缓存输入属于输入，推理输出属于输出；模拟HTTP用量排除。范围不含本聊天、实现/监控及其他Codex任务；共享账户额度百分比不能直接归因于本实验。此次未用Ofox，无可核对货币账单，不猜美元费用。

已按用户要求清理10项可再生下载/缓存与闲置临时磁盘，实际释放 **10.2938 GiB**（11,052,912,640字节）。原源码、结果、轨迹、用量账本、活动磁盘依赖链与独有崩溃证据保留。[清理清单](storage_cleanup_2026-11-22.json)

新代码与产物位于 `/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/`；原交接目录和旧结果不改。第三批冻结配置、归档和状态保留，第四批使用新记录。[代码变更](code_changes.md) · [第三批冻结配置](formal_03_config.json)
