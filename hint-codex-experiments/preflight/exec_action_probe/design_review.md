# Stateless structured-action 独立设计复核

状态：主线程已建立 `codex_exec_bridge.py` 候选，本独立复核通过 **17 项假进程契约测试**。测试调用候选真实 subprocess/stdin/JSONL/HTTP/SSE 路径，模型由本地 Python 子进程模拟；不是重写一份桥逻辑来代替候选。此组测试没有启动真实 Codex、没有调用真实模型，没有修改候选或冻结源码。实际 CLI / 模型 / SDK 验证由主线程及其他审计材料单列。

## 核心边界

SDK 保存学生的一轮解题历史。每次 HTTP 请求启动新的 `codex exec`，通过 stdin 传入 SDK 当前完整 messages 和工具定义。工具实际执行仍由原 SDK 完成，真实回执进入下一份 messages。不能使用 exec resume、--last、fork 或原生线程的隐藏历史补充当前请求。M 的上下文应来自原 SDK 持续会话所提交的完整历史，而不是 native resume。

当 SDK 压缩或替换历史时，下一个 exec 必须只看到该请求的新历史。不能把旧请求中被删掉的消息偷偷补回去，也不能再依赖 user 前缀相同的检查。system、developer、assistant、tool 和各自 content 块应按当前请求顺序完整序列化；不把它们混成无角色的纯文本摘要。

完整历史的 JSON 是给 CLI 的结构化任务输入，仍与原 API 原生 role 通道存在表示上的区别。这里承诺“外部 SDK 保持自己的上下文与执行循环”，不承诺与原 API 每个采样细节完全等价。

## 建议的最小模型输出

候选 schema 见 `proposed_action_schema.json`，只包含：

```json
{"content":"Optional assistant text","tool_calls":[{"name":"Read","arguments":"{\"file_path\":\"/app/example.py\"}"}]}
```

- `tool_calls` 非空：模型提出下一批操作；可以同时有正文。每条 arguments 必须是可解析的 JSON 对象文本，工具名应来自本次请求的 tools。桥只转换调用，不执行工具。
- `tool_calls` 为空：content 必须有非空白的最终文本。
- 两者都空不是成功，也不能当作一道题的失败评分；这是本次模型响应失败。
- 使用 arguments 字符串是为了保持原 OpenAI tool_call.function.arguments 接口，并避免把不同 SDK 工具的全部嵌套参数 schema 再复制成一套大型输出 schema。仍把原完整 tools 放进模型输入。
- 不让模型生成 call ID、usage、时间戳、退出码或伪造工具结果。这些分别来自桥、真实 CLI 日志和 SDK。
- JSON/schema 约束自身不能保证 arguments 的内容是合法 JSON，也不能保证工具存在；这里需要最小解析与实际工具映射。这是响应契约，不是额外重试或通用防御框架。

具体工具名可由实现选用本次工具列表的 enum。无工具请求的表示方式以及 CLI 接受的 schema 子集，需要零模型 provider 验证；不要先使用复杂的 oneOf/条件 schema。

## 复用现有 HTTP/SSE 出口

`create_app` 只依赖 bridge 的 `chat(body, headers, route)`、`status()`、`stop(reason)`、`close()` 和 `stopped`，可以复用，不必重写路由。`CodexBridgeError` 仍用于错误 HTTP 响应。`MODEL` 与 health/model 列表应来自同一实际配置。

`chat` 的返回值继续采用原格式：

```json
{
  "id":"chatcmpl-unique-request",
  "object":"chat.completion",
  "created":0,
  "model":"gpt-6.1-terra",
  "choices":[{
    "index":0,
    "message":{
      "role":"assistant",
      "content":"Optional assistant text",
      "tool_calls":[{
        "id":"call-unique-operation",
        "type":"function",
        "function":{"name":"Read","arguments":"{\"file_path\":\"/app/example.py\"}"}
      }]
    },
    "finish_reason":"tool_calls"
  }],
  "usage":null
}
```

有工具时 finish_reason 为 tool_calls；没有工具时为 stop，省略 tool_calls。content 为空但有工具时可返回 null。工具 ID 由桥生成、在当前响应内和不同请求间唯一，并在下一次 SDK 请求中原样保留。

现有 `_sse` 已做到正文独立 chunk、每个工具独立 chunk、保留 index/ID/name/arguments、最后一块包含 finish_reason 与 usage；应原样复用。它在模型完成后转为 SSE，不是逐 token 实时流。不要重新合并多个工具到同一个 chunk，否则会再次触发已确认的 LiteLLM 拼接问题。

## 状态和消费记录

会话 URL、角色和 phase 仍用于实验归属及日志，不应作为模型上下文的第二份来源。每个请求需要独立输出位置和子进程，不能共用 response.json 或依赖 --last；同题跨组相同文字也不能串线。

usage 只读取真实 CLI 的 JSONL usage，不能相信模型 action 内自报数字。需要用零模型 provider 确认该版本事件里的 input/cached/output 字段，以及多个 turn.completed 的累计规则；不能凭字段名猜测。cached input 不应在 total 中再加一次。原 HTTP usage 映射与实际消费账本应各自可追溯到一次 exec。

错误或取消前已经报告的用量仍应记录；没有报告时标注未知，不能写 0。CLI 自己的可重试通知不等于最终失败，最终退出码、成功响应及终态共同决定结果。重试若真的启动另一次 exec，就分别记真实消费；不把它误算成一次，也不默认免费。

先沿用实验已有 Terra/low；原请求 temperature、max_tokens、thinking 等字段能否由 CLI 真正实现需要单独核对。保留字段到输入/日志不代表这些采样参数已生效。

## 建议验证顺序

1. 独立 schema 与转换器：真实 JSON 参数、批量操作、正文混合工具、空响应和错误。
2. 假 exec 子进程：检查完整输入、参数、并发隔离、usage 和退出行为。
3. 本地假 provider + 真实 CLI：验证 structured output、禁止 native 执行、实际 JSONL 终态和用量；0 真实模型。
4. 原 LiteLLM + 原 streaming_fix + 实际 SDK 闭环：SDK 执行真实小工具，第二次 exec 输入必须包含真实结果，连续请求与六路交错都通过。
5. 只有主线程确认候选后再安排少量真实模型 smoke；此文档不是正式实验启动许可。

具体用例见 `regression_cases.json`。不需要为每个 JSON 字段机械增加测试，应优先覆盖曾导致批次失败的交付、并发和上下文边界。

## 当前独立验证结果

`action_contract_tests.json`：17/17 通过，最新 fresh Python 回归约 1.55 秒。`test_exec_action_bridge.py` 和 `fixture_exec.py` 是完整可复现测试入口。

已验证当前完整历史、system/developer 与 content 块、SDK 子代理的原始历史、压缩后替换历史、实际工具结果下一次输入；三工具与正文的转换/SSE；六路交错的独立输入输出目录、使用量与耗时；重复 HTTP 请求产生两次 exec 并分别记账；JSON 和参数错误、空白 final、进程失败及失败后已知用量；重试通知后成功；turn.failed 即使进程退出 0 也不作为成功；工具选择与并行限制；单路取消与额度全局停止。

额外复现并由主线程修复了停止竞态：停止发生在子进程启动完成、登记之前，原候选仍会继续发送 prompt。修复在登记之后、stdin.write 之前检查 stopped；新测试确认 prompt 未发送、无合成用量。修复前证据保留在 `action_contract_tests_before_stop_fix.json` 和同名日志。

本轮只读复核确认 tool_choice 的 auto/none/required/指定函数，以及 parallel_tool_calls=false 的动作约束均已进入候选。HTTP 取消会清理自己的子进程，并在 model_errors 写入 request_cancelled、对应 request_id / session / role / phase 与 elapsed_seconds。最新回归确认该终态日志存在且耗时为正；未上报 usage 时不写伪造的零用量，也不生成成功模型响应。取消后其他请求仍可正常执行。

尚不能由这些测试推出：真实 CLI 完全遵循输出 schema、模型内部完全保留原 API 角色优先级、原 temperature/max_tokens 参数生效，或真实 SDK 工具闭环已完成。相应证据必须另行验证。