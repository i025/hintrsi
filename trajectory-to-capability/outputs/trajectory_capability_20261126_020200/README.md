# Trajectory-to-Capability RSI 六小时初步实验

运行窗口：UTC 2026-11-25 18:02—2026-11-26 00:02（北京时间2026-11-26 02:02—08:02）。此目录是独立结果目录；原始 Hint RSI、Scene 工程、旧失败和归档均保留。

核心实验已完成：两个Test上的B0、K0、K1、K2正式成功数为0/2、2/2、0/2、1/2。能力库已在Test开始前冻结，额外Hint探索及截止清理已结束；最终核算以中文研究报告为准。不要把已通过的接入夹具或 Selection 当成独立终测成功。

## 审计与协议

- `audit_hintrsi.md`、`audit_scene.md`：中文审计、覆盖率和未审范围。
- `trajectory_inventory.csv`：历史轨迹轻量索引；`audit/attempt_inventory.csv` 补充没有完整轨迹的原状态项。
- `audit/scene_artifact_inventory.csv`、`scene_bundles.csv`、`scene_deep_audit_sources.json`：Scene 文件范围和截断情况。
- `audit/audit_D*.md`、`audit/audit_S*.md`：CLI产出的逐案英文证据报告；`audit/related_work.md`：已实际打开的近邻工作与创新性边界。
- `config/task_split.json`：模型提取前保存的开发/Selection/Test划分和顺序。
- `config/protocol.json`、`library_delivery.json`、`extraction_budget.json`：实际参数、知识交付规则及提取预算。

## 源码与知识

`source/` 基于服务器上已验收的 `hint-codex-experiments/source_parallel_13` 复制后增量修改。复用原 CLI Bridge、SDK、容器初始化、工具执行与独立评价；本次入口是 `source/run_capability_experiments.py`。源码差异在 `results/source_changes.diff`，接线错误修复前的差异也单独保留。

`knowledge/K0_v1.md`、`K1_v1.md`、`K2_v1.md` 是实际交付学生的文本。`raw_candidates/` 保存模型原始输出；`*_pre_metadatafix*` 保存正式评价字段投影修正前的版本。原 `.job.json` 对应模型生成响应，特别是K2原始810词与交付526词应通过 `library_delivery.json` 区分。交付统一保留前四个完整能力单元，未根据任务成绩改写内容。

Test使用 `knowledge/frozen_v1/` 的独立副本，并从 `knowledge_freeze.json` 读取路径。SDK原生 Skill 保持禁用；通过原系统提示附加机制加载能力文件。

## 实际运行与结果

- `runs/`：每次学生的完整SDK轨迹、补丁、实际系统提示、加载知识、注入证据、工具日志、独立正式评价。
- `logs/bridge/`：完整原始模型请求与响应、CLI事件、实际用量、逐请求schema/最终输出/stderr。
- `logs/visual_SV*/`：原生图像CLI审计记录；实际图片与原文件路径在 `evidence/scene_visual_inputs/`。
- `attempt_metrics.csv`、`results/attempt_metrics.json`：全部12个计划主实验格子，包含未启动、运行、完成或缺失评价，不能只筛成功项。
- `extra_attempt_metrics.csv`：参数转发修复前的B0及K0初始化中断，以及公共提示修复前的四组Selection，共六个额外启动，全部单列，不混入核心对照。
- `results/actual_usage_summary.json`：实际CLI已报告token及未报告用量的请求；缓存输入不重复加到输入总量，SDK估算美元不当成实际结算费用。
- `logs/engineering_fixes.json`：字段投影、生产参数接线、CLI输入长度及修复记录。
- `logs/monitor.jsonl`、`monitor_latest.json`：持续监控；`deadline_cleanup.json` 在截止清理后生成，只管理本次记录的进程和精确容器标签。

## 实际提示条件修复

请求逐字对比发现SDK默认preset与附加提示路径有不同身份句。`source/run_cc_sdk.py`仅增加公共空reminder，让B0不加载知识时也使用相同附加路径；知识组的非空路径保持原样。旧capability_v1 Selection四组结果完整保留在额外尝试表，使用capability_v1_matched_prompt统一复核。两道Test继续使用原冻结文本；已开始的K1/K2走未改动路径，后续B0走修复路径。实际系统提示（只移除能力原文）、工具定义和题目消息的逐字比较在 `results/model_condition_validation.json`。最初冻结记录不重写，复核和Test结果不调整知识。中性夹具只证明接入，不计入独立终测。

## 复查注意

所有新实验模型请求明确指定 `gpt-6.1-terra / low`。宿主全局默认模型不同，实验Bridge使用 `--ignore-user-config` 和显式模型参数；没有切换模型。所有主实验学生从原始任务基线和新会话开始，无在线教师、GT或旧求解轨迹；Test各组唯一允许的知识差别是冻结能力文本。

原始日志保留UTC时间；北京时间仅作明确标注的对应换算。历史文件计数包含原输出和公开副本时明确标注，不能作为独立试次数。文本截断、缺失评价、技术中断和预算停止均须独立解释。

本目录不包含认证信息、模型权重或重复导出的GB级任务镜像。既有数据、VM、运行时和新准备镜像的真实位置保存在配置与审计文件中。可选Hint探索只有在核心12次尝试完成、且剩余至少150分钟时才允许开始；否则按预算跳过，不影响核心实验。

Selection K2首次缺失正式新增测试报告，保留原评分器结果；同一补丁唯一一次实际诊断复评完整通过，主表采用首个完整报告。详见 `config/evaluation_triage.json`、`evaluation_diagnostics.csv` 和 `audit/evaluation_diagnostic_selection_K2.md`；没有增加学生尝试或改动解答。

可选探索的四个计划格子及实际教师检查/交付/Token见 `hint_attempt_metrics.csv`。此阶段只评估开发题即时效果，不验证Hint产生知识的独立迁移价值。

冻结后额外审计E03–E09七条历史记录，历史学生深审总计17/117文件、1210事件（含知识队列8条397事件、仅补审9条813事件），其余100份未深审。新补审未用于学习；历史B08无Hint通过不替代当前B0或本轮未评分NoHint。

三条实际在线Hint原文另存于 `hints/Error_r1.md`、`hints/Strategy_r1.md`、`hints/Exploration_r1.md`；生成/筛选原记录在 `logs/hint_progress/progress.jsonl`，实际模型请求进入证据见 `results/hint_condition_validation.json`。

实际结束时间（UTC）：2026-11-26T00:01:12.553602+00:00。截止清理与最终运行核验见 `logs/deadline_cleanup.json`、`results/final_verification.json`。
