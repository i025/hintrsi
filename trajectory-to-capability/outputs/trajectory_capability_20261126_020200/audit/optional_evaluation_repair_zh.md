工程补充：此前修复仅针对核心评估器日志；其后另行修复可选评估超时。现有运行脚本仅对 capability_hint_development_ 前缀运行，将原测试命令包装为 timeout --kill-after=10 600。核心12次配对结果 均已完成且不受影响。首次 可选No Hint 的 Vitest worker 持续占用 CPU；该运行早于包装器，在容器创建后 600.022 秒被外部停止，实际执行起点未知，停止请求后约 13.129 秒进程结束。因此名义上为 10 分钟加宽限期，但与后续包装运行的计时并非严格相同。原始 reward 缺失、退出码 137，F2P/P2P 未知，不应计为正常失败。学生正常 end_turn，补丁未变且未重试；根因未知。未检查或修改隐藏测试源码及任务答案代码。

记录：[工程修复日志](../logs/engineering_fixes.json)；[首次评价限时记录](../logs/optional_evaluation_timeout_NoHint.json)。
