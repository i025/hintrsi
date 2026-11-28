# 第四阶段代码审查：通用独立 Student 入口

基于 `2e342e6`。本次只建立“外部参考图和可选能力库 → 原SDK学生 → 交付与原始记录”的单次入口。不启动正式重建、不调用模型，不接入独立评价、自动晋升或下一轮调度。

## 修改文件与复用边界

| 文件 | 作用 |
|---|---|
| [harness/run_student.py](../harness/run_student.py)（新增） | 读取外部配置、冻结参考图和可选库、准备原SDK会话、调用既有 `execute`、分别收集执行与交付状态。 |
| [harness/run_capability_acquisition.py](../harness/run_capability_acquisition.py) | 将原能力注入文本抽成 `with_capability_library(prompt, library)`；原 `student_jobs()` 仅改为调用此函数。A0–A5分组、原任务划分、挂载、调度和其他算法不变。 |
| [configs/student_inputs/](../configs/student_inputs/)（新增三份JSON） | 同一参考图配合原始A3库、历史候选库、空库的外部输入例子。 |
| [tests/test_student.py](../tests/test_student.py)（新增） | 11项离线检查，覆盖外部起点、预算、快照、旧入口一致性、交付状态和失败留存等。 |
| [tests/preflight_student.py](../tests/preflight_student.py)（新增） | 三种真实文件输入的隔离预检：实际SDK图像/文本输入、只读库、工具配置、Bash文件操作及Blender版本命令。 |
| [README.md](../README.md)、本文件、仓库顶层README | 当前入口、配置、调用关系、验收与限制。前三阶段审查文档保留原文。 |
| [工程验收记录](../experiments/student_execution/stage_04_code_review/) | 单元日志、原始配置、SDK构造输入、挂载命令、Blender记录、结果及未修改源码对照。 |

[集中实际差异](../experiments/student_execution/stage_04_code_review/implementation.diff)只含实现、配置、测试和文档，不混入工程生成记录。

没有修改 `run_sdk_session.py`、`sdk_student.py`、`isolation.py`、`run_experiment.py`、SDK、Bridge、评价算法或前三阶段改进入口。复用第三阶段的已审查源码清单，只在学生环境开放其中七个SDK文件，不增加历史研究知识入口。

## 外部配置

三个完整例子是 [a3.json](../configs/student_inputs/a3.json)、[candidate.json](../configs/student_inputs/candidate.json) 和 [base.json](../configs/student_inputs/base.json)。路径相对**配置文件所在目录**解析，支持绝对路径。

```json
{
  "run_id": "S01-a3",
  "output_directory": "../../experiments/student_execution/examples/S01-a3",
  "reference_image": "../../data/evaluation_gt/office/office_s1210607561/color.png",
  "capability_library": "../../experiments/experiment_03a_capability_acquisition/libraries/A3",
  "budget": {
    "seconds": 1500,
    "calls": 120,
    "cpus": [32, 33, 34, 35, 36, 37, 38, 39],
    "port": 19765
  }
}
```

`capability_library` 为 `null`、空字符串或省略时，准备无能力库学生；其他字段必填。库路径可以是原始冻结库、此前候选的 `candidate/library`，或者其他符合原有结构的目录，不经过A组名称推断。输出必须是新目录，不能位于输入库内部；不会覆盖已有运行、库、候选或旧实验。不同运行使用不同目录，准备失败的部分记录也不会被自动清除后重做。

本次候选示例指向第一阶段保存的工程候选，含 `ENGINEERING_PROBE.md`，仅用于证明任意已保存目录可直接作为输入，不是模型学习成果。

参考图沿用原SDK的PNG协议；PNG字节直接复制，保持与已有实验一致。非PNG会在准备时明确报错，避免将其他格式错误标为 `image/png`。本次没有安装图像依赖或扩展原SDK媒体协议。

模型仍由既有后端固定为 `gpt-6.1-terra / low`。时间、请求数、CPU及端口从外部预算传给原 `execute`。共同 `formal_prompt.txt` 保持原文件不变；当预算不是1500秒/120请求时，只替换其中时间和请求上限句。默认预算下Prompt原文不变，非默认预算使用明确秒数。Blender仍使用CPU、八线程，交付分辨率仍为640×360；CPU亲和性按传入CPU列表设置。

## 能力注入与信息边界

原03-A和新入口使用同一 `with_capability_library`：

1. 有库时，将指定库的 `SKILL.md` 正文拼入初始Prompt。
2. 延用原英文说明：库只读位于 `/capabilities`，学生可按适用性选择使用或采用自己的方法，并自行保留交付代码的必要依赖。
3. 不强制调用任何方法，不改变六个工具、Skill自动加载或在线教师策略。

新入口先将选定库复制到本次运行的 `library/`，再从该副本读取 `SKILL.md` 并只读挂载 `/capabilities`。因此Prompt和实际可读库来自同一保存版本；来源目录之后的修改不影响已准备的副本。`run.json` 保存来源路径、运行副本路径和文件名/字节数清单；副本本身保存实际内容，没有哈希或版本树。

学生可见的是匿名 `/app/reference.png`、自己的空白工作区、共同SDK/工具和可选 `/capabilities`。原始外部 `input.json`、`run.json` 及库来源信息保存在宿主运行根目录，不挂入学生 `/inputs`；参考图即使来自GT目录，也只复制该PNG，不挂载其父目录或旁边的GT。

不会因选择候选而提供其生成过程、教师反馈、历史轨迹、改进报告、完整系统归档、其他库或GT。库本身已编码的知识不会被清除，也不新增准入判定或宣称候选已获准晋升。

## 调用关系与命令

```text
外部配置
  → run_student.prepare(input_file)
      → 新目录 + 输入配置副本 + 参考图副本 + 可选库副本
      → formal_prompt：仅调整本次预算句
      → run_capability_acquisition.with_capability_library
      → isolation.prepare：workspace、images.json、prompt、session
      → inputs/invocation.json + run.json(status=prepared)
  → run_student.run(directory)
      → run_sdk_session.execute(**已保存参数)
          → 原Bridge / LiteLLM代理
          → isolation.command
          → sdk_student → run_cc_sdk → Claude Agent SDK
          → 原Codex CLI Bridge → gpt-6.1-terra / low
          → SDK工具执行，真实结果回到上下文；保留原始轨迹及Blender捕获
      → finally: run_student.collect
          → 原 usage_summary.summarize
          → costs.json、result.json、run.json
```

准备一个新运行（不调用模型）：

```bash
/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -B harness/run_student.py prepare \
  --input configs/student_inputs/a3.json
```

审查之后的真实执行命令仍是单个原SDK会话：

```bash
/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -B harness/run_student.py run \
  --directory experiments/student_execution/examples/S01-a3
```

**本次未执行上述真实 `run`。** 正常 `run` 在 `finally` 中完成收集；`collect --directory ...` 只用于尚未收集的恢复情况，既有结果不覆盖、不重跑。原03-A命令及Experiment02的教师检查点方式保持可用。

## 输出与状态

采用现有运行根目录结构，工作区不增加新的任务阶段：

```text
run/
  input.json                       # 原始外部配置，仅宿主可见
  run.json                         # run_id、来源、快照、预算、状态
  library/                         # 可选实际运行库，只读挂载
  runtime/sdk/                     # 通用SDK运行副本
  inputs/
    reference.png、base_prompt.txt、prompt.txt、images.json
    session.json、invocation.json
  workspace/
    reference.png
    build.py、scene.blend、final.png # 由学生实际产生；缺失时不补造
  capture/                         # SDK轨迹、Blender源码版本、命令、日志、场景/图像
  bridge/、proxy/、sdk_command.json # 真实模型请求、返回、Token和原执行命令
  status.json、resources.jsonl     # 原监督器执行记录
  costs.json                       # 原用量汇总，缺失用量仍未知
  execution_error.json             # 异常时存在
  result.json                      # 分开记录执行与交付
```

`result.json.supervisor_state` 保存原监督器状态；`sdk_status` 独立读取真实轨迹/监督器的SDK状态。`delivery` 只检查三个要求文件是否存在且非空：

- `missing_files`：至少一个缺失或为空。
- `files_present_unvalidated`：三个文件存在且非空，未证明场景可打开、代码可复现或视觉恢复正确。

正常SDK结束但没有交付时，仍记录缺失。执行异常时保存实际部分文件、错误和成本，不补写答案。`run.json.status=collected` 只说明结果已收集。`independent_quality_evaluation=not_run`、`candidate_promotion=not_performed` 始终明确本入口没有执行独立验证或晋升。

原评价程序需要的 `workspace/`、`capture/`、`sdk_command.json`、状态、实际源图和可选库快照均保留。其03-A批处理CLI仍依赖原任务划分/命名；本阶段没有把任意新运行自动接到该CLI，也没有改其评价算法或启动评价。

## 工程验收

[单元日志](../experiments/student_execution/stage_04_code_review/unit_tests.log)：36项全部通过（前阶段25项＋本阶段11项）。其中用真实五组冻结库和历史Prompt生成原03-A学生任务，A0–A5六份Prompt逐字节匹配旧文件，挂载内容不变；新入口覆盖外部A3/历史候选/空库、非默认预算、独立副本、来源保护、状态分离、异常、未知用量及重复运行拒绝。

[真实隔离预检](../experiments/student_execution/stage_04_code_review/preflight/verification.json)使用同一已有办公室PNG，分别选择真实A3库、真实历史候选库、空库。每次都是新的独立目录和隔离进程：

- 原 `sdk_student.prompt_messages()` 实际构造图像和文本消息，解码后的图像字节与输入PNG一致，`SKILL.md` 注入来自实际只读副本。消息保存为 `capture/preflight_sdk_input.json`，明确标记**构造但未发送**。
- 隔离内逐文件读取可见库，返回内容与外部指定来源直接字节比较，确认候选起点不是重新读取A3；空库时没有 `/capabilities`。
- 真实六工具配置、SDK客户端构造和Bridge模型/effort核对通过，没有连接或查询模型。
- 实际Bash与文件读写/修改通过；每次执行 `blender --version`，均返回Blender5.2.2并经原记录器保存命令、stdout、stderr和结果。没有建模、渲染或假交付文件。
- 宿主完整工程路径、GT、历史证据、历史分析源码和候选父目录不可访问；原始外部配置不在学生 `/inputs` 中。
- 原库、历史候选和参考图内容不变；用原收集函数保存工程结果，`sdk_status=null`、交付缺失、未评价、未晋升，没有冒充完成重建。

原SDK、Bridge、学生执行、隔离、Improvement、知识提取和评价源码的未修改对照见 [preserved_sources.json](../experiments/student_execution/stage_04_code_review/preserved_sources.json)。能力注入函数抽取的实际差异单独列明。

复查命令：

```bash
PYTHONDONTWRITEBYTECODE=1 /srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -B -m unittest discover -s tests -v

PYTHONDONTWRITEBYTECODE=1 /srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -B tests/preflight_student.py \
  --output experiments/student_execution/new_offline_check
```

这些检查需要已有完整工程及历史文件；没有重新下载或安装环境。预检实际调用模型0、正式重建0。SDK输入和工具环境经过离线检查，没有模型驱动的完整工具往返；未来真实重建效果和候选收益仍未知。

GitHub保存本次源码、配置和实际工程记录；重复SDK副本留在本机，当前SDK源码在仓库 `scene-rsi/sdk/`。没有新增教师算法、能力准入、知识提取、GT学习、强制调用、独立评价、自动晋升、多轮搜索或Harness自修改。本阶段停止在代码审查。
