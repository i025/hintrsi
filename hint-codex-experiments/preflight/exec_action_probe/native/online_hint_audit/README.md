# 轮内教师 Hint 机械注入门禁

通过。此门禁只验证提示能否穿过原 hook / SDK / proxy / exec bridge，不能用于判断真实教师是否应给提示，也不能说明提示能提升解题效果。现有真实 I 实验的 `no_hint_needed` 选择及原记录未改变。

使用 lane1 新建的独立禁网容器、当前 scope-v2 exec bridge、checked 中已修复 usage 的代理，以及原样复制的 `run_cc_sdk.py`。`OnlineTeacher` 与 `create_agent_options` 均直接使用原类/函数；没有改 SDK、20 次工具阈值、最多 3 次检查、原教师超时规则或模型设置。容器内 127.0.0.1:8766 是本测试的假 progress 服务，不访问 host 教师服务。模型动作由独立 fake exec 提供，真实模型调用 0。

第一条模型入口请求返回 20 个 Read 操作；SDK 在 `/app/observations/` 实际读取 20 个不同文件，各文件有独立标记。原 hook 在全部完成且没有在途工具时触发：`tool_count=20`、`checks=1`、`inflight=[]`。假 progress 只收到一次请求并立即返回一条英文方向性提示。

下一条真实 SDK 请求（`result/bridge/model_requests.jsonl` 第 2 行，request_id=`29d38a6fc50a415abacef4533b47a944`）包含：

- 全部 20 条 `role=tool` 回执，ID 与原 20 个 Read 一一对应，20 个文件标记全部保留，没有错误回执。
- `messages[24]`（从 0 计）的 `role=user` 内容：`PostToolUse:Read hook additional context: Teacher guidance:\n`，随后是完整英文 Hint；Hint 只出现一次。
- fake exec 核验上述条件后返回最终文本；实际 SDK 以 `is_error=false`、`terminal_reason=completed` 正常结束。

英文 Hint 为：

> Before concluding, compare the boundary conditions in the collected observations and verify that the relevant cases are covered.

实际模型入口仅 2 次，小于上限 6；SDK 阶段 26.92 秒，小于 90 秒；假教师等待 0.102 秒。代理冷启动 110.51 秒，host 总执行 168.67 秒。没有触及第二、第三检查，也未覆盖 600 秒超时分支。

SDK 和桥账本均记录人工用量 input=200、output=40、合计 240。SDK 按人工 token 显示的 $0.0016 并非实际费用；这些数据全部排除正式实验统计。自己的容器和容器内服务已清理，未启动/修改 host 全局服务。

证据：`result/result.json`、`result/host_result.json`、`result/student/online_teacher_state.json`、`result/student/online_teacher_events.json`、`result/teacher_requests.json`、`result/sdk_messages.json`、`result/bridge/model_requests.jsonl`。

新增代码仅本目录 `probe.py`、`guest.py`、`fake_exec.py`，沿用之前真实代理/SDK 的离线夹具。原 SDK、正式数据和教师决策规则均未修改。
