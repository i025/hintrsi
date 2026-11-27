## B. 实际代码与接入

### B.1 实验边界与运行配置

原六小时实验已封存；下述29次学生尝试是用户授权后的独立扩展计划，不应与封存实验的实际运行次数或结果混同。扩展沿用实际基线 `source_parallel_13` 派生版本，完整源代码已保留。与封存版本比较，记录中仅薄队列驱动文件 `run_capability_experiments.py` 有改动：增加 Development 和 Hint-transfer 阶段、预存队列交错、显式续跑及对应冻结检查等；并未重写 Bridge、SDK、容器或评分器。工程运行辅助脚本服务于调度、恢复和记录，不是提供给学生的知识。

模型配置统一为 Codex CLI 的 `gpt-6.1-terra`、`low` 推理强度；SDK 原生 Skill 禁用，能力库通过已有的 prompt 拼接路径实际加载，而不是作为原生 Skill 安装。学生单次上限1800秒、8 CPU、128 GB 内存，最多一轮，无在线教师；形式验证器上限900秒。普通失败不自动重试，同一补丁的评估诊断最多一次。最多三个学生队列并行。相同调用次数和预算上限并不意味着实际 token 消耗相同；未知费用不估算。

计划由4次新 Development、7次 Selection、14次主实验 Test 和4次 Hint-transfer Test 构成。两个新 Development 任务分别由 K1 V1、K2 V1 求解；Selection 比较 B0 和各 K0、K1、K2 的 V1/V2；两个独立 Test 各运行这七组。共享的第二个 Test 另安排四个 HT 库，并与主队列按预存顺序交错，保留各自相对顺序。新增 K0 V1 对照和交错顺序均在相应新 Selection/Test 成绩出现前保存；交错不增加尝试数。历史接触搜索在可访问的原运行及预检记录中未发现五个新任务名，但其范围不包括所有可能历史，也未读取 GT 或隐藏测试源。

V2 每臂只有一个候选：在预存 Selection 上与本臂不变的 V1 比较；正式成功改善，或成功相同且 F2P/P2P 计数不退步，才选 V2，否则保留 V1。技术性缺失成绩不能判胜，部署选择保留 V1。无论选择结果如何，预存的 V1、V2 均计划进入 Test，并区分测试候选与部署选择；提取和选择不使用 Test 反馈。Test 前要求冻结相关能力库。这里的规则是预设流程，不是已完成的选择。

### B.2 中断、恢复与可复查性

记录显示，模型访问曾返回 `model_not_found` / `model_not_in_accessible_catalog`，实际报错称该模型不受当时 Codex ChatGPT 账户支持。随后同一模型、推理强度、CLI、账户和 Bridge 的请求成功；恢复原因未知，操作者未更换模型或凭据，也未转到 CLI 之外推理。106个 Scene 审计分块及一次 Test 前库比较最初受影响；保留原始失败，仅对失败的审计作业以不同会话重发。首个 Selection 学生当时已结束，其无模型验证器另行超时；恢复队列时不重跑该学生。用户中断上一轮后，原监控进程结束，服务和三个自有 VM 仍在；确认旧 PID 不存在后重启监控并保留日志。Scene 审计的图像渲染覆盖仍须单独说明，不能由这些恢复记录推定覆盖完成。

其他工程记录包括：原 VM 套接字不可连接后复用原覆盖层、运行时和资源，仅将套接字移至短路径；镜像仓库 429 的失败记录保留，镜像就绪前未启动学生；超时的 `-1` 哨兵被明确识别为正式计数未知，而非完成成绩。一次只读事后审查重复调用被保留并计入额外调用。上述处置不构成学生能力或评测成功证据。

**依据文件（绝对路径）：**
- 配置与任务划分：`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/config/protocol.json`；`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/config/task_split.json`。
- 源码变更清单及差异：`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/results/source_changes_vs_closed_six_hour.json`；`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/results/source_changes_vs_closed_six_hour.diff`。
- 中断与工程记录：`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/config/model_access_incident.json`；`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/logs/engineering_fixes.json`。

## C. 实际算法与能力库

### C.1 对照、提取与增量更新

B0 不加载能力库。K0 是描述与教师先验对照：V1 和 V2 均只使用旧、新 Development 的公开描述及自身知识，不看学生轨迹或解答；其中 V2 包含对生命周期、恢复和结构化数据边界等的建议，这些不是对学生行为的观察。

K1 是按时间顺序提炼：沿学生从检查、观察、修改、探针到验证和结果的过程归纳可迁移约束。K2 则以推断的程序状态及转换组织证据，将不同任务中功能相近的子目标、约束和操作对齐；对齐是基于记录的解释，不等于任务实现相同。V1 的 K1、K2 使用相同固定 D01–D08 原始轨迹队列；V2 更新时，各臂分别接收自身不变的 V1、源自该固定队列的本臂原 Development 中间分析，以及各自用 V1 在同两个新任务上生成的两条新轨迹。旧原始证据仍归档，增量更新中由先前分析代表；新轨迹是各臂独立的 on-policy 数据，因而不相同，V2 差异不能纯归因于状态对齐。

每个条件的提取预算为两次调用、每次输入最多70万字符，中间分析最多2200词；交付库最多700词、四个完整单元。相同调用数和输入上限只是预算控制，不保证实际 token 相同。内容审查指出 K1 V2 按时间线区分了局部探针、未完成运行和正式 Development 结果；K2 V2 的对齐将保留可用状态、跨转换身份和表示协调作为不同功能约束，但所引快照探针并未证明带钩子的运行中至终止身份匹配。旧 D01–D08 的相关主张依赖所供先前分析，而非本次重新审阅全部旧原始轨迹。

### C.2 实际交付内容与限制

K1 V2 实际交付619词、四单元；K2 V2 四单元原稿为707词，超过上限，按事先共享的整单元规则删除末尾能力后，实际交付505词、三单元。不能把被删单元作为学生收到的第四单元，也不能声称两库等长或覆盖等同。K2 分析中有关失败分类和验证报告的单独覆盖，在交付库中有所损失；分析不是额外注入学生的指导。

七个实际交付单元均以能力名称作标题，加上六个明确标签：适用问题、可迁移约束、候选方法、验证步骤、不适用情形和证据来源，共满足七个语义字段。内容是有条件的行为约束和检查，而非可复制实现或新测试答案。例如，K1 强调跨边界追踪、复现后重测及准确报告验证范围；K2 更显式地按延续状态、身份和表示协调分组。保留旧状态、稳定身份或等价性检查均须服从具体合同，不能机械套用。K0 已包含部分相关先验，因此内容差异既不证明新增知识，也不证明学生采纳或能力收益。

### C.3 Hint-transfer 库

`HT_NoHint`、`HT_Error`、`HT_Strategy`、`HT_Exploration` 四库分别来自先前独立的对应 Development 尝试，使用相同模型、两次提取调用预算和词数上限，冻结后拟在同一个新的无在线教师 Test 上与 B0 比较。四条来源轨迹、反馈及结果质量不同；尤其 NoHint 来源正式成绩未知，超时不能记为零分或普通失败。现有材料没有严格的相同中间状态反事实，不能将库差异或未来比较纯粹归因为 Hint 风格。各库中的边界追踪、递归协议和验证范围等指导也只是依据来源形成的候选知识，不是已证实的迁移。

**依据文件（绝对路径）：**
- V2 内容与机制审查：`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/audit/library_review_v2.md`；`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/audit/library_mechanism_comparison_pretest.md`。
- 主能力库：`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/knowledge/K0_v1.md`；`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/knowledge/K0_v2.md`；`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/knowledge/K1_v1.md`；`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/knowledge/K1_v2.md`；`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/knowledge/K2_v1.md`；`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/knowledge/K2_v2.md`。
- HT 四库：`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/knowledge/HT_NoHint.md`；`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/knowledge/HT_Error.md`；`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/knowledge/HT_Strategy.md`；`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/knowledge/HT_Exploration.md`。

**状态说明：**本文为独立终测运行前的方法稿；Selection 尚未完成，不报告终测结果、部署采纳或长期能力收益。最终应以完整评测与最终配置为准。


运行后补记（北京时间2026-11-26 22:34）：恢复后的登录文件修改时间为22:16:54，与初始故障时记录不同；22:21的同型号CLI请求成功。操作者未修改认证或模型配置。由此不能再将“恢复时认证文件也未变化”作为事实；更新主体与完整因果原因未验证。见 config/model_access_incident.json。


运行后参数补记：在剩余Selection与全部新Test开始前，正式评测上限统一从900秒修订为3600秒，学生仍1800秒。首个补丁只增加一次统一上限补评，F2P66/66、P2P30014/30014；旧900秒尝试及诊断保留。详见 config/verification_budget_revision.json 与原始复评状态，不以方法稿中的旧900秒描述覆盖最终协议。
