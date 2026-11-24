# 第 11 版候选：参数编码修复与权限问题诊断

工具参数双层 JSON 的修复已在独立候选 source_parallel_11 完成，离线链路验收通过。正式实验保持停止；权限误判尚未修复，这一版没有接入正式启动器。不能把本次局部修复当作正式实验已经就绪。

## 编码错误为何发生、如何修改

旧桥要求模型把参数对象先写成 JSON 字符串，再把这份字符串放进外层结构化响应。外层输出约束只能保证外层是 JSON，无法保证字符串里面又是一份合法 JSON。比如 shell 正则中的 `executeChat\(`、`CLAUDE\.md` 可以是正常参数，却会在内层 JSON 中触发非法转义。

新桥让模型返回结构化键值参数，由程序还原成 SDK 参数对象，最后使用 Python 的 json.dumps 生成原接口要求的字符串。命令本身不做转义猜测或文本修补。例如 CLI 返回的结构为：

```json
{
  "content": "Search the call sites.",
  "tool_calls": [{
    "name": "Bash",
    "arguments": {
      "entries": [{"key": "command", "value": "rg -n 'executeChat\\(' /app"}]
    }
  }]
}
```

原 SDK 最终得到的参数对象仍然是：

```json
{"command": "rg -n 'executeChat\\(' /app"}
```

嵌套对象递归使用 entries 形式，数组和标量保持普通 JSON 值。这样能够保留任意参数名、Workflow.args 等任意嵌套对象，以及“省略可选参数”和“明确传 null”的区别。输出使用键值条目，是因为 CLI 严格结构化输出要求对象属性预先声明，直接把任意参数字典塞进去并不普遍兼容；参见 [OpenAI 结构化输出说明](https://developers.openai.com/api/docs/guides/structured-outputs)。原 SDK 的工具定义和参数含义没有改动，模型的返回格式发生了变化，需要后续单独验证真实生成行为。

生产源码相对 source_parallel_10 只改 codex_cli_bridge.py：原有英文格式说明、action_schema、结构到参数对象的转换函数，以及接口边界处的序列化。任务提示、教师提示、SDK 工具执行、模型、思考强度、轮数、资源和上下文窗口均未改动。旧批源码与所有结果保留。

## 为何学生误判只读

同一个学生模型看到了两套执行环境的描述：

| 环境 | 实际职责 | 权限信息 |
|---|---|---|
| Codex CLI 所在宿主 | 决定下一步，返回操作请求 | 启动参数为 read-only，CLI 自动加入原生 developer 权限指令 |
| 原 SDK 的学生题目容器 | 真正执行 Read、Edit、Bash 等操作 | SDK 配置为 bypassPermissions；容器根文件系统可写，/app 没有只读挂载 |

原 CLI 请求中确实有这段自动生成的指令：

```text
sandbox_mode is read-only: The sandbox only permits reading files.
```

它适用于 CLI 本地环境。原 SDK 会话及其工具列表则被桥放进另一份 JSON 输入中，消息角色也是该 JSON 的字段。Kea 学生把 CLI 的只读限制套到了题目工作区上，未调用任何工具，就回复需要 /app 写权限。这次没有观察到真实工具尝试写入后返回权限拒绝。

已有桥接说明曾提醒“本地 CLI 与外部 SDK 是不同环境”，但真实 Kea 请求仍然拒绝，说明这份文字提示不足以稳定表达权限边界。容器元数据只是确认预期配置，没有重新启动被保留的实验容器做写入探针。原因判断来自真实拒绝响应、零工具调用记录、实际 CLI 自动指令和 SDK 配置的共同证据。

本次保留了原权限配置，没有给 CLI 扩大权限。后续要单独解决模型看到的权限描述与实际执行器之间的对应关系，保持学生可修改、教师工作区只读。

## 本次验证范围

- 7 个真实失败的正则参数逐字回放通过。
- 108 项离线回归通过，覆盖可选参数省略、null、布尔、数值、嵌套对象、数组、引号、Unicode、实际换行与字面转义序列。
- 六路真实 Codex CLI 进程对本地模拟服务完成两阶段调用，共 12 次进程、84 项检查通过。
- 原 SDK 和完整 LiteLLM 代理实际执行 6 个工具调用：读取、带正则的搜索、字面转义输出、预期失败、修改和精确内容校验。预期工具失败 1 次，桥接错误 0 次。
- 所有模型响应均为本地模拟；新增真实模型调用 0，Ofox 调用 0。临时验收容器已删除。

这些检查证明了序列化和 SDK 工具执行链路的修复；尚未证明真实 Terra 模型能稳定生成新格式，更没有证明只读误判已经消失。九题没有重启。

## 记录

- 差异：reports/parallel_11_arguments.diff
- 验收摘要：reports/parallel_11_arguments.json
- SDK 实测：preflight/parallel_11_arguments/sdk_gate/result.json
- CLI 六路实测：preflight/parallel_11_arguments/native_six/result.json
- 权限证据：preflight/parallel_11_arguments/permission_audit.json
- 原始失败批次：reports/parallel_10_startup_failure.json
