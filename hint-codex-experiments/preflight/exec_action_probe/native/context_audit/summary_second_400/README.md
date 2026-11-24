# SDK 摘要请求再次超限的受控验证

只验证这一条路径。真实 Claude SDK 0.2.186、实际 LiteLLM 1.81.8、既有 context mapping 候选，连接独立假 exec；lane1 专用容器禁网。未修改候选、SDK 自动摘要环境变量或窗口阈值，真实模型调用为 0。

结果为正常技术失败退出，没有无限循环，也没有触发夹具 10 请求/90 秒上限。`result/result.json` 中 passed=true 表示该故障路径的验证完成，不表示任务解题成功。

实际入口共 6 请求：

1. 初始 Read 请求成功，HTTP 200。
2. 带真实 Read 回执的主请求返回明确上下文错误，HTTP 400。
3. 第一次 SDK 摘要尝试发出两个 HTTP 400 请求，其中第二个是 SDK 的 server-fallback stripping-and-retrying。messages 序列化长度均为 23733 字符。
4. SDK 进行一次 head truncation 后作第二次摘要尝试，仍包含两个 HTTP 400 请求，messages 长度均降为 14147 字符。
5. SDK 日志明确记录 giving up，然后自然返回错误结果，没有 compact_boundary。

最终 ResultMessage：`subtype=success`，但 `is_error=true`、`api_error_status=400`、`terminal_reason=prompt_too_long`、`result=Prompt is too long`。因此必须按 is_error 判断；已有 `source_parallel_09_checked/run_cc_sdk.py:615` 会将其记为 incomplete。

SDK 调用墙钟 41.09 秒；代理冷启动 109.54 秒；宿主整个 gate 172.20 秒。所有 bridge 子进程退出，专用容器已清理，见 `result/host_result.json`。

Token：只有初始成功请求有一条合成 usage，10020 tokens；另 5 个失败请求均在 `reported_usage_unknown` 中。SDK 最终 ResultMessage 的 usage 为 0，不能据此覆盖桥已记录用量或认定全程零消耗。所有数字均来自假命令，不计入正式实验。

证据：`result/sdk_debug.log:203–230` 对应两次摘要尝试、fallback、一次 head truncation 与 giving up；`result/result.json` 保存每次请求阶段、长度、状态及未知 usage ID。这个小夹具证明二次超限会有限尝试并退出，不证明任意真实长历史都能成功压缩。
