# Scene RSI

这是独立的图像到可编辑 Blender 场景工程。学生沿用 hintrsi 的 Claude Agent SDK 执行循环，Codex CLI Bridge 调用 `gpt-6.1-terra`（low）返回模型决策，工具由 SDK 执行。实验 01 研究无教师的自然重建轨迹；实验 02 研究固定教师 Hint 对共同检查点分支的影响。实验 03-A 进行一轮外部能力库获取与新场景迁移；实验 03-B 冻结通用教师和人类原则引导教师的 RGB 评价。各批均没有进行完整 RSI、模型微调、长期递归能力增长或正式人类审美对齐。

- `sdk/`：复用 trajectory-to-capability 的 SDK、Bridge、消息转换与日志代码；多模态改动见实验目录的 `sdk_changes.diff`。
- `harness/`：新建的文件与网络隔离、SDK 入口、透明 Blender 记录器及实验调度。没有 SceneEvolve 建模策略。
- `configs/`：统一英文提示词、冻结场景清单与资源配置。
- `data/`：IDEAL-Scenes 的少量候选、共同开发 GT 和实验 03 冻结的新场景数据；GT 仅挂载给获准的开发教师或独立评价端。
- `analysis/`：实验结束后的场景提取、复现、轨迹比较和人工评价材料生成。
- `experiments/experiment_01_natural_trajectories/`：真实预检、工程中断、九次正式执行及报告。
- `experiments/experiment_02_teacher_guided_exploration/`：三个共同检查点、E0–E4 五组、核心 15 次与额外完整重复 15 次，以及独立评价和候选知识。
- `experiments/experiment_03a_capability_acquisition/`：五种知识来源生成并冻结能力库，四个新参考场景 × A0–A5 六组，共 24 次独立学生运行及事后评价。
- `experiments/experiment_03b_teacher_alignment/`：12 个开发案例与 4 个独立案例的 T0/T1 冻结批评，匿名人工表单和真实反馈接收接口。

实验 01、02 的正式场景为办公室、卧室、厨房。实验 01 每场景独立重建三次，仅提供匿名 RGB。实验 02 从指定自然检查点开始，各组使用相同代码、场景、初始渲染与参考 RGB，采用全新 SDK 会话。GT 和其他结果不挂载给学生；实验 02 教师也没有 GT。每次学生预算为 25 分钟、120 次模型请求、8 个 CPU 核，要求 640×360 最终渲染。运行库源码可见范围、实际工具访问与其他限制分别记录在各批报告。

实验协议、实际工程修复、源码快照和中文报告保存在各自实验目录。SDK 自报的美元费用不是 Codex 实际账单；实际记录请求数、Token 和耗时。

数据来源：[IDEAL-Scenes](https://huggingface.co/datasets/IDEAL-Benchmark/IDEAL-Scenes)，CC BY 4.0。[项目主页](https://ideal3d.github.io/)。仅复用数据，没有复用其 Agent 或重建 Harness。

实验 01 已完成九次正式重建、九次独立再生成与事后分析。详见 [实验 01 报告](experiments/experiment_01_natural_trajectories/REPORT_ZH.md) 和 [人工评价页面](experiments/experiment_01_natural_trajectories/analysis/human_review/index.html)。

实验 02 已完成 30 次学生分支、30 次独立再生成、30 份匿名自动视觉评价和 30 份轨迹标注，保存 75 个策略配对与 39 条候选知识。详见 [实验 02 报告](experiments/experiment_02_teacher_guided_exploration/REPORT_ZH.md)、[结果对照](experiments/experiment_02_teacher_guided_exploration/analysis/comparison_core.png)、[匿名人工评价页面](experiments/experiment_02_teacher_guided_exploration/analysis/human_review/index.html)。没有收集真实人工评分，没有验证无教师新场景迁移。

当前源码还包含运行结束后的接入修复；各批实际运行版本、受影响角色和未重采样范围均有单独记录。大型科学文件保留在本地，以各批 file_index.json、sync_manifest.json 定位。实验 02 已上传 [GitHub 完整归档](https://github.com/i025/hintrsi/releases/tag/scene-rsi-experiment-02)。实验 03 已上传 [完整归档](https://github.com/i025/hintrsi/releases/tag/scene-rsi-experiment-03)，保留原始轨迹、场景与 GT。

实验 03-A 已结束全部 24 次学生运行，22 次交付完整、2 次没有生成文件；22 次完整交付均通过无外部能力库的源码再生成，交付与再生成渲染 RGBA 像素一致。失败保留在全部组间配对分母中。各学习组只有一份生成的能力库，每个测试场景／组只有一次学生运行；这些结果不能建立采样方差、长期学习或可执行工具优于纯文本的因果结论。报告和完整证据见 [实验 03-A 报告](experiments/experiment_03a_capability_acquisition/REPORT_ZH.md)、[真实结果对照](experiments/experiment_03a_capability_acquisition/analysis/comparison.html)。

实验 03-B 已完成 32 次正式 T0/T1 评价及四个新场景 Base 结果，没有真实人工标签，T2/T3 尚未运行。详见 [实验 03-B 报告](experiments/experiment_03b_teacher_alignment/REPORT_ZH.md)、[开发表单](experiments/experiment_03b_teacher_alignment/human_review/development/index.html)、[独立表单](experiments/experiment_03b_teacher_alignment/human_review/independent/index.html)。人工表单隐藏教师输出，开发与独立数据分别导出。

实验 03 的实际来源、冻结版本、权限修复、缺失 Token 记录、自动评价及限制均保存在各批目录；实验结束时的同步索引见 `experiments/experiment_03_sync_index.json`。

实验 03-A 的独立掩码评价保留全部 205 条候选对应，其中 115 条实际测量、90 条未知；未知包含一次评价超时留下的 13 条未复核记录。预指定的 20 个场景／组对照中，16 个有相同 GT 实例集合的双侧测量，共 77 个对象配对。这些对应由自动模型提出和复核，未经人工确认；数值描述二维可见投影，不是可靠对齐后的三维误差。详见 `analysis/paired_projection_differences.json`（实验 03-A 目录内）。

实验 03 最终记录 147 个已结束／中断 SDK 会话、570 次请求，已知输入＋输出合计 16,566,207 Token；其中 14 次请求缺失用量，不能当作零。实际 Codex 美元账单未知，没有调用 Ofox。分实验完整账本见 [联合用量记录](experiments/experiment_03_usage_summary.json)，包含保留的工程失败与报告生成消耗。

第一阶段代码修改已增加“评价反馈 → 单次 SDK 改进 Agent → 独立能力库候选”入口，详见 [完整代码审查说明](docs/STAGE_01_FEEDBACK_REVIEW.md)、[调用源码](harness/run_capability_improvement.py)和[完整英文 Prompt](configs/capability_improvement_prompt.txt)。本阶段通过14项单元检查和真实资料的隔离预检，新模型调用与正式学生重建均为0。候选不会自动晋升，03-A结果在后续反馈中作为历史开发经验；未来独立测试须用新留出场景。工作停止在源码审查阶段。
