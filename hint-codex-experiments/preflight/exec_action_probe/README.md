# 第二路线：SDK 保存会话，Codex exec 返回操作请求

当前结论：小夹具完整功能预检通过，正式九题未启动，原始交接目录与冻结 `source_parallel_09` 未修改。此结果不代表严格 API 等价或科学实验得分。[完整审计](full_chain/audit.json) · [状态](status.json) · [变更记录](../../reports/code_changes.md)

## 会话与压缩由谁负责

学生一轮内的可见历史由原 Claude Agent SDK 保存。每次把 SDK 当前完整 `messages` / `tools` 交给一个全新的 `codex exec --ephemeral --json --output-schema`；模型返回动作 JSON，桥转换为原接口响应，原 SDK 执行真实工具并把结果接回历史。持续教师初始与复盘使用同一 SDK 会话；每次 native exec 仍为新进程，不使用 native resume。下一轮学生的重置规则沿用原框架。

会话历史压缩由 SDK 判断、发出摘要请求、用摘要替换旧历史；摘要本身仍由后端模型生成，现在该请求也交给 Codex。桥遵从压缩后的新历史，不补回已删除消息。原 SDK 自动压缩和阈值保持原样。教师 Hint 的压缩继续由原 `compress_hint.py` 负责，这是另一种压缩。

## 真实模型完整预检

使用自包含的小代码题：时间窗口统计应包含起点和终点，空结果行为保持。原代码4项测试中3项失败，修复后4项通过。不是正式 DeepSWE 任务，也不拿以下两位学生的结果做 B/I 效果比较。I 额外要求20次分片读取，仅用于触发原检查点。模型 Terra、effort=low；各容器8CPU/128GiB，原SDK/提示/工具；B在lane5，教师和I在lane3。两套真实SDK曾同时处理请求，最大并发2。

| 阶段 | 请求 | 已报告 tokens | SDK或阶段墙钟 | CLI请求耗时合计 |
|---|---:|---:|---:|---:|
| 无Hint学生B | 5 | 127575 | 96.12秒 | 52.18秒 |
| 教师初始指导 | 5 | 122638 | 113.19秒 | 70.21秒 |
| 原模块压缩Hint | 1 | 7544 | 14.83秒 | 14.71秒 |
| 在线学生I | 5 | 147011 | 124.12秒 | 64.04秒 |
| 在线教师检查 | 1 | 46859 | 11.74秒 | 11.65秒 |
| 同教师会话复盘 | 2 | 67910 | 84.12秒 | 48.36秒 |

共19次完整流程请求、519537 tokens。I的SDK墙钟已包含11.95秒教师等待，不再重复相加；并行阶段也不能相加当总墙钟。代理冷启动另记，B约105秒；B含启动及收集共215.22秒。

- B原SDK实际完成 Bash、Read、Edit、Bash测试，独立后评测4/4；只有实现一行改动。[证据](transport/complete_sdk/attempt_04/audit.json)
- 教师真实写出初始Hint，原模块完成压缩；I在20个主工具完成后触发检查，教师合法返回 `no_hint_needed`，随后I真实修改并通过4/4测试。因此本次真实追加指导注入覆盖为 `not_exercised`。[阶段记录](full_chain/continuation/attempt_02/phase_summary.json)
- M复盘使用实际I成功轨迹和原成功复盘提示；SDK ID不变，首个复盘请求保留初始工具回执与最终指导，实际写出复盘文件。[历史审计](full_chain/continuation/attempt_02/teacher_audit.json)
- 指导注入另由零模型门禁验证：原SDK执行20次Read，原OnlineTeacher收到模拟教师提示，下一实际SDK请求保留提示及20个回执，随后成功完成。只证明机械通路，不证明真实教师选择或Hint效果。[证据](native/online_hint_audit/result/result.json)

## 本次发现并修复的接入问题

1. 明确的 native 上下文超限原先被转为503，阻止SDK识别。现在仅把明确上下文错误恢复为400及原兼容错误文本。[差异与门禁](native/context_audit/README.md)
2. 原代理把空delta用量消息丢弃，SDK因此见到零用量；此问题原交接代码中也存在。只在checked副本移动异步路径已有用量合并代码，不改数值、SDK、阈值或SSE格式。真实代理/SDK零模型门禁验证非零用量、工具成败和自动压缩均正常。[证据](native/usage_audit/README.md)
3. 第一版真实学生与教师把 native 只读限制套用于外部SDK，拒绝写入。英文外层协议现明确两套环境的范围，外部操作仍受SDK原权限与实际工具拒绝约束。相同历史单次重放正常请求Edit，之后全新完整流程通过。[差异](native/permission_scope/bridge_scope.diff)

此前第一版真实预检9次调用、220869 tokens单列保留；权限修复单次重放1次25910 tokens也单列，不把失败或重放混入成功流程。新增fixture两次装配失败及压缩客户端SOCKS环境错误均发生在模型入口前，消耗0；原始错误记录保留。仅临时本地客户端进程清除代理变量，没有安装包或修改全局环境。

## 验证范围与用量

- 最新17项离线接口回归全部通过。[结果](action_contract_after_permission_scope.json)
- 六路真实CLI接本地假provider，两阶段12个新thread、78项检查通过。[结果](native/bridge/result.json)
- 真实Terra记忆小样本3次、19031 tokens另保留。[结果](real_memory/result.json)
- 原SDK手动压缩/resume和工具闭环零模型门禁保留。[结果](transport/audit.json)
- 原SDK自动压缩零模型门禁通过：400→摘要→新历史，同会话完成；摘要再次超限会有限重试并明确 `is_error=true/prompt_too_long` 结束。[自动压缩](native/usage_audit/sdk_gate/result.json) · [二次超限](native/context_audit/summary_second_400/result/result.json)

本次完整预检合计29次真实调用、766316已报告tokens（含旧失败预检和单次重放），输入输出均来自CLI账本；无真实缺失usage请求，无接口错误。缓存与推理分项属于总数的子集，不重复加；SDK用量不能再相加。Ofox调用0、GPU使用0，SDK美元估算不当作Codex账单。人工用量全部排除。

此前第二路线记忆小样本19031 tokens加本次后，第二路线累计785347 tokens；再加此前已记录79067226，为79852573已记录tokens。不包括本聊天、实施工作或未报告的消耗，不声称账户完整账单。

## 仍需注明的限制

- 原API角色在这里是JSON数据字段，并非模型原生角色通道；不恢复上一exec的隐藏推理状态。
- temperature/top_p/max_tokens未映射到CLI；CLI默认采样和输出限制是新后端条件，不能声称历史API参数原样生效。
- Terra窗口元数据500000，SDK原配置按1m处理；已验证错误触发及退出，没有做真正接近上限的长历史压力实验。
- SDK缓存细项、thinking统计及美元估算可能与CLI不同，以CLI已报告账本为准；缺失usage必须保留未知。
- 真实并发覆盖两套SDK，六路覆盖本地假provider；未声称完成六路真实模型长题、正式评分或dehint泛化实验。

模型输入全英文，原题目与提示由SDK原样传递；没有自动换模型、额外决策重试或哈希验证。已保存[原预检源码](full_chain/validated_source.tar.gz)及[权限修复版源码](full_chain/validated_source_scope_v2.tar.gz)。临时服务已停止，六套环境运行容器均为0，历史停止容器与结果保留。[清理证据](full_chain/final_runtime.json)
