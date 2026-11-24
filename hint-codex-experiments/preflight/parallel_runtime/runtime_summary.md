# 并行实验运行环境准备记录

快照时间：2026-11-22 03:52 UTC。六个 lane 的运行环境均已准备完成；本次仅准备环境，没有启动新增正式实验，也没有真实模型调用。

| Lane | SSH 端口 | 分配任务 | 状态 |
| --- | --- | --- | --- |
| 0 | 22230 | Claude Code、Termenv | 复用现有 VM，仅读取 Docker 元数据 |
| 1 | 22231 | Igel、Textual | 镜像、版本、资源及网关检查通过 |
| 2 | 22232 | Ink、Valibot | 镜像、版本、资源及网关检查通过 |
| 3 | 22233 | Kea | 镜像、版本、资源及网关检查通过 |
| 4 | 22234 | Obsidian Linter | 镜像、版本、资源及网关检查通过 |
| 5 | 22235 | SQLfmt | 镜像、版本、资源及网关检查通过 |

每个 VM 均使用 8 vCPU、144 GiB 内存、Nehalem、pc-q35-4.2、TCG multi、QEMU 8.2.2 和同一 BIOS/kernel/initrd。六个 QEMU 进程的 nice 均为 10；学生/教师容器继续使用 8 CPU、128g 内存。总配置为 48 vCPU、864 GiB 客体内存。

新增 VM 的磁盘均以同一个只读历史基盘为 backing，没有使用正在写入的主 VM overlay。每个 VM 使用独立 overlay、SSH 端口、Docker socket、日志和双向隧道；读取 /proc 的证据显示 backing 文件以只读方式打开。主 VM、原实验进程和服务未被重启或修改。

五个新 VM 的统一 runtime 均实测为 Python 3.12.16、Claude Agent SDK 0.2.186、LiteLLM 1.81.8、bundled Claude CLI 2.1.329，kernel 为 6.8.0-147-generic。runtime 在容器中只读挂载；原任务镜像 alias 保留。Ink 和 Kea 直接从原流程使用的公开 registry 获取，没有从当前主 VM 执行镜像导出。

Lane 1 另完成一次无网络、假 API 的真实 SDK 工具检查：Read/Edit/Bash 后恢复同一 SDK 会话，再完成 Read/Edit/Bash，共 6 个实际成功工具调用，执行阶段约 54.87 秒。结果不作为正式解题成绩或性能比较；假 API usage 排除在实际模型 token 账本之外。五个版本检查容器及该工具检查容器均已移除。

基盘中的 Docker 服务未自动启动，SSH GatewayPorts 也与主 VM 后续设置不同，因此仅在新增客体内启动已有 hint-docker 服务、设置 GatewayPorts clientspecified 并刷新各自隧道。早期冷启动时的 socket/readiness 失败已保留在原日志中；没有更换参数或重启 VM 来隐藏失败。随后五个新增 lane 的最终检查全部通过。

最终入口为 runtime_manifest.json，逐 lane 证据为 lane0_ready.json 至 lane5_ready.json，操作辅助代码清单为 helper_inventory.json。六个辅助 Python 文件已稳定，可独立归档。最终容量快照见 capacity_snapshot_ready.json。后续正式 worker 的启动和旧 Anko 实验交接由主任务控制。
