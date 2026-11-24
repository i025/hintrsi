# 预检与联调消耗记录

报告更新：2026-11-21T22:25:16+00:00；模型用量快照：2026-11-21T22:21:06+00:00。环境状态沿用 2026-11-21T21:51:20+00:00 快照。模型统一为 gpt-6.1-terra、low。

截至模型用量快照，预检实际消耗 **509,250 Token**（含失败探针）；integration_01 单列 **104,702 Token**，integration_02 单列 **1,137,967 Token**。正式实验前这三部分合计 **1,751,919 Token**。它们用于环境、兼容性与联调，均不计入正式十题实验成绩；正式实验的新调用不纳入本快照。

## 实际消耗

| 项目 | 输入 | 其中缓存输入 | 输出 | 其中推理输出 | 总Token | 模型请求耗时/秒 |
|---|---:|---:|---:|---:|---:|---:|
| 修复后宿主压缩接口验证 | 7,993 | 0 | 414 | 0 | 8,407 | 13.55 |
| SDK v1（失败） | 88,477 | 72,704 | 361 | 16 | 88,838 | 20.76 |
| SDK v2（读写、测试、会话续接通过） | 118,551 | 102,528 | 382 | 0 | 118,933 | 26.87 |
| 真实模型 Agent fork 验证 | 102,058 | 89,216 | 383 | 0 | 102,441 | 22.63 |
| 真实20次主工具检查（学生） | 52,623 | 44,544 | 124 | 0 | 52,747 | 11.14 |
| 真实20次主工具检查（教师候选；自主不发Hint） | 75,322 | 4,608 | 69 | 0 | 75,391 | 6.32 |
| 独立1次Read提示传输（固定英文标记） | 49,839 | 43,904 | 83 | 0 | 49,922 | 10.03 |
| 独立CLI动态工具探针（单列） | 12,534 | 6,144 | 37 | 0 | 12,571 | — |
| integration_01初始教师（联调单列） | 101,804 | 77,312 | 2,898 | 19 | 104,702 | 62.05 |
| integration_02（联调单列） | 1,121,895 | 974,720 | 16,072 | 754 | 1,137,967 | 377.05 |
| 预检小计（含独立CLI） | — | — | — | — | **509,250** | — |
| 正式实验前总计（预检＋两次联调） | — | — | — | — | **1,751,919** | — |

缓存输入已包含在输入内，推理输出已包含在输出内；不能再次加进总Token。公共桥只累加实际返回的 delta，不重复累加累计值；独立CLI的12,571另计，真实子代理的102,441、20工具学生与教师合计128,138、独立提示传输49,922已经包含在预检小计内。假HTTP fixture返回的合成usage全部排除。
SDK统计为零不代表没有消耗，实际以Codex账本为准。没有可核对的货币账单，因此不换算美元，也不把这些Token等同于Ofox美元扣费。

本目录Token报表只统计实验程序经模型桥和独立探针实际记录的调用，不包含本聊天的实现、监控对话或其他Codex任务。账户额度百分比可能受其他会话影响，不能直接当作这批实验的货币账单。

原始记录：[公共桥Token增量](/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/logs/bridge/token_usage.jsonl)、[请求/响应耗时](/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/logs/bridge/model_responses.jsonl)、[独立CLI结果](/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/preflight/cli_tool_result.json)。

## 已通过与失败的验证

| 验证 | 当前结果 | 说明 |
|---|---|---|
| 独立CLI动态工具 | 通过 | 动态工具实际执行；原生工具为0。 |
| SDK v1 | 失败，记录保留 | 实际容器可写，模型误认为只读，未调用Edit；两次会话内测试未修复。已消耗88,838 Token。 |
| SDK v2 | 通过 | 首段Read→Edit→Bash测试；续接同一SDK会话后再次Edit，原修复保留，独立测试通过。 |
| 宿主压缩接口 | 通过 | 移除本批进程继承的SOCKS代理后，独立压缩成功，消耗8,407 Token。 |
| 轮内Hook：真实SDK＋假HTTP | 通过，0真实模型调用 | 20次Read后触发1次检查；20份原工具结果完整；同会话，Hint只送达一次。 |
| fork/fresh子代理：真实SDK＋假HTTP | 通过，0真实模型调用 | 父子独立thread；父输入保持；正式摘要只返回一次；fork继承工具历史。 |
| 历史注入管理接口 | 通过，0模型turn | 持久化读取确认user/assistant/工具调用/工具结果保留。 |
| 真实模型Agent fork | 通过 | 子代理实际读到继承标记与容器标记；摘要返回父会话，2项独立测试通过，原生工具为0。 |
| 真实模型20工具教师检查 | 通过 | 完成20次主工具且在途清空后检查1次；教师自主决定无需Hint，未执行筛查或发送提示。 |
| 独立真实提示传输 | 通过 | 1次Read后固定英文标记只送达一次，保持同Codex thread/turn、原工具结果完整，原生工具为0；不改变正式20/3门槛。 |
| 离线协议测试 | 通过 | 该落盘测试快照记录62项通过。 |

证据：[SDK v1](/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/preflight/sdk_fixture/result.json)、[容器可写检查](/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/preflight/sdk_fixture/filesystem_probe.json)、[SDK v2](/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/preflight/sdk_fixture_v2/result.json)、[Hook gate](/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/preflight/sdk_hook_fixture/result.json)、[子代理回放](/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/preflight/sdk_subagent_fixture/bridge_replay_result.json)、[注入读取核验](/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/preflight/fork_history_admin_rpc.json)、[真实Agent gate](/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/preflight/sdk_subagent_real/result.json)、[真实20工具教师检查](/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/preflight/sdk_online_real/result.json)、[独立真实提示传输](/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/preflight/sdk_context_real/result.json)、[测试容器已停止](/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/preflight/fixture_cleanup_status.json)。

## 首次联调为什么没有学生成绩

integration_01完成了Termenv初始教师生成，随后宿主压缩连续3次因继承SOCKS代理、缺少socksio而失败。压缩请求尚未到达模型桥，因此这3次压缩没有新增模型Token；此前初始教师已经消耗104,702 Token。学生尝试为0、正式评测为0，不能将其写成解题失败或通过率0%。后续 integration_02 已在本报告单列，未计入预检小计。

证据：[首次联调状态](/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/runs/codex_integration_01/experiment_state.json)、[压缩错误原日志](/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/runs/codex_integration_01/codex_integration_01_shared/logs/termenv-preserve-ansi-resets/step_01_compress_r1.log)。

## 第二次联调的统计边界

integration_02 共消耗 **1,137,967 Token**。Termenv H 完成正式评测（reward=1，35/35），教师续接探针保持原 SDK 会话和 Codex thread。Kea I 学生在15次主工具后自行结束，提交补丁为空；当时框架未运行正式评测，因此不能给它写通过率或将其当作正常评分失败，轮内教师也尚未触发。该次停止不是额度停止，原生工具事件为0。之后空补丁评测逻辑的修复不追改该联调结果。

联调仅用于验证接线，不能据这两个任务推断四组方案的效果。[integration_02 状态](/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/runs/codex_integration_02/experiment_state.json)。

## 时间开销

| 项目 | 整流程墙钟/秒 | 容器执行墙钟/秒 | SDK Python墙钟/秒 |
|---|---:|---:|---:|
| 独立CLI | 8.56 | — | — |
| SDK v1两段 | 305.64 | 106.97 | 55.72 |
| SDK v2两段 | 328.90 | 124.36 | 66.36 |
| 真实Agent fork | 235.95 | 71.81 | 45.64 |
| 真实20工具教师检查 | 251.39 | 84.51 | 58.10 |
| 独立真实提示传输 | 216.55 | 51.57 | 25.87 |
| integration_01 | 301.94 | — | 教师 97.08 |

整流程墙钟含容器准备、启动和收集；容器exec墙钟与SDK Python墙钟分列。模型请求耗时不是纯推理时间；父子turn时间重叠，不相加为墙钟。并行环境准备与探针可能重叠，不计算虚假的全局总墙钟。

## 环境准备快照

**十题镜像全部准备完成，10项统一只读runtime检查全部通过。** Kea此前公开仓库429限流的问题已通过旧缓存导出解决。
固定运行环境：Python 3.12.16、claude-agent-sdk 0.2.186、LiteLLM 1.81.8、bundled Claude CLI 2.1.329。只读运行环境共用，任务源码仍可写；没有修改用户既有Python环境。

Kea缓存准备的完整墙钟为 **2626.771秒（43.8分钟）**，使用临时 **1 vCPU、8 GiB** 虚拟机。该流程只做QEMU/Docker导出、传输和导入，模型调用和模型Token均为0。旧磁盘保持只读，写入仅发生在临时覆盖层；临时虚拟机现已关闭。

| Kea缓存准备阶段 | 耗时/秒 |
|---|---:|
| 临时环境搭建 | 408.216 |
| 缓存镜像导出 | 1322.605 |
| 新VM镜像导入 | 767.170 |
| 全流程墙钟 | 2626.771 |

第二次联调还单独记录 **1263.242秒（21.1分钟）** 的镜像编排等待。这段等待发生在该学生SDK执行完成之后，不能计入学生解题耗时。等待期间子教师复盘仍可继续，其模型消耗归 integration_02，在本报告单列，排除预检小计和正式实验成绩；这次暂停不是额度停止。缓存准备与编排等待时间有重叠，不能相加作为全局总墙钟。

证据：[runtime十题检查](/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/preflight/runtime_image_compatibility.json)、[镜像准备完成记录](/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/preflight/image_preparation.json)、[Kea缓存准备及临时VM关闭](/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/vm/kea-cache-export/state.json)、[第二次联调镜像等待](/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/logs/integration_02_image_wait.json)。

本次补齐真实20工具教师检查与独立提示传输的消耗，并单列第二次联调。预检小计为509,250 Token，正式实验前总计为1,751,919 Token；环境准备耗时及重叠排除规则保持原记录。未进行文件哈希验证。
