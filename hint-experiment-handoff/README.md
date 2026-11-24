# Hint 实验交接包

这个实验让编程 Agent 修复 DeepSWE 中的真实代码任务：先用**参考答案补丁（Golden Patch）和代码仓库生成提示**，再让解题 Agent 按提示探索、修改代码、提交补丁；测试失败后，复盘轨迹，更新提示，从旧版本重新尝试。

它想检验：**把正确解法的方向提前告诉模型，能否提高解题成功率？模型能否用好提示，并把推理过程写得连贯？**

历史文档报告了 **10 道题：无提示通过 5 道，Hint 循环通过 9 道，50%→90%，提高 40 个百分点**。后者包含参考答案提示、失败复盘和最多 5 次重试。这是整个流程的效果；首轮 Hint 通过 3 道。此次交接整理没有重新跑模型实验。

## 从这里开始

| 你想知道什么 | 打开哪个文件 |
|---|---|
| 输入输出是什么、每一步怎么做 | [实验解读](docs/实验解读.md) |
| 安装什么、数据放哪里、如何启动 | [运行指南](docs/运行指南.md) |
| 改哪段代码、怎么追踪实现 | [代码导览](docs/代码导览.md) |
| 之前整理的实验 Markdown 和 Prompt | [Hint实验.md](docs/Hint实验.md) |
| 逐题结果、指标含义、结论边界 | [结果说明](results/README.md) |
| 代码版本、下载方法、包内改动 | [来源与改动](SOURCE.md) |
| 本包做过哪些检查 | [验证记录](VALIDATION.md) |

## 包内有什么

```text
hint-experiment-handoff/
  README.md                  开发者入口
  docs/                      实验解读、运行指南、代码导览、此前整理的 Markdown
    Hint实验_assets/         两张图、Hint Loop 图、完整/压缩 Hint 示例
  source/                    cc-run hint 分支的实验代码和直接依赖
    benchmark/deepswe/       生成、压缩、编排、验收、复盘、报告与 DeHint
    litellm_proxy/           Claude Code SDK 到可配置模型端点的代理
  scripts/run_experiment.py   配置读取与预检入口，调用 source 中的原实验链路
  scripts/check_package.py    无需模型服务的静态检查
  config/run.example.json    本地配置模板，不包含凭据
  requirements.txt           宿主机 Python 依赖清单
  data/README.md             外部数据准备说明
  results/                   历史结果的 Markdown、JSON、CSV、10 题 ID 列表
  SOURCE_MANIFEST.json        源文件来源、原/包内 SHA256、改动记录
  MANIFEST.sha256             交付文件校验清单
```

源码保持原有相对目录结构，包含 Hint 实验实际调用的脚本和 Prompt。包内副本已移除硬编码模型 Key 和个人 Docker 登录凭据，改用运行者配置；模型算法和实验循环未改写。

## 最快看见运行链路

在解压后的包根目录执行（仅需 Python；无需模型 Key 和 Docker）：

```bash
python3 scripts/run_experiment.py --dry-run --max-rounds 2
```

这会打印生成→压缩→解题→复盘的命令，并在 `runs/` 写入 dry-run 日志。实际运行前，需要按 [运行指南](docs/运行指南.md) 准备 **Linux/Docker 环境、模型服务与 Key、匹配的 Parquet、tasks 目录和任务镜像**。这些外部数据和历史完整运行日志不在包内。

## 读结果时记住三点

1. Golden Patch 是提示生成和复盘阶段的输入，所以这是有参考答案辅助的实验。
2. 每次外层重试都重新启动环境和解题会话；上一轮代码不会接着改。
3. DeHint 修改已产生轨迹的措辞，不改变补丁成绩，也不能证明模型独立推导出了答案。
