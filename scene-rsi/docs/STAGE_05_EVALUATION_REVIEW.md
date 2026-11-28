# 第五阶段代码审查：通用独立 Evaluation 入口

基于 `13c2417`，仅建立“已结束 Student → 独立 Evaluation → 外部反馈输入”。不要求 A0–A5、任务名或03-A目录，不启动新学生、不调用真实模型，不运行候选改进、晋升或迭代。

## 实际修改

| 文件 | 作用 |
|---|---|
| [analysis/evaluate_student.py](../analysis/evaluate_student.py)（新增） | 外部配置、实际输入定位、既有技术评价调度、匿名RGB会话准备/调用及结构化反馈。 |
| [analysis/summarize_run.py](../analysis/summarize_run.py) | `summarize(directory, output=None)` 可将证据索引写到独立评价目录；缺失监督器状态保留null。默认仍写原运行的 `analysis/`。 |
| [analysis/review_capability_acquisition.py](../analysis/review_capability_acquisition.py) | `session_file(..., path=None)` 可指定新会话配置路径；原默认目录、参数、工具和视觉Prompt不变。 |
| [configs/evaluation_inputs/](../configs/evaluation_inputs/)（新增三份JSON） | 技术评价、含独立RGB评价、下一次外部Improvement输入例子。 |
| [tests/test_evaluation.py](../tests/test_evaluation.py)（新增） | 13项离线检查：新入口、缺失交付、未知视觉、旧默认行为、外部反馈接入及隔离输入构造。 |
| [tests/preflight_evaluation.py](../tests/preflight_evaluation.py)（新增） | 一次真实旧交付再生成、真实RGB隔离输入、部分/无交付以及Improvement准备的工程预检。 |
| README、本说明、[工程记录](../experiments/student_evaluation/stage_05_code_review/) | 使用方法、实际差异、真实反馈、验证结果与本地大文件索引。 |

集中差异见 [implementation.diff](../experiments/student_evaluation/stage_05_code_review/implementation.diff)。没有修改Student、Improvement、知识获取、教师Hint、SDK、Bridge、隔离、场景/图像评价算法、原03-A评价批处理或研究记录。两处既有函数的可选参数均保留原调用方式。

## 外部配置和调用关系

路径相对**配置文件所在目录**解析，也接受绝对路径。例如：

```json
{
  "student_run": "/absolute/path/to/any-ended-student",
  "output_directory": "/absolute/path/to/new-evaluation",
  "items": ["reproduction", "scene", "images", "evidence", "visual"],
  "budget": {
    "cpus": [32, 33],
    "stage_seconds": 120,
    "visual_seconds": 240,
    "visual_calls": 12,
    "visual_port": 19865
  }
}
```

`items` 由外部选择已有项目。`stage_seconds` 是每个Blender子进程上限，沿用原函数的语义：源码再生成及生成场景检查分别有此上限；不是整批总时限。Blender仍采用原32GiB地址空间上限、CPU渲染、nice15和指定CPU亲和性。`visual_*` 仅在准备实际RGB会话时需要，直接传入原SDK监督器。没有新安装或数据下载。

配置示例中的Student路径对应第四阶段示例，须先存在一个已结束的实际运行。本次没有执行这些示例中的新Student。实际已执行预检的配置保存在 [preflight目录](../experiments/student_evaluation/stage_05_code_review/preflight/)。

```text
run_student.prepare → run_student.run/collect
  → 已保存的参考图、library、workspace、capture、bridge、状态与成本
  → evaluate_student.prepare(input_file)
      → 保存外部配置和实际参考图
      → 需要时准备盲评两图、原VISUAL_PROMPT、原隔离SDK会话
  → evaluate_student.technical(directory)
      → evaluate_capability_acquisition.reproduce
      → environment / blender / invoke / acquisition_scene_metrics
      → compare_images → image_metrics.metrics
      → summarize_run.summarize + code_facts
  → evaluate_student.visual(directory)（可选；本次未真实执行）
      → run_sdk_session.execute → sdk_student → Claude Agent SDK
      → Codex CLI Bridge → gpt-6.1-terra / low
      → 原Read/Write工具 → 实际visual_evaluation.json
  → evaluate_student.collect(directory)
      → usage_summary.summarize + 原始状态/交付 + 实际评价结果
      → feedback.json、costs.json、evaluation.json
  → 外部Improvement配置：feedback=上述feedback.json
      → run_capability_improvement.prepare（本次只验证到这里）
```

使用已有分析环境（含numpy、Pillow、scipy）：

```bash
/srv/lab-disks/disk2/users/xymo/miniforge3/envs/scenemosaic/bin/python -B analysis/evaluate_student.py prepare \
  --input configs/evaluation_inputs/with_visual.json

/srv/lab-disks/disk2/users/xymo/miniforge3/envs/scenemosaic/bin/python -B analysis/evaluate_student.py technical \
  --directory /absolute/path/to/new-evaluation

# 可选真实模型评价；本次没有执行
/srv/lab-disks/disk2/users/xymo/miniforge3/envs/scenemosaic/bin/python -B analysis/evaluate_student.py visual \
  --directory /absolute/path/to/new-evaluation

/srv/lab-disks/disk2/users/xymo/miniforge3/envs/scenemosaic/bin/python -B analysis/evaluate_student.py collect \
  --directory /absolute/path/to/new-evaluation
```

`run --directory ...` 顺序执行技术项目、已准备的RGB会话及最终收集；若选了visual且图像齐全，会真实调用模型。本次仅使用分步接口，RGB调用用离线mock验证。已有输出不覆盖，RGB不自动重试。原03-A的 `evaluate_capability_acquisition.py` 与 `review_capability_acquisition.py` CLI保留原逻辑。

## 实际输入及评价范围

参考图优先取该Student冻结的 `inputs/reference.png`，兼容旧运行时回退到它自身 `workspace/reference.png`；不从组名、split或GT查图。旧工作区副本未被独立冻结时，不能额外保证它未被历史学生改写，这一限制不以数据集图片补齐。

能力库只认该运行实际保存的 `library/`，不重新读取来源库或按A组推断。实际库内容由该副本与学生初始Prompt保留；反馈记录来源与快照位置及SKILL正文是否在准备Prompt内。没有运行副本的旧有库运行标记 `runtime_library_status=unknown`；明确无库标记 `none`。库出现在上下文、工具Read、源码静态调用、实际执行和收益是不同证据，不会被汇总为自动能力采用或失败归因。

技术端在**独立副本**中移除已有交付并调用原 `reproduce`，保持源码独立复现标准（不挂载能力库或GT）。原始场景检查同样先复制工作区；索引/源码事实写入评价目录。原始Student、原始库和候选均不改写。图像辅助指标继续使用原MAE与Gaussian SSIM，没有新综合分数或语义/三维质量算法。原场景提取保留包围盒候选、材质节点等事实及其不确定性，不启动GT对应、投影或统一光照评价。

轨迹证据保留原SDK工具事件、模型记录、Blender实际命令/捕获源码和文件入口。静态源码调用不是实际执行证明，评价者再生成不是学生行为。没有相应原始记录时不能从空计数推断真实行为不存在，应读取反馈及原文件的可获取情况。

## 独立RGB信息边界

完整英文Prompt直接使用原 [VISUAL_PROMPT](../analysis/review_capability_acquisition.py)，没有新增评分要求。初始内容仅为该Prompt与两张真实PNG：`Reference image`、`Candidate reconstruction`。模型及effort仍为 `gpt-6.1-terra / low`，模型决策经原SDK工具循环执行。

评审工作区只复制 `reference.png`、`final.png`；`/inputs` 只含 `prompt.txt`、`session.json`、`images.json`。只允许原Read/Write工具，Hint/持久能力/在线教师关闭。只读SDK副本沿用第三阶段明确清单中的七个SDK文件；通用SDK和工具本身仍然可用。宿主配置、Student路径、能力库、条件、旧分数、GT、历史资料不进入评审工作区或初始消息，也没有对应挂载。宿主 `visual/invocation.json` 不挂入评审 `/inputs`。

实际评价JSON按原样保存，不重新生成缺失分数。自动模型判断保留 `annotation_kind`、证据、局限和未知，不能作为人工评价；`human_rating` 始终明确为null。SDK结束状态与报告是否存在分别记录，有报告不等于SDK正常结束或报告已获人工认可。

## 反馈结构和缺失语义

完整真实例子见 [preflight/complete/feedback.json](../experiments/student_evaluation/stage_05_code_review/preflight/complete/feedback.json)。它来自真实历史完整交付的明确标记副本，不是新学生成果；视觉模型没有运行。

```text
feedback.json
  schema_version, kind=independent_student_evaluation
  student
    run, run_id, record, supervisor_state, sdk_status
    delivery: kind, files(path/exists/bytes), required_files_present
  inputs
    reference_source, reference_used, runtime_library
    runtime_library_status, skill_in_prepared_prompt
  technical
    reproduction / scene / images / evidence
      status, result, seconds（执行过时）；missing/error（实际存在时）
  visual
    status, result(null或实际模型JSON), human_rating=null
    session_state, execution_error, report（尝试执行后）
  costs
    student: 原汇总、日志是否可获取、请求总数是否已知
    visual: 尝试后实际汇总，未执行则null
    technical: 实际技术阶段耗时和命令记录入口
  student_evidence, evaluator_evidence
  data_policy, limits
```

交付状态只描述三个文件是否存在且非空：`complete_files_unvalidated`、`partial`、`none`，不把正常SDK退出等同交付完成，也不把文件齐全等同重建正确。

技术项目分别记录 `completed`、`failed`、`skipped`（必要文件缺失）、`not_run`、`not_requested`。`completed` 表示评价函数完成，不代表质量通过；复现是否成功还需读实际退出状态、生成文件及原可移植交付判定。一个项目失败不会丢弃其他项目或整个Student结果。

视觉分别记录 `not_requested`、`skipped`、`not_run`、实际报告或缺失/无效报告；没有真实报告时 `result=null`。原始无效报告保留，不补写分数。缺少Token/请求日志时明确总数是否已知，实际美元账单保持null；历史Student成本与本次评价成本分别记录，历史调用不是本次新增调用。

反馈通过现有外部 `feedback` 字段直接传给Improvement。原始证据的文件路径不会自动赋予访问权限；后续若希望Agent读取轨迹、代码、场景、评价细节或模型原记录，必须像 [next_improvement.json](../configs/evaluation_inputs/next_improvement.json) 那样在 `evidence` 显式选择。开发GT和候选历史仍分别由外部配置，可为空。没有自动创建下一轮或执行改进；评价结果一旦用于改进即属历史开发经验，未来独立测试须用新留出场景。

## 工程验收与边界

[unit_tests.log](../experiments/student_evaluation/stage_05_code_review/unit_tests.log)：49项通过（原36项及本阶段13项）。覆盖任意名称/目录、实际冻结参考图、原库/历史候选/空库、旧库未知、完整/部分/无交付、失败留存、原函数调用、原索引默认路径、盲评两图及原Prompt、模型调用入口mock、无报告/坏JSON保留未知、反馈被既有Improvement直接接收。

[真实预检 verification.json](../experiments/student_evaluation/stage_05_code_review/preflight/verification.json)：

1. 将旧 `A-T01-A3` 的实际交付、轨迹及原记录复制到任意名 `arbitrary.name`，明确标记工程兼容副本。实际库从该Student归档命令的 `/capabilities` 来源复制，未按组名推断。
2. 仅此副本执行一次真实源码再生成：CPU32/33、nice15、每子进程120秒上限；实际再生成16.12秒。生成场景与原场景均成功检查，189个对象、12个材质、未发现缺失外部图像；原交付与再生成均为640×360，RGBA逐像素一致。指标是旧交付的工程复验，不是新研究收益。
3. 在真实隔离进程中运行原 `sdk_student.prompt_messages()`，实际解码两张图像并逐字节核对，核对原Prompt、Read/Write工具、模型标识及SDK客户端构造；宿主工程、能力库、GT和历史资料不可访问。SDK消息保存为“构造但未发送”，没有模型往返。
4. 删除完整副本的一个场景文件建立明确标记的派生部分交付用例，不冒充历史学生失败。另直接使用第四阶段的原库、候选、空库三个已结束工程探针，正确保留无交付，跳过无法执行项目，保留可提取证据。
5. 实际 `feedback.json` 被现有 `run_capability_improvement.prepare()` 原样复制，能力库起点匹配，显式证据可用，GT不挂载。该目录只准备，未启动改进Agent、未生成候选更新。
6. 实际历史Student、原始能力库和三个旧探针文件内容不变；源码未修改对照另见 [preserved_sources.json](../experiments/student_evaluation/stage_05_code_review/preserved_sources.json)。

真实预检共20.47秒，新模型调用0、新Student重建0、历史交付再生成1次。没有调用视觉模型、没有伪造视觉评分；RGB模型完整往返仍未在本阶段实测。可复查命令：

```bash
PYTHONDONTWRITEBYTECODE=1 /srv/lab-disks/disk2/users/xymo/miniforge3/envs/scenemosaic/bin/python -B -m unittest discover -s tests -v

PYTHONDONTWRITEBYTECODE=1 /srv/lab-disks/disk2/users/xymo/miniforge3/envs/scenemosaic/bin/python -B tests/preflight_evaluation.py \
  --output experiments/student_evaluation/new_offline_check \
  --candidate-output experiments/capability_improvement/new_evaluation_check/prepared_only
```

预检输出和候选准备均须使用新目录，已有记录不覆盖。本次候选准备目录为 `experiments/capability_improvement/stage_05_evaluation_feedback/prepared_only`。大型重复输入、完整原始SDK图像消息、Blender场景状态与系统副本保存在本机，通过 [local_file_index.json](../experiments/student_evaluation/stage_05_code_review/local_file_index.json) 定位；GitHub保留源码、配置、实际反馈、命令/日志、场景摘要、指标和验证记录。

本阶段停止在代码审查。未新增评价算法、失败原因归因、能力准入、候选选择/排名/晋升、多轮调度或任何建模能力。
