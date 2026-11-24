# 按题并行版核心代码改动记录

冻结时间：2026-11-22T03:35:50+00:00。
以 immutable formal_04_source.tar.gz 的 source/tests 文本为基线，仅比较独立 source_parallel/tests_parallel 副本；不读取原交接凭证入口、不计算哈希。旧 source、04配置、快照及结果不改。

| 文件 | 状态 | 新增行 | 删除行 |
|---|---|---:|---:|
| `source_parallel/report_codex_experiments.py` | 修改 | 58 | 4 |
| `source_parallel/run_codex_experiments.py` | 修改 | 20 | 2 |
| `source_parallel/run_parallel_experiments.py` | 新增 | 262 | 0 |
| `tests_parallel/test_codex_cli_bridge.py` | 修改 | 103 | 1 |
| `tests_parallel/test_paired_experiments.py` | 修改 | 1 | 1 |
| `tests_parallel/test_parallel_experiments.py` | 新增 | 322 | 0 |
| `tests_parallel/test_report_codex_experiments.py` | 修改 | 1 | 1 |
| `tests_parallel/test_task_partition.py` | 新增 | 131 | 0 |
| `tests_parallel/test_teacher_progress.py` | 修改 | 1 | 1 |
| `tests_parallel/test_tool_result_transport.py` | 修改 | 2 | 2 |
| `README_parallel.md` | 新增 | 54 | 0 |

## 核心变化

- `run_codex_experiments.py`：新增可选 --task_ids，从固定题目清单按原顺序选择，按原全局索引保留组别轮换；记录 task_partition。独立worker不承接历史、不改变联调范围；已有DOCKER_HOST环境继续生效，各进程使用独立实验名、会话、输出与清理标签。状态先写同目录临时文件再替换，父进程只读完整版本；resume探针解析到当前副本的原模块。
- `run_parallel_experiments.py`：固定九题按6路分配2/2/2/1/1/1，每路调用同一原驱动、路内串行。启动要求旧04非额度停止且Anko B/H/I自然终态；Root另外在边界确认成功复盘结束、旧模型/容器已收尾且下一题尚未启动。总状态只读承接Anko与各路状态；子进程成功退出后以终态刷新避免旧缓存误判。额度/协议或worker失败统一停止模型及本批进程，清理只匹配本批每路标签，不触碰旧03/04。
- `report_codex_experiments.py`：递归读取总控、worker、04与03来源，用集合去重后从原始usage账本聚合一次；03取消M1保留真实消耗但不计成绩。Anko v1过渡排除于九题v2 H/M对比。parallel_new_totals只计算新并行部分，明确分开整体墙钟与单次SDK/有效时间。账本尾行尚未完成时留待下次刷新。
- 原英文Prompt、Terra/low、SDK工具和权限、JIT0、题目/参考补丁、每次学生与教师8CPU/128GiB、超时/轮内检查/五轮预算均保持。并行只改变跨题调度；同一题共同首轮H/M依赖及轮内检查因果顺序不变。

## 验证与范围

- 主任务联合离线套件93项通过（1.069秒），日志 preflight/offline_tests_parallel_05.log；没有真实模型调用。新增覆盖固定分配与原索引、独立DOCKER_HOST/标签、状态中断写入、自然交接拒绝、worker全局停止/旧标签保护、递归费用去重、终态读取竞态。
- 桥生产代码未变。新增两项并发回归复用FakeRPC：两个独立非fork会话同时pending工具，反向交回真实callId/RPC结果后各自最终输出及usage正确；额度和原生工具异常均唤醒两个阻塞会话、中断各自turn，并阻止后续模型请求。
- 其余历史测试只把导入路径从 source 指向 source_parallel；新增测试不会执行Docker、虚拟机或实际模型。
- 核心归档包含36份执行源码、9份测试与 README_parallel.md，共46份；完整清单见 parallel_05_snapshot.json。凭证入口、缓存、Git元数据及认证/用户shell配置排除。
- 本次仅冻结核心代码；六路runtime完整验证、自然交接、共享服务fresh确认、最终配置及正式并行启动均仍为pending。原第四批继续运行，不据此宣称已交接或启动。

## 独立维护的操作代码（未纳入本核心归档）

- `preflight/parallel_runtime/check_lanes.py`
- `preflight/parallel_runtime/prepare_lane.py`
- `preflight/parallel_runtime/prepare_remaining.py`
- `preflight/parallel_runtime/probe_lane.py`
- `preflight/watch_parallel_handoff.py`

这些文件用于环境准备、假API探针或边界观察，维护者仍在更新。其最终运行代码将另行归档并对应实际环境证据；本核心快照不声称冻结了它们。


## 核心第二版：首次状态出现竞态修复（2026-11-22T03:45:08+00:00）

- 第一版五份核心归档/快照/差异/清单/说明已原样保存于 `preflight/parallel_core_revision1/`，正式并行尚未启动。旧04源码、冻结与结果未修改。
- `source_parallel/report_codex_experiments.py` 的目录扫描和来源扫描会先后读取worker状态；若新worker的第一个完整状态恰好在两次读取之间出现，第二次会查找尚未登记的catalog项，导致KeyError并误触发全局停止。现仅在来源扫描发现新experiment时，先用setdefault加入已读取的完整状态再递归；已有目录项保持原值，去重规则和原始账本聚合方式不变。
- `tests_parallel/test_parallel_experiments.py` 增加受控出现回归：第一次worker读取返回不存在，第二次才出现真实状态，同时有该worker100 Token的真实形状usage记录；验证来源、题目、B组、新并行总量和实际总量都正确，避免仅吞掉异常却遗漏费用。
- 报告/总控专项21项通过（0.143秒）；随后完整离线套件94项通过（1.049秒），完整日志 `preflight/offline_tests_parallel_05_revision2.log`，真实模型调用0。上文93项和README中的93项记录对应第一版已完成门禁；第二版最新结果以本节及snapshot为准。
- 第二版仍为46份核心文件，snapshot标记freeze_revision=2和not_started。六路runtime、自然交接、共享服务fresh、最终配置与正式启动仍由主任务完成；本次未操作服务、VM或任何模型。操作脚本继续排除于核心快照并另行维护。


## 操作代码独立冻结（2026-11-22T03:54:31.513417+00:00）

- 六份环境准备辅助代码及 `preflight/watch_parallel_handoff.py`、`preflight/start_services.py` 共 8 份代码已单独冻结到 `parallel_05_operations.tar.gz`，总源码 35,804 字节。逐文件用途、字节数、冻结时间及完整路径见 `parallel_05_operations.json`。
- 已逐个解读归档成员并与源文件直接比较完整字节，8 份全部一致；没有计算哈希。归档只含代码，不含凭证、私钥、runtime bundle、镜像、日志或实验数据。核心第二版归档保持原样。
- 六路 runtime 的实际最终检查于 2026-11-22 03:52:32 UTC 通过；入口 `preflight/parallel_runtime/runtime_manifest.json`，各路版本、8 CPU/128g 容器资源、原镜像 alias 和网关证据均已记录。Lane 1 的真实 SDK 假 API 工具/resume 检查通过，真实模型调用为 0。
- 本次只完成运行环境和操作代码归档，没有修改 immutable 04、重启服务/VM或启动正式并行 worker。旧 Anko 的自然交接、服务 fresh 确认、最终配置与并行启动仍由主任务控制。


## 并行06长提示修复与候选新题恢复（2026-11-22T05:01:39.098082+00:00）

- 05因202,118字符复盘内容展开为单个argv而退出126，教师SDK/模型未启动；原05代码与结果保留。独立source_parallel_06修复教师及学生传参，英文提示和工具协议不变；文件读取仅移除尾随LF以匹配旧有效参数。
- 改动生产文件6份：get_hint_by_task.py、run_cc_sdk.py、run_multi_turn_loop.py、run_cc_trajs_swe_pro.py为文件传输；run_parallel_experiments.py准备仅启动从未开始新题；report_codex_experiments.py明确新题分母与旧题延后。详细新增/删除行和完整diff见parallel_06_changed_files.json及parallel_06_source_changes.diff。
- 102项联合离线测试通过（unittest 6.987秒，启动至结束12.909秒），记录preflight/offline_tests_parallel_06_result.json。真实SDK networknone检查fresh/resume约234.7k字节，原126新0、同SDK会话、六次Read/Edit/Bash均成功，消耗模型0。
- 仅对完成学生但原评测中断的IgelI1/Kea共同首轮补原verifier；原补丁字节未变，不重跑学生，结果另存恢复目录。InkB1/ObsidianI1仍未完成学生，无正式分数。05新增17,475,084 tokens、历史33,611,260不变。
- 两份新增操作代码是preflight/probe_prompt_file_06.py（隔离SDK检查）及runs/codex_parallel_05_eval_recovery/run_verifier_recovery.py（原评测补回），另行冻结parallel_06_operations.tar.gz。核心冻结parallel_06_source.tar.gz及snapshot，所有成员直接字节比较、不用hash。
- 三题候选仅Termenv/Textual/Valibot，原六题保留待恢复，用户选择pending。原M的Codex轨迹存在，但SDK持久会话未备份，当前不能按原接口恢复；没有用新会话冒充续聊。正式06模型调用尚未启动，六VM和旧停止服务保留。


## 07 九题新批次

见README_parallel_07.md及reports/parallel_07_changed_files.json。四个生产文件新增教师SDK导出、中断保留容器、教师原生绑定检查点。长提示文件传参继承06。原05结果独立保留，07重采样九题，Anko不重跑。106项离线测试与跨容器真实SDK模拟恢复通过，无新增验证模型消耗。
