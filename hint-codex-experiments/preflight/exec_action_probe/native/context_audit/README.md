# Exec action 上下文与 token 审计

本目录所有模型响应均由本地假服务或假命令生成，真实模型调用为 0。原型和正式配置未修改；SDK 自动压缩未关闭。

## 已复现的 CLI 行为

`result.json` 使用真实 CLI 和当前实际 bridge：

- 新进程接收 176138 字符的完整历史，测试专用自动压缩阈值设为 1000；首个 provider 请求仍完整提交该输入，没有先发 native compaction 请求。此测试不证明生产 provider 一定接受该长度，也不证明任意输入不会触发其他处理。
- Provider 返回 HTTP 400、结构化 `context_length_exceeded`，CLI 发出 `turn.failed`，原型将其作为 `exec_failed` 返回 503。当前映射会失去 SDK 用于识别上下文超限的 400。
- `protocol_variants/result.json` 同样复现结构化 `context_window_exceeded` 被映射为 503。

SDK 是会话历史的维护者；每次 exec 接收其当时提供的完整历史。新 CLI 没有前一次 exec 的上下文，不能依赖 CLI 在发送首次超长输入前自动摘要。CLI 本身仍有窗口限制与 native 压缩机制，因此“会话摘要由 SDK 管理”不等于“只有 SDK 一层窗口限制”。SDK 当前把未知 Terra 当作约 1m 窗口；只读本地 Terra cache 得到 context_window=500000、effective_context_window_percent=95。本轮没有改变这些设置；本地假 provider 使用 fallback metadata，不能将它的窗口当成生产 Terra 窗口。

## 最小映射候选

`candidate/codex_exec_bridge.py` 与 `context_mapping.diff` 只恢复明确上下文错误：解析 CLI error.message 内 JSON 的 provider.error.code，匹配 `context_length_exceeded` / `context_window_exceeded`，或已有结构化 `codexErrorInfo=contextWindowExceeded`。返回 HTTP 400，添加 SDK 已知的 `prompt is too long:` 前缀并保留原详细错误。其余失败继续原有 503；没有对任意 `too long` 文本、HTTP 503 做宽泛匹配，也没有新增重试或关闭压缩。

`test_mapping.py` 的 6 个零模型回归已通过：上述明确代码/字段为 400，普通工具路径过长、其他 provider code、无效 JSON 仍为 503。真实 SDK 自动触发证据由 `sdk_gate/` 单独记录，不能用手动 `/compact` 代替该验证。

## 全链路 token 记录边界

主要账本应使用桥的 request_id + token_usage.jsonl：每次真实 exec 请求的 input + output 各计一次，包括教师、学生、SDK 摘要请求和重新提交历史的请求。cached input 是 input 的子集，reasoning output 是 output 的子集，不能再次相加。SDK ResultMessage 的 usage/cost 可交叉核查，但不能与桥账本叠加；SDK 对未知模型的美元估价也不是实际 Codex 订阅扣费。

明确存在未报告消耗的情况：`protocol_variants/after_usage_error/` 的真实 CLI 先接受一次合成 usage=120 的模型响应并运行纯内存 exec，随后第二次 provider 请求遇上下文错误。CLI 仅发出 error/turn.failed，没有 turn.completed usage，所以桥没有 token_usage 行。不能把这次失败当成 0 tokens，也不能用这 120 推算真实缺额。

报告直接以请求记录与 token 账本 request_id 的差集列出 `reported_usage_unknown`；无需新增通用记账框架。总量应写“CLI 已报告 tokens”，同时列未知项数量及其 role/session/phase。对超时、终止、错误请求同样保留未知状态。SDK 摘要若正常完成，会像其他请求一样留下 usage 行；native 压缩可能不报告自身 usage，详见先前 native_compaction 审计。

耗时区分每次 exec 墙钟时间、各请求耗时相加、整个实验墙钟时间；并行请求的耗时相加不能当作总实验时长。摘要时间会进入调用耗时，外部工具和评测时间则属于相应阶段。

## 自动 SDK gate 最终结果

`sdk_gate/result.json` 与 `host_result.json` 已通过：真实 SDK → 真实 LiteLLM → 独立候选 → 假 exec，依次为 initial / context_error / compact / after_compact，HTTP 状态为 200 / 400 / 200 / 200。同一 SDK session 发出 trigger=auto 的 compact_boundary，最终 success、is_error=false。没有手动 /compact，也没有设置 DISABLE_AUTO_COMPACT 或更改摘要窗口。6 项独立错误映射回归同时通过。

4 请求中 3 条 usage 合计合成 10260；失败请求没有 usage，`summary.json` 将其明确列为 reported_usage_unknown。代理冷启动 111.69 秒，宿主 gate 168.84 秒。专用 lane1 容器已清理。

该夹具的摘要 pre_tokens=2416、post_tokens=2487，只证明触发和恢复流程，不证明真实长文本的压缩率。真实超过 native 窗口时，SDK 的摘要请求自身仍可能超限；本次未验证这条二次超限路径，不能宣称长会话已通过。
