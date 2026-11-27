# Trajectory-to-Capability RSI 扩展实验

原六小时实验已封存；本目录记录用户授权续做的扩展工作，不覆盖原结果。更新于北京时间 2026-11-27T08:10:03.363552+08:00。

本轮已完成，收尾记录见 logs/followup_cleanup.json。预定学生尝试29次（Development 4、Selection 7、Test 14、Hint来源独立迁移4），目前状态：{"complete": 29}。已有完整正式成绩 29 条，未知成绩保持空值。

实际模型为原有 Codex CLI `gpt-6.1-terra / low`。四次新增Development已完成；V2、四份Hint来源能力库已生成并审查。主能力库冻结状态：True；新独立终测开始状态：True。

历史Hint完整文本审阅 257/257 文件；Scene规范范围完整文本审阅 360/360 文件。Scene另有12份非重复归档内容，以及实际执行代码、教师控制与阶段事件补审；复制文件、归档成员和独立实验数分别统计，不能互换。

此前指定模型出现账户目录访问错误，原始失败保留；北京时间22:21同型号请求恢复。恢复前22:16登录文件元数据发生更新，操作者未改认证或模型；完整原因未验证。详见 `config/model_access_incident.json`。

首个Selection学生正常提交后，900秒正式评测超时；一次900秒同补丁诊断独立保留。后续Selection与所有新Test统一使用3600秒正式评测上限，并对首个补丁仅补一次同上限评测。学生解题时限仍为1800秒，没有修改答案、测试或能力库。见 `config/verification_budget_revision.json`；旧Development评价上限为900秒，须分阶段解释成本。

主要交付入口：

- `attempt_metrics.csv`：全部29个计划格子，含未开始、未知、额外评价次数和实际成本。
- `trajectory_inventory.csv`：真实轨迹与复制来源索引；不是独立试验计数表。
- `audit_hintrsi.md`、`audit_scene.md`：中文证据审计。
- `audit/`：逐块、分组、图像、几何、Hint采用及论文审阅。
- `config/task_split.json`、`config/protocol.json`：预定任务、顺序、预算与规则；正式修订另存旧版本。
- `knowledge/`：全部候选、交付文本和冻结库；审计输出不回流学生。
- `runs/`、`logs/bridge/`：真实学生轨迹、补丁、正式评价及模型原始调用。
- `logs/monitor.jsonl`：持续观测；中断空窗明确保留，不声称全时连续覆盖。
- `logs/engineering_fixes.json`：实际工程问题与处理。
- `results/actual_usage_summary.json`：实际CLI Token；未报告用量不填零，结算美元费用未知。
- `source/`、`scripts/`：实际工程源码与研究辅助脚本，不包含认证文件。

未运行任务不能填成功或失败，技术中断不能当普通算法失败。最终研究报告入口为 research_report_zh.md，实际完成状态以本页首段和收尾核验为准；方法稿与中间审计不能替代最终结果。


## 已完成交付入口

- [中文最终研究报告](research_report_zh.md)
- [全部29次尝试指标](attempt_metrics.csv)
- [两个额外评价诊断](additional_evaluation_metrics.csv)
- [Hint RSI 审计](audit_hintrsi.md)
- [Scene 审计](audit_scene.md)
- [实际命令与源码差异](commands_used.md)
- [最终成本与关闭附记](final_accounting_zh.md)
- [最终交付核验](results/final_verification.json)

扩展的两道独立 Test 中，B0、K0/K1/K2 的各 V1/V2 条件均正式通过 1/2；匹配 V1 比较未支持 K2 的成功率优势。状态机共同基线超时保留为工程限制，所有正式分数未改动。原六小时和用户授权续做的后续扩展分别报告，未合并成功率。


调度与配置：两道不同 Test 任务两路并行，同题各组按预存交错顺序串行；并非所有组同时启动。实际复用三台 VM，每台 8 vCPU、144 GiB 配置，QEMU TCG、nice 10；每次学生 8 CPU、128 GiB 上限，正式验证器 8 GiB，CPU 受所在 VM 的 8 vCPU 约束。上述为配置／限额，非实际内存常驻量；关闭前 08:06:40 三台 VM 的 RSS 合计约 20.70 GiB，包含其访客内存。没有使用 GPU。采样峰值及空窗见 [资源统计](results/resource_summary.json)；关闭前点观测见 [宿主资源点记录](logs/host_resource_snapshots.jsonl)。
