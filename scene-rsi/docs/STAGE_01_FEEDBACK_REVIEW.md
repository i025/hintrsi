# 第一阶段代码审查：评价反馈与独立能力库候选

本阶段已经实现单次“真实评价反馈 → SDK 改进 Agent → 独立能力库候选”的调用入口，完成代码检查和不调用模型的工程验证。到此停止，等待源码审查。没有开始新的正式学生实验，没有运行多轮 RSI，没有把任何候选切换为正式版本，也没有验证模型能自主产生有效改进。

## 一、实际审查与复用

审查基准为仓库 `ad837c5`，优先使用服务器完整工程及原始记录，而非只阅读 README。

| 已有代码 | 实际行为及本次处理 |
|---|---|
| [run_capability_acquisition.py](../harness/run_capability_acquisition.py) | `prepare/learn/validate/freeze/students` 五个阶段；生成、验证和冻结能力库，学生从固定 `libraries/Ax` 只读取库。复用 `copy_tree`、`write`、工具列表；没有修改其执行路径。 |
| [evaluate_capability_acquisition.py](../analysis/evaluate_capability_acquisition.py) | 学生结束后独立再生成、检查场景、分析代码及图像，保存结果；不调用下一次学习。评价代码及标准保持原样。 |
| [run_sdk_session.py](../harness/run_sdk_session.py) | `execute()` 管理 SDK、Bridge、模型请求预算、CPU、进程清理、轨迹和原始用量。教师通过现有 `diagnostic_teacher` 路由获得可写的独立工作区；不是旧代码题的只读教师路由。新增入口直接调用它。 |
| [sdk_student.py](../harness/sdk_student.py) | 调用原 `create_agent_options` 和 `run_agent_execution`，关闭自动 Memory/Skill，使用显式只读挂载。已有空 `initial_images`、工具列表和挂载接口足够，不需要改动。 |
| [run_cc_sdk.py](../sdk/run_cc_sdk.py) | Claude Agent SDK 管理会话、工具和压缩；保存真实消息。保留原执行循环，本次不用 CLI 原生 Agent。 |
| [codex_cli_bridge.py](../sdk/codex_cli_bridge.py) | 固定 `gpt-6.1-terra / low`，每次返回 SDK 的结构化操作；SDK 执行工具并把结果带回。原生 CLI 工具关闭，已有图像转换和 Token 记录。完全未改。 |
| [run_exploration.py](../harness/run_exploration.py) | Experiment02 生成固定教师诊断、冻结 Hint，再从共同检查点运行独立分支；不依据实验后评价更新能力库。保持原样。 |
| [代码题复盘编排](../../hint-experiment-handoff/source/benchmark/deepswe/run_loop_by_hint.py) | `step_review()` 读取真实轨迹、当前 Hint 和 Golden Diff，输出复盘；`run()` 将复盘加入下轮 `step_compress()`。复用“结果及真实证据进入下一次生成”的机制思路；不照搬其代码补丁解析、Hint 压缩或预设归因 Prompt。 |

另外检查了 Experiment01 的正式运行来源与轨迹，Experiment02 的冻结设计、教师输入与 E3/E4 来源，03-A 的生成、验证、冻结库、24 份结果和实际源码快照，以及03-B 的冻结评价设置与来源边界。新入口不把自动评价改称人工标签。

## 二、新增和修改文件

以下路径均相对于 `scene-rsi/`；核心实现只有一个新模块和一份新 Prompt。

| 文件 | 类型 | 具体作用 |
|---|---|---|
| [harness/run_capability_improvement.py](../harness/run_capability_improvement.py) | 新增 | `prepare` 准备真实反馈、独立库副本、只读证据和 GT；`run` 调现有 SDK；`collect` 保存候选、差异、Agent 报告、异常与成本。 |
| [configs/capability_improvement_prompt.txt](../configs/capability_improvement_prompt.txt) | 新增 | 完整英文改进 Prompt。允许自主调查、执行检查、实际改库、拒绝备选方案、不改动或判断证据不足；没有指定 Blender 函数、算法、材质方案或失败组件。 |
| [analysis/usage_summary.py](../analysis/usage_summary.py) | 修改两行 | `summarize(directory, scope, root=ROOT)` 新增可选路径基准，用来记录独立候选目录的成本；旧调用默认值及计算规则不变。 |
| [tests/test_capability_improvement.py](../tests/test_capability_improvement.py) | 新增 | 14 项单元检查，覆盖证据、原版保护、SDK 调用参数、增改删差异、无需修改、证据不足、中断、启动失败、无效报告、历史候选和缺失用量。SDK 调用在这些测试中被模拟，不冒充真实模型执行；另检查旧目录输出被拒绝、文件被目录替换时仍保存真实差异。 |
| [tests/preflight_capability_improvement.py](../tests/preflight_capability_improvement.py) | 新增 | 从真实03-A记录准备候选，使用原隔离环境验证可读和只读边界、候选写入与保存；不启动 SDK 或 Bridge。 |
| [.gitignore](../.gitignore) | 修改 | 只增加 `experiments/capability_improvement/**/evidence/`，避免把只读硬链接证据视图重复提交。原始证据依旧保留。 |
| [README.md](../README.md) | 修改 | 增加第一阶段入口、审查说明和验证记录链接，更新已有03归档的导航文字。 |
| `docs/STAGE_01_FEEDBACK_REVIEW.md` | 新增 | 本文，提供调用关系、完整 Prompt、真实反馈结构、保存方式、验证范围和未实现部分。 |

逐个文件的完整路径、变更类型及用途另见 [CHANGED_FILES.json](../experiments/capability_improvement/stage_01_verified_review/CHANGED_FILES.json)，包括工程输入、快照和原始检查输出。

本轮还保存了 `experiments/capability_improvement/stage_01_code_review/`、`stage_01_final_review/` 和 `stage_01_verified_review/` 工程记录。分步补充了旧容器路径说明、启动异常保存和拒绝向历史目录输出的边界，均完成了工程预检；前两次记录仍保留，最终审查以后一个目录为准。它们不是新的正式研究实验。

## 三、修改前后的实际流程

原03-A执行路径保持原样：

```text
run_capability_acquisition.py
  prepare → learn → validate → freeze → students
                                              ↓
                     evaluate_capability_acquisition.py
                                              ↓
                       记录独立评价、分析、报告 → 结束
```

新入口是在评价之后可显式调用的一次开发改进，不自动触发旧实验，也不自动循环：

```text
run_capability_improvement.py prepare
  ├─ 原 frozen library → initial/library（独立副本，只读）
  ├─ 原 frozen library → seed/library（独立副本，候选起点）
  ├─ 当前源码 → initial/system（只读快照）
  ├─ 旧 file_index → evidence（只读证据视图）
  └─ 真实评价、来源、验证、成本、历史 → inputs/feedback.json
                                      ↓
run_capability_improvement.py run
  → run_sdk_session.execute(**inputs/invocation.json)
  → isolation.prepare / isolation.command
  → sdk_student.main
  → run_cc_sdk.create_agent_options / run_agent_execution
  → Claude Agent SDK → 原 Codex CLI Bridge → gpt-6.1-terra / low
  → SDK 执行 Read/Bash/Write/Edit/Glob/Grep
  → Agent 自主调查及选择，实际写 /app/library 与 update_report.json
                                      ↓
collect（正常完成或异常退出后保存）
  → candidate/library + library.diff + file_changes.json
  → 原样 update_report.json、成本、SDK 轨迹和异常
  → independent_validation_status=not_run
  → promotion_status=not_promoted
  → 停止，等待审查
```

旧的学生任务仍从原 `experiment_03a_capability_acquisition/libraries/Ax` 取库，不读取新候选目录，因此生成或保存候选不会改变下一次旧实验的正式版本。

## 四、反馈结构与真实文件入口

完整实例见 [feedback_example.json](../experiments/capability_improvement/stage_01_verified_review/feedback_example.json)，为最终工程预检实际准备的输入，约40 KB。它包含24条原始结果记录，没有人为添加失败原因。以下是字段说明：

| 字段 | 实际内容 |
|---|---|
| `execution_budget` | 当前单次调用的时间、请求数、CPU、端口、模型和 effort；准备后固化于调用记录。 |
| `path_mapping` | 服务器项目根路径到 `/evidence` 的映射；原记录的绝对路径保留。 |
| `historical_container_paths` | 原会话 `/app`、`/capture`、`/capabilities` 等对应哪个历史目录，避免和当前候选 `/app` 混淆。 |
| `data_policy` | 03-A结果重新归类为历史开发经验；明确未来独立测试需要新的留出场景。只写新记录，不改原冻结划分及历史报告。 |
| `components` | 原库、新候选库、当前 Harness/SDK/评价源码快照、冻结时的真实来源记录。 |
| `generation`、`validation` | 原学习输入、Prompt、执行目录、源码/轨迹/实际检查、验证报告及被拒绝方案的入口。 |
| `student_outcomes` | 现有 `analysis/observed_results.json` 的原始内容，含完整交付、再生成、辅助指标、自动估计和空人工评分。 |
| `student_runs` | 每次执行的真实工具轨迹、Blender代码、场景、渲染及独立评价目录。 |
| `independent_evaluation` | 原始评价结果与评价者记录，不只是报告里的归纳。 |
| `costs` | 03-A实际104个会话、476次请求、已知15,544,359输入＋输出Token、12次缺失用量；实际美元账单未知。原始请求、用量和资源记录同样可读。 |
| `allowed_development_gt` | 仅直接挂载原开发 S01/S02/S03 的完整GT；旧评价中可能已有GT派生观察。没有挂载03-A原测试场景的完整GT目录。 |
| `candidate_history` | `--history` 显式提供的历史记录、修改前后文件、差异、报告、成本和实际会话轨迹。第一份预检输入为空，未虚构历史成功或失败候选。 |
| `evidence_index`、`unavailable_evidence` | 实际可访问文件的索引和缺失项；文件名出现在旧清单里不代表已获访问权限。 |

真实样例中的一条结果为 `A-T01-A2`：SDK状态是 `completed`，但 `complete_delivery=false`，代码、场景与渲染均未产生，`human_rating=null`。这组事实原样进入输入；没有提前告诉改进 Agent 应将其归因于哪个组件。其他23条结果和对照也一并提供。

最终证据视图包含 **35,070个实际文件，缺失项0**。复用原索引建立硬链接视图，避免复制数GB载荷，再通过原隔离机制将整个视图只读挂载。因此候选目录应位于和工程相同的文件系统，推荐使用 `experiments/capability_improvement/`。`initial/library` 和可写候选使用普通独立副本，不与原库硬链接。`/initial/system` 保存当前 `sdk/harness/analysis/configs` 内容。

原始模型消息、调用与工具结果仍在 `session/bridge`、`session/proxy` 和 `session/capture/trajs.json` 等现有位置；新增入口没有再建模型适配器或另一个 Agent 框架。只读挂载和网络隔离来自既有 Harness，不只依靠 Prompt。

## 五、候选的实际保存方式

```text
experiments/capability_improvement/C001/
  candidate.json                 # 机械状态、Agent决策、验证/晋升状态、后续验证输入
  initial/library/               # 修改前能力库独立副本
  initial/system/                # 修改前相关系统源码快照
  seed/library/                  # SDK工作区的独立起点
  inputs/
    feedback.json                # 真实反馈
    evidence_index.json          # 原始证据访问索引
    prompt.txt                   # 实际交给Agent的完整Prompt
    session.json                 # 工具和只读挂载
    invocation.json              # 冻结的execute()参数
  evidence/                      # 原始资料的只读硬链接视图，不重复提交Git
  session/
    workspace/library/           # Agent实际可写库；容器内/app/library
    workspace/update_report.json # Agent实际输出；可能缺失或格式无效，原样保留
    capture/                     # SDK轨迹和真实Blender执行捕获
    bridge/、proxy/              # 实际模型请求、返回、图像、用量
    resources.jsonl、status.json # 实际运行状态与资源
  execution_error.json           # 执行异常时存在；保存异常类型与原因，不吞掉异常
  candidate/
    library/                     # 执行结束后的独立候选快照
    library.diff                 # 增、改、删的实际文本差异
    file_changes.json
    update_report.json           # 原样复制的报告；缺失时不伪造
    costs.json                   # 已观察请求/Token/执行成本，缺失用量保留未知
```

`status=collected` 仅说明文件收集结束，不说明执行成功或候选有效。`session_state`、`execution_error`、`report_status` 和 `agent_decision` 分开记录。Agent可以返回 `candidate_update`、`no_change` 或 `insufficient_evidence`；实际文件差异也单独保存。没有合法报告时，决策保持未知，不把正常SDK退出等同于实际交付。

无论候选生成是否成功，都保持 `independent_validation_status=not_run`、`promotion_status=not_promoted`。Agent自己做的检查保存在原始轨迹和报告里，不被冒充独立验证。三个入口只允许向 `experiments/capability_improvement/` 下的新尝试目录输出，拒绝把旧实验或原库目录用作输出。新的 `prepare` 或 `run` 不允许覆盖既有尝试；`collect` 也不会覆盖已保存候选。

## 六、调用方式（本次未执行真实run）

在服务器完整 `scene-rsi` 工程内，审查后可使用：

```bash
/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -B harness/run_capability_improvement.py prepare \
  --condition A3 --directory experiments/capability_improvement/C001 \
  --seconds 600 --calls 24

/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -B harness/run_capability_improvement.py run \
  --directory experiments/capability_improvement/C001
```

`prepare` 只准备文件，不调用模型；`run` 才启动单个改进SDK会话，使用已经保存的预算、工具、Prompt与挂载。默认预算是600秒、24请求、CPU32–39、端口19665，可在准备时显式设置，并非本阶段已执行的研究配置。`collect` 用于已有会话尚未收集的情况，正常 `run` 已在 `finally` 中完成收集，不应再次收集同一目录。

`--history <既有候选目录>` 可重复提供历史候选。这里只是读取历史的输入接口，不包含多轮搜索、自动选择下一轮或自动晋升。

## 七、已经完成的工程验证及边界

最终记录见 [verification.json](../experiments/capability_improvement/stage_01_verified_review/verification.json) 和 [unit_tests.log](../experiments/capability_improvement/stage_01_verified_review/unit_tests.log)。

- **14项单元检查通过**，包含真实结果的缺失交付、原始轨迹访问、修改前后独立性、实际增改删差异、三种决策、已有SDK参数派发、异常和启动失败留存、无效报告、历史候选、旧用量接口及缺失用量。
- 三次真实资料预检均通过，最终一次约 **25.15秒**。使用真实隔离环境读取了真实反馈、学生轨迹、代码、`.blend` 和渲染；验证 `/app/library` 可写。
- 通过无截断、无实际写入的写模式打开测试，确认原库、原始学生轨迹和开发GT均只读；宿主完整工程路径及03-A原测试GT未挂载。
- 原01–03实验 **59,289个历史文件** 的大小和修改时间未变；五份冻结库逐文件内容未变。没有建立哈希或校验和系统。
- 与 `ad837c5` 直接比较，用户指定的7份现有核心执行源码完全相同，只有新入口、新Prompt及用量函数的可选参数等本阶段改动。
- **新模型调用0、正式学生重建0、GPU使用0、重新下载/安装环境0。** 未启动 SDK 或 Bridge，因此没有复制登录凭据或遗留模型会话。

为证明候选文件确实可保存，隔离预检只新增了 `ENGINEERING_PROBE.md` 标记，并在候选差异中保留。该标记由工程探针写入，不是模型产生的能力，不包含空间、几何或材质实现，不作为研究改进。预检没有Agent报告，因此 `agent_decision=null`、`report_status=missing`；这些状态没有被伪造成模型成功。

测试需使用已有完整实验记录；Git仓库中的可浏览子集不包含全部原始请求和捕获，需要本机完整工程或先恢复对应Release归档。本次没有为测试重新下载这些数据。

可复查的命令为：

```bash
PYTHONDONTWRITEBYTECODE=1 /srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -B -m unittest discover -s tests -v

PYTHONDONTWRITEBYTECODE=1 /srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -B tests/preflight_capability_improvement.py \
  --output experiments/capability_improvement/another_engineering_check
```

## 八、尚未实现及停止位置

没有运行真实改进模型，尚未验证模型会如何选择调查、是否修改或产出更好的能力。这需要后续审查后的单独授权与开发验证。

本阶段没有实现候选独立执行验证、候选排名、自动晋升、多轮RSI调度、完整Harness自修改、Meta-Agent演化、模型权重更新或新的正式独立测试。`candidate/library`、`update_report.json`、`costs.json` 和 `--history` 已为后续验证及迭代保留输入接口；本阶段没有提前执行它们。

## 九、改进Agent的完整英文Prompt

以下正文与 [configs/capability_improvement_prompt.txt](../configs/capability_improvement_prompt.txt) 一致。实际调用副本在候选目录 `inputs/prompt.txt`；原SDK的系统提示与真实模型消息继续按已有机制保存。

```text
You are the development improvement agent for an editable Blender reconstruction system. Your task is to investigate actual evaluation feedback and, when supported by evidence, modify a candidate capability library. Use the existing SDK tools in this workspace. The original system and frozen libraries are read-only; your candidate is not a promoted student version.

Start with /feedback/feedback.json. It contains actual recorded outcomes, costs, provenance, current component paths, and entries into the original evidence. /feedback/evidence_index.json lists the available historical files. Original records may contain host paths: use the host_root to mounted_root mapping in feedback.json to locate the corresponding files. For paths inside earlier containers, use historical_container_paths rather than treating an old /app as this candidate workspace. An old inventory is not an access grant. Read the evidence needed for your investigation rather than automatically re-auditing every historical trajectory.

The current library before this attempt is /initial/library. The writable candidate starts as an independent copy at /app/library. The current SDK, student Harness, and configuration are preserved at /initial/system. Historical source snapshots describe the versions actually used in earlier runs. Inspect their real contents when relevant; do not infer implementation behavior from a report or README alone.

You may investigate the library's generation sources and process, validation attempts, actual student SDK messages and tool results, written and executed Blender code, saved scenes, renders, independent evaluations, prior successful or unsuccessful checks, rejected alternatives, and actual costs. The evidence index and feedback record point to these files. You may read images and inspect accessible Blender files using the existing environment. Only the development GT directories explicitly listed in feedback.json are mounted as GT sources. Original A1-A5 information restrictions describe historical conditions, not the current development agent's permission boundary.

Experiment03-A outcomes made available here are historical development experience. They cannot be reused as an independent test of a candidate informed by them. Any future independent test must use new held-out scenes. Do not access unavailable data, retrieve external reference scenes, or infer hidden model reasoning.

Choose your own investigation and update. Determine what the evidence supports, which competing explanations remain, whether further checks are useful within the budget, and whether any change is justified. No particular component is presumed responsible. You may identify issues outside the editable scope and explain them, but this stage only permits capability-library changes. Do not modify the student Harness, SDK, bridge, evaluator, improvement controller, prompts, original records, or GT.

If an update is justified, implement it in /app/library, not merely in a proposal. Keep the public library transferable: readable English documentation, Python and JSON, with SKILL.md and capabilities.json as entry points. Retain the existing limits of 6,000 documentation/JSON words, 1,200 nonblank Python lines, and 120 KiB, using only .md, .py, and .json files. Keep task-specific measurements, GT data, scenes, images, original assets, complete historical reconstructions, probes, and development answers outside library/. Do not encode a historical scene's solution in a general capability.

You may create investigation notes and checks elsewhere in /app and execute them through the tools. Preserve failed checks and rejected alternatives. Describe a proposed check as unexecuted until an actual tool result establishes otherwise. Distinguish proposed methods, written code, execution, observed output, and final retained changes. Independent evaluator results, automatic model judgments, and actual human ratings are different evidence types. Missing observations and missing usage remain unknown; do not turn them into successful checks or zero cost. A check you perform is not independent candidate validation or proof of transfer.

You may instead conclude that evidence is insufficient or that no library change is warranted. Do not force a change to satisfy the task. Never claim that a generated candidate is an improved or promoted version solely because files were produced.

Before finishing, write /app/update_report.json as English JSON with:
- decision: candidate_update, no_change, or insufficient_evidence.
- observations: claims with specific evidence paths and event/code locations.
- investigations: questions examined, commands actually executed, observations, and remaining uncertainty.
- changes: actual file changes, their evidence-supported reasons, expected effects, and possible side effects.
- rejected_candidates: alternatives considered or tried, their evidence, and why they were not retained.
- further_validation: concrete checks still needed and the observations that would support or reject the candidate.
- limitations: unresolved explanations and issues outside the editable scope.

Save the actual candidate files and report, then finish. The controller will preserve the initial version, your input and trajectory, candidate snapshot, diff, and costs. It will not start student reconstruction, independently validate, rank, promote, or launch another improvement round. The recorded execution budget in feedback.json applies to this single attempt.
```
