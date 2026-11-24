# 运行环境恢复记录

快照时间：2026-11-22 01:23:03 UTC。记录来宾内核故障及SDK启动故障后的维护与验证；本轮离线恢复门禁新增真实模型调用为0。Formal01/02均已停止，Formal03配置已准备、尚未启动。

## 已确认的事实

| 阶段 | 实际结果 | 实验处理 |
|---|---|---|
| 原QEMU4.2.1环境 | Formal01运行中，来宾内核在 `kmem_cache_alloc` 发生double fault并panic | 保留4次已评测成绩；B2技术未完成；整批停止 |
| 新QEMU6.2.0候选环境 | 可启动并完成旧B2文件抢救；随后在启动约200秒时再次发生内核panic | 环境门禁失败，不能标为稳定或允许正式开跑 |
| Ubuntu24.04/QEMU8.2.2候选 | SDK导入、反向通道和修正命令后的Go重复测试均通过 | 满足本次三项环境门禁；尚不等于长期稳定性证明 |

QEMU6.2的保留控制台记录：`[200.278284] int3`，CPU6、`Comm: swapper/6`、`RIP: enqueue_task_fair+0xa0/0x370`，随后 `[200.284114] Kernel panic - not syncing: Fatal exception in interrupt`。这是来宾内核再次失效的直接证据。运行维护确认故障发生在SDK导入/Go压力验证完成前；`gate_failure.json`明确记录 `failed_before_model_calls`、`model_calls: 0`。不能把计划中的SDK、反向转发或Go `test -count 5`门禁写为通过；现有目录仅提供失败记录，没有完成这些门禁的结果。

QEMU进程存在、QMP显示running或SSH曾连通，都不足以证明来宾系统健康；本轮失败不会增加任何题目的失败次数，也不产生正式评测结果。

## QEMU6.2候选的配置与变量

准备从Ubuntu22.04官方软件仓库下载并解压121个软件包，归档共48,083,384字节，准备阶段耗时104.889秒。软件只放在 `vm/runtime-new/`，未执行系统安装，旧QEMU目录未修改。包装入口通过该目录的私有glibc加载器和依赖启动QEMU，不能把宿主系统的加载器当作等价入口。

| 项目 | Formal01环境 | QEMU6.2失败候选 |
|---|---|---|
| QEMU | 4.2.1 | 6.2.0（Ubuntu包 `1:6.2+dfsg-2ubuntu6.31`） |
| VM CPU | 8 vCPU，Nehalem | 相同 |
| VM内存 | 147456MB（144GiB） | 相同 |
| 来宾内核 | 6.8.0-147-generic | 相同文件 |
| BIOS | 原私有SeaBIOS文件 | 相同文件 |
| 加速 | `tcg,thread=multi` | 相同 |
| 机型 | QEMU4.2的q35 | 显式 `pc-q35-4.2` 兼容机型 |
| 学生/教师/评测配置 | 冻结的四组解题协议 | 未启动正式学生；未修改Prompt或组别协议 |

改变模拟器版本是技术缓解尝试，不是学生算法变量。6.2再次崩溃已否定“升级到6.2即解决当前运行问题”的判断，但尚不能锁定具体内核、TCG或硬件模拟缺陷。准备阶段的能力/版本检查通过只证明候选可执行及支持相关参数，不等同运行稳定性门禁通过。

## 下一候选的依据与限制

Ubuntu QA的2024年问题记录描述了Jammy QEMU6.2搭配Linux6.8时，不同现场出现int3或double fault、在处理中断时崩溃；作者当时提出QEMU8.x中断修复可能相关，并预期Noble环境不出现该现象。这是作者的排查假设，不是针对本次环境的已证实结论。[Ubuntu QA：Bug2078790](https://archive.lists.launchpad.net/canonical-ubuntu-qa/msg05345.html)

据此选择Ubuntu24.04的QEMU8.2作为下一候选有近似现象的原始资料支持；本实验仍需实际运行验证。历史报告的内核构建、机型和触发现场与本实验不完全相同，不能声称已确认同一bug或已定位具体修复。新候选保持资源/CPU/机型/来宾配置的实际情况，应由维护者在最终配置快照中记录，再据其门禁结果决定能否启动新批次。

QEMU8.2.2实际版本为Ubuntu包 `1:8.2.2+ds-0ubuntu1.18`；私有准备记录86个包、37,881,382字节，未系统安装，旧运行目录未修改。实际VM元数据仍为8 vCPU、147456MB、Nehalem、`pc-q35-4.2`、`tcg,thread=multi`，内核/BIOS文件保持原路径。版本/依赖/CPU/机型列表检查通过，以下为随后执行的无模型运行门禁。

### 8.2.2运行门禁实际结果

| 检查 | 退出码 | 该检查墙钟（秒） | 记录 |
|---|---:|---:|---|
| SDK导入 | 0 | 82.669 | 输出 `SDK_RUNTIME_OK` |
| 反向转发 | 0 | 4.384 | 模型桥与教师服务状态端点可达；没有调用模型 |
| 首版Go命令 | 1 | 103.369 | 命令参数 `-p8` 写错，测试程序拒绝该参数；保留原失败 |
| 修正后的Go检查 | 0 | 151.056 | `go test -count=5 -p=8 ./...` 全部通过 |

首版 `formal_02_runtime_gate_noble/result.json` 的整体状态仍为failed，它记录的是维护者的门禁命令错误，没有本次来宾内核崩溃证据。维护者仅另建无模型检查容器修正Go参数，保留先前通过的SDK/通道结果；没有重复学生实验。修正版记录在 `formal_02_runtime_gate_noble_go/result.json`。两份记录合并后，SDK、反向通道、Go重复测试三项门禁均通过，准备工作可以交由维护者进入新批次配置冻结与启动步骤。

上述检查及两次Go调用的新增模型调用均为0；首版门禁整体墙钟197.957秒已包含其中的三个子检查，不能再与这些子检查耗时重复相加。修正版151.056秒单独记录。门禁通过只覆盖这些操作及观察时段，不能证明长时间运行不会再次内核崩溃，也不能据此确认Bug2078790就是本次具体根因。

## 抢救产物与统计边界

Formal01崩溃磁盘副本保留为 `preflight/formal_01_connection_recovery/guest-crash.qcow2`，大小6,803,095,552字节。停止容器的12份恢复归档包含运行目录/日志/系统Prompt配置及7个已修改或新增源码文件，详见恢复清单。`0_turn_1.tar`只有 `base_commit.txt`，没有完成的轨迹或补丁产物；7个源码文件只用于故障诊断，不补交评测、不导入新批次。旧批两只容器已由运行维护按Formal01标签清理，清理前清单已保存。

恢复门禁与产物抢救均没有模型调用；在新批次启动前核对时，Formal02前缀的模型请求与Token记录为0，尚无其状态文件。维护者随后已独立启动Formal02；该批随后产生的模型用量归Formal02，不归环境恢复。恢复机器/准备包的墙钟属于环境维护，不应计入学生解题或模型请求时间。Formal01原实际Token总量4,709,961保持不变；其四个评测与B2未完成状态也不变。本次三项环境验证已通过；维护者已另行冻结Formal02最终配置并启动新批次。旧批不自动恢复、不混拼成绩；所有运行环境变化须随新批配置公开记录。

截至Formal02启动前，已记录的实验相关Token口径如下。缓存与推理子集保持原账本定义，不重复相加。

| 范围 | 实际总Token |
|---|---:|
| 共享桥预检 | 496,679 |
| 联调 | 1,242,669 |
| 独立CLI预检 | 12,571 |
| 正式前预检与联调小计 | 1,751,919 |
| 中断批Formal01 | 4,709,961 |
| **Formal02前累计** | **6,461,880** |

该累计值只说明已发生投入，不把预检/联调成绩算入正式实验，也不包括本对话、实现和监控任务或其他Codex任务；不换算美元。

## Formal02另批启动

维护者于 2026-11-22 00:19:08 UTC从头启动 `codex_formal_02`。冻结配置记录QEMU8.2.2及上述资源；模型保持Terra/low，四组、10题、最多5次独立学生尝试。旧批Hint、教师/学生会话和已改源码不转入新批。源代码快照相对Formal01仅增加报告P2P字段补读及其回归测试；解题Prompt、学生/教师执行与组别调度保持原冻结方案。此节仅记录启动及配置，不预报新批成绩。

## Formal02之后的SDK启动缓解

Formal02于2026-11-22 00:46:21 UTC停止：H1的SDK捆绑原生CLI/Bun子进程exit -11，在首个模型请求前退出，VM当时仍健康；此故障与Formal01已确认的来宾内核panic分开记录。具体SDK崩溃根因仍未确认。

离线真实SDK压力门禁现已完成26/26：原设置6/6，`BUN_JSC_useJIT=0`候选20/20，覆盖短Prompt、完整H指导长度、长Prompt、工具/Hook与续接。JSC选项确认原设置useJIT=true、候选useJIT=false。两组均未复现原崩溃，因此不能用通过率证明JIT是原因，也不能证明关闭JIT降低了故障概率。全部检查使用本地模拟HTTP响应，真实模型调用0，模拟用量排除于Token报表。

另一次43.451秒的完整Anko H Prompt环境检查通过：Bash子进程明确返回 `BUN_JSC_useJIT=0`；仅读取该单个键，没有读取完整环境，项目源码保持不变。这表明设置会被工具子进程继承，工具运行的Bun任务脚本也可能受影响。四组统一设置，跨批耗时不视为完全相同运行环境。

共同SDK入口已作两行调整：为ClaudeAgentOptions传入 `env={"BUN_JSC_useJIT":"0"}`，并把stderr回调接入既有logger。学生B/H/M/I、初始教师、fresh复盘和resume复盘均走此入口；stderr写入现有 `sdk_script.log`，由原收集路径随轮次/阶段保存。SDK0.2.186、捆绑原生CLI2.1.329、模型/Prompt/工具权限/组别/资源/时限均保留。调整后65项离线测试通过（0.711秒）。

Formal03仅完成本次启动前配置与源码准备，尚未启动；最终启动健康检查与启动由维护者另行记录。本批拟从头生成Hint和新会话，不复用旧批Hint、教师/学生会话、代码或成绩；旧配置、快照与结果保留不改。当前设置属于有证据确认生效的运行缓解措施，不是已证明根因的修复。

新增依据：[SDK压力结果](../preflight/sdk_sigsegv_diagnosis/stress_result.json)、[JSC选项确认](../preflight/sdk_sigsegv_diagnosis/option_ack_nojit.log)、[环境传播检查](../preflight/sdk_sigsegv_diagnosis/environment_propagation.log)、[65项离线检查](../preflight/offline_tests_formal_03.log)、[Formal02中断说明](formal_02_interruption.md)、[Formal03配置](formal_03_config.json)。

原始依据：[Formal01中断说明](formal_01_interruption.md)、[原崩溃控制台](../preflight/formal_01_connection_recovery/console.log)、[B2恢复清单](../preflight/formal_01_connection_recovery/recovered_b2/recovery.json)、[旧批容器清理前清单](../preflight/formal_02_runtime_gate/old_batch_cleanup.json)、[QEMU6.2门禁失败记录](../preflight/formal_02_runtime_gate/gate_failure.json)、[QEMU6.2保留控制台](../preflight/formal_02_runtime_gate/console_formal_02.log)、[QEMU6.2保留配置](../preflight/formal_02_runtime_gate/vm-state.json)、[QEMU6.2私有准备记录](../vm/runtime-new/preparation.json)、[下一候选准备记录](../vm/runtime-noble/preparation.json)、[QEMU8.2首版门禁记录](../preflight/formal_02_runtime_gate_noble/result.json)、[QEMU8.2修正Go门禁](../preflight/formal_02_runtime_gate_noble_go/result.json)、[QEMU8.2控制台](../vm/console_formal_02_noble.log)、[Formal02源代码快照说明](formal_02_snapshot.json)、[Formal02最终配置](formal_02_config.json)、[Formal02独立状态](../runs/codex_formal_02/experiment_state.json)。
