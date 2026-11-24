# 多工具 SSE 传输修复候选（未部署）

候选只修改复制出的 `codex_cli_bridge.py::_sse`：先发送正文，再给每个工具调用发送一个独立 SSE 块，最后沿用原结束原因和用量块。工具的顺序、index、id、name、arguments 均保留。模型、Prompt、工具定义和配置不变。

原因已复现：LiteLLM 1.81.8 将同一个块内的三个工具调用转换成一个 `tool_use`，并拼接三个参数字符串，产生无效 JSON；同块正文也丢失。拆块后，原有 `streaming_fix` 能正确转换正文和所有工具调用。

验证使用实际安装的 LiteLLM 1.81.8 和冻结版本的 `streaming_fix`，未修改适配器。纯文本、单工具、三工具、正文加工具、Unicode/转义参数、结束原因及用量均通过；25 项既有桥接器/工具传输测试通过。全部验证禁止网络，无真实 Codex 或模型调用。

额外的空文本且无工具对照保留原行为：现有适配器未关闭空文本块。候选与冻结原版输出相同，本次未扩大范围修复这一已有问题。所有非空正文和工具测试的块均正确关闭。SSE 完整 usage 保留；Anthropic 侧验证既有输入/输出 token 转换，未更改其他 usage 字段的既有解释。

文件：`candidate.diff` 为相对冻结 08 的最小差异；`result.json` 为实际流转换结果；`regressions.json` / `regressions.log` 为25项回归结果；`manifest.json` 记录范围。

`source_parallel_08_static`、当前服务/进程/配置和实验数据均未改动。本目录只供审阅，没有部署操作。
