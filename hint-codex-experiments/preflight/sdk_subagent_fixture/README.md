本 fixture 不调用真实模型；使用真实 Claude SDK 0.2.186/CLI 2.1.329 和原 SDK 工具，所有响应及 usage 来自容器内部固定 HTTP server。独立容器 network_mode=none，统一 runtime 只读，容器运行完已删除。

父代理真实执行 Read，再用 SDK Agent 的 fork 类型启动子代理；子代理真实执行 Read 后返回摘要，父代理收到摘要后结束。保留原 Agent 工具、原 Hook 与生产检查设置。SDK 执行本身通过：5 个请求，SDK 消息 parent_tool_use_id 指向父 Agent 调用；主工具计数为 2，子 Read 没有计入主代理次数。

实际报文确认父子使用相同 metadata.user_id 和模型。fork 请求继承父 Read 及 Agent 的调用历史，并包含 Agent 的占位工具结果“Fork started — that fork is you.”、fork-boilerplate 和子任务指令。父最终请求中的同一 Agent 调用才包含真实子摘要。

初次 bridge 回放失败：历史 callId 路由将子请求误回父 thread，把占位结果提前送给父；父收到真实子摘要时因历史变化报错。bridge_replay_result.json 保存逐步证据，rpc_responses 保存实际送给桥底层的结果。该 gate 的 passed 需 SDK 与 bridge 两项都通过；修复后运行 replay_bridge.py 重新验证，不需要任何模型。

另外，新子 thread 需要继承原请求中的 assistant/tool 历史；仅发送 user 文本会丢失 fork 上下文。这与区分父子路由属于同一次兼容性验证。

修复后已通过同一批真实报文回放：fork 与 general-purpose fresh 子代理均使用独立 Codex thread，执行子任务时父 user_inputs 保持不变；父 Agent 到正式摘要才完成，摘要只送达一次。fork 的父调用、工具结果及原始读取内容通过 thread/inject_items 按角色保留。新 bridge 的 native 工具禁用配置也已检查。fork 结果见本目录 bridge_replay_result.json，fresh 结果见 general-purpose/bridge_replay_result.json；修复前结果保留在 bridge_replay_before_fix.json。两种模式的真实 SDK 容器均已移除，未产生真实模型请求。实际 app-server 对 inject_items 的管理接口读取验证由桥接模块负责人单独记录。
