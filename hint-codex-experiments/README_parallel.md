# 六路按题并行实验（准备中）

用户已授权在约不超过共享主机一半CPU的范围内并行。计划使用六台相同8vCPU/144GiB VM，合计48vCPU；保留每学生/教师8CPU、128GiB及原题内流程。**当前仅准备新环境与并行副本，`codex_parallel_05`尚未启动。** 原第四批继续自然完成Anko；不重跑已有成绩、不改旧源码/冻结配置/结果或当前VM与服务。

配置和完整边界见[并行配置草稿](reports/parallel_05_config.json)、[并行协议](reports/parallel_protocol.md)，当前结果见[实验总览](reports/experiment_summary.md)。统一离线套件已通过93项（1.069秒、真实模型调用0），[原始检查日志](preflight/offline_tests_parallel_05.log)保留；六路环境、自然交接、最终冻结和实际启动仍未完成，不以离线通过代替。

## 工作分配

| 路 | 固定题目 | 环境 |
|---|---|---|
| 0 | recursive delegation、Termenv | 原`vm/`，待Anko交接完成后复用 |
| 1 | Igel、Textual | 新`vm-lane1/` |
| 2 | Ink、Valibot | 新`vm-lane2/` |
| 3 | Kea | 新`vm-lane3/` |
| 4 | Obsidian Linter | 新`vm-lane4/` |
| 5 | SQLfmt | 新`vm-lane5/` |

分配是原九题清单的固定轮转，路内顺序执行、跨路并行，保留原全局题序决定的题内分组顺序。各题独立；H/M共同首轮、失败后H新教师/M续教师、I检查点等待、最多五轮等均不变。共同首轮成功仍保留一次H诊断复盘，M机制不触发；Anko不参与九题v2 H/M比较。

## 交接与启动

Root观察进程只在Anko B/H/I全部自然终态且成功复盘结束后停止第四批，保存交接与无下一题模型调用的证明。供稿时Anko B3仍运行，B2正式未解出；I1已通过并收到1条轮内Hint。准备期间完成各新环境检查与源码冻结；自然交接后才重启共享模型服务。只有六路验证、交接证据、最终健康及源码/配置冻结均确认后，才启动并行队列。不要直接把本说明的计划入口当作已经获环境放行。

最终runtime manifest预期为`preflight/parallel_runtime/runtime_manifest.json`，格式：

```json
{"lanes": [{"lane": 0, "docker_host": "unix:///absolute/path/vm/docker.sock"}]}
```

实际文件须含整数lane0—5六项，由Root在环境验证后填写；示意内容不能用于运行。新SSH端口22231—22235，每台各自覆盖层，只读后备为原`hint-baseline-run/vm-cpu-probe/guest.qcow2`，不把活动VM0读写磁盘用作后备。

待实际交接、验证及冻结完成后，计划入口为：

```bash
/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -u -B \
  /srv/lab-disks/disk2/users/xymo/hint-codex-experiments/source_parallel/run_parallel_experiments.py \
  --experiment_name codex_parallel_05 \
  --prior_state /srv/lab-disks/disk2/users/xymo/hint-codex-experiments/runs/codex_formal_04/experiment_state.json \
  --runtime_manifest /srv/lab-disks/disk2/users/xymo/hint-codex-experiments/preflight/parallel_runtime/runtime_manifest.json
```

协调器要求旧状态已停止、非额度停止、Anko自然完成；六个worker调用并行副本的原驱动，只增加固定任务选择。每个worker有自己的DOCKER_HOST、标签、会话、状态和输出。每30秒轮询共享桥与刷新汇总；任一worker或全局额度/原生工具异常会保存并停止所有本批worker，不自动重试、不清理旧批。

## 文件与统计

- `source_parallel/`、`tests_parallel/`：独立源码/测试副本；旧`source/`及04快照不改。
- `runs/codex_parallel_05/experiment_state.json`：总状态，引用六路状态及旧第四批。
- `runs/codex_parallel_05/lanes/codex_parallel_05_laneN/`：每路独立产物；`worker_logs/`保存各路日志。
- `preflight/parallel_runtime/`、`preflight/parallel_handoff/`：Root的环境准备与自然交接证据。
- `reports/parallel_05_config.json`：当前草稿；最终冻结、测试及实际启动另行确认。

Anko成绩只读承接，不重跑；03取消M1无正式成绩但真实成本保留。总报表递归统计03、04与六路实际账本各一次；`parallel_new_totals`仅含新并行消耗，勿将整份含历史的报告再加到旧总量。第一、二批只列历史开销。缓存/推理Token分别是输入/输出子集，不估算美元；不用Ofox，不新增哈希验证。

所有角色继续Terra/low、原SDK工具和权限、原英文Prompt、JIT0、原超时及同一账户。并行改变调度、共享CPU/网络/缓存/额度压力；各路设置和环境开销、排队、学生有效时间、教师等待及整体墙钟分别记录，不据此承诺固定倍数提速或Token不变。容量观察是时点信息，不是独占资源承诺；完整实验尚未完成，不提出训练或DeHint泛化结论。
