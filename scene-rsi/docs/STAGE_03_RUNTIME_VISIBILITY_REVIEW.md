# 第三阶段代码审查：运行源码与历史研究知识分离

基于 `442807b`。只修正改进 Agent 的默认源码可见范围，保留外部初始库、反馈、显式证据、单次 SDK 改进和候选保存机制。本次没有模型调用或正式重建，停止在代码审查阶段。

## 实际修改

| 文件 | 作用 |
|---|---|
| [harness/run_capability_improvement.py](../harness/run_capability_improvement.py) | 增加17项 `RUNTIME_FILES` 明确清单；保留完整宿主源码快照；另建运行源码视图；不再挂载整个 `initial/`。反馈列出实际默认源码，候选记录保存宿主归档位置。 |
| [configs/capability_improvement_prompt.txt](../configs/capability_improvement_prompt.txt) | 仅修改源码访问说明：默认运行源码可见，完整归档不挂载，历史源码须显式授权。自主调查、检查、三种决策和准入要求均未改变。 |
| [tests/test_capability_improvement.py](../tests/test_capability_improvement.py) | 保留原23项回归，增加默认源码范围及显式历史源码访问两项检查，使用真实历史源码作为文件内容。 |
| [tests/preflight_runtime_visibility.py](../tests/preflight_runtime_visibility.py)（新增） | 在真实隔离环境中分别检查空证据和显式分析文件，验证 SDK/Bridge 导入、客户端构造、只读权限、Bash写入及候选收集。 |
| [README.md](../README.md)、本说明 | 更新当前审查入口；第一、二阶段说明与历史结果保留原文。 |
| 仓库顶层 README | 增加第三阶段入口。 |
| [工程验收记录](../experiments/capability_improvement/stage_03_runtime_visibility/) | 保存实际配置、挂载、反馈、命令、日志、可见源码清单、候选差异和验收结果。 |

集中审查用的[实际差异](../experiments/capability_improvement/stage_03_runtime_visibility/implementation.diff)只包含本次实现、Prompt、测试和文档，不混入工程生成记录。

## 三类内容如何分开

```text
prepare(外部 input.json)
  ├─ initial/library/：指定初始库，原路径保持不变
  ├─ seed/library/：候选工作区起点，原行为保持不变
  ├─ initial/system/：完整 sdk、harness、analysis 源码快照及三个共同Prompt
  │                    只保存在宿主机，不自动挂载
  ├─ runtime/：逐文件复制 RUNTIME_FILES 中的17个运行文件
  └─ evidence/：按原有外部 evidence 明确选择的历史文件
        ↓
只读挂载
  initial/library/ → /initial/library
  runtime/         → /initial/system
  runtime/sdk/     → /sdk
  inputs/          → /feedback
  显式证据视图     → /evidence（按原条件存在）
        ↓
原 run_sdk_session.execute → Claude Agent SDK → 原 Bridge → gpt-6.1-terra / low
        ↓
原 collect：候选库、差异、报告、成本；不晋升、不独立验证、不启动下一轮
```

关键变化是删除整个 `initial/ → /initial` 的挂载。否则即使另建通用视图，Agent仍可沿旧路径读取完整快照。

现有隔离器本来会把宿主 `sdk/` 挂到 `/sdk`。本次改进会话通过原有 `readonly_mounts` 机制，将该路径覆盖为经过明确选择的 `runtime/sdk/`，因此SDK源码不会经另一个入口整目录开放。没有修改隔离器或学生执行源码，其他实验会话不变。

`components.current_system_snapshot` 仍为 `/initial/system`，现在明确指向通用运行视图；新增 `components.runtime_source_files` 列出17个文件。`candidate.json.host_system_archive` 保存真实宿主归档路径。既有反馈字段、外部配置结构、库路径、预算和收集机制保持不变。

## Agent 默认可见的项目源码

以下为完整的默认运行文件清单，不根据文件内容执行自动分类：

```text
sdk/run_cc_sdk.py
sdk/codex_cli_bridge.py
sdk/codex_model_catalog.json
sdk/logging_utils.py
sdk/skills_manager.py
sdk/litellm_proxy/claude_code_proxy.py
sdk/litellm_proxy/streaming_fix.py
harness/run_sdk_session.py
harness/isolation.py
harness/sdk_student.py
harness/bridge_server.py
harness/proxy_server.py
harness/socket_tunnel.py
harness/blender.py
configs/student_prompt.txt
configs/formal_prompt.txt
configs/capability_improvement_prompt.txt
```

这些文件可在 `/initial/system/` 下查看。七个SDK文件同时用于 `/sdk`；已有 `/harness/sdk_student.py`、`/harness/socket_tunnel.py` 和 `/runtime/bin/blender` 运行别名仍保留相同源码。系统库、Python环境、第三方SDK依赖和Blender继续按原隔离器提供。

没有默认挂载 `analysis/` 中的任何源码，也没有默认挂载历史实验编排源码、实验配置或 `sdk/run_cc_sdk_vs_parallel13.diff`。四个明确验证为不可默认访问的文件是：

- `analysis/annotate_experiment.py`
- `analysis/write_report.py`
- `analysis/write_exploration_report.py`
- `harness/run_exploration.py`

完整宿主归档仍含上述文件及其他当前研究源码。没有修改或删除其中的研究发现、策略、缺陷和技术经验。默认清单不是新的外部配置层，未来新增研究源码不会因为进入 `harness/` 或 `analysis/` 而自动开放。

## 显式访问历史源码

沿用原外部 `evidence` 字段，例如已有输入文件中：

```json
"evidence": ["/srv/lab-disks/disk2/users/xymo/scene-rsi/analysis/annotate_experiment.py"]
```

准备后可从 `/evidence/001/annotate_experiment.py` 读取，映射和具体文件仍记录在原 `feedback.json`、`evidence_index.json` 中。不会因此开放同目录的其他分析源码。需要某个完整历史源码目录时，也可按原机制显式选择；目录选择意味着授权其内的研究文件。

输入库、反馈或显式证据本身包含的既有知识不被抹除。本次控制的是因通用运行源码而额外自动开放的内容，不做语义删改或知识清洗。

## 已完成验收

[25项离线回归日志](../experiments/capability_improvement/stage_03_runtime_visibility/unit_tests.log)全部通过。原有用例继续覆盖初始库、历史候选起点、反馈、三种决策、SDK参数派发、异常保存、候选差异、成本与缺失用量；新增两项检查真实历史源码的默认隐藏和显式访问。

[真实隔离预检](../experiments/capability_improvement/stage_03_runtime_visibility/preflight/verification.json)完成两个工程配置：

| 配置 | 证据 | 实际结果 |
|---|---|---|
| empty | 空列表 | 四个历史文件及SDK历史差异文件在默认路径均不可见；17个运行文件可读，初始库和运行源码只读。 |
| explicit_analysis | 仅 `analysis/annotate_experiment.py` | 仅通过显式证据路径读取真实分析源码，字节数匹配且只读；默认运行目录仍不含该文件。没有执行历史分析程序。 |

两种配置均实际导入原 `sdk_student`、`run_cc_sdk`、Bridge及消息转换代码，构造原SDK客户端并核对六种工具配置；**没有连接客户端或发起请求**。实际Bash在独立工作区写入工程标记，再用原 `collect` 保存候选、差异和成本。没有伪造模型报告，`agent_decision=null`、`promotion_status=not_promoted`。

预检逐文件对比宿主源码与新归档，确认全部归档文件仍可复查；原始A3能力库、实际反馈和源码在预检前后内容未变。执行记录和成本沿用既有机制。具体耗时、文件数与每项检查以真实 `verification.json` 为准。

复查命令（需本机完整工程和旧实验文件）：

```bash
PYTHONDONTWRITEBYTECODE=1 /srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -B -m unittest discover -s tests -v

PYTHONDONTWRITEBYTECODE=1 /srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -B tests/preflight_runtime_visibility.py \
  --output experiments/capability_improvement/new_runtime_visibility_check
```

真实SDK模型驱动的工具往返没有重跑，本次只验证源码可见范围、依赖导入与离线接口。SDK、Bridge、学生执行、知识提取、Hint、准入与评价源码的实际未修改对照另见 [preserved_sources.json](../experiments/capability_improvement/stage_03_runtime_visibility/preserved_sources.json)。新模型调用0，正式重建0。

完整归档和重复运行源码视图留在本机候选目录；GitHub保存实际配置、反馈、命令、日志、候选和结果，当前源码位于仓库 `scene-rsi/`，不重复上传相同源码副本。没有哈希验证、源码内容分类器、新的准入规则、自动晋升或多轮调度。本阶段到此停止，等待源码审查。
