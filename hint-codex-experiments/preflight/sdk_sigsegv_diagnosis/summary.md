# SDK 原生 CLI 崩溃排查与离线压力验证

记录时间：2026-11-22T01:22:23.005911+00:00。本次没有真实模型调用，真实模型 token 为 0；假 HTTP 返回的合成 usage 不计入模型账本。生产源码、共享 runtime、VM 与服务均未由本探针修改。

原生默认配置 6/6 通过；设置 `BUN_JSC_useJIT=0` 的 20 个新会话 20/20 通过。原生对照同样没有崩溃，因此本次没有复现正式 H1 的 SIGSEGV，不能证明其根因或保证禁用 JIT 已治愈问题。这是保持相同 SDK/CLI 版本的运行时缓解候选验证。

共同条件为 SDK 0.2.186、bundled Claude CLI 2.1.329、LiteLLM 1.81.8、QEMU 8.2.2 MTTCG、Nehalem、容器 8 CPU/128 GiB、只读共享 runtime、容器 network none。使用原 `create_agent_options`，仅为所有探针共同加 stderr/debug 日志捕获。候选与原生唯一控制差异为 CLI 的 `BUN_JSC_useJIT=0`。短 prompt、原始格式化 Anko prompt + 精确 3,785 字符 H append、长 prompt 均覆盖。

候选执行了 23 个 query 阶段、126 个实际成功工具结果。3 个候选分别在第 20 个主学生完成工具处触发一次原 hook，假 API 收到上下文标记；3 个候选恢复相同 SDK session 并保留前次代码，执行 Read → Edit → Bash 测试。保存轨迹的事后审计对全部 26 个 case 核对了每阶段精确 tool_use_id 集合、工具无 is_error、Bash 的 `LOCAL_TEST_PASSED`，全部通过，审计未新增执行。

`BUN_JSC_dumpOptions=2` 的实际原生输出为 `useJIT=true`，候选输出为 `useJIT=false (default: true)`；不是仅凭设置了环境变量推断生效。

另外保留完整 Anko `/app`、相同原任务 prompt/H append，实际 SDK Bash 仅读取指定的一个环境键，得到 `BUN_JSC_useJIT=0`。耗时 43.451 秒，原项目源码状态未变化。这确认该值会继承到工具子进程，应作为全部实验组共同的运行条件披露；没有读取完整环境或凭证。

以下是首 6 个匹配探针的 host exec 时间，包含相应工具执行和启动开销；仅用于离线探针比较，不能推断正式题速度。

| 原生 case | 原生秒 | no-JIT 秒 | 差值秒 |
| --- | ---: | ---: | ---: |
| native_00_short | 56.054 | 57.833 | +1.779 |
| native_01_h | 38.948 | 42.023 | +3.075 |
| native_02_long | 40.107 | 41.310 | +1.202 |
| native_03_short | 45.174 | 48.783 | +3.609 |
| native_04_h | 41.509 | 41.647 | +0.139 |
| native_05_long | 38.910 | 43.164 | +4.254 |

压力探针与补充环境探针的容器均已停止。早先 `setup01/` 的 metadata AttributeError 发生在任何 SDK query 之前，已保留，不计作 SDK 崩溃证据。

官方 npm 的 2.1.329 包不含可替代原生后端的 cli.js；其 Node wrapper 仍启动 native 包，因此不能在保持该版本时简单切换到 JS/Node 后端。[官方 exact-version npm 元数据](https://registry.npmjs.org/@anthropic-ai%2fclaude-code/2.1.329)。

使用 prefixed JIT 环境键的依据来自 [Bun 维护者讨论](https://github.com/oven-sh/bun/issues/22901)，并由本机实际 option 输出复核。[Claude 原生 CPU/SIGSEGV issue](https://github.com/anthropics/claude-code/issues/87974) 仅提供相关线索；[Bun 当前 CPU 要求](https://bun.com/docs/installation#cpu-requirements) 包含 Nehalem/SSE4.2，因此不能仅凭 guest 没有 AVX 认定不受支持。bundled Bun 的精确 revision 未独立识别。

证据：`stress_result.json`、`tool_evidence_audit.json`、逐 case 的 `result.json/sdk_messages.json/captured_requests.json/*stderr.log/*debug.log`、`option_ack_native.log`、`option_ack_nojit.log`、`environment_propagation_host.json`、`environment_propagation/`。机器可读汇总见 `summary.json`。
