# Scene RSI

这是独立的图像到可编辑 Blender 场景工程。学生沿用 hintrsi 的 Claude Agent SDK 执行循环，Codex CLI Bridge 调用 `gpt-6.1-terra`（low）返回模型决策，工具由 SDK 执行。实验 01 研究无教师的自然重建轨迹；实验 02 研究固定教师 Hint 对共同检查点分支的影响。两批均没有进行完整 RSI、模型微调、长期能力学习或真实人工审美对齐。

- `sdk/`：复用 trajectory-to-capability 的 SDK、Bridge、消息转换与日志代码；多模态改动见实验目录的 `sdk_changes.diff`。
- `harness/`：新建的文件与网络隔离、SDK 入口、透明 Blender 记录器及两路调度。没有 SceneEvolve 建模策略。
- `configs/`：统一英文提示词、冻结场景清单与资源配置。
- `data/`：IDEAL-Scenes 的少量候选资料，以及只对评价端开放的三个完整 GT。
- `analysis/`：实验结束后的场景提取、复现、轨迹比较和人工评价材料生成。
- `experiments/experiment_01_natural_trajectories/`：真实预检、工程中断、九次正式执行及报告。
- `experiments/experiment_02_teacher_guided_exploration/`：三个共同检查点、E0–E4 五组、核心 15 次与额外完整重复 15 次，以及独立评价和候选知识。

正式场景为办公室、卧室、厨房。实验 01 每场景独立重建三次，仅提供匿名 RGB。实验 02 从指定自然检查点开始，各组使用相同代码、场景、初始渲染与参考 RGB，采用全新 SDK 会话。GT 和其他结果不挂载给学生；实验 02 教师也没有 GT。每次学生预算为 25 分钟、120 次模型请求、8 个 CPU 核，要求 640×360 最终渲染。运行库源码可见范围、实际工具访问与其他限制分别记录在各批报告。

实验协议、实际工程修复、源码快照和中文报告保存在各自实验目录。SDK 自报的美元费用不是 Codex 实际账单；实际记录请求数、Token 和耗时。

数据来源：[IDEAL-Scenes](https://huggingface.co/datasets/IDEAL-Benchmark/IDEAL-Scenes)，CC BY 4.0。[项目主页](https://ideal3d.github.io/)。仅复用数据，没有复用其 Agent 或重建 Harness。

实验 01 已完成九次正式重建、九次独立再生成与事后分析。详见 [实验 01 报告](experiments/experiment_01_natural_trajectories/REPORT_ZH.md) 和 [人工评价页面](experiments/experiment_01_natural_trajectories/analysis/human_review/index.html)。

实验 02 已完成 30 次学生分支、30 次独立再生成、30 份匿名自动视觉评价和 30 份轨迹标注，保存 75 个策略配对与 39 条候选知识。详见 [实验 02 报告](experiments/experiment_02_teacher_guided_exploration/REPORT_ZH.md)、[结果对照](experiments/experiment_02_teacher_guided_exploration/analysis/comparison_core.png)、[匿名人工评价页面](experiments/experiment_02_teacher_guided_exploration/analysis/human_review/index.html)。没有收集真实人工评分，没有验证无教师新场景迁移。

当前源码还包含运行结束后的接入修复；各批实际运行版本、受影响角色和未重采样范围均有单独记录。大型科学文件保留在本地，以各批 file_index.json、sync_manifest.json 定位；实验 02 当前尚未另行上传 GitHub。
