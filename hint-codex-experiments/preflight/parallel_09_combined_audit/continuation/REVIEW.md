# Checked 桥的独立合并复核

本次只读取 `source_parallel_09_checked`，在本目录增加组合测试和适配后的既有测试；没有修改 checked、原始 O、冻结 09 或实验数据，没有启动正式实验。

## 合并结论

对照 `../bridge.diff`，响应交付快照、部分工具补发、`willRetry`、取消后的实际工具回执恢复和 `skills.bundled.enabled=false` 均在合并版保留，未发现相邻修改遗漏。原全局停止和会话错误检查位于重发快照之前；取消后的工具结果先完成实际观察恢复，随后才保存可重发的最终响应。

执行 **143 项测试，全部通过**：原 106、六路并发 6、响应交付 11、重试通知 5、生命周期 7、新组合 8。耗时 8.43 秒，真实模型调用为 0。`all_tests.json` 记录每个项目模块的实际文件路径；生产代码全部来自 `source_parallel_09_checked`，`unexpected_project_modules` 为空。测试没有悄悄使用旧 candidate。组合测试使用另一模块名加载的也是同一个 checked 源文件。

11 项交付测试仅做导入适配以及 checkpoint 预期调整：lifecycle 新增的 `recovered_tool_results` 可以序列化，`last_request`、`last_response` 两个快照仍不得序列化。旧 Session 和 ToolRequest 构造参数可使用新增字段默认值；这不等于新增了进程重启自动恢复功能。

## 新组合覆盖

1. 原工具响应丢失后 native 已取消并提前结束：重发同一个调用，SDK 实际结果到达后恢复一次，重发最终响应不重复记 token。
2. 三工具响应只收到前两个、第三个已取消：只补发第三个原 ID，前两个走原 RPC，第三个走一次结果恢复。
3. 三个相同请求在恢复期间交错到达：同一 Session 锁保证只恢复一次，三个响应的正文、ID 和 usage 一致。
4. 晚回执恢复过程中收到 `willRetry=true`：保留真正处理结果后的最终正文，不保留提前的 final，不留下致命 error。
5. 全局停止先于缓存重发和结果恢复生效。
6. checkpoint 排除响应快照，保留 lifecycle 状态，并检查旧参数默认值。
7. 原 API 输入契约差异探针：后续修改 system 或 assistant 文本、添加 temperature/max_tokens，均未进入 native 请求。
8. 同一工具会话中末尾 user 消息追加 hook 文本：只发送新增后缀，通过 steer 进入当前 turn，不重放原题。

## 原 API 契约差异，不能由通过测试消除

原始文件位于 `hint-experiment-handoff/source`，本次只读。

| 输入或行为 | 原 API 框架 | checked 桥 |
| --- | --- | --- |
| 模型上下文 | 每次发送 SDK 当前完整 messages | 原生线程保留上下文，后续只发送 user 增量和实际工具 RPC；SDK fork 是单独注入参考历史的特例 |
| system/developer | 当前请求携带当前内容 | 首请求合并进 baseInstructions；后续 system 改写不更新，并另有 external-tool developer 指令 |
| assistant 历史 | 当前 messages 中的 assistant 内容参与请求 | 普通 assistant 重写不注入原生历史；实际 native 生成的历史继续保留 |
| 工具回执时机 | SDK 组织当前 API 请求的完整工具历史 | 按 messages 顺序逐个回应 RPC，native 可以在回执到达后继续推进；工具身份保持不代表时序完全相同 |
| 输出与采样配置 | O compress_hint 使用 temperature=0.3、max_tokens=16384；O review 默认 max_tokens=32000，并传 thinking 配置 | 桥不读取这些请求字段；使用固定 Terra/low，因此不能声称完整保留原采样和输出预算参数 |
| 工具取消 | 由原 API/SDK 工具循环决定后续上下文 | Code Mode 取消后，SDK 晚到的实际观察通过同一 native thread 的 toolOutput 保留；必要时产生新的 native turn，相关 token 计账 |
| 历史缩短或改写 | 无状态请求直接采用最新 messages | 路由和 user 增量逻辑依赖历史前缀；不能据此假定与任意 SDK 压缩后的完整消息等价 |
| 请求重发 | 由客户端/API 处理 | 同进程同 Session 仅保存末响应；haiku one_shot 另有独立调用边界，未在本次修改 |

上述差异意味着当前版本可以提供统一的组内实验接入，但本轮测试不能证明“仅替换 API 连接方式，模型实际输入和原框架完全一致”。正式启动前应以主线程的原 API 契约核对结果为准。

主要证据：`all_tests.json`、`all_tests.log`、`combined_tests.json`、`test_combined_delivery.py`、`run_checked_regressions.py`。所有测试与进程已经结束。
