# Trajectory-to-Capability RSI：六小时封存实验与后续扩展报告

截至北京时间 2026-11-27 07:53 的事实快照，四个研究问题得到的证据并不一致：**轨迹能否提炼为可交付知识**——已形成带来源和适用条件的冻结文本，但不等于模型参数学会了知识；**状态对齐是否优于普通时间线总结**——匹配 V1 和事先选中的部署版本在新 Test 上均未表现出正式成功优势，且 V2 证据来源和交付长度不同，不能单独归因于对齐；**Hint 来源能否改善后续迁移**——四个历史轨迹来源库在一题上均正式未解，不能据此确定 Hint 风格的因果作用；**能否迁移到 Scene**——已有审计提供候选机制和失败链，但没有新的 Scene 迁移实证。样本极小，无正式统计显著性；同一任务下的多个参数化测试不是多个独立任务。

本稿仅呈现既有实验和审计，不继续实验、改动学生、能力库或评测，也不编写新任务解答。原六小时实验已封存；后续扩展的 29 条计划尝试已取得正式成绩，但快照时报告工作和资源关闭尚未完成。最终关闭记录、最后两次报告调用及最终成本以之后真实操作的附记为准，不在此预先声称新实验 VM 或服务已关闭。

## A. 两项工程审计：实际覆盖与证据边界

### A.1 Hint RSI：文件、分块与历史不可访问范围

扩展清单中可访问的 **117 份学生、104 份教师、36 份预检文件，共 257 份**，解码全文分为 **294 个块，均完成 CLI 模型文本审阅**，该历史全文队列未按字段或前缀截断。另捕获 116 份实际学生系统提示、117 份提示配置、28 份在线教师状态、12 份教师事件文件，并形成 20 个 guidance 审阅任务。文件、关联轮次、教师材料和副本不是独立尝试；模型文本审阅也不是全部程序重放或人工核验。原交接中不可访问的完整 rollout 仍未补齐，不纳入可访问分母。

原六小时报告的学生 **17/117**、教师 **4/104** 是当时截止状态，不能反写旧报告，也不能用来描述现时覆盖。另有 152 份历史 CSV 的 **1,130 条元数据记录**，包括 260 条尝试记录、860 条分组或 driver 汇总、10 条任务汇总以及计划、共享引用和缺失路径，既不是 1,130 次独立尝试，也不是全部深审的轨迹。详见[扩展 Hint 审计](audit_hintrsi.md)、[轨迹清单](trajectory_inventory.csv)和[历史记录表](audit/historical_attempt_records.csv)。

**具体结果和干预链：**

- Claude 递归委派 D05 的教师要求检查旧上下文与新输入、成功和不同失败的反馈及调用 ID。学生事件 49–57 暴露并修改续接输入，84–85 检查结果和 ID；正式 **F2P 7/7、P2P 31/31**。后续图像上下文修改未被展示的同一探针单独验证，本地仍有 handler 失败；高度对应支持可能采纳，不证明教师因果贡献。[原轨迹](../../../hint-codex-experiments/runs/codex_parallel_12/lanes/codex_parallel_12_lane0/codex_parallel_12_lane0_I_r2/infer_logs/claude-code-by-agents-recursive-delegation/turn_1/trajs.json)。
- D02 有实质实现和先失败后通过的窄 mock，正式 **6/7、31/31**，空文本案例未通过，内部原因未确定。D01 和 D04 则因调用的 Skill 所涉提供者歧义而停问、空补丁；D03 声称只读但无工具拒绝证据。H2 有非空复现脚本而无可见修复，不能与零字节补丁混同。它们不都是完成实现后的算法失败。
- 历史 B08 实际无任务教师 Hint，却正式 **7/7、31/31**；同批收到参考的 H、I 分别为 **6/7、2/7**。运行时和预算不构成严格受控比较，但反驳“教师是历史成功必要条件”。[B08 轨迹](../../../hint-codex-experiments/runs/codex_parallel_08/lanes/codex_parallel_08_lane0/codex_parallel_08_lane0_B_r1/infer_logs/claude-code-by-agents-recursive-delegation/turn_1/trajs.json)。
- Igel D06 无任务教师参考，自主复现并实现 schema 保存和使用，正式 **23/24、2/2**；较早评价摘录指出 `feature_schema.joblib` 的生产者／消费者路径契约问题。D07 收到指导却因分支问题停问，**0/24、2/2**，替代分支存在不等于获得使用授权。[D06 审计](../trajectory_capability_20261126_020200/audit/audit_D06.md)。
- SQLfmt D08 是真实 source-13 接入预检而非正式九题成功：实现和聚焦检查后正式 **30/32、1271/1273**；一个可见间距差异不解释所有失败。历史另有 HTTP 400、进程退出 -11、取消及 API 402 后未评价等中断，缺失成绩不计为普通算法失败。[D08 审计](../trajectory_capability_20261126_020200/audit/audit_D08.md)。

实际捕获的系统提示优先于组名和可用 Hint 档案；收到、行为一致、因指导而行动、正式通过和长期能力是不同命题。

### A.2 Scene：索引、全文、像素和几何不是同一覆盖

- 规范主轨迹 **360/360 文件、571 分块**完成全文审阅；工作档案 454 条路径中，410 为原导出／脱敏副本、32 为解码文本完全副本，另 **12 份不同内容、12 块**完成审阅。不是 814 次独立实验。
- 27 个 tar 包的 **13,085 个成员已索引**；27 个归档控制块完成。执行映射涉及 1,483 个不同文件、1,644 条归档链接和 161 条轨迹链接，73 个执行块完成；另审阅 526 个选定控制文件和 722 个阶段／调用文件。索引、映射或归档保留不等于所有成员载荷深审；部分原始 API sidecar 未逐项重读。
- 新增视觉审阅为事先保存清单的六案：18 个图像引用中有六份不同参考内容、八份不同渲染内容；按版本字典序选择有渲染轨迹并跳过重复任务 ID，非随机或总体代表样本。全量像素、全部 `.blend` 二进制与精确网格关系未审。两个连续旧几何检查点**各**观察 874 对象、筛选 48 mesh、计算 1,128 对 AABB 下界；AABB 为零不证明接触或拓扑连接。

例如 Scene D01 教师指出植物可见性和显示器支撑疑问，补丁与阶段事件支持植物和面板实际修改，但遮挡、画外和过曝是竞争解释；抽样支架与底座未变，接触未知。S0087 第三步超时后保留第二步，S0078 第三步成功后仍选第二步；S0335 模型 CLI 超时且未开始 Blender，不是几何失败。S0354 局部锚点误差改善时另有误差变大。教师诊断、学生执行、候选接受、独立视觉质量必须分开。[Scene 全审报告及原始行号、归档成员、图像入口](audit_scene.md)；[主清单](config/scene_full_audit_manifest.json)；[视觉清单](config/scene_visual_expansion_manifest.json)。

## B. 原框架、实际入口与工程修复

原六小时实现是 `source_parallel_13` 的派生：复用原 SDK、Bridge、任务初始化、容器和评分器，通过 `capability_path` 将知识传给求解步骤，经已有 append-prompt 路径注入并保存实际加载文本；B0 走匹配的空追加路径，不注入知识。原有薄入口负责预存队列和 Hint 探索，不是重新训练学生或重写评分器。原工程曾修复能力路径未转发、空／非空追加的系统身份句不匹配，以及评价输出收集；被取代的尝试和成本保留。[原源码差异](../trajectory_capability_20261126_020200/results/source_changes.diff)。

后续扩展相对封存版本的源码差异清单仅列 `run_capability_experiments.py`：增加 Development、Hint-transfer、预存交错顺序、冻结检查、显式续跑及截止补丁首次评估处理；并未重写 Bridge、SDK、学生工具或评分逻辑。[扩展差异](results/source_changes_vs_closed_six_hour.diff)。

实际模型请求标识为 **`gpt-6.1-terra`、effort `low`**，不是全局默认型号；基础 CLI 形式为 `codex exec --ephemeral --json --ignore-user-config --sandbox read-only --model gpt-6.1-terra -c 'model_reasoning_effort="low"'`。完整实际命令见[命令记录](../trajectory_capability_20261126_020200/commands_used.md)。SDK 消息和工具经桥接序列化，不能宣称与原生 API 完全等价。实际首请求比较显示，同题组移除知识文本后公共系统文本、工具定义和非系统消息匹配；原生 Skill 禁用。未训练权重，只能保证已记录请求的模型标识和 effort 相同，服务端 checkpoint 不可见。

工程事件包括：原 VM socket 路径超过 UNIX 长度限制，复用原覆盖层并将 socket 移至短路径；镜像仓库 429 后保留失败并在镜像就绪后才启动学生；`-1` 超时哨兵修正为成绩未知；一次只读事后审查重复调用保留并计费。模型访问曾报 `model_not_found / model_not_in_accessible_catalog`，不是已证实额度耗尽；恢复前登录文件元数据更新，但操作者未改认证或型号，原因未定。受影响审计块以不同会话重发，已完成学生未重跑。用户中断后监控 PID 消失，核验后单独恢复控制器，保留监控空窗。[工程修复日志](logs/engineering_fixes.json)；[访问事件](config/model_access_incident.json)。

## C. 对照、能力库、预算与冻结

B0 不加载能力库。K0 仅用 Development 公开描述和教师一般先验，不看学生轨迹或解答；K1 沿时间线提炼检查、修改、探针和结果；K2 将**推断的**子目标与实际状态、操作和约束按跨任务功能对齐。V1 的 K1/K2 使用同一固定 D01–D08 队列；V2 则各自使用旧 V1、各自源自该队列的中间分析及两条各自在相同新 Development 题上生成的 on-policy 轨迹，故新证据不同，不能将 V2 差异单独归因于状态对齐。旧原始证据归档，增量更新时由先前分析代表。

共同提取上限为每条件两次调用、每次最多 700,000 字符、中间分析最多 2,200 词，交付最多 700 词和四个完整单元；同上限不等于实际消耗相同。新轨迹输入逐字段上限 1,800 字符、补丁上限 30,000 字符；新尝试事后审查同样有裁剪，不是历史全文分块审计。原 V1 的 K1/K2 使用相同机械过滤的 615,929 字符来源；提取字段修复前后的调用均留存并计入额外成本。

| 库 | 交付词数／单元 | 来源或部署状态 |
|---|---:|---|
| K0 V1 / V2 | 644／4；630／4 | 描述与先验；Selection 选 V2 |
| K1 V1 / V2 | 578／4；619／4 | 时间线；Selection 选 V2 |
| K2 V1 / V2 | 526／4；505／3 | 功能状态对齐；Selection 保留 V1 |
| HT_NoHint / Error / Strategy / Exploration | 688／4；654／4；677／4；647／4 | 分别来自四条历史 Development 轨迹 |

K2 V2 原稿 707 词、四单元，按事先规则整单元删除末项后交付 505 词、三单元；K1 V2 为 619 词、四单元。不能说等长，也不能把分析中被删的失败分类单元恢复成学生收到的内容。七个 V2 交付单元均以名称标题加六个标签满足七字段：适用问题、知识／行为约束、候选方法、验证步骤、不适用情形、证据来源。

K2 的具体区别是将 Cattrs 部分结果保留、旧续接和 schema 例子按“后续消费者需要何种状态”对齐；将 Snapshot 身份变化与 D05 请求／响应 ID 按功能联系；将类型修复及旧格式／schema 问题归为表示协调。它不是声称实现相同。K1 也要求保留已有结果、重跑探针和检查身份；K0 已包含生命周期、身份、schema、失败通道和合同检查等许多相同通用知识。状态对齐的强调与组织有区别，但不能仅凭措辞证明新增知识或行为收益。[机制比较](audit/library_mechanism_comparison_pretest.md)；[冻结记录及全部主库路径](config/knowledge_freeze.json)；[HT 冻结记录](config/knowledge_freeze_hint.json)。

HT 名称表示知识来源；**HT_NoHint 仍加载从旧无 Hint 轨迹提取的知识，不是 B0**。四个新迁移测试均无在线 Hint。本次没有重新执行同预算的四种主动 Hint 生成试验，也没有共同中间状态反事实回放。

五个新任务的未见核查仅覆盖本机可访问历史元数据、精确任务 ID、公开需求及仓库明显重复；未读取 Test GT 做完整参考实现语义去重，也不能排除不可访问历史或模型预训练接触。[任务划分](config/task_split.json)；[公开需求筛查](audit/public_duplicate_screen.md)。

## D. 封存结果、扩展成绩与成本

正式成功是评价器二元标准；F2P 为目标测试、P2P 为既有行为保持的辅助计数。部分正确不代替正式全解，正式通过也不保证完整真实世界契约。技术缺失或中断不按算法失败填零。

### D.1 原六小时封存结果：不可与后续 29 次合并

匹配 Selection 的 SuperJSON：B0、K1、K2 正式成功，K0 未解；K2 原评价缺新增测试报告、记 0，唯一一次同补丁完整诊断为 **80/80、116/116**，原结果和恢复成本保留。两道 Test 每组各一次：K0 **2/2**、K2 **1/2**、B0 和 K1 均 **0/2**。TOMLKit 的 K2 为 **59/60、964/964**，不是全解；HTTPX 的 B0、K1 各 **115/115、1280/1281**，仍正式未解。原可选开发 Hint：Error、Strategy、Exploration 各正式 **7/7、31/31**；NoHint 评价中断、成绩未知。原逐题 Token、调用、耗时、额外启动与异常见[封存完整报告](../trajectory_capability_20261126_020200/research_report_zh.md)和[原尝试指标](../trajectory_capability_20261126_020200/attempt_metrics.csv)。

旧 NoHint 原约 600 秒中断与后续同补丁 900 秒诊断计时起点不同；后者仍超时，F2P/P2P 未知。已知好 Error 补丁对照 **7/7、31/31**，证明该路线可以完成，不证明 NoHint 根因查清；对照 stderr 的 Node 堆 OOM 与正式通过并存，其影响未知。[分诊](audit/nohint_evaluator_triage_zh.md)。

### D.2 扩展：29 条计划尝试的正式结果

四次 Development、七次 Selection、十四次主 Test、四次 HT 均已取得正式成绩。下方独立占位行由渲染程序插入全部逐尝试 F2P/P2P、Input/Output/Cached、模型／工具调用、耗时、异常和额外评测成本；空字段表示未知。Input 已含 Cached，不能再相加。

<<ALL_PLANNED_ATTEMPTS_TABLE>>

| 题组 | 正式成功汇总 | 有证据的限制 |
|---|---|---|
| Development：cattrs | K1 V1、K2 V1 各 **1/1**，均 69/69、7/7 | 局部完整套件未必完成；正式通过限于评价覆盖。 |
| Development：aiomonitor | K1 V1、K2 V1 各 **0/1**，均 52/53、8/8 | 空 snapshot 列表无输出；两者均有实现并正常结束，局部 console 失败无基线，原因未知。 |
| Selection：mashumaro | B0、K0 V2、K1 V1/V2、K2 V1 各 **1/1**；K0 V1、K2 V2 各 **0/1** | 后两者均 66/66，但 30013/30014：默认 helper 返回新增键，是真实 P2P 合同退化。 |
| Test：adaptix | B0、K0 V1/V2、K1 V1/V2、K2 V1/V2 各 **1/1**，均 44/44、2738/2738 | B0 是截止补丁首次正式评价通过，学生未正常完成。 |
| Test：statemachine | 七个主组各 **0/1** | K0 V1/V2、K2 V1/V2 空补丁；B0、K1 V1/V2 有实现且各 69/72。全部 P2P 为 1285/1286，见共同基线诊断。 |
| HT：statemachine | NoHint、Error、Strategy、Exploration 各 **0/1** | 四组均 69/72、1285/1286；Strategy 为学生截止补丁首次评价，非正常结束。 |

**匹配 V1 对 V1：**新 Test 的 K1 V1 与 K2 V1 均 **1/2**；adaptix 均通过，statemachine 均未解，但 K1 有实现且 69/72，K2 空补丁 0/72。B0 和 K0 V1 也均 **1/2**。这些辅助差异不是正式成功差异，更不是因果效应。

**Selection 事先选择的部署版本：**K0 V2 因正式全解改善而保留；K1 V2 与 V1 正式成功相同，且 F2P、P2P 均未退化，故保留；K2 V2 未满足预先不退化规则，故保留 V1。选择不是依据 Test 成绩或解题成本。选中 K0 V2、K1 V2、K2 V1 在新 Test 均 **1/2**，但 K1 V2 与 K2 V1 是混合版本比较，不能当作状态对齐的纯因果效果。新 Test 未使用在线教师、GT 或旧会话，只加载各自冻结库；这不是脱离所有记忆后的参数能力证明。

首个 Selection 的 K1 V1 原 900 秒评价与一次 900 秒同补丁诊断均保留，诊断无完整计数；在其余 Selection 和任何新 Test 前统一将正式上限改为 **3600 秒**，补一次同补丁正式评价，学生未重跑，最终 **66/66、30014/30014**。初次 `wall_seconds` 仍为 1682.790 秒，含恢复等待的 `end_to_end_seconds` 为 12277.350 秒；诊断 912.661 秒、统一上限补评 1439.114 秒分别列账，不再重复加到端到端跨度。旧 Development 正式上限为 900 秒；学生上限始终 1800 秒。[预算修订](config/verification_budget_revision.json)。

**截止补丁与技术恢复。** Adaptix B0 和 HT_Strategy 均到 1800 秒 `student_timeout`，原编排器取消后未进入正式评价；随后仅对原样保存补丁进行**首次**正式评价，不是学生重跑或重复评测，保留原取消及等待成本。B0 正式通过不等于正常结束或已提交；Strategy 正式未解。薄队列政策对后续确认的同类截止统一适用，学生模型、工具、权限、预算、冻结库和测试不变；已运行进程可能仍加载旧调度代码，遇同类情况同样保留并继续首次评价。控制器因原子进程 PID 退出而单独恢复，不是学生重新开始。[B0 截止记录](runs/capability_followup_v2_test_adaptix-name-mapping-aliases_B0_r1/budget_stop_evaluation.json)；[Strategy 截止记录](runs/capability_followup_hint_transfer_hint_transfer_python-statemachine-state-data-scoping_HT_Strategy_r1/budget_stop_evaluation.json)。

**状态机共同基线问题。** 未修改 pristine base 也在 `test_statistical_distribution` 的既有测试触发 **60 秒单项 pytest 超时**；各完成运行唯一 P2P 失败 ID 与之相同，尚不能直接归为学生引入退化，也不能证明补丁没有性能影响。外层正式 verifier 上限为 3600 秒，相关 verifier 均正常结束；单项 60 秒不是外层中断。保留原正式分数，不排除该测试制造全通过。三个 F2P 失败另涉及无数据状态返回 `{}` 而非 `None`。冻结后的工程诊断不是 K2 学生或提取方法的发现，不能算 K2 迁移收益。[最新诊断](audit/statemachine_baseline_timeout_diagnosis_zh.md)。

### D.3 用量与资源快照

截至快照，扩展记录 **1,857 个 CLI 请求，其中 1,748 个有用量**：Input **139,168,675**、Output **1,142,846**、Cached Input **9,114,752**，缓存已包含在 Input 内。未报告用量不能填零；分类包括历史文本审计、知识提取、学生各阶段、事后审计和报告等。历史 117 份学生文件中 108 份可关联 CLI Token，只有 56 份有逐 request 用量 ID；native CLI turn、Token 更新和 SDK 请求不是同一计数。原 SDK 美元为代理估计，不是真实 CLI 账单；结算美元未知。[历史成本表](audit/historical_attempt_costs.csv)；[各角色会话表](audit/historical_cli_usage_by_session.csv)。

资源采样 1,258 次，最大间隔约 6,674 秒，存在中断空窗；观测到自有容器同时最多四个、采样内存合计峰值约 4.17 GB，短峰可能漏测。宿主负载含其他用户，不归为本实验；VM RSS 已含访客容器，不能相加。报告与复核后最终账本和关闭附记优先于此快照。

## E. 采纳、行为变化、冗余与迁移失败

**输入可见不等于因果采纳。** 冻结库与首请求检查证明文本可用；行为与指导一致仍可能来自任务要求、源码、模型先验或普通工程实践。D05 教师问题后的针对性探针是较强的同轮行为一致证据，仍无隔离教师效应的对照。

- Cattrs K2 V1 的事件 63–64 检查修复失败字段时保留已有值；71–84 中泛型修复先破坏旧复现，再修正并重跑。该序列支持“状态保留、回归后重测”的语义提炼，不证明知识导致行动。K1 同题也做了复现和检查，事件 74–77 的自定义 hook／嵌套状态问题并未显示同一探针重跑。[K2 案例](audit/posthoc_development_cattrs-partial-structuring-recovery_K2_v1.md)。
- Aiomonitor 两组均实现并测试若干边界，却漏掉空列表反馈；K2 事件 33–45 的身份修改和探针不证明运行中到终止的完整身份匹配。两组局部 console 失败均缺可靠基线，不能臆断退化原因。[K1](audit/posthoc_development_aiomonitor-task-snapshots-diff_K1_v1.md)；[K2](audit/posthoc_development_aiomonitor-task-snapshots-diff_K2_v1.md)。
- Selection 的 B0 也自主复现、发现别名及默认值问题并修复；K2 V2 事件 41–44 的 helper 默认键改动最终造成 P2P 退化，尽管多次局部修复和 43 项选定测试通过。K1 V2 则发现同类默认键问题并在事件 33–42 修正。差异是可观察过程，不证明由库造成。[B0](audit/posthoc_selection_mashumaro-flattened-dataclass-fields_B0.md)；[K2 V2](audit/posthoc_selection_mashumaro-flattened-dataclass-fields_K2_v2.md)。
- Statemachine 中 K2 V2 一次请求、零工具、空补丁即提前结束；K0 V1/V2 和 K2 V1 则读仓库并复现缺失 API 后空补丁。它们不是实际算法实现失败的同一类型，也不能把低成本提前结束称为效率提升。B0 与 K1 两版本有实质实现但仍漏无数据合同；HT_NoHint、Error、Exploration 同样有实现但正式未解，Strategy 截止。HT_NoHint 事件 161–178 检查并修复回调修改不持久，临时复现最终删除；Exploration 事件 161–164 则观察到修改未持久。相同行为或分数不证明库产生收益。[HT_NoHint](audit/posthoc_hint_transfer_python-statemachine-state-data-scoping_HT_NoHint.md)；[HT_Exploration](audit/posthoc_hint_transfer_python-statemachine-state-data-scoping_HT_Exploration.md)。

重复宽泛搜索、依赖阻塞、重跑测试和临时探针有真实代价；有些发现缺陷，有些未完成，不能一概称浪费或归因于库。普通 K1 总结和 K0 先验已有大量边界追踪、验证与状态知识；K2 的功能对齐是分析假设及实际文本差异，不自动构成独有能力。

## F. 值得迁往 Scene 的机制与待验证条件

仅提出候选机制：将消费者所需状态映射到对象身份、几何关系与场景阶段；把局部探针扩展为对象清点、精确接触／支撑检查及渲染检查；保留参考、修改前后状态、教师诊断、实际补丁与独立验收的链接；对相机、几何、材质、光照分别记录可能混杂。保留状态仅在合同要求连续性时适用，不能对所有对象机械套用。

验证前须固定或记录证据与预算，区分遮挡、出框和缺失，使用可复现的图像及几何检查，比较候选与普通总结及无库基线，并将提案复核、Selection 保留和独立质量验收分开。现有 Scene 的技术执行、有限像素观察及教师自评不足以证明上述机制有效；本次代码成绩不是 Scene 实证。

## G. 九项近邻工作与贡献边界

以下基于既有官方全文 CLI 审阅，不是复现或穷尽综述；论文结果为作者报告。[全文边界审阅](audit/related_work_fulltext_zh.md)。

1. [GEPA](https://arxiv.org/abs/2507.19457)：用轨迹和反馈反思、演化并筛选提示；固定权重提示改进并非本研究首创。
2. [DoVer](https://arxiv.org/abs/2512.06749)：在失败处恢复上下文与状态、干预重规划并验证假说；本研究没有完成相同中间状态的反事实回放。
3. [Trace2Skill](https://arxiv.org/abs/2603.25158)：分析成功与失败轨迹并合并技能补丁；多轨迹总结和错误分析并非新颖点。
4. [SkillGen](https://arxiv.org/abs/2605.10999)：检索相近案例并用修复与退化评价候选；验证集参与选择，不等同独立 Test。
5. [SKILL-KD](https://arxiv.org/abs/2607.28048)：对照教师与失败学生轨迹，用学生重跑验证技能；教师指导及重跑验证已有先例。
6. [Socratic Skill Learning](https://arxiv.org/abs/2610.17860)：学生测试建议并编辑资源，教育者审阅；教师—学生指导和跨会话技能并非首创。
7. [SimWorld Studio](https://arxiv.org/abs/2605.09423)：从动作—观察失败形成规则，并结合场景图及视觉检查；其场景方法不证明本研究的 Scene 迁移。
8. [SceneEvolve](https://arxiv.org/abs/2610.37046)：利用几何检查及开发评分选择工具／技能组合；整套候选选择不等于单项机制效果。
9. [Liu 和 Wu：Teaching the Harness](https://arxiv.org/abs/2611.13144)：技能跟踪进度、语义与后置条件，候选须在匹配开发任务优于空库；其验证与本研究问题重叠。

较具体、仍待严格检验的问题是：**在相同证据和预算下，跨轨迹按功能等价状态与约束对齐，是否比时间线提炼带来增量价值**。现有 V1 较接近该比较，V2 因 on-policy 证据及交付覆盖不同不能隔离该因素；上述审阅未见明确隔离同一比较，并不证明其他工作不存在或本方法新颖。

**结语。** 已实现的是可追溯的历史全文审计、冻结文本知识与小样本新任务评价；观察到具体修复、正式通过、部分正确、空补丁、退化和技术中断并存。尚未验证状态对齐的独立因果收益、主动 Hint 风格效应、稳定效率收益或 Scene 迁移；后续最终成本和资源关闭状态应由真实操作附记补充。
