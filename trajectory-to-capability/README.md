# Trajectory-to-Capability RSI：真实实验与审计

原六小时实验已封存，用户授权续做的扩展也已结束。两段结果分开保存，不能合并成功率或称全部工作在六小时内完成。本次 GitHub 同步只整理已有产物，没有重新解题、调用模型或渲染。

| 内容 | 入口 |
|---|---|
| 最终中文研究报告（含 A–G、限制与成本） | [扩展报告](outputs/trajectory_capability_followup_20261126_182329/research_report_zh.md) |
| 原六小时封存结果 | [原报告](outputs/trajectory_capability_20261126_020200/research_report_zh.md) · [原指标](outputs/trajectory_capability_20261126_020200/attempt_metrics.csv) |
| 全部 29 次计划尝试 | [指标 CSV](outputs/trajectory_capability_followup_20261126_182329/attempt_metrics.csv) · [正式表格](outputs/trajectory_capability_followup_20261126_182329/results/attempt_tables_zh.md) |
| 两次额外同补丁评价诊断 | [独立诊断表](outputs/trajectory_capability_followup_20261126_182329/additional_evaluation_metrics.csv) |
| 两个仓库的实际审计 | [Hint RSI](outputs/trajectory_capability_followup_20261126_182329/audit_hintrsi.md) · [Scene](outputs/trajectory_capability_followup_20261126_182329/audit_scene.md) |
| 全部轨迹与来源 | [轻量索引](outputs/trajectory_capability_followup_20261126_182329/trajectory_inventory.csv) · [原始运行](outputs/trajectory_capability_followup_20261126_182329/runs/) · [模型日志](outputs/trajectory_capability_followup_20261126_182329/logs/) |
| 分组、任务和顺序 | [预存任务划分](outputs/trajectory_capability_followup_20261126_182329/config/task_split.json) · [协议](outputs/trajectory_capability_followup_20261126_182329/config/protocol.json) |
| 知识与冻结 | [全部能力库](outputs/trajectory_capability_followup_20261126_182329/knowledge/) · [主库冻结](outputs/trajectory_capability_followup_20261126_182329/config/knowledge_freeze.json) · [Hint 来源库冻结](outputs/trajectory_capability_followup_20261126_182329/config/knowledge_freeze_hint.json) |
| 实际修改后源码和辅助脚本 | [源码](outputs/trajectory_capability_followup_20261126_182329/source/) · [脚本](outputs/trajectory_capability_followup_20261126_182329/scripts/) · [实际命令](outputs/trajectory_capability_followup_20261126_182329/commands_used.md) |
| 工程问题与最后核验 | [修复日志](outputs/trajectory_capability_followup_20261126_182329/logs/engineering_fixes.json) · [交付核验](outputs/trajectory_capability_followup_20261126_182329/results/final_verification.json) · [关闭记录](outputs/trajectory_capability_followup_20261126_182329/logs/followup_cleanup.json) |
| 压缩文件、外部附件与发布处理 | [发布说明](../publication/trajectory-capability/README.md) · [逐文件映射](../publication/trajectory-capability/file-manifest.json) |

## 结果与边界

| 实验范围 | B0 | K0 | K1 | K2 |
|---|---:|---:|---:|---:|
| 原六小时两道终测，各组 V1 | 0/2 | 2/2 | 0/2 | 1/2 |
| 后续两道新终测，匹配 V1 | 1/2 | 1/2 | 1/2 | 1/2 |
| 后续 Selection 事先选中版本 | 1/2 | V2：1/2 | V2：1/2 | V1：1/2 |

后续全部 29 次学生尝试及正式评价均已完成：Development 4、Selection 7、主 Test 14、历史 Hint 来源能力库迁移 4。表中的独立新 Test 只有两题，多个参数化测试不是独立任务；不能证明状态对齐优越性、稳定效率优势或长期能力提升。

Adaptix 各主要条件均正式全通过；Statemachine 全部正式未解，非空实现为 F2P 69/72，四个空补丁条件为 0/72，P2P 均 1285/1286。后者同一既有统计测试在未修改基线也触发 60 秒超时；保留原正式分数，不能直接归为新退化。三个目标测试失败仍在，不因共同基线问题而改判通过。全部失败、提前结束、截止及同补丁首次评价记录保留。

K0 仅用开发描述与教师先验；K1 使用普通时间线提炼；K2 使用按功能目标对齐的状态变化证据。K1/K2 V1 共用 D01–D08；V2 则使用各自新的 on-policy 轨迹，不能将 V2 差异单独归因于状态对齐。HT_NoHint 也加载从旧无 Hint 轨迹提取的库，不是 B0；四个来源库在同一新题上均正式未解，没有重新进行四种主动 Hint 的统一预算随机实验。

Hint 可访问历史 257 文件／294 分块完成文本审阅；Scene 主范围 360 文件／571 分块及另 12 份不同内容完成审阅。这些是文件覆盖，不是独立实验次数，也不是全量程序重放、全量图像或几何检查。Scene 的候选机制尚无新增迁移实验支持。

## 成本与运行条件

实验统一使用 Codex CLI `gpt-6.1-terra / low`。不同 Test 任务两路并行，同题各组串行，每次学生 1800 秒、8 CPU／128 GiB 限额；复用三台各 8 vCPU／144 GiB 的 VM，无 GPU。结束后本实验 VM、隧道及服务已关闭，原覆盖层、镜像和其他用户进程保留。

后续账本共 1861 请求、1752 个用量回报，109 个未报告用量；已报 Input 139635598、Output 1157529、Cached Input 9114752。缓存已包含在 Input 内；美元结算费用未知，本聊天操作开销不在该实验 CLI 账本中。[最终成本分类](outputs/trajectory_capability_followup_20261126_182329/results/final_cost_breakdown.json)与[带日期的附记](outputs/trajectory_capability_followup_20261126_182329/final_accounting_zh.md)保留具体口径。

原始绝对路径保留用于复查；Markdown 链接为 GitHub 浏览调整。大于 4 MiB 的日志追加 `.gz`，没有因大小丢弃学生尝试；论文全文缓存与旧 Scene 大型分包的发布边界见上传说明。
