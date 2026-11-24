本预检不调用真实模型，所有模型响应及 usage 均由容器内固定 HTTP fixture 生成，不计入正式实验。运行的是原始 Claude SDK 0.2.186 与其 Claude CLI 2.1.329；使用生产 create_agent_options 和 OnlineTeacher，保持每 20 次主工具完成检查、最多 3 次检查。独立容器 network_mode=none，统一 Python runtime 只读挂载，执行后已移除容器。

真实 SDK 的第 20 次 Read 后，Hook 指导出现在下一请求 messages 内单独的 role=system 消息；并非保证嵌入 tool_result。原 LiteLLM adapter 会丢弃这个消息。新实验副本 streaming_fix 在原位置把这类内部 system 映射为 user，保留文本；请求顶层 system 原样保留。另保留 tool_result 的 is_error 到本地 OpenAI 兼容桥，这是本地扩展字段，不是外部 OpenAI API 字段。

result.json 同时记录 SDK 原始传输与 bridge 回放两项 gate。bridge_replay_result.json 证明两份真实捕获请求经过实际 LiteLLM adapter 和离线桥后：20 份工具结果逐字完整，使用同一 thread/turn，教师指导通过一次 steer 送达，marker 恰好一次，重复历史请求不重复回复工具或指导。replay_bridge.py 可独立复现。test_tool_result_transport.py 额外使用真实 LiteLLM/OpenAI 序列化和 HTTP mock 验证 is_error 不会再次丢失。

兼容边界：此次验证覆盖文本 Read 及阶段性 Hook 指导；图片等多模态结果未在此 fixture 验证。stdout_attempt1.log 是导入函数名错误的首次搭建记录，尚未开始任何模型 HTTP 请求；后续成功运行见 stdout.log。
