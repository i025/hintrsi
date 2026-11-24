# formal_03 只读协议审计

本记录只审计codex_formal_03，模型用量和成绩不合并formal_01/02。持续状态、实际用量及各阶段会话见同目录formal_03_protocol_audit.json；监控不调用模型，不运行额外探针，不干预驱动或服务，不修改冻结源码与配置。

## 首次尝试：Anko B1

- 正式评测正常完成：reward=0，F2P0/2，P2P119/119；SDK metadata.status=completed，ResultMessage.is_error=false；补丁11885字节。
- 完整流程1292.091秒，学生有效时间847.040秒；实际Codex累计2,167,131 tokens，缓存与推理数是对应输入/输出子集。
- 实际system_prompt_config为mode=preset、append_char_count=0、append_text=null，SYSTEM_PROMPT_FILE及APPEND_SYSTEM_PROMPT_FILE均为空。旧日志仅根据默认system-reminder判定“hint已加载”，该行不能用来认定baseline获得实验Hint。
- 已只读调用当前真实report_codex_experiments.attempt_metrics，从原eval_path补齐P2P得到119/119，同时保留reward=0、F2P0。当前驱动live report.md/results.csv是简表，没有P2P列；本审计未重写正式报告文件。

## 新stderr捕获的实际观测

首个SDK日志已保存3行Claude CLI stderr，证明回调进入既有归档路径。其中两行表示当前容器缺少bubblewrap/socat，因此SDK自身的Bash sandbox未启用；另一行是原SDK对自定义gpt-6.1-terra标签的unrecognized_model警告。此次SDK仍正常完成，桥接的强制Terra/low协议没有模型错误或原生工具事件。以上属于实际可观测的运行条件，监控没有安装工具或改变权限；外部工具仍由现有SDK在本次容器中执行。

统一BUN_JSC_useJIT=0已写入冻结的create_agent_options，且恢复阶段无模型探针已确认工具子进程继承0。正式尝试的普通产物没有逐进程环境实测字段，因此持续JSON对此保留null，不把源码声明冒充每个进程的再次观测；没有为监控新增环境探针。

H/M/I初始Hint文本、共享教师及压缩用量只计一次、fresh学生线程及持续教师线程等检查，会随现有产物到达而在JSON中更新。

## 兼容日志原文（B1已归档stderr）

```text
⚠ Sandbox disabled: sandbox is enabled but dependencies are missing: bubblewrap (bwrap) not installed, socat not installed · install missing tools (e.g. apt install bubblewrap socat) or see https://code.claude.com/docs/en/sandboxing
  Commands will run WITHOUT sandboxing. Network and filesystem restrictions will NOT be enforced.
[claude-code:unrecognized_model] {"model":"gpt-6.1-terra","query_source":"sdk"}
```

仅记录原文；不安装组件、不更改路由或权限。所有组保持相同运行条件。
