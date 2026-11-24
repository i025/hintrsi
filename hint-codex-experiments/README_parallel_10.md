# Codex exec 接入版：第 10 版候选

当前状态：`not_ready_real_startup_failed`。本批于北京时间 2026-11-23 00:02:59 启动，首批实测出现工具参数内层 JSON 转义错误，以及学生混淆宿主只读与 SDK 工作区权限的问题，已保存并停止。六路容器均停止并保留，工作进程退出，没有自动重跑。当前没有新增完成的正式评测；本批不能用于有效组间比较。

停止时已上报 1,440,804 token，另有 4 次被中止请求未上报用量；Ofox 调用为 0。完整证据和后续启动条件见 `reports/parallel_10_startup_failure.json`。下文的局部验收通过记录保留，但这些检查不足以证明可以正式运行。

## 实际执行方式

```text
原 Claude SDK 保存当前会话及工具列表
    ↓ 完整 messages + tools
独立桥启动一次 codex exec --ephemeral
    ↓ 返回英文文本及结构化操作请求
原 SDK 在原容器中执行 Read / Bash / Edit 等工具
    ↓ 把真实工具结果加入同一 SDK 会话
下一次请求继续携带 SDK 当前完整历史
```

模型统一为 `gpt-6.1-terra`，思考强度 `low`。桥不使用原生 `resume` 或 `--last`。学生一轮内的记忆由原 SDK 保存；M 教师跨复盘阶段也恢复原 SDK 会话。一次学生解题仍可包含多次模型请求和多次工具调用。

上下文压缩继续使用原 SDK 的算法和英文总结提示。统一增加 `CLAUDE_CODE_AUTO_COMPACT_WINDOW=400000`。当前 SDK 实测有效窗口为 380000、触发阈值为 367000；累积会话达到 370017 token 时自动压缩并继续完成。Codex 本地模型元数据窗口为 500000，有效比例为 95%，对应 475000。窗口设置留有余量，但单份过大的固定输入或工具结果仍可能超限；结构化上下文错误会恢复为 SDK 能识别的 400，以沿用其恢复流程。

## 固定配置与组别

| 项目 | 本版设置 |
|---|---|
| 学生、教师模型 | gpt-6.1-terra，low |
| Codex / SDK / 内置 Claude CLI / LiteLLM | 0.163.0 / 0.2.186 / 2.1.329 / 1.81.8 |
| 每组最多轮数 | 5；B 明确设置 baseline_rounds=5 |
| H/M 首轮 | 共用一次实际学生执行和一次评测，消耗只计一次 |
| 每次实际学生尝试 | 新容器、新 SDK 会话，不继承前次代码 |
| M 教师 | 初始教师及后续复盘恢复同一 SDK 会话 |
| I 教师检查 | 每 20 个工具调用检查，最多 3 次，每条至多 100 个英文词，单次 600 秒 |
| 超时 | 学生有效时间 7200 秒；初始教师 3600 秒 |
| 学生、教师容器 | 每个 8 CPU / 128 GiB；评测容器内存 8 GiB |
| 环境 | 6 个现有 VM，每个 8 vCPU / 144 GiB；TCG，启动 Python/代理较慢 |
| 工具呈现 | ENABLE_TOOL_SEARCH=false，预期初始 18 个工具；BUN_JSC_useJIT=0 |
| Hint | 保留既有 GT→教师→压缩→学生→评测→复盘流程；九题重新生成，不复用旧批 Hint |
| 异常与额度 | 保存并停止，不自动续跑；未完成不记作正常解题失败 |

B 为无 Hint；H 为当前框架中的新教师复盘；M 改为教师会话连续；I 增加轮内指导。H/M 首轮通过时，两组策略均计通过，但只有一个实际样本，M 的后续记忆机制没有触发。首轮失败后才分别执行 H 和 M 的第 2 至第 5 轮。Anko 只保留历史观察，不能视为新后端下重新完成的实验。

| 路 | 固定题目顺序 |
|---|---|
| 0 | Claude Code → Termenv |
| 1 | Igel → Textual |
| 2 | Ink → Valibot |
| 3 | Kea |
| 4 | Obsidian |
| 5 | SQLfmt |

路与路之间并行；每路内部保持既有题目、组别和轮次顺序。

## 与原 API 的关系和边界

题目提示、GT 权限、工具执行器、容器资源、评测器、Hint 压缩和轮内教师策略沿用本框架已确认的设置。本次没有改动这些文件。多工具 SSE 和代理用量传递修复继续沿用已验收版本。

本版不声称与最原始 API 逐项等价。SDK 的 system/developer 等角色保留在 JSON 内，再作为 Codex 的输入；这些不是原生 API 角色。原 API 的 `temperature`、`top_p`、`max_tokens` 没有映射，使用 CLI 的采样与输出默认设置。40 万的 SDK 压缩窗口也是本批统一记录的新后端条件。因此，本版用于在同一 CLI 后端下比较 B/H/M/I；与旧模型、旧 API 和旧批成绩应分开解释。

六路实际 CLI 对本地模拟服务的协议检查已完成；本批六路真实模型同时解题尚未运行。历史真实 Terra 小例题的读代码、修改、测试、教师 GT 生成及教师续接证据保留在 `preflight/exec_action_probe/full_chain/audit.json`，不计为新批正式成绩。该历史例题中的真实在线教师曾选择不发 Hint；本次额外验证了机械注入路径，不据此声称 Hint 有效。

保留镜像中 SDK 的嵌套命令隔离依赖缺失，与既有环境相同；主要隔离仍由容器及教师代码/GT 的只读挂载提供，历史真实小例题验证过只读约束。本次没有调整环境依赖或工具权限。

官方非交互模式说明：[OpenAI 文档](https://developers.openai.com/codex/noninteractive/)。本版行为以本机版本和实际验收记录为准。

## 启动前通过的局部验收（未覆盖本次失败）

| 验收 | 结果与记录 |
|---|---|
| 离线回归 | 104 项通过；preflight/parallel_10_integration/regression.json |
| 实际 Codex CLI 并行 | 6 路 × 2 阶段，12 次进程，78 个检查通过；native_six/result.json |
| 原 SDK 自动压缩 | 累积工具会话触发自动压缩，之后继续完成，全部请求 200；sdk_gate/result.json |
| 上下文错误恢复 | 首份用例记录了 200→400→200 总结→200 完成；context_behavior.json |
| I 的 Hint 注入 | 20 次真实 SDK Read 后检查一次，下一请求含完整 20 份工具结果和一次 Hint；online_resume/result.json |
| SDK 会话恢复 | 关闭并重开后编号相同，保留工具结果、Hint 和最终回答；online_resume/result.json |
| 九题编排 | 6 路全部完成演练；preflight/dryruns/codex_parallel_10_dryrun |
| 实际环境及服务 | 6 路镜像、资源和网关检查通过；service_check/health.json |

上述新验收的模型响应均为本地模拟；模拟 token 不计入真实消耗。压缩首份用例未通过主动压缩条件：它把庞大用量模拟成不可压缩固定前缀。该记录完整保留在 sdk_gate_attempt_01，后续改用累积会话用例通过；没有把前一次未通过记录改成成功。

验收目录的完整前缀为 `/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/preflight/parallel_10_integration/`。

## 用量、耗时与文件

正式新批使用独立的 `logs/codex_parallel_10/bridge` 和 `logs/codex_parallel_10/progress`。每次请求记录完整输入、CLI 事件、真实 token、输出、错误及耗时。缓存和推理 token 单列，属于输入/输出的子项，不能再次加入总量。缺失用量标为未知；SDK 总量不与桥记录重复相加。

`exec_turns.jsonl` 记录进程启动到一次决策完成的耗时，包含 CLI 开销，不含两次请求之间 SDK 执行外部工具的时间。每次学生完整流程、SDK 耗时、教师等待、扣除教师等待后的时间和并行整批墙钟继续分列。新日志没有旧调用时，不自动补入旧批费用；历史观察的成绩和费用来源明确分开。

本次接入新增真实模型请求为 0。此前实验及预检已记录 79,852,573 token，来源为 `preflight/exec_action_probe/status.json`；该历史数不含本次聊天与实现工作，也不含模拟用量，未换算为美元账单。

- 完整配置：reports/parallel_10_config.json
- 验收状态：reports/parallel_10_readiness.json
- 改动明细：reports/parallel_10_source_changes.diff
- 文件清单：reports/parallel_10_snapshot.json
- 源码快照：reports/parallel_10_source.tar.gz
- 测试快照：reports/parallel_10_tests.tar.gz
- 改动说明：reports/code_changes.md

## 入口

默认只检查服务及六路环境，完成后关闭检查用服务，不启动实验：

```bash
/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -B /srv/lab-disks/disk2/users/xymo/hint-codex-experiments/preflight/launch_parallel_10.py
```

本版已启动过并因兼容失败停止。结果目录 `runs/codex_parallel_10/` 保留，当前验收状态禁止再次启动。必须先完成失败报告中的修复与验证，再建立新的统一批次。
