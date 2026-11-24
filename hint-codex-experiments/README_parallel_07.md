# 九题六路并行实验 07

用户于2026-11-22明确要求将Anko之外的九题并行实验。本批采用全新采样：05因长提示传参错误中止，原M教师SDK会话已随容器删除，不能继续当作原连续会话。05的全部成绩、补评测、未完成轨迹和17,475,084 tokens原样保留，作为中断批次单列；不并入07的九题效果统计。Anko沿用03/04已完成的7次评测，不重跑，仍属于v1过渡。

## 运行协议

- 六套既有VM，各8vCPU/144GiB，总48vCPU；宿主256逻辑CPU，符合不超过约一半CPU的要求。
- lane0：Claude Code → Termenv；lane1：Igel → Textual；lane2：Ink → Valibot；lane3：Kea；lane4：Obsidian Linter；lane5：SQLfmt。每路一次一题，不同路并行；题内组序沿用原全局题序轮换。
- 全角色gpt-6.1-terra/low、英文Prompt、原Claude SDK工具、共享初始Hint、H/M共用学生首轮；共用首轮只实际执行及计费一次。共同失败后H新教师复盘，M沿用初始教师会话；后续学生均从新环境开始。
- B/H/M/I各至多5轮，通过则停止该组。B没有Hint；H常规轮后复盘；M教师持续会话；I在一轮内每20个主要工具后检查，最多3次，每条Hint最多100词。
- 学生有效时限7200秒、教师3600秒、I检查600秒；学生和教师8CPU/128GiB，评测8GiB。SDK0.2.186、原生CLI2.1.329及BUN_JSC_useJIT=0不变。
- 真实token账本和阶段耗时持续记录。额度不足或运行故障时全局保存并停止；不自动购买、重置额度或改变模型。

## 本次新增代码

来源为冻结的source_parallel_06，包含已验证的长Prompt文件传参修复。07只改四个生产文件：

1. benchmark/deepswe/get_hint_by_task.py：每次教师阶段完成后导出/root/.claude/projects及子会话，并在teacher_state.json记录归档；异常阶段保存现有会话并停止保留容器。
2. run_codex_experiments.py：异常终止时停止并保留本worker容器；正常完成仍按原方式清理。
3. run_parallel_experiments.py：全局异常停止的兜底清理改为停止保留本批容器。
4. codex_cli_bridge.py：保存教师原生会话绑定、SDK工具定义、已送输入和待处理工具信息，便于后续恢复检查；模型请求/路由逻辑不变。

未更改任何模型Prompt、数据、评分、轮数或组别算法。归档仅保存会话项目目录，不复制宿主认证文件。未新增自动恢复机制；SDK归档恢复验证不代表原生Codex中断中的工具调用能自动恢复。旧05会话仍不可据此复原。

## 验证与记录

106项联合离线测试通过；九题六路完整dry_run通过，真实模型调用0。真实SDK模拟服务验证首次会话→导出→删除原容器→新容器导入→同一会话继续，恢复后检查包含原始会话文本并能执行Read/Edit/Bash。该验证隔离网络，无真实模型调用。

新批次输出：runs/codex_parallel_07/。配置、源码归档、文件差异、运行启动记录在reports/parallel_07_*及logs/codex_parallel_07_process.json。先前实验累计实际tokens为33,611,260；07新增费用独立统计。旧05失败结果不能隐藏或用07替换为更好成绩。
