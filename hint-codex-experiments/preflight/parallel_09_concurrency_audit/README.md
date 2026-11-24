# 09 并行接入审计及响应交付候选

正式 09 未启动。本目录只包含离线审计、候选和测试，没有修改冻结源码，没有启动容器或真实模型。

## 并行与会话结论

新增 6 项交错执行测试通过：六路 HTTP 请求同时推进、工具结果反序到达、token 与响应耗时按会话记录；六个 M 教师跨生成和两次复盘保持同一线程；H/I 学生及 H 教师跨轮创建不同线程；六路 I 指导的 GT、提示历史、阶段 URL 和累计等待时间互不混用；取消一路 HTTP 等待不干扰其他路；全局停止中断准确的六个线程及 turn。

测试调用真实冻结 `bridge.chat`、FastAPI ASGI 路由及 `TeacherProgress`，原生 RPC 使用可交错事件的替身，因此它证明框架并发路由，不替代真实 Codex 和真实 SDK 的完整链路验证。主线程及其他审计任务另有相应证据。

既有 106 项测试的实际导入路径也已检查：34 个本项目模块路径均来自 `source_parallel_09` 或其测试目录，没有误用默认 source。`ROOT` 指向项目根，子脚本路径由当前源码文件的位置决定。证据为 `import_paths.json`。

运行控制保持原设计：六个 worker 使用不同 Docker socket、输出根和实验标签；教师/学生容器独立，容器内同名 `/tmp` 文件不会跨 lane 共享。`run_loop_by_hint` 的当前子进程变量位于各 worker 进程内。共享桥按 Session 加锁，创建原生线程另有开锁保护；I 指导每个学生有独立锁。全局停止是明确的共同故障边界，任何一路指导异常或桥的账户/传输/原生工具异常都可能停止整批，不能把它与工具结果串线混淆。

H/M 共用首轮的实际分支由原测试覆盖：共用一次学生结果，成功不进入 M 机制；失败后 H/M 读取相同轨迹，分别新教师和初始教师同会话复盘，保持五轮上限。新增并发测试没有改变该规则。

## 确认的响应交付缺口

若模型桥已经发出工具响应，但 SDK 没有收到，SDK 使用相同历史重试时，原桥已将调用标记 served 并清空 ready；它会等待 SDK 尚未见过的工具结果，双方停住。`lost_response_retry.json` 是零网络、零模型的确定复现，不表示已证明 08 发生同一 HTTP 丢包。最终文本响应丢失也会使相同历史重试拿到空正文。

候选 `candidate/codex_cli_bridge.py` 只调整这段交付逻辑：

- 每个 Session 只保存上一份请求历史及 phase 和完整响应的深拷贝；相同最后请求重发原正文、工具、ID 和 usage。
- 部分工具已经写进 SDK 历史时，仅补发尚未见到且未完成的 pending 调用，保留旧调用在新到调用之前的顺序。
- 不开启新原生 turn，不重复提交工具结果，也不新增原生 token 账本记录。HTTP 响应中的 usage 重复表示同一请求的重发。
- 工具定义一致性和全局停止检查仍先执行；外部代码修改返回对象不会修改保存的快照。
- 两个快照字段只留在内存，排除出教师 checkpoint，避免每次 token 通知把整段 SDK 历史重复写盘；既有教师恢复记录字段集合保持一致。

## 原生重试通知

实际协议 `preflight/parallel_08_schema/v2/ErrorNotification.json` 要求 `willRetry` 为布尔字段。原桥把每条 error 都永久写入 Session；确定复现显示，`willRetry=true` 后 CLI 正常 completed，桥仍报错。候选只在不会继续重试或出现额度错误时保留致命状态，继续记录全部原始事件，不增加自己的重试机制。额度错误无论 willRetry 真假仍全局停止。

新增 5 项回归覆盖暂时错误后继续工具与最终输出、六路等待时一路暂时错误、真正失败只影响所属会话，以及两种 willRetry 下额度准确中断六路。`retry_notification_probe.json` 直接对比冻结源码与候选。

`native_retry/result.json` 进一步记录真实 Codex CLI 的本机假 provider 验证：第一次 SSE 流在 response.created 后结束，CLI 发出 `Reconnecting... 1/1`、`willRetry=true`，随后第二次请求成功。整个过程只有一个 native turn，候选正常返回完整文本、无残留 error，25 个合成 token 仅记入隔离探针目录。无真实模型调用；CLI 和本机服务均已关闭。首次探针只因检查事件时误把 RPC 响应当通知而断言失败，其实际桥恢复也成功；原记录保留在 `native_retry_attempt_01`。

## 验证与边界

候选通过 **128 项测试**：原 106 项、6 项六路并发、11 项交付回归、5 项重试通知回归，耗时约 8.61 秒，0 次真实模型调用。测试覆盖工具响应和纯文本压缩结果丢失、完整正文/usage、部分已见工具、新到工具顺序、已见未完成工具不重发、完成后不重复执行、深拷贝、正常后续上下文、M 新复盘阶段以及 checkpoint 格式。见 `candidate_all_tests.json` 和对应日志。

候选只保障同一桥进程、已解析到同一个 Session 的末请求交付。它没有增加跨进程持久缓存，也不会任意重放已经被新上下文跨过的旧请求。原有 haiku one_shot 辅助请求分流可能在重发判断之前创建新 Session；该边界由另一审计任务继续核查，候选未擅自取消其独立调用语义。

HTTP 等待取消本身不等于原生 turn 取消；既有原生工具等待取消、SDK 命令继续和晚回执问题属于另一项候选，不声称本目录已解决。最终组合版本应再执行统一回归及真实接入验证后启动。

主要文件：`candidate.diff`、`candidate/codex_cli_bridge.py`、`test_concurrency.py`、`test_response_delivery.py`、`test_retry_notifications.py`、`probe_native_retry.py`、`run_checks.py`、`result.json`。
