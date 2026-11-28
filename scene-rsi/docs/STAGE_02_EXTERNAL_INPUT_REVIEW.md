# 第二阶段代码审查：外部改进起点与知识来源

本次基于 `2ac0342`，只修改输入组织与信息访问边界。保留第一阶段的评价反馈、自主 SDK 改进 Agent、独立候选、差异与成本收集。本次没有调用模型、没有正式学生重建、没有执行多轮 RSI，也没有产生研究意义上的新能力。提交差异可在本次 GitHub commit 的 Files changed 中逐文件审查；[仅实现、配置、测试与文档的实际差异](../experiments/capability_improvement/stage_02_external_inputs/implementation.diff)排除了重复的生成记录，便于集中审查。

## 1. 修改前后

原入口：

```text
prepare(--condition A3, --experiment 03-A, --history ...)
  → 固定读取 03-A/libraries/A3
  → 开放整批 03-A 索引中的历史证据
  → 自动挂载原三个开发 GT
  → 历史候选仅作为旁证，无法直接成为起始库
  → 原 SDK 单次执行 → collect → 未晋升候选
```

现在：

```text
外部 input.json
  ├─ initial_library：任意符合现有库结构的起始目录
  ├─ feedback：实际执行/评价反馈 JSON
  ├─ evidence：明确允许读取的文件或目录
  ├─ development_gt：明确允许的 GT 文件或目录，可为空
  ├─ history：明确允许的历史候选/经验文件或目录，可为空
  ├─ budget：秒数、模型请求上限、CPU、端口
  └─ context：可选来源、实验背景等元数据
        ↓
prepare(--input ...)
  → 独立复制指定库，冻结输入与实际反馈
  → 仅为明确选择的证据建立只读视图
  → 原 SDK 单次执行 → 原 collect → 未晋升候选
```

A1–A5 仅存在于原实验和单独的 03-A 输入适配器中。通用 `prepare(directory, input_file)` 不读取实验 split、冻结库记录、03-A 结果固定目录或组名；离线测试删除这些固定来源后仍能准备其他目录中的库。

## 2. 新增和修改文件

| 文件 | 作用 |
|---|---|
| [harness/run_capability_improvement.py](../harness/run_capability_improvement.py) | `prepare` 接收外部配置；`evidence_view` 只展开显式路径；生成 schema 2 的反馈包装、证据索引、SDK invocation；`run/collect` 保留既有执行、差异、异常和成本语义。 |
| [harness/prepare_improvement_03a.py](../harness/prepare_improvement_03a.py)（新增） | 将已有 03-A 冻结库和真实结果整理成外部配置。组名及旧实验目录只留在这里。证据、GT、历史均须显式传入。只写配置，不启动 Agent。 |
| [harness/isolation.py](../harness/isolation.py) | 仅在 `image is not None` 时复制初始图。新改进会话使用 `image=null`、`initial_images=[]`；已有有图调用保持原行为。工具和隔离执行逻辑未改变。 |
| [configs/capability_improvement_prompt.txt](../configs/capability_improvement_prompt.txt) | 将来源说明改成通用外部输入与显式权限；保留自主调查、实际候选修改、三种决策、原准入限制与报告结构。未指定具体重建方法。 |
| [configs/improvement_inputs/a3_feedback_only.json](../configs/improvement_inputs/a3_feedback_only.json)（新增） | 原始 A3 库与真实结果，无额外轨迹、GT、历史。 |
| [configs/improvement_inputs/a3_selected_evidence.json](../configs/improvement_inputs/a3_selected_evidence.json)（新增） | 相同 A3 库与指定执行、评价、生成、验证和成本证据，无完整 GT。 |
| [configs/improvement_inputs/a3_selected_evidence_gt.json](../configs/improvement_inputs/a3_selected_evidence_gt.json)（新增） | 相同 A3 库、相同指定证据，显式增加一个办公室开发 GT。 |
| [configs/improvement_inputs/previous_candidate.json](../configs/improvement_inputs/previous_candidate.json)（新增） | 从第一阶段已保存候选库开始，历史范围仅包括显式列出的记录。该旧候选含工程标记，并非模型学习成果。 |
| [tests/test_capability_improvement.py](../tests/test_capability_improvement.py) | 保留第一阶段契约，扩展为23项离线检查。 |
| [tests/preflight_capability_improvement.py](../tests/preflight_capability_improvement.py) | 使用真实旧文件执行三种输入配置及真实文件隔离检查；不启动 SDK、Bridge 或 Blender。 |
| [README.md](../README.md)、本文件 | 现行入口、调用关系、权限语义和验收说明。第一阶段审查说明及旧实验记录保留原文。 |
| [.gitignore](../.gitignore) | 发布时排除可重建的证据、GT、历史视图；原始文件仍由索引指向。 |
| [本次工程验收记录](../experiments/capability_improvement/stage_02_external_inputs/) | 保存实际配置、prepare/隔离命令与日志、输入副本、初始库、工程候选、差异和验证结果。属于工程记录，不是新正式实验。 |

仓库顶层 README 同步增加本阶段入口。运行源码快照保留在各工程候选的 `initial/system/`；这些是源码副本，不是额外实现。

## 3. 外部输入完整示例

以下对应 `a3_feedback_only.json` 的主体，路径相对于**输入 JSON 所在目录**解析，而非调用者工作目录：

```json
{
  "initial_library": "../../experiments/experiment_03a_capability_acquisition/libraries/A3",
  "feedback": "../../experiments/experiment_03a_capability_acquisition/analysis/observed_results.json",
  "evidence": [],
  "development_gt": [],
  "history": [],
  "budget": {
    "seconds": 600,
    "calls": 24,
    "cpus": [32, 33, 34, 35, 36, 37, 38, 39],
    "port": 19665
  },
  "context": {
    "note": "Original A3 library with recorded outcomes only. No historical trajectory or GT access is granted."
  }
}
```

`initial_library`、`feedback`、`budget` 必填；三个证据列表及 `context` 可省略。列表元素是文件或目录路径，既支持本工程路径，也支持其他本地位置。选择目录代表允许读取该目录内的普通文件；不要把不想开放的材料放进所选目录。

`feedback` 是实际反馈 JSON 文件，不需要重新改写成固定实验字段。其原文复制到 `inputs/recorded_feedback.json`，Agent 从该真实文件读取。文件本身包含哪些结果，由外部实验配置负责决定：示例使用完整03-A真实结果，不代表只看到A3组反馈；要限制到某些评价，应由外部提供相应真实反馈子集。`context` 也属于提供给 Agent 的信息，不应写入本次不允许的知识。

模型保持代码中固定的 `gpt-6.1-terra / low`，不是本次可调实验变量。预算的 `calls` 是请求上限，不是已消耗调用量。

选择历史候选作为起点只需替换 `initial_library`，例如：

```json
"initial_library": "../../experiments/capability_improvement/stage_01_verified_review/offline_candidate/candidate/library"
```

这不会自动开放候选的输入、原始证据、GT、轨迹或其他候选。若需要其改进经验，应在 `history` 中明确列出 `candidate.json`、`candidate/update_report.json`、`candidate/costs.json` 或所需轨迹目录。`history` 不再自动推断、扩展一个候选父目录的内容。

## 4. 准备与调用

在本机完整 `scene-rsi` 工程内：

```bash
/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -B harness/run_capability_improvement.py prepare \
  --directory experiments/capability_improvement/reviewed_C001 \
  --input configs/improvement_inputs/a3_selected_evidence.json
```

`prepare` 不调用模型。审查后，如需真实单次改进，仍使用既有入口：

```bash
/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -B harness/run_capability_improvement.py run \
  --directory experiments/capability_improvement/reviewed_C001
```

**本次没有执行该 `run` 命令。** 入口不会自动启动学生验证、晋升或下一轮。`collect` 仍用于已有但尚未收集的会话；正常 `run` 已在 `finally` 收集，不重复覆盖。

03-A 的可选配置生成方式：

```bash
/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -B harness/prepare_improvement_03a.py \
  --condition A3 \
  --output /tmp/scene-rsi-a3-input.json \
  --evidence experiments/experiment_03a_capability_acquisition/runs/A-T01-A2/capture/trajs.json \
  --evidence experiments/experiment_03a_capability_acquisition/analysis/final_usage_summary.json \
  --seconds 600 --calls 24
```

该适配器的默认反馈文件是原03-A `observed_results.json`；可用 `--feedback` 更换。`--evidence`、`--gt`、`--history` 可重复传入，默认全部为空，`--condition A3` 只决定初始库与来源元数据，**不会增加权限**。`--experiment` 可指向恢复的03-A目录。通用模块不再接受旧的 `--condition/--experiment/--history/--seconds/...` 准备参数；它们迁移到适配器或外部 JSON，避免两个优先级来源。第一阶段已经准备好的 invocation 仍能由原 `run` 执行保存的参数。

## 5. 关键源码与完整调用关系

```text
可选 prepare_improvement_03a.configuration()/main()
    → 外部 input.json
run_capability_improvement.main(): prepare --input
    → prepare(directory, input_file)
       → 复制指定 initial_library 到 initial/library 和 seed/library
       → 冻结 inputs/input.json、recorded_feedback.json、prompt.txt
       → evidence_view() 分别处理 evidence / development_gt / history
       → feedback.json、evidence_index.json、session.json、invocation.json
       → candidate.json(status=prepared)
run_capability_improvement.main(): run
    → run(directory)
       → 读取已保存 invocation
       → run_sdk_session.execute(**invocation)               [保持原有实现]
          → isolation.prepare(image=None, initial_images=[]) [新增纯文本准备支持]
          → Bridge + 现有 LiteLLM 消息转换/代理
          → isolation.command(): 独立文件/网络命名空间 + 显式只读挂载
          → sdk_student.py → sdk/run_cc_sdk.py
          → Claude Agent SDK 执行会话和工具循环
          → Codex CLI Bridge → gpt-6.1-terra / low 模型决策
          → SDK 工具调用执行，工具结果进入后续模型上下文
          → 保存原始消息、请求/返回、轨迹、状态、资源与用量
       → finally: collect(directory)                        [保持原有实现]
          → 保存 workspace/library 和原样 update_report
          → 对比 initial/library，记录真实增/改/删及 library.diff
          → usage_summary.summarize(..., root=directory)
          → candidate.json：实际状态、未知报告/用量、未独立验证、未晋升
```

不使用 Codex 原生 Agent 执行上层学生或教师任务，后端替换边界未改变。`run_capability_acquisition.py` 仅复用既有 `TOOLS/copy_tree/write` 通用工具，不向通用 `prepare` 传入A1–A5逻辑。SDK、Bridge、工具、Hint算法、知识提取、学生能力调用、独立评价和能力准入实现均未修改。

## 6. 实际反馈结构与文件权限

准备后 `inputs/feedback.json` 为 schema 2，核心结构：

```json
{
  "schema_version": 2,
  "recorded_feedback": "/feedback/recorded_feedback.json",
  "components": {
    "initial_library": "/initial/library",
    "writable_candidate": "/app/library",
    "current_system_snapshot": "/initial/system",
    "editable_scope": "capability_library_only",
    "source_library": "<external initial_library>"
  },
  "allowed_evidence": [{"source": "<selected host path>", "path": "/evidence/001/<name>", "scope": "evidence"}],
  "allowed_development_gt": [],
  "candidate_history": [],
  "path_mapping": ["<the actual source/path/scope entries>"],
  "evidence_index": "/feedback/evidence_index.json"
}
```

完整真实实例见 [final_preflight/a3_limited/inputs/feedback.json](../experiments/capability_improvement/stage_02_external_inputs/final_preflight/a3_limited/inputs/feedback.json)，原始反馈副本为同目录 `recorded_feedback.json`。`evidence_index.json` 对每个文件记录宿主来源、可访问路径、作用域、是否存在及字节数，不为缺失文件编造内容。`path_mapping` 只有显式选择的映射，原记录里的其他路径不因此获得访问权。映射有重叠时以文件索引中的具体项为准。

`initial/library`、`inputs` 和证据视图只读挂载；`/app/library` 是独立可写副本。证据在同一文件系统使用硬链接，跨文件系统时复制；没有重复下载。已有私密运行目录、凭据和符号链接不进入证据视图。历史目录被明确选中时，它包含的普通研究文件也属于授权范围；若只想提供某个报告，应选择该文件，不选择整个候选目录。

共同运行源码仍开放，避免 Agent 仅凭 README 猜测实现。自动复制的 `configs/` 现在仅包含三个共同 Prompt，不包括 `scenes.json`、历史任务配置、其他实验输入或新增的外部配置示例。这些额外材料若需要，应显式选为证据。源码中存在的组名或路径字面量不等于挂载相应数据。

空 `development_gt` 不创建 GT 挂载，也不再为纯文本改进复制任何默认参考图。但是，库或反馈中已经存在的 GT 衍生知识不会被“抹除”。外部显式选择含 GT 的证据目录或将 GT 内容写入反馈，同样会提供该知识；本模块不对任意文件做语义删改或重新分类。不同知识来源对照必须由外部配置准确控制。

03-A 的结果一旦用于改进，就按历史开发经验使用，不能再当作相应候选的独立测试。旧split和报告保持不变；未来正式独立测试仍需新的留出场景。

## 7. 保存方式与验收

目录结构沿用第一阶段：

```text
attempt/
  initial/library/、initial/system/       # 改进前库、共同系统源码
  seed/library/                           # 独立工作区的起始库
  inputs/input.json                        # 外部配置原文
  inputs/recorded_feedback.json            # 实际反馈原文
  inputs/feedback.json、evidence_index.json
  inputs/prompt.txt、session.json、invocation.json
  evidence/、development_gt/、candidate_history/  # 显式选择的只读视图；发布时不重复上传
  session/workspace/、capture/、bridge/...  # 真实运行时按原机制保存
  candidate/library/、library.diff、file_changes.json
  candidate/update_report.json（若存在）、costs.json
  candidate.json
```

23项单元检查覆盖原有收集、异常、三种决策、未知用量、SDK参数派发及新接口。还验证独立外部库、相同库的不同证据、空GT、历史候选起点、相对路径、符号链接访问边界、跨文件系统证据、缺失记录和旧有图像/已准备invocation行为。

真实预检详见 [final_preflight/verification.json](../experiments/capability_improvement/stage_02_external_inputs/final_preflight/verification.json) 和 [unit_tests.log](../experiments/capability_improvement/stage_02_external_inputs/unit_tests.log)。三组分别验证：

| 工程配置 | 初始库 | 额外证据 | GT/历史 | 验证内容 |
|---|---|---|---|---|
| a3_limited | 原始A3 | 指定真实轨迹、完成运行的代码/场景/渲染及评价 | 均为空 | 文件可读且只读，宿主原路径不可访问，空GT不挂载。 |
| a3_expanded | 相同A3 | 增加生成轨迹、验证报告、真实成本 | 显式一个开发GT及两份历史记录 | 同一起点可使用不同信息范围；新增来源实际可读且只读。 |
| previous_candidate | 第一阶段已保存候选库 | 无 | 均为空 | 旧工程标记完整进入新起点，未重新读取A3冻结库，未自动获得旧证据或GT。 |

三个起点均逐文件对比实际字节，确认 `initial/library`、`seed/library` 与指定来源一致；原始A3和历史候选逐文件内容不变。每个新候选只被工程探针增加 `ENGINEERING_PROBE_02.md`，通过原 `collect` 保存差异。没有模型报告，因此 `agent_decision=null`，候选均未晋升。工程探针不是能力学习结果。

检查01–03实验与第一阶段已验证记录共94,475个历史文件，大小和修改时间无变化。直接与 `2ac0342` 比较的八个现有核心执行、SDK、Bridge、评价和用量文件相同；`isolation.py` 的唯一功能变化单独列明。未使用哈希或校验和系统。

四份已交付配置还逐一执行了真实 `prepare`，没有缺失证据文件，见 [example_checks.json](../experiments/capability_improvement/stage_02_external_inputs/example_checks.json)。03-A适配器的命令行也实际生成配置，并交给通用入口完成准备，见 `adapter_cli_input.json` 与 `adapter_cli_preparation/inputs/`；均没有模型调用。

工程记录通过 [file_index.json](../experiments/capability_improvement/stage_02_external_inputs/file_index.json)列出本地文件与发布范围。GitHub保存实际配置、反馈、索引、命令、日志、初始/候选库、差异和验收记录；显式证据/GT/历史的只读视图及重复系统源码快照保留本地，不重复上传。当前完整源码在仓库 `scene-rsi/`。

复查命令：

```bash
PYTHONDONTWRITEBYTECODE=1 /srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -B -m unittest discover -s tests -v

PYTHONDONTWRITEBYTECODE=1 /srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -B tests/preflight_capability_improvement.py \
  --output experiments/capability_improvement/new_offline_input_check
```

本机完整旧实验或恢复的原始归档是测试数据前提，Git可浏览子集不包含所有原始轨迹。此次未重新下载数据或安装环境。实际准备、隔离和收集日志已保存；SDK执行仅通过离线mock验证派发，未启动真实模型会话。新模型调用0、新学生重建0、GPU使用0。

## 8. 本阶段停止位置

保留模型自主决定修改、不修改或证据不足的既有机制，但本次没有真实调用模型，因此没有检验新的自主诊断效果或候选收益。不修改准入标准、教师Hint、知识提取或评价标准，不自动排名、晋升、验证学生、多轮调度或自修改Harness。下一步仍是审查源码与外部权限配置。

完整英文改进 Prompt 以 [实际配置文件](../configs/capability_improvement_prompt.txt) 为准；真实准备的原文副本保存在各 `inputs/prompt.txt`。与第一阶段相比只调整外部来源、映射及权限表述，未加入具体Blender方法或指定失败原因。
