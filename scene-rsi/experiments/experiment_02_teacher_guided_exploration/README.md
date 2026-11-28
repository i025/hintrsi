# Experiment 02：教师引导的诊断与主动探索

这是在同一自然重建检查点上、使用全新 SDK 会话的受控分支实验，不是恢复原学生内部状态，也不是完整 RSI、长期能力学习或已经完成的人类审美对齐教师。

- `REQUEST.md`：本次完整用户要求。
- `PROTOCOL.md`、`configs/frozen_design.json`：正式运行前冻结的组别、顺序、预算、评价和追加规则。
- `checkpoints/`：只从 Experiment 01 复制的三个原始工作区。原实验目录保持不变。
- `teacher_inputs/`、`teachers/`：教师的完整可见证据和真实 SDK 会话、诊断输出及消耗。教师不能访问 GT。
- `hints/`、`prompts/`：实际冻结的英文提示词。E3/E4 都保留 E2 的同一缺陷描述。
- `runs/`：E0–E4 各组的真实学生工作区、模型请求、工具轨迹、代码版本、场景及渲染。
- `source_at_formal_run/`、`source_changes.diff`：正式启动时的源码快照及相对 Experiment 01 当前版本的增量。
- `preflight/`、`ENGINEERING_LOG.md`：真实多模态预检、合成测量样本和工程修复记录。合成样本不进入正式实验。
- `analysis/`：运行全部结束后的独立再生成、几何与视觉评价、策略相似度、候选经验及匿名人工评价材料。

执行仍为 Claude Agent SDK → 原 Codex CLI Bridge → gpt-6.1-terra / low。CLI 只返回模型决策；SDK 执行工具。学生每次追加预算 25 分钟、120 次模型请求，两路并行，每路 CPU 八线程，禁用 Skill、Memory、持久能力和在线教师。教师、视觉评价与轨迹标注也走同一 SDK/Bridge。

请以最终研究报告和实际状态文件判断完成范围；运行次数不等于成功率，自动视觉判断不等于人工评分。此目录中的原始失败版本和被放弃候选均保留。

最终入口：[中文研究报告](REPORT_ZH.md)、[核心结果对照](analysis/comparison_core.png)、[额外重复对照](analysis/comparison_repeat.png)、[匿名人工评价页面](analysis/human_review/index.html)。完整索引在 file_index.json，大型文件与复用 GT 位置在 sync_manifest.json；源码、报告、结果及可浏览证据已经整理至此；完整模型请求、工具轨迹、所有场景和中间状态由 [完整归档](https://github.com/i025/hintrsi/releases/tag/scene-rsi-experiment-02)提供。`file_index.json` 和 `sync_manifest.json` 保留实验完成时的本地索引，实际上传范围见 [publication.json](publication.json)。
