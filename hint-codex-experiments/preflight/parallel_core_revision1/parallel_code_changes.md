# 按题并行版核心代码改动记录

冻结时间：2026-11-22T03:35:50+00:00。
以 immutable formal_04_source.tar.gz 的 source/tests 文本为基线，仅比较独立 source_parallel/tests_parallel 副本；不读取原交接凭证入口、不计算哈希。旧 source、04配置、快照及结果不改。

| 文件 | 状态 | 新增行 | 删除行 |
|---|---|---:|---:|
| `source_parallel/report_codex_experiments.py` | 修改 | 57 | 4 |
| `source_parallel/run_codex_experiments.py` | 修改 | 20 | 2 |
| `source_parallel/run_parallel_experiments.py` | 新增 | 262 | 0 |
| `tests_parallel/test_codex_cli_bridge.py` | 修改 | 103 | 1 |
| `tests_parallel/test_paired_experiments.py` | 修改 | 1 | 1 |
| `tests_parallel/test_parallel_experiments.py` | 新增 | 291 | 0 |
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
