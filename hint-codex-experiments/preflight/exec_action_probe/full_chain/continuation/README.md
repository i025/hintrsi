本目录是独立预实验的 M/I 准备与证据检查。正式九题尚未从这里启动，冻结的 source_parallel_09_checked 不作修改。

复用与差异：
- 模型仍为 Terra / low；学生和教师均使用原 run_cc_sdk.py、完整静态 SDK 工具、原 LiteLLM 代理；SDK 负责会话，exec 每次接收完整当前 messages。
- 教师初始指导直接使用原 HINT_AGENT_SYSTEM_PROMPT/HINT_AGENT_USER_PROMPT；压缩直接使用原 compress_hint 的模板、call_llm 与使用规范；复盘使用原 compress_trajectory/build_user_prompt，并按真实 I 评测选择原成功/失败分支。
- M 两阶段共享同一教师容器、代理与 SDK session ID。初始结果导出后清除 /tmp 阶段文件，保留 /root/.claude/projects。教师仓库与 GT 文件均实际 bind-remount ro；guest 检查内核 EROFS。
- I 使用独立新学生容器和 SDK 会话，GT 仅在 host registration 与教师容器中。它沿用原 OnlineTeacher/TeacherProgress：20 个主 Agent 已完成工具、最多 3 次、每次 600 秒。题目另加一条仅用于预实验的输入要求：先用 20 个独立 Read 读取共享 fixture 的 20 个数据文件，不改变原工具列表或 hook。
- 与正式实验的区别：题目为共享 window-report fixture，使用预实验容器装配，未伪造 DeepSWE parquet 或运行 DeepSWE 容器编排。M 复盘复用 I 的真实带指导轨迹，用于验证接口，不构成独立正式 M/I 对照成绩。额外 Read 要求也不能用于正式效果比较。
- 原 API 的参数/消息角色语义与 JSON 结构化 exec 仍有已说明的差异；本测试验证当前授权路线的完整工具链，不证明严格 API 等价。实际输出预算/max_tokens 使用 Codex CLI 默认；原代理/复盘请求中的 65536/32000 等字段仅存档，未映射为实际生成上限。

入口都在本目录。主线程确认服务就绪后才逐阶段执行：

```bash
PYTHONDONTWRITEBYTECODE=1 LITELLM_LOCAL_MODEL_COST_MAP=True /srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -B /srv/lab-disks/disk2/users/xymo/hint-codex-experiments/preflight/exec_action_probe/full_chain/continuation/controller.py --mode M-initial --attempt attempt_01
```

随后保持同一个 `--attempt attempt_01`，将 `--mode` 依次替换为 `compress`、`I`、`M-review`。这四个阶段都会调用真实模型；当前文档与离线测试本身没有调用模型。教师容器在 M-initial 后保留，最后用 `--mode cleanup` 导出后清理。I 学生完成后自动删除独立容器。全局请求上限由 root 的预实验 bridge 控制，不在本控制器另设模型策略。

每阶段保存原 SDK 轨迹、会话归档、耗时、命令、实际教师会话 ID；I 保存实际测试前后日志、补丁、评测状态。token 以 `full_chain/bridge/token_usage.jsonl` 的真实 exec 账本按 session、role、phase、request_id 归属，原 SDK usage 是独立报告口径，不能再叠加。

教师检查：

```bash
/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -B audit_stages.py teacher --initial attempt_01/M_initial --review attempt_01/M_review --bridge ../bridge --session exec-preexperiment-m --output attempt_01/teacher_audit.json
```

不仅检查相同 SDK ID，还检查 review 首个实际 bridge 请求中保留初始阶段工具回执与最终指导。I 检查：

```bash
/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -B audit_stages.py online --student attempt_01/I_student --progress ../progress --bridge ../bridge --session exec-preexperiment-i-r1 --output attempt_01/online_audit.json
```

`no_hint_needed` 可以通过 checkpoint 验证，但其 `actual_guidance_injection_verified=false`、`guidance_injection_coverage=not_exercised`。只有真实 delivered hint 在随后的学生请求历史出现，才标记指导注入通过。不让学生故意犯错，也不强制教师给 hint。

网络隔离复用 B driver 的 VM netns helper，仅调整该容器 netns，并记录 VM 全局规则前后相同。教师仅放行 gateway 8765，I 另放行 8766；不在镜像安装 iptables。同 SQLfmt 镜像的目录与 GT 单文件只读挂载已在 lane3 零模型验证，结果在 readonly_mount_probe/result.json；临时容器已删除。

当前状态：控制器与材料已准备，7 项离线测试通过；仅只读挂载零模型小检查实际运行并清理，M/I 的真实模型阶段尚未由本子任务启动。全流程最终报告由主线程在真实运行完成后填写。
