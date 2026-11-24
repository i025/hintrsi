# Formal01 中断记录与后续实验方法

记录时间：2026-11-22 00:20:35（UTC）。批次：`codex_formal_01`。该批次已停止，保留全部已有记录，作为因基础设施故障中断的正式批次单独报告。

## 中断原因

运行从2026-11-21 22:22:16 UTC持续至23:51:04 UTC，墙钟约5,327.978秒（88.8分钟）。已保留的虚拟机控制台确认：Anko的B组第二次独立尝试期间，来宾内核发生 `PANIC: double fault`，随后 `Kernel panic - not syncing: Fatal exception in interrupt`。控制台文件最后更新时间为2026-11-21 23:50:01.767 UTC；崩溃处记录CPU6、`Comm: go`、`RIP: kmem_cache_alloc+0xf0/0x350`，内核为 `6.8.0-147-generic`，QEMU版本为4.2.1。这些信息定位了崩溃现场，尚不足以判定究竟哪个内核或虚拟化缺陷触发了故障，也不能据此归因于学生的解题算法。

SSH日志的 `Timeout, server 127.0.0.1 not responding.` 和后续Docker连接拒绝是此次来宾内核失效后的连接故障表现。轨迹、补丁等产物无法正常导出，未进入正式评测；清理教师容器也失败。此前观察到的QEMU进程仍存活、QMP仍报告 `running`，只说明模拟器进程未退出，不能证明来宾系统健康；因此将此前“主VM仍存活、诱因未明”的描述更正为“来宾内核崩溃已确认”。

恢复诊断目录保留了控制台、QMP状态及6,803,095,552字节（约6.8GB）的 [崩溃磁盘副本](../preflight/formal_01_connection_recovery/guest-crash.qcow2)。运行维护已通过新启动，从停止的B2容器抢救出日志、原系统Prompt配置和7个已修改/新增源码文件，清单见 [恢复记录](../preflight/formal_01_connection_recovery/recovered_b2/recovery.json)。这些文件只保存在诊断目录，不导入新实验。

`recovered_b2/0_turn_1.tar` 实际仅含 `base_commit.txt`，没有生成完成的 `trajs.json` 或 `patch.diff`，也没有B2正式评测。因此恢复不改变B2“未完成”状态；日志和7个源码文件不能作为补交答案。此次维护不继续旧批学生、不调用模型。

恢复维护曾测试私有目录中的QEMU6.2.0及配套私有glibc，保留8CPU、147456MB VM内存、Nehalem、旧内核/BIOS和TCG多线程，并显式使用 `pc-q35-4.2` 兼容机型。但该候选在启动约200秒时再次内核panic，现场为CPU6、`swapper/6`、`enqueue_task_fair`，环境门禁失败，SDK/Go验证未完成。此升级不能记为修复成功；该6.2候选失败时正式02尚未启动，恢复维护新增模型调用为0。后续Ubuntu24.04/QEMU8.2.2已通过SDK导入、反向通道及修正参数后的Go重复测试三项无模型门禁；首版Go参数 `-p8` 错误及其失败记录另行保留，没有当成内核故障。此结果不证明长期稳定或具体根因已修复；候选选择依据是近似现象的Ubuntu QA原始问题记录。各阶段配置、失败证据与边界见 [运行环境恢复记录](runtime_recovery.md)。

状态文件的停止原因为 `Student attempt did not produce a formal evaluation: anko-default-function-arguments/B/2`。这是技术中断；未发现额度耗尽证据。模型桥在父流程停止后统一停止上游请求。122个已记录模型请求均为 `gpt-6.1-terra`、`low`，响应账本中的模型请求错误数为0；这一点不代表SSH基础设施无故障。

## 已有成绩

本批计划10题、B/H/M/I四组、每题每组最多5次独立学生尝试。实际仅Anko有以下记录，另外9题均未执行。

| 组别与轮次 | 正式评测 | F2P | P2P | 结论 |
|---|---|---:|---:|---|
| B1：无Hint | 已完成 | 0/2 | 119/119 | 正常未解出 |
| H1：原框架对齐版 | 已完成 | 2/2 | 119/119 | 通过 |
| M1：教师会话连续 | 已完成 | 2/2 | 119/119 | 通过 |
| I1：允许轮内指导 | 已完成 | 0/2 | 119/119 | 正常未解出 |
| B2：第二次独立尝试 | 未完成 | — | — | 来宾内核崩溃；不能计作正常失败 |

四个首轮学生SDK均正常结束。I1在86.121秒后结束，主工具完成9次，低于20次检查阈值，教师检查0次、送达Hint 0条、教师等待0秒；空补丁已经官方评测，未通过。其结果不能作为轮内指导被实际使用的证据。上表P2P直接取自四份原始 `eval_result.json`；派生报告的读取遗漏已按下节修复。

H/M/I首轮共用同一份初始压缩Hint。M的初始生成与首轮结束后的教师复盘确实使用同一Codex线程，线程号为 `01a20040-5401-7a61-8948-8fb5031e5448`；但没有M2学生结果，因此尚未观察到连续教师记忆对后续学生尝试的影响。H1/M1成绩发生在各自首轮复盘之前，不能归因于复盘差异。

## 实际消耗

按共享模型桥 `token_usage.jsonl` 中 `codex_formal_01-` 前缀的124条实际增量重新汇总，与最终 `metrics.json`、阶段CSV及报告一致：

| 归属 | 实际总Token |
|---|---:|
| B1学生 | 262,519 |
| B2学生（中断） | 1,311,169 |
| H1学生 | 1,093,718 |
| H1结束后复盘 | 96,837 |
| M1学生 | 1,480,624 |
| M1结束后复盘 | 95,187 |
| I1学生 | 133,072 |
| I1结束后复盘 | 104,191 |
| 共享初始教师 | 124,537 |
| 共享首轮Hint压缩 | 8,107 |
| **合计** | **4,709,961** |

输入4,682,251 Token，其中缓存输入4,413,440；输出27,710，其中推理输出3,995。缓存与推理均为各自父项的子集，不另加到总量。H/M/I共享初始教师与压缩合计132,644，仅实际计一次；M后续复盘95,187正确归M。I的104,191属于首轮结束后的复盘，轮内候选/检查消耗为0。

122个模型请求的耗时合计651.844秒，与整批墙钟不是同一口径。上述消耗包含B2中断前已产生的Token，不因缺少成绩而删除；不包含预检、联调、本对话或其他Codex任务。无可核对货币账单，不换算美元，也不将SDK显示的0美元当作免费。

## 恢复方法与解释边界

维护者在QEMU8.2.2的上述三项门禁通过后，已于2026-11-22 00:19:08 UTC另启全新的 `codex_formal_02`；不续跑或覆盖Formal01，不恢复其B2学生，也不把其教师会话、Hint或学生代码带入新批次。新批次按冻结协议从头生成共享初始Hint，并执行同一10题、四组、最多5次独立学生尝试，模型、思考强度、资源、Prompt和轮内检查门槛保持一致。新批次的启动属于技术修复后的重新实验，不能因已有通过/未通过结果选择性保留旧轮次。若技术修复改变内核或虚拟化参数，应在Formal02配置中明确记录。

Formal01的四个已评测结果继续保留为中断批次的描述性证据；Formal02的成绩与消耗独立统计，汇报累计投入时再把两批实际消耗相加并列明批次。B2维持“未完成”，未执行题目/轮次维持“未执行”；任何一项都不能补成失败。现有数据不足以给出10题总体成功率、完整五轮累计成功率、H/M差异或轮内指导有效性的结论。现有报告第2—5轮沿用的累计通过数仅表示首轮已观察到的通过，不表示这些轮次均实际执行。

## P2P派生报告修复

原报告仅从状态文件的精简 `eval` 摘要读取成绩，摘要没有P2P字段，导致CSV/指标中的P2P为空；原始评测结果完整且未受影响。`source/report_codex_experiments.py`现仅在字段缺失或为None时，从该尝试的 `eval_path` 补读原始评测字段，保留状态中已有的0值，缺少正式评测的B2仍为空。新增一项针对实际字段形状的离线测试，覆盖补读、0值保留、未完成缺评测及CSV落盘；报告模块7项测试通过。

修改前的 `report.md`、`metrics.json`、`attempt_metrics.csv`、`token_usage_by_stage.csv` 以及本说明原版，已先保存在 [原报告存档](../preflight/formal_01_connection_recovery/report_before_p2p_fix/)。随后只重建Formal01的这四份派生报告：四个首轮的P2P均补齐为119/119；四份正式成绩、B2未完成状态、首轮/累计数量和4,709,961实际Token均保持一致。实验状态、原始账本、原始评测、学生/教师Prompt与执行代码未改动。

原始依据：[状态](../runs/codex_formal_01/experiment_state.json)、[最终报告](../runs/codex_formal_01/report.md)、[指标](../runs/codex_formal_01/metrics.json)、[阶段Token明细](../runs/codex_formal_01/token_usage_by_stage.csv)、[尝试明细](../runs/codex_formal_01/attempt_metrics.csv)、[Token增量账本](../logs/bridge/token_usage.jsonl)、[请求账本](../logs/bridge/model_requests.jsonl)、[响应账本](../logs/bridge/model_responses.jsonl)、[运行日志](../logs/codex_formal_01.log)、[故障SSH日志](../preflight/formal_01_connection_recovery/ssh-tunnel.log)、[内核崩溃控制台](../preflight/formal_01_connection_recovery/console.log)、[故障时QMP状态](../preflight/formal_01_connection_recovery/qmp_status_before_recovery.json)、[冻结配置](formal_01_config.json)。
