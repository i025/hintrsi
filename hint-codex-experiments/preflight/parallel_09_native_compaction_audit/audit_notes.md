# Native 自动压缩与原 API 生命周期对照

正式实验和原版源码均未修改；没有调用真实模型。所有测试返回由本地受控 Responses 服务生成，合成 tokens 不计入实验。

## 本次实际验证

CLI 0.163.0，测试专用 `model_auto_compact_token_limit=5000`，强制 code mode，provider capability `remote_compaction="v2"`。首个响应合成 usage 为 6005，第二次 turn/start 自动触发压缩，未调用 thread/compact/start。真实 CLI 向同一个 `/v1/responses` 发出带 `compaction_trigger` 的请求；夹具返回 `compaction` 项后，CLI 发出已完成的 `contextCompaction` 事件。

同一 thread `01a20277-8781-7592-9a5a-1844388666c1` 的两 turn 均完成，压缩前后工具 schema 一致，压缩后的动态 Read 工具成功执行，其真实夹具回执出现在下一次 provider 请求。7 项精确检查见 `summary.json`，原始请求和事件见 `requests.json`、`events.json`，完整 thread/read 结果见 `result.json`。

这只验证两个短 turn、一次受控压缩的协议与生命周期。压缩正文是本地伪造的 opaque marker，没有验证真实模型总结质量、重要历史保留、多次压缩、压缩中断、压缩后恢复、生产 provider 的行为或任意长度会话。最初错误 capability 与错误响应格式产生的失败夹具已保留，最终通过条件明确检查两 turn status，而非只检查 RPC 无异常。

## Token 账本的精确限制

普通响应合成 tokens 为 6005 + 55 + 55 = 6115；压缩响应另返回合成 usage 120。CLI 发出的 thread 累计序列是 6005、6005、6060、6115。累计没有因压缩重置，但压缩响应的 120 没有进入该通知账本。因此不能由“累计不清零”推导“覆盖所有压缩消耗”。桥接器以这个 native total 的 delta 记账，也无法自行补出 native 未报告的压缩费用。

这 120 是夹具数字，不能用来推算真实 provider 的计费或历史漏计数量。

只读扫描 `logs/bridge/codex_events.jsonl` 全部 107221 行（0 坏行，timestamp 1795292685.4544933 至 1795335072.6221957），严格匹配 `item/completed` 且 `params.item.type=contextCompaction`，完成 0，开始也为 0，08 会话亦未发现。没有把正文里的 compact 字符串误计。此结论仅限该文件，不外推其他日志、服务端隐藏处理或真实总费用；详见 `historical_compactions.json`。

## 取消接回候选与原 API 的联系和差异

原始 `/srv/lab-disks/disk2/users/xymo/hint-experiment-handoff/source/run_cc_sdk.py:400–422` 将 agent 循环交给 ClaudeSDKClient，SDK 收到工具调用后执行工具，并通过后续 API 请求提交历史和回执。原框架由 SDK 持有可摘要的历史。

候选已通过的局部保证：同一个 SDK 操作不重复执行；实际返回内容、错误标记、原调用 ID 和参数保留；取消后的迟到结果进入原 native thread；交给 SDK 的最终文本在实际回执到达后生成；正常未取消路径不由恢复逻辑额外开启 turn。

这些局部保证不等于原 API 的完整语义。至少存在以下差异：

- CLI code mode 允许 exec/wait 等 SDK 看不到的模型采样。工具仍在 SDK 执行时，native 模型可能生成 wait/terminate 以及提前 final；bridge 暂扣 final 并不会撤销已经发生的采样，也不会删除 native 历史里的提前判断。
- 已取消 RPC 不能原地重新打开。候选用受支持的 `turn/start.toolOutput` 提交新的工具观察，内容为包含原 call ID、arguments、is_error 和 output 的 JSON envelope。它保留事实，但不是恢复原调用的原始回执关联。
- 如果 native turn 已结束，接回会新开 native turn；如果仍活动，则把观察加入现有 turn。两者都可能增加模型请求与上下文，改变耗时和 token。
- 普通 API 以 SDK 每次提交的完整 messages 为请求输入。当前长期 native thread 主要增量接受 user 输入和工具回执，并保有原生历史与其内部采样，不能据“同一 thread”断言与当前 SDK messages 完全一致。
- 关闭 SDK 自动摘要、改由 native 摘要，会改变上下文管理者和摘要策略，因此不是保持原 API 框架不变的方案。此设置未部署。

因此取消接回只能称为“避免真实工具结果丢失的兼容补救”，不能称为严格 API 等价。真实工具不丢失和最终回答晚于回执，是正确性底线；采样历史、工具接口、上下文与预算的一致性仍需单独约束和实测。
