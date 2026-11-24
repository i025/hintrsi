# SSE usage 传递核查（零模型）

结论：原代理的 async 流包装器在合并 usage 前先把其空 delta 当作无内容块丢弃，导致 SDK 收到 0 token。仅拆分桥的 finish/usage SSE 块无法修复；LiteLLM 已经会将这两种输入规范化为相同的独立 usage chunk。

原交接包 `hint-experiment-handoff/source/litellm_proxy/streaming_fix.py` 与 checked 版本的整个 `_patched_anext` 完全一致，证据见 `original_async_match.json`。这是原代理已有问题，不能称为 Codex 特有问题。

## 最小候选

`candidate/streaming_fix.py` 只将 async 分支原有的 `holding_stop_reason_chunk + usage` 合并块移到 `_accumulate_reasoning` / `_should_start_new_content_block` 之前。代码、数值及字段映射均沿用原合并块。未修改 sync 分支、桥 SSE、原 SDK、压缩阈值、模型或提示词。原交接包和冻结源码均未改；父任务负责审阅后合入。

补丁：`streaming_usage.diff`。

## 实际模块前后对照

`lightweight.py` 使用实际共享桥 `create_app/_sse`、本地 HTTP、LiteLLM 1.81.8 和实际 `AnthropicStreamWrapper + streaming_fix`。分别测试文本结束、两个工具调用，每种使用原同块 SSE 和 finish 后独立 usage SSE，共 4 种组合。

- 修前：四组 `message_delta.usage` 均为 input=0、output=0。
- 修后：四组均保留 fixture 的 input=123、output=17。
- 排除随机 message ID 和预期变化的 usage 后，所有 Anthropic 事件完全一致：文本、工具 ID、参数、顺序、finish reason 均保持。

完整事件：`before.json`、`after.json`；断言：`verify_lightweight.py`；结果：`lightweight_result.json`。这些数值是人工 fixture，不是实际模型用量。

## 实际代理和 SDK 门禁

`probe_sdk_gate.py` 在 lane1 新建独立禁网容器，仅复制候选代理模块；使用原实际 LiteLLM CLI、Claude SDK 0.2.186 和现有 exec bridge。独立 fake exec 产生已知事件，不调用 Codex/native/外部模型。SDK 执行真实 Read、成功 Bash、exit 7 Bash，三个回执 ID 逐一匹配且错误标记正确。

原共享桥 SSE 完全未改。四次请求为 200 → 400（明确 context_length_exceeded）→ 200（SDK 自动摘要）→ 200（完成），同一个 SDK session。自动压缩 pre_tokens=10099、post_tokens=2488；没有关闭或改变 SDK 压缩。

SDK 最终 `usage` 报 input=10100、output=40；`model_usage` 报 input=10200、output=60，与桥三条成功请求的账本总计 10260 完全一致。这里 SDK `usage` 不含摘要请求的 100+20，而 `model_usage` 包含；全链路汇总应以请求账本为主，不能将两套统计相加。SDK 显示的 cost=0.042 只是根据人工 token 估算，真实费用为 0，不能并入正式模型费用。

失败请求无 `turn.completed.usage`，继续记为 `reported_usage_unknown`，不能计为实际消耗 0。本修复只恢复已经报告的 usage；不解决 CLI 失败未报告用量、原生压缩未报告用量等既有边界。

证据：`sdk_gate/result.json`、`sdk_gate/sdk_messages.json`、`sdk_gate/bridge/token_usage.jsonl`、`sdk_gate/host_result.json`。host 执行 162.18 秒，其中代理启动 107.42 秒。SDK 自报 duration=15.809 秒。自己的容器已删除，代理和桥随容器结束；未干预正式容器/服务。

## 新增文件

`candidate/streaming_fix.py`、`streaming_usage.diff`：唯一运行代码候选。
`lightweight.py`、`verify_lightweight.py`：轻量实际模块夹具与断言。
`probe_sdk_gate.py`、`guest.py`、`fake_exec.py`：沿用既有门禁的小幅路径/断言调整，用于此次实际代理/SDK 零模型验证。
其他 JSON/log 文件为本次核查证据。未修改正式源码。
