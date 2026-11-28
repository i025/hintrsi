# 第六阶段代码审查：候选能力库独立配对验证

基于 `b8de748`。本次仅新增固定批次的“父库＋候选库 → 同任务独立Student → 独立Evaluation → 配对反馈”。前五阶段源码和全部评价标准保持不变。没有启动正式重建或真实模型调用。

## 修改文件

| 文件 | 作用 |
|---|---|
| [harness/run_candidate_validation.py](../harness/run_candidate_validation.py)（新增） | 外部配置、两库及参考图快照、配对Student/Evaluation配置、调用既有入口、保留全部配对及原指标差值。 |
| [configs/validation_inputs/historical_candidate.json](../configs/validation_inputs/historical_candidate.json)（新增） | 直接使用既有Improvement的 `initial/library` 与 `candidate/library` 的完整配置。示例未执行。 |
| [configs/validation_inputs/next_improvement.json](../configs/validation_inputs/next_improvement.json)（新增） | 将配对反馈作为外部Improvement输入；不是自动下一轮或晋升。 |
| [tests/test_candidate_validation.py](../tests/test_candidate_validation.py)（新增） | 13项离线检查，覆盖版本、任务、预算、重复、配对差值、失败/未知保留、反馈接入和原件保护。 |
| [tests/preflight_candidate_validation.py](../tests/preflight_candidate_validation.py)（新增） | 真实输入准备、模拟执行及配对收集，并实际调用旧Improvement.prepare。 |
| README、本说明、[工程验收记录](../experiments/candidate_validation/stage_06_code_review/) | 实际差异、完整输入、配对反馈样例、验证结果和本地索引。 |

源码、配置及文档的实际差异见 [implementation.diff](../experiments/candidate_validation/stage_06_code_review/implementation.diff)。没有修改 Student、Evaluation、Improvement、教师Hint、多轨迹提取、GT学习、能力库准入、SDK、Bridge、视觉Prompt、现有指标及旧实验记录。源码逐文件对照见 [preserved_sources.json](../experiments/candidate_validation/stage_06_code_review/preserved_sources.json)，采用直接内容比较，没有新增哈希系统。

## 外部配置

所有路径相对**配置文件所在目录**解析，也可使用绝对路径。任务ID完全来自外部；内部仅按任务序号和重复编号生成输出名，不解析A组或历史场景命名。

```json
{
  "parent_library": "/absolute/attempt/initial/library",
  "candidate_library": "/absolute/attempt/candidate/library",
  "candidate_record": "/absolute/attempt/candidate.json",
  "output_directory": "/absolute/new-validation",
  "tasks": [
    {"id": "any-external-task", "reference_image": "/absolute/reference.png"}
  ],
  "repetitions": 2,
  "student_budget": {
    "seconds": 1500, "calls": 120,
    "cpus": [32, 33, 34, 35, 36, 37, 38, 39], "port": 19875
  },
  "evaluation": {
    "items": ["reproduction", "scene", "images", "evidence", "visual"],
    "budget": {
      "cpus": [32, 33], "stage_seconds": 120,
      "visual_seconds": 240, "visual_calls": 12, "visual_port": 19876
    }
  }
}
```

`candidate_record` 可省略；若明确提供，原记录及可获取状态会保留在宿主，不进入Student或RGB评价上下文。它可以包含Agent的未修改、证据不足、失败、成本和决策等已有记录；这些是来源记录，不作为已验证收益。`context` 为可选原样保存的说明，例如明确标记工程模拟，不进入学生Prompt。

两版库可以是原始库、既有候选或其他符合原Student结构的目录。外部来源先复制到本批 `libraries/parent` 和 `libraries/candidate`；Student再通过原入口复制到每次运行的只读实际库，Prompt仍使用原SKILL注入。准备之后外部库的修改不影响本批副本。

库缺失或候选未生成时记录 `unavailable`，保留对应计划侧，不把它替换成无库学生。目录存在但不符合原Student输入时保留 `preparation_failed` 及原异常，不新增准入判定或人工修库。两库内容直接比较后记录 `changed`、`unchanged` 或 `unknown` 和增删改文件；文件有变化不证明能力有改进。Agent报告证据不足但仍有实际保存库时，可以按外部配置比较该库，报告仍保留原样。

示例中的历史候选是此前真实保存、带 `ENGINEERING_PROBE.md` 的工程候选，**不是模型自主学习成果**。它用于接口审查，不能据此宣称Agent能力更新有效。示例场景也是历史开发图像，不能再作为最终留出测试。

## 任务公平性和调用关系

每个任务、每次重复有两个独立空白Student工作区和新SDK会话，使用同一冻结PNG、共同基础Prompt、模型、工具、学生预算及评价配置。差别是各自注入及只读挂载的能力库。没有共享代码、场景、对话、教师反馈或执行结果，也不强制使用能力。

模型保持 `gpt-6.1-terra / low`，执行由既有Claude Agent SDK负责，经原Codex CLI Bridge调用底层模型。没有替换为Codex原生Agent。

批次按预先生成的列表串行执行，父版先/候选先按配对交替。每一侧顺序执行Student及Evaluation，再进入下一侧；两侧资源设置相同，端口串行复用。顺序不依赖结果，没有自动重试或补采样，也没有新的并行调度机制。相同预算不代表实际消耗相同；实际停止、调用和成本分别保留。

```text
run_candidate_validation.prepare(input_file)
  → 冻结两版库、参考图、可选候选来源记录
  → 每个任务 × 重复 × 两版生成 Student/Evaluation JSON
  → run_student.prepare：原共同Prompt、SKILL注入、SDK配置及独立工作区
  → validation.json：全部计划侧、配对、顺序与准备状态

run_candidate_validation.run(directory)
  → 对每个已准备侧调用 run_student.run
      → 原 run_sdk_session.execute → Claude Agent SDK → Bridge
      → Student原始交付、工具/Blender记录、状态和成本
  → evaluate_student.prepare（只在Student执行结束后）
  → evaluate_student.technical
      → 原 reproduce / scene inspection / compare_images / evidence index
  → evaluate_student.visual（仅已选择且图像齐全时）
      → 原VISUAL_PROMPT、匿名双图、原Read/Write及SDK执行
  → evaluate_student.collect：该侧原始 feedback.json
  → 保存该侧状态和实际异常；继续其他计划侧
  → finally: run_candidate_validation.collect
      → 全部任务/重复/两侧记录及原指标的 candidate - parent
      → comparison.json、feedback.json

外部后续输入
  → run_capability_improvement.prepare(
       initial_library=外部指定起点,
       feedback=本批feedback.json,
       evidence=显式选择的原始资料)
```

`Evaluation` 的实际输入仍来自该Student保存的参考图、库副本、交付和轨迹。盲RGB评价只使用原Prompt及该次真实的参考/重建图，不传父版/候选身份、另一侧图片、能力库、旧分数或GT。技术再生成仍沿用原不挂载外部能力库/GT的标准。技术阶段的 `stage_seconds` 继续是每个Blender子进程上限，而不是整批总时限；不改变原评价语义。

## 使用命令和输出

使用已有分析环境，不安装或下载依赖：

```bash
/srv/lab-disks/disk2/users/xymo/miniforge3/envs/scenemosaic/bin/python -B harness/run_candidate_validation.py prepare \
  --input configs/validation_inputs/historical_candidate.json

# 真实执行命令；本阶段没有执行未模拟的run
/srv/lab-disks/disk2/users/xymo/miniforge3/envs/scenemosaic/bin/python -B harness/run_candidate_validation.py run \
  --directory experiments/candidate_validation/examples/historical-candidate
```

`prepare` 仅复制及生成配置，不调用模型或Blender。`run` 是一个固定验证批次，将实际调用Student及已选择的RGB评价。`collect --directory ...` 可单独收集现有状态，包括未尝试的计划侧；收集不证明执行完成，不自动补跑。已有输出、比较记录和尝试不覆盖或重跑；中断时在finally保留部分记录与其余未尝试侧。

```text
validation/
  input.json、candidate_source_record.json（可选）
  libraries/parent/、libraries/candidate/（实际可用时）
  references/T001.png、T002.png...
  configs/T001-R01-V1-student.json、...-evaluation.json...
  students/T001-R01-V1/、T001-R01-V2/...
    # 原Student目录：library、inputs、workspace、capture、bridge、状态及成本
  evaluations/T001-R01-V1/、T001-R01-V2/...
    # 原Evaluation目录：技术记录、盲RGB、feedback与costs
  validation.json                 # 所有计划侧、预算、顺序、进度与错误
  comparison.json                 # 全部配对及原始证据/成本/差值
  feedback.json                   # 可直接作为外部Improvement.feedback
```

`V1` 固定对应父版，`V2` 对应候选；任务外部ID与内部序号、重复编号均保留在配对记录。两边实际用库分别由批次来源、批次快照和Student `run.json.runtime_library` 追溯。

## 配对反馈及未知处理

完整样例：[工程模拟 feedback.json](../experiments/candidate_validation/stage_06_code_review/preflight/paired/feedback.json)。样例顶层 `context.kind=offline_engineering_test`、`simulated_execution=true`、`not_research=true`；Student/评审状态同样标记模拟，不能作为研究结果或候选收益。

```text
feedback.json
  kind=paired_candidate_validation_feedback
  context, libraries, library_comparison, candidate_source_record
  student_budget, evaluation, model, reasoning_effort
  coverage: planned_pairs, planned_attempts, attempt_status_counts
  pairs[]
    pair_id, task, repeat, execution_order
    parent / candidate
      attempt: 配置、路径、准备/执行状态、原异常
      library: 外部来源、批次副本、文件清单
      actual_student_record, student_result, supervisor_state
      evaluation_feedback: 该侧原Evaluation完整JSON，缺失则null
      metrics: 原有可获取指标
      costs: 原Student/Evaluation成本，缺失仍保留未知
      evidence: 实际库、轨迹、Blender捕获、模型记录、评价目录
    metric_differences
      auxiliary_ssim / mae_rgb / model_visual_estimate_0_100
        parent, candidate, candidate_minus_parent
  execution_error, data_policy, promotion_status=not_performed, limits
```

三个数值字段分别原样来自既有参考图Gaussian SSIM、RGB MAE、原RGB评价可选粗略估计。差值只是双方真实有限数字的候选减父版；任一缺失、未知或非数字时差值为null，真实0仍是0。不同指标方向不一，没有自动“获胜”判定、综合分数、平均成功案例分数或统计显著性声明。完整技术结果（包括源码独立可移植性及检查状态）仍保留在各侧原始评价反馈，没有改造为新的质量指标。

所有任务/重复都保留两个计划侧，不因无库、失败、无交付、无视觉或缺失评价而过滤配对。`finished` 只表示该侧调用链结束；SDK成功、完整/部分/无交付、技术复现、视觉判断和能力收益分别读取原记录。执行异常后若仍可评价已有文件，会调用原评价入口；不能评价时保留异常、原Student结果、成本及null评价。

原始轨迹及源码事实仍区分SKILL在上下文、实际Read、静态调用、捕获执行与收益，没有自动认定某组件导致失败。自动RGB判断不作为人工评分；本阶段模拟不写视觉报告，所有视觉结果未知。

可将本批 `feedback.json` 直接填入现有Improvement外部配置。原证据访问仍由 `evidence`、`history`、`development_gt` 显式决定，反馈中的路径不自动赋予权限。验证任务标记为开发/选择集；用于改进或版本选择后，未来独立测试须用新留出任务。本入口不会启动改进Agent、修复库、选择候选或改写候选晋升状态。

## 工程验收

[单元日志](../experiments/candidate_validation/stage_06_code_review/unit_tests.log)：62项通过，含原49项及本阶段13项。

[预检 verification.json](../experiments/candidate_validation/stage_06_code_review/preflight/verification.json) 使用真实保存的父库/历史工程候选、两个现有真实参考PNG，生成2任务 × 2重复 × 2版共8份Student配置及8份Evaluation配置。实际使用既有Student准备/收集和Evaluation准备/图像辅助指标/证据提取/收集；仅替换执行后端为测试mock，没有模型或Blender执行。

- 实际用库逐文件匹配指定两版；原库、候选、参考图和历史交付内容保持不变。
- 同任务参考图、基础Prompt、工具、预算和重复编号正确对应；每侧独立工作区。全部既有评价项目的配置透传由单元测试覆盖。
- 模拟后端8次，模拟视觉后端4次；复制历史交付建立测试用例，保留完整2、部分4、无交付2，包括两次模拟执行异常。没有将这些状态冒充新Student行为。
- 图像指标是对实际测试副本计算的已有指标，仅用于工程检查。无重建质量或候选收益结论。
- 原盲评Prompt、Read/Write、双图和SDK挂载配置检查通过；没有写入假视觉报告或评分。缺失评价、非数字、0和中断未尝试侧另有单元测试。
- 配对反馈被原Improvement.prepare逐字节接收，显式证据及候选起点正确，空GT不挂载。只准备输入，没有启动Agent或生成下一候选。

预检约0.90秒。**新模型调用0，新Student重建0，Blender执行0。** 所有运行/评价结果均为明确标记的工程模拟；没有测量候选收益、模型驱动工具往返或正式配对效果。

复查命令：

```bash
PYTHONDONTWRITEBYTECODE=1 /srv/lab-disks/disk2/users/xymo/miniforge3/envs/scenemosaic/bin/python -B -m unittest discover -s tests -v

PYTHONDONTWRITEBYTECODE=1 /srv/lab-disks/disk2/users/xymo/miniforge3/envs/scenemosaic/bin/python -B tests/preflight_candidate_validation.py \
  --output experiments/candidate_validation/new_offline_check \
  --candidate-output experiments/capability_improvement/new_paired_feedback/prepared_only
```

两个输出均须为新目录。完整副本、重复SDK、场景和系统归档保存在本机，见 [local_file_index.json](../experiments/candidate_validation/stage_06_code_review/local_file_index.json)。GitHub保存新增源码、配置、实际生成的配对JSON、调用记录、证据索引和验收记录。

本阶段停在代码审查，没有自动晋升、候选排名、多轮RSI调度、Harness自修改或新增建模方法。
