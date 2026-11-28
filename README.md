# Hint RSI：代码题与三维场景实验、实现和完整记录

这里整理了原始 Hint 实验交接包、Ofox 补充 baseline，以及后续通过 Codex CLI 运行的各版代码、配置、测试、实验成绩和诊断记录。上传整理时间：2026-11-24。原始实验目录保留，仓库是独立的脱敏副本。

## 2026-11-28：Scene 能力获取与教师评价实验

新增 [实验 03-A 报告](scene-rsi/experiments/experiment_03a_capability_acquisition/REPORT_ZH.md)与[实验 03-B 报告](scene-rsi/experiments/experiment_03b_teacher_alignment/REPORT_ZH.md)。03-A 为四个新场景 × A0–A5 六组，共 24 次独立学生运行，22 次完整交付、2 次未生成文件；没有建立稳定迁移收益或 A5 最优的结论。03-B 完成 32 次 T0/T1 自动评价，未收集真实人工标签，T2/T3 尚未运行，不能宣称完成人类对齐。

[03-A 对照页面](scene-rsi/experiments/experiment_03a_capability_acquisition/analysis/comparison.html)、[03-B 人工评价材料](scene-rsi/experiments/experiment_03b_teacher_alignment/human_review/independent/index.html)、[联合调用与 Token 账本](scene-rsi/experiments/experiment_03_usage_summary.json)。147 个 SDK 会话共 570 次请求，已知输入＋输出 16,566,207 Token，14 次请求缺少用量，实际 Codex 美元账单未知。完整原始轨迹、场景与 GT 见 [实验 03 Release](https://github.com/i025/hintrsi/releases/tag/scene-rsi-experiment-03)。旧实验保留独立。

## 2026-11-28：Scene 教师诊断与主动探索实验

新增 [Scene 实验 02](scene-rsi/experiments/experiment_02_teacher_guided_exploration/README.md)：三个共同检查点、E0–E4 五组、每组两次，共 30 次学生重建；全部完成独立再生成且交付渲染逐像素一致。教师 Hint 改变了部分策略和缺陷，但主动探索并非始终优于其他组；这不代表完成了 RSI 或可迁移能力学习。

入口：[中文研究报告](scene-rsi/experiments/experiment_02_teacher_guided_exploration/REPORT_ZH.md)、[核心对照图](scene-rsi/experiments/experiment_02_teacher_guided_exploration/analysis/comparison_core.png)、[重复实验对照图](scene-rsi/experiments/experiment_02_teacher_guided_exploration/analysis/comparison_repeat.png)。源码、分析、学生交付和人工评价材料可在仓库浏览；完整原始模型请求、工具轨迹和场景记录见 [GitHub Release](https://github.com/i025/hintrsi/releases/tag/scene-rsi-experiment-02)，具体范围见 [上传记录](scene-rsi/experiments/experiment_02_teacher_guided_exploration/publication.json)。历史实验保持独立。

## 2026-11-27：Scene 自然重建轨迹实验

新增独立 [Scene 工程](scene-rsi/README.md)：复用代码题的 Claude Agent SDK 与 Codex CLI Bridge，建立独立的 Blender 重建 Harness。办公室、卧室、厨房各独立运行三次；九次均完成可编辑场景交付和独立再生成。这里是自然轨迹分析，没有教师指导或完整 RSI，也不把技术完成度当作视觉质量成功率。

[中文研究报告](scene-rsi/experiments/experiment_01_natural_trajectories/REPORT_ZH.md)包含策略相似度、重复缺陷、互补方法与实际消耗；[完整运行记录](scene-rsi/experiments/experiment_01_natural_trajectories/runs)包含原始模型/工具轨迹、代码、场景和渲染。三个完整 IDEAL-Scenes GT 及评价材料也在 `scene-rsi/` 中；上传范围见 [publication.json](scene-rsi/publication.json)。该目录的 Blender 文件直接存储在 Git 中，不适用下方历史代码题大文件压缩说明。

## 2026-11-27：Trajectory-to-Capability RSI

新增[研究交付入口](trajectory-to-capability/README.md)：原六小时实验与授权续做分别归档，包含中文报告、修改后源码、全部能力库、29 次扩展尝试的完整成绩和原始轨迹，以及 Hint RSI／Scene 审计。后续两道终测各主要条件均正式通过 1/2，未提供 K2 优于普通轨迹总结的证据；共同基线超时、空补丁与技术中断均单独保留。详见[最终研究报告](trajectory-to-capability/outputs/trajectory_capability_followup_20261126_182329/research_report_zh.md)与[本次上传说明](publication/trajectory-capability/README.md)。

下方原版本说明和状态表保留 2026-11-24 的历史口径；最新研究结果以上述新增目录为准。

## 先看哪些文件

| 内容 | 入口 |
|---|---|
| 原实验是什么、历史十题与 Prompt | [原始交接说明](hint-experiment-handoff/README.md) · [实验解读](hint-experiment-handoff/docs/实验解读.md) |
| 最新代码和接入修复 | [第 13 版说明](hint-codex-experiments/README_parallel_13.md) · [源码](hint-codex-experiments/source_parallel_13/) |
| 最新预检、Token 与耗时 | [第 13 版验证记录](hint-codex-experiments/reports/parallel_13_validation.json) · [就绪记录](hint-codex-experiments/reports/parallel_13_readiness.json) |
| 最近一次正式批次的结果和问题 | [第 12 批状态核查](hint-codex-experiments/reports/parallel_12_status.json) · [逐次成绩](hint-codex-experiments/runs/codex_parallel_12/attempt_metrics.csv) |
| Ofox 补充 baseline | [逐题结果](hint-baseline-run/baseline_results.csv) · [原始状态](hint-baseline-run/baseline_state.json) |
| 后续两个尝试方向 | [方向记录](hint-experiment-next-directions.md) |
| 上传范围、压缩和脱敏 | [上传说明](publication/README.md) · [完整文件映射](publication/file-manifest.json) |

## 目前结果及其边界

这些记录来自不同模型、协议和接入版本，不能合并成同一组成功率。

| 实验或验证 | 已有结果 | 解释边界 |
|---|---|---|
| 原始历史十题 | 交接文档报告 baseline 5/10、Hint 循环 9/10；Hint 首轮 3/10 | 历史报告，未在此次整理中重跑；历史模型版本未能确定 |
| Ofox 补充 baseline | 3 题通过、3 题未通过、4 题未完成 | `deepseek/deepseek-v4.1-flash-1017`；每题一个正式解题尝试；含 2/8 vCPU 和超时、费用保护差异；不是严格同模型对照 |
| Codex 第 12 批 | 53 次实际尝试完成评测：1 次通过、52 次未通过；另有 3 次尝试中断 | 共 56 次尝试启动，H/M 共用首轮只计一次；通过的是 Claude Code I2；批次因接入故障停止，不是完整九题对照 |
| 第 13 版修复验证 | 117 项回归检查通过；真实 SQLfmt 验证有非空补丁，F2P 30/32、P2P 1271/1273，未解出 | 属于预检；64 次真实模型请求共报告 3,141,263 Token；**第 13 批正式实验尚未启动** |

第 12 批已报告用量为 24,362,922 Token，另有 1 个请求用量未知。缓存输入已经包含在输入 Token 内，不能重复相加。这里的 Token 记录不能直接当作美元支出。历史 Anko 成绩与新九题分开记录。

更早批次的报告、补评测、停止原因和消耗均保留在原目录；旧文档中的“当前状态”指它写入时的状态，请优先以本页及第 13 版记录判断最新情况。不能把技术中断算作正常失败，也不能把预检成绩填入正式实验。

## 框架与对照组

框架通过教师生成指导、压缩、学生使用工具修改代码、导出补丁、独立测试、失败复盘来工作。教师可以读取 GT 参考补丁，GT 本身保持不变；复盘更新的是指导。模型权重没有训练更新。

| 组别 | 机制 |
|---|---|
| B | 无 GT Hint，最多五次从初始代码与新会话开始的尝试 |
| H | 初始 GT Hint；失败后由新的教师会话复盘，学生重新尝试 |
| M | 初始指导和后续复盘由同一个教师 SDK 会话完成 |
| I | 初始指导和轮间复盘之外，教师还根据轮内工具轨迹阶段性提供受限指导 |

H/M 共用一次实际首轮，后续分别运行。每次学生尝试内部包含多次模型响应和工具调用；外层重新尝试不继承上一轮代码。一轮内的对话、工具执行和压缩由原 SDK 管理；第 13 版每次模型决策用独立的 `codex exec` 返回结构化操作，由 SDK 执行。

第 13 版统一使用 `gpt-6.1-terra / low`；六套 VM 各 8 vCPU/144 GiB，任务容器 8 CPU/128 GiB，评测内存 8 GiB，无 GPU。I 组每 20 个主会话工具调用检查一次，最多三次，每条指导最多 100 个英文单词。学生活动超时 7200 秒。完整参数以[配置文件](hint-codex-experiments/reports/parallel_13_config.json)为准。

CLI 接入没有被认定为原始 API 的严格等价替换：采样参数、角色传递和部分模型能力仍有差异，相关限制及审计均保留。当前记录也尚不能证明 I 或 M 显著优于其他组，或证明去掉教师后学生获得了可泛化能力。

## 目录

```text
hint-experiment-handoff/         原始交接源码、Prompt、历史结果和说明
hint-baseline-run/               Ofox baseline、费用监控代码、数据、逐题轨迹和评测
hint-codex-experiments/
  source*/                      各次接入和实验代码，最新为 source_parallel_13
  tests*/                       对应版本测试
  reports/                      配置、状态、代码差异、源码快照及结果核查
  runs/                         历次正式尝试、Hint、轨迹、补丁与评测结果
  logs/                         模型请求、事件、Token 与进度日志
  preflight/                    预检代码、结果、故障诊断和原始证据
  vm*/                          VM 启动代码和运行元数据；不含磁盘和运行时二进制
hint-experiment-next-directions.md
publication/                    上传清单、文件映射、排除项和整理说明
```

大于 4 MiB 的未压缩文件以 `.gz` 上传；具体路径在文件映射中逐一记录。例如 `trajs.json.gz` 解压后仍是原来的 JSON。小文件和汇总结果可直接浏览，完整轨迹没有因体积而省略。

## 在其他机器使用

1. 克隆仓库后，先读[原运行指南](hint-experiment-handoff/docs/运行指南.md)和相应版本说明。
2. 安装独立依赖环境，准备任务容器与 Docker；`hint-baseline-run/data/` 保存了本次使用的任务定义、参考补丁和 Parquet。
3. 按本机位置调整配置中的绝对路径、VM 端口和资源设置。历史状态中的本机路径保留用于解释记录，不代表克隆后即可直接运行。
4. 自行配置模型登录或 API 凭据。本仓库不含认证文件、SSH 私钥、虚拟机镜像或已安装环境；启动 VM 的脚本引用的这些外部文件需重新准备。

本次上传没有启动或续跑实验。源文件的来源说明保留在 [SOURCE.md](hint-experiment-handoff/SOURCE.md)；任务及第三方代码继续遵循其原来源和许可，不统一重新授权。旧文件中的 SHA 清单是历史记录，脱敏和归档整理后不能用来校验此发布副本；本次没有新增哈希校验。
