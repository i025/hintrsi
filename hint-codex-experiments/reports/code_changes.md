# 新增与修改代码记录

本记录比较原交接包 source 与本次独立 source 副本，只按文本差异记录，不进行哈希验证。原目录未改动。

| 文件 | 状态 | 新增行 | 删除行 |
|---|---|---:|---:|
| `benchmark/deepswe/compress_hint.py` | 修改 | 66 | 10 |
| `benchmark/deepswe/eval_deep_swe.py` | 修改 | 6 | 1 |
| `benchmark/deepswe/gen_review_hint.py` | 修改 | 36 | 64 |
| `benchmark/deepswe/get_hint_by_task.py` | 修改 | 208 | 65 |
| `benchmark/deepswe/review_hint_traj.py` | 修改 | 67 | 18 |
| `benchmark/deepswe/run_loop_by_hint.py` | 修改 | 94 | 89 |
| `benchmark/deepswe/run_one_hint.sh` | 修改 | 7 | 2 |
| `benchmark/deepswe/run_one_loop.sh` | 修改 | 6 | 2 |
| `codex_cli_bridge.py` | 新增 | 728 | 0 |
| `constant_zhy.py` | 修改 | 10 | 6 |
| `litellm_proxy/streaming_fix.py` | 修改 | 33 | 0 |
| `report_codex_experiments.py` | 新增 | 517 | 0 |
| `run_cc_sdk.py` | 修改 | 223 | 66 |
| `run_codex_experiments.py` | 新增 | 510 | 0 |
| `run_multi_turn_loop.py` | 修改 | 97 | 17 |
| `teacher_progress.py` | 新增 | 253 | 0 |
| `update_trajs.py` | 修改 | 10 | 10 |

## 实际改动

- `codex_cli_bridge.py`：把原模型 API 请求接到 Codex app-server；保留真实工具调用编号和待处理队列，同一会话续接；原 SDK 继续执行工具；原生 Codex 环境工具禁用；记录实际 Token、耗时及停止状态。
- `run_cc_sdk.py` 与 `run_multi_turn_loop.py`：加入主学生工具完成计数、轮内教师回调和附加指导；保留原工具输出；学生有效时间扣除教师等待；异常保存部分轨迹和补丁；教师模式跳过学生 git 操作。
- `get_hint_by_task.py`、`review_hint_traj.py`：生成与复盘使用相同教师角色和工具；教师仓库只读；保存、继续或新建教师会话，状态配置不依赖已删除的临时文件。
- `compress_hint.py`、`gen_review_hint.py`、`update_trajs.py`：沿用原模板和结构，将模型指导统一为英文；轮内候选指导复用现有复盘与压缩模块，增加筛查。
- `run_loop_by_hint.py` 与两个 shell 包装：加入实验阶段与会话参数；baseline 可显式多次独立尝试，默认仍为一次；缺失正式评测记为未完成。
- `run_codex_experiments.py`：按原十题运行 B/H/M/I 配对比较，首份 Hint 共享、通过即停、独立学生尝试和新实验名保护；异常统一停止上游；先联调再正式。
- `teacher_progress.py`：最多三次轮内检查、每次含筛查最多600秒、实际提示不超过100英文词；保存候选/筛查/发送内容和等待时间。
- `report_codex_experiments.py`：按模型实际 Token 增量聚合，区分缓存/推理子集、共享成本、各阶段、每轮累计通过及未完成，不折算美元。
- `constant_zhy.py`：固定SDK版本；本批使用统一只读预装环境，跳过重复安装；健康检查只确认进程存活；给TCG环境有限的启动等待。
- `litellm_proxy/streaming_fix.py`：保留原 Anthropic 工具结果的 is_error 标志，作为本地桥扩展字段传输；不通过错误文字猜测。

## 联调中修复的兼容问题

- 原生宿主只读说明曾被模型误认为外部学生容器只读。实际容器写入检查成功；加入统一英文工具作用域说明，没有提高宿主权限，也没有启用原生工具。
- stdio JSONL 单行默认上限过小；显式设为16MiB，并以真实模拟子进程的200KB事件验证。
- LiteLLM 转换会丢弃 tool_result.is_error；在本副本原转换扩展处保留，并用真实转换/HTTP客户端的离线链路验证。
- 对照组没有注册轮内教师时仍应查询全局停止状态；已支持零教师等待。
- 大工具批次跨过多个检查阈值后，不连续追赶补发提示；每次实际检查后再等待至少20个主工具完成。

## 辅助文件与验证

`tests/` 保存兼容协议、错误传递、检查点、配对编排和报表的离线测试。`preflight/` 的CLI/真实SDK/假API工具执行探针仅用于联调，消耗与正式结果分开。`vm/` 保存本次覆盖层和统一runtime，不安装到用户现有环境。具体实际版本见 preflight/runtime_bundle.json 与 SDK 联调 result.json。

完整源码差异见 `source_changes.diff`；实际实验结论见 runs 各批次 report.md。本记录会在联调修复后刷新。

## 已确认的 Hook 与子代理兼容修复

- 真实 SDK 在第20次主工具完成后，把 PostToolUse 的 additionalContext 作为 messages 内独立的 system 消息发送；原 LiteLLM 转换会忽略它。本次仅在新副本 streaming_fix 扩展中，将这类内嵌 system 消息按原位置转为 user，保留原文；请求顶层 system 不变。真实20次 Read 的捕获请求经过实际转换与离线桥回放后，20份原工具结果完整，仍使用同一 thread/turn，提示通过一次 steer 送达，重复历史请求不会重复送达。
- 真实 SDK 的 Agent fork 会继承父调用历史，并使用与父相同的 metadata.user_id 和模型；继承记录中包含尚未给父返回真实摘要的 Agent 占位结果。原先依据任意历史 callId 续接会误把子代理当作父代理，并提前交付占位结果。本次桥按真实 Agent 调用和 SDK fork 协议识别子分支，父调用保持待完成至真实子摘要返回；子分支使用独立 Codex thread，通过 thread/inject_items 按角色保留继承的消息、工具调用和工具结果。
- fork 和 general-purpose fresh 两种真实 SDK 子代理均经过五请求回放验证：父→子→父路由正确，子执行期间父输入不变，正式摘要只送达一次，fork 保留原始父工具输出，未启用原生 Codex 工具。修复前误路由证据与修复后结果均保留。
- 上述真实 SDK 工具执行使用独立、无网络容器和固定假 HTTP 响应，没有真实模型调用；其合成 usage 不计入正式 Token。可复现脚本及证据分别位于 preflight/sdk_hook_fixture/ 与 preflight/sdk_subagent_fixture/。修复后完整离线测试62项通过；实际 app-server 管理接口验证另由桥接模块记录。

上方行数、changed_files.json 与 source_changes.diff 已按当前联调源码刷新。

- `eval_deep_swe.py`：评测容器加入本批归属标签，异常中断后可随学生和教师容器一同清理；不改评测内存、网络或CPU配置。
- 本地进程清除继承的 SOCKS 全局代理，避免 HTTPX 在访问本机桥时依赖未安装的 socksio；容器仍使用原HTTP代理。仅修改本批子进程环境，不修改用户shell配置或已有Python环境。

## 教师超时与失败状态修复（integration_02停止后应用）

- 仅修改 get_hint_by_task.py 的统一教师执行入口：用现有 GNU timeout 的 argv 形式 `-s INT -k 30 3600` 包裹原 bash 命令。到3600秒先中断SDK，30秒后仍未退出则强制结束，保留SDK已有 finally 轨迹保存路径；原线程等待仅作为收尾缓冲。初始生成和 fresh/resume 复盘均使用此入口，学生逻辑不变。
- 教师阶段先收集当前 trajs，再要求进程成功、metadata.status=completed、存在 ResultMessage 且不是 is_error。SDK报错但进程退出0，也不会被视为有效完成。检查字段与 integration_02 已完成教师的实际 metadata 一致。
- 初始教师失败仍收集并保存非空 partial Hint 供检查，但返回非0、不保存可续接教师状态、不保留失败容器；只有完整成功后才允许 keep_teacher。沿用现有驱动的失败停止和上游模型中断路径，不增加新的控制框架。
- 补丁保留在 preflight/teacher_timeout_fix.patch，专项脚本为 preflight/test_teacher_timeout_fix.py。应用后专项4项通过（0.521秒），覆盖正常/续接、实际短GNU timeout中断并保存partial、进程0但SDK失败、非空partial不得成功；主离线测试62项通过（0.680秒）。全部无模型调用。

本修复未改实验驱动、组别、提示或轮数，也未改写已有联调产物；上述修复当时尚未刷新清单；本次 formal_01 冻结准备已统一刷新上方行数、changed_files.json 与 source_changes.diff。

## formal_01 冻结准备（2026-11-22T06:18:52+08:00）

- 在原交接目录保持只读的情况下，用 Python difflib 比较执行源码文本；未计算或验证哈希。本次共记录 17 个增改文件（新增 4、修改 13），清单和统一补丁已经包含统一教师3600秒超时/失败判定与空补丁评测修复。历史说明保留。
- `eval_deep_swe.py` 的 `find_patch_file` 现在接受已有0字节 patch.diff；文件不存在仍记 no_patch，容器归属标签与原评测设置不变。新增两项针对性测试，分别验证空提交真正进入 verifier 并落盘 reward，以及缺失提交不构建/执行 verifier。最终离线主测试64项通过。
- 原 integration_02 I-r1 的0字节 Kea 补丁只在新的 `preflight/empty_patch_verifier/` 中正式评测，没有覆盖原联调结果。原Jest base报告140/140通过，new报告14项中2通过12失败；白名单P2P139/139通过，F2P0/12通过且缺失数0，reward=0、评测退出0。容器实际标签、8GiB内存、无网络和两份原始报告均留存；这是正常失败提交，不是缺失报告或环境错误。
- 原 `benchmark/deepswe/run_deepswe.sh` 已知含旧凭证且不参与本次执行：不读取其内容，不纳入文本diff或新执行源码包。`__pycache__`、`.pyc`、`.pyo`、`.git` 同样排除。快照只代表本次可执行源码集合，不声称是完整原包归档，也不打包登录凭证或shell配置。
- 固定实际版本：Codex CLI 0.163.0，Claude Agent SDK 0.2.186，实际SDK捆绑 Claude Code 2.1.329（不同于旧Alpine安装的2.1.177）；Python 3.12.16，LiteLLM 1.81.8，AnyIO 4.16.0，HTTPX 0.28.1，FastAPI 0.165.0，Docker Python 7.2.0，tiktoken 0.11.0。Docker Engine 29.10.0/API 1.57，guest kernel 6.8.0-147-generic，QEMU 4.2.1（Debian 1:4.2-3ubuntu6.30），TCG仿真；SDK环境在容器内只读挂载。版本分别来自本机包元数据、CLI --version 和已有真实SDK/runtime预检记录。
- 传输边界与README一致：原SDK→LiteLLM Anthropic/OpenAI适配→本地Chat Completions兼容桥→Codex app-server stdio JSON-RPC，实际工具仍由原SDK执行。所有角色强制 gpt-6.1-terra/low，禁原生环境工具、无模型回退；动态工具按真实callId与pending队列分批交付，fork子会话通过角色化history注入保留继承上下文。
- 旧API的 `temperature`、`max_tokens` 字段仍可出现在请求中，但没有映射到Codex原生生成参数；low以外采用当前CLI/模型默认，不能宣称旧采样/输出限制生效。没有新增种子或暗中补齐这些参数，B/H/M/I统一采用本实现。
- 正式运行尚未启动；本次冻结点已生成 `formal_01_source.tar.gz`、`formal_01_config.json` 与 `formal_01_snapshot.json`。源码包含35份执行源码、7份测试与本批README，排除项如上；没有创建正式run。正式启动仍由主任务等待design audit和transport/context gate，不由本次记录任务执行。



## Formal01中断后的P2P报告补读

仅修改 `source/report_codex_experiments.py` 的 `attempt_metrics`：状态精简评测字段缺失/None时从原 `eval_path` 补读，保留显式0值，未完成尝试仍保留空字段。`tests/test_report_codex_experiments.py` 增加实际形状回归用例，报告模块7项离线测试通过。原派生报告已在 `preflight/formal_01_connection_recovery/report_before_p2p_fix/` 存档，再重新生成Formal01的4份派生报告；P2P补齐为119/119，成绩、未完成状态与Token不变。不改实验Prompt、学生/教师执行或原始数据。内核崩溃证据及恢复边界见 `reports/formal_01_interruption.md`。


## formal_02 源码冻结准备（2026-11-22T08:04:16+08:00）

- 主离线测试一次运行65项全部通过（0.699秒），完整日志为 `preflight/offline_tests_formal_02.log`；未调用模型或运行容器测试。
- 逐份比较 formal_01 的43份归档文件，只有 `source/report_codex_experiments.py` 和 `tests/test_report_codex_experiments.py` 改动：补读原始评测的P2P等缺失字段并保留显式0值。其余执行源码、测试、README原文不变；没有改Prompt、组别或解题流程。
- 与原交接源码的文本清单仍为17份增改（新增4、修改13）。上表、`changed_files.json` 和 `source_changes.diff` 已刷新；标准diff保留原文件末尾无换行标记，按实际diff逐行计数，不进行哈希验证。旧凭证入口与缓存继续排除，未读取其内容。
- 单独生成 `formal_02_source.tar.gz`（35份执行源码、7份测试、README，共43份）及 `formal_02_snapshot.json`；保留 formal_01 原快照。这里只冻结源码，执行状态记为尚未开始；本批QEMU 6.2及运行配置由主任务完成环境验证后另外冻结，尚未生成最终运行配置，也不沿用旧QEMU配置声明。


## formal_03 SDK运行缓解与源码冻结（2026-11-22T09:21:49+08:00）

- 相对formal_02执行源码，仅在 `run_cc_sdk.py` 的 `create_agent_options` 增加两行：统一SDK子进程环境 `BUN_JSC_useJIT=0`，并将原生CLI stderr经英文前缀写入已有logger。继续使用原 `sdk_script.log` 和原归档路径，不额外转储环境变量、认证头或请求；没有新增日志文件、工具或模型入口。
- 初始教师、复盘、续接及B/H/M/I学生统一使用该入口。SDK按原逻辑合并子进程环境，Bash等后代工具进程也继承此值；因此这是一项明确记录的运行环境变化，后续各组统一应用。模型、effort、Prompt、真实SDK工具权限、题目与预算不变。
- 原生CLI仍为2.1.329，SDK仍为0.2.186。无模型离线验证记录在 `preflight/sdk_sigsegv_diagnosis/`：原生对照6/6、禁JIT候选20/20通过，包含Read/Edit/Bash检查、Hook与同会话resume；`tool_evidence_audit.json`逐份核查预期tool_use_id集合及LOCAL_TEST_PASSED。`environment_propagation.log`另确认完整Anko项目中的工具子进程读取到0，项目源码不变。所有模拟usage均不计正式模型消耗。
- 原生对照同样未复现SIGSEGV，现有日志没有定位故障指令；禁JIT属于经离线样本验证的环境缓解，不能声称已确认根因或彻底修复。formal_01/02已有结果和归档均保留。
- 修改后现有主离线测试只运行一次，65项全部通过（0.711秒），日志 `preflight/offline_tests_formal_03.log`。未新增平凡测试；本次源码/文档任务没有调用模型、重启服务或启动实验。
- 原交接目录保持只读，文本差异清单仍为17份（新增4、修改13），已用difflib刷新上表及清单；旧凭证脚本与缓存继续排除，未读取其内容，也不计算哈希。formal_03源码包沿用43份文件范围；README记录任务已通知就绪后生成 `formal_03_source.tar.gz` 及 `formal_03_snapshot.json`。最终运行配置由相应记录任务独立完成；本源码任务不修改该配置。


## formal_04 共享首轮与只读承接冻结（2026-11-22T02:45:51+00:00）

- 用户在第三批 Anko H1 已通过、独立 M1 已完成学生但未出正式评分时，明确选择共用 H/M 首轮并保存停止。第三批原始 state、轨迹、补丁、Token 与归档均保留；取消记录见 `preflight/formal_03_user_protocol_change/M1_cancellation.json`。第四批只读承接已完成 B1/H1 和原初始 Hint/GT，保留 origin_experiment，不补造 M1 成功或失败。Anko 标记 v1_transition，M 跳过，B 从下一轮继续，I 独立且 fresh 复盘。
- `run_codex_experiments.py` 新增显式 `--shared_first_attempt`、`--continue_from`，默认编排不变；新实验名保留既有输出，额度停止不得续跑。后续九题按 shared_first_v2 执行：实际 H 首轮只运行一次，记录 shared_with=[H,M]；其代码和学生会话仍每次新建。共同首轮计入最多五轮。
- 共同首轮通过时，保留原 H 成功轨迹复盘一次，归 HM/shared_success_review；不启动 M 学生或 M 续接复盘，持续教师机制记 not_triggered。失败时，原 H fresh 复盘和 M 初始教师会话 resume 都读取同一实际 H 轨迹，各自累计指导，后续 H2/M2 至最多 H5/M5 独立解题。`run_loop_by_hint.py` 仅增加可选 trajs_override，原 Prompt、Hint、GT 与工具入口复用；I 与 B 规则不变。
- `report_codex_experiments.py` 按实际观察只记一次共同学生成本，再分别显示 H/M 政策结果；共同成功复盘成本也只记一次。取消的第三批 M1 消耗单列并仍包含在实际总成本，Anko 过渡题不纳入 v2 H/M 对比。若共同学生中断、尚未写 shared_first_attempts，报告从真实 attempt 的 shared_with/stage 识别，且与显式引用去重。运行中的 shared-first 非演练报告统一调用同一正式报告模块，避免 M 共同通过被临时报告显示为零。
- 相对 formal_03 的43份归档文件，只有六份变化：两份核心编排、报告模块、两份对应测试及 README。没有改变模型 Terra/low、英文 Prompt、SDK 工具权限、统一 no-JIT 环境、任务、镜像、资源、评测或预算；原联调门禁证据继续沿用。
- 主任务联合离线测试79项全部通过（1.103秒），日志 `preflight/offline_tests_formal_04.log`；覆盖共同通过/失败、同轨迹复盘、M 先于 H 的轮换顺序、五轮预算、I 独立、只读承接、额度拒绝、取消成本与中断报告回退。此源码冻结没有模型调用、服务操作或正式运行。
- 与原交接源码的 difflib 文本清单现为 17 份增改（新增 4、修改 13），行数、changed_files.json 与 source_changes.diff 已刷新。沿用35份执行源码、7份测试和 README 的43文件范围；旧凭证脚本及缓存排除，未读取旧凭证入口，不做哈希验证。第四批执行状态在快照中仍为 not_started；最终配置由主任务单独维护，不在本次改写。


## formal_04 启动前路径修正与第二次冻结（2026-11-22T02:49:57+00:00）

- 第一次启动在构造编排对象、读取取消记录时失败：实验名是 codex_formal_03，实际记录目录是 formal_03_user_protocol_change。失败发生在任何 state、容器或模型会话建立之前，实际 Token 为0；初次源码包、配置、快照及进程日志完整保存于 `preflight/formal_04_constructor_failure/`，不覆盖该留档。
- 仅修正 `run_codex_experiments.py` 的记录目录派生，对源实验名移除 codex_ 前缀；补充实际 codex_formal_03 目录命名回归测试，原 old 命名测试保持。没有改解题、提示、资源、评测或预算；这次是启动前文件接线修复，不是根据得分重试。
- 联合离线测试80项全部通过（1.127秒），完整日志仍为 `preflight/offline_tests_formal_04.log`。`preflight/formal_04_continuation_actual_probe.json` 另以真实第三批只读运行构造、Hint及GT复制检查：B1/H1来源正确，M1取消及1,261,995实际Token保留，I fresh、三份原指导/GT一致，旧教师配置存在，第三批 state 字节不变；模型调用0。
- 本次 formal_04_source.tar.gz 与 formal_04_snapshot.json 标为 freeze_revision=2，沿用43文件范围，与第三批仍只差六份文件。上方最新行数及原交接源码diff已刷新，历史79项首轮冻结记录保留为当时证据。第四批执行状态仍为 not_started，最终配置由主任务随后同步；本冻结不操作模型、服务或驱动。


## 2026-11-22：09重测前接入审计（未部署）

新增独立候选 `source_parallel_09_checked/`，相对冻结 `source_parallel_09/` 只修改 `codex_cli_bridge.py`：最近一次响应重放与未交付工具补发、willRetry通知语义、取消后的实际工具回执接回、禁用宿主内置技能。采用现有Session/ToolRequest与RPC结构，没有引入通用重试框架、哈希验证或修改原交接代码。总差异在 `preflight/parallel_09_combined_audit/bridge.diff`。`tests_parallel_09_checked/` 复用原测试并仅改源目录引用；新增故障/并发组合探针位于相应 preflight 审计目录。143项合并检查和六路真实CLI模拟检查通过，但API等价验收未通过；尤其未部署关闭SDK压缩的方案。正式09未启动，真实模型调用0。完整边界见 `README_parallel_09.md` 与 `reports/parallel_09_api_equivalence.json`。


## 2026-11-22：第二路线的独立 exec 操作请求原型

用户同意先试第二路线后，新增 `preflight/exec_action_probe/codex_exec_bridge.py`，复用 `source_parallel_09_checked/codex_cli_bridge.py` 的 HTTP 路由、错误类型和已修复SSE输出。新类不沿用持久 native thread、工具等待队列或教师原生会话映射；每次完整传递SDK当前消息和工具，独立调用 `codex exec --ephemeral --json --output-schema`，仅把结构化操作请求交回原SDK执行。原始任务、教师/学生提示由SDK传入并完整保留；仅新增英文的输出协议说明，使用本次调用的model_instructions_file，不改全局配置。

本次联调中的已确认边界采用最小处理：工具选择约束、不允许空白最终答案、turn.failed不能伪装成功、额度停止、请求取消清理、停止与进程启动竞态、已报告usage和耗时日志。无额外自动决策重试或哈希验证。

新增联调文件均位于该preflight目录：接口回归与假进程、真实CLI本地provider探针、实际SDK/LiteLLM闭环夹具和真实Terra记忆小样本。测试使用既有隔离环境，无GPU；真实小样本3次调用报告19031 token、30.77秒，Ofox调用0，独立于旧实验账本。尚未修改正式启动器或启动九题实验；完整SDK工具闭环、手动压缩/恢复门禁现已通过（假exec决策），最终证据和范围见该目录README和status.json。

该方式保留SDK当前可见历史，但不复用内部推理状态；将role字段作为JSON数据传入CLI，不等于原API的原生role通道。temperature/top_p/max_tokens及native上下文管理差异仍存在，不宣称严格API等价。


## 2026-11-22：SDK 自动会话压缩的接入修复与验证

原型桥此前把 Codex 的明确上下文超限错误统一转成 503，使原 SDK 无法识别其自动压缩触发信号。本次仅在 `preflight/exec_action_probe/codex_exec_bridge.py` 识别原生 `contextWindowExceeded` 和 provider 的 `context_length_exceeded` / `context_window_exceeded`，返回原接口兼容的 400 与 `prompt is too long`。其他错误维持原处理；未关闭 SDK 压缩、未改压缩阈值、未新增摘要器。差异与证据在 `preflight/exec_action_probe/native/context_audit/`。

六种错误映射回归通过；修复后现有 17 项接口回归全部通过。实际 SDK→实际 LiteLLM→候选桥→假 exec 的自动压缩门禁通过：一次明确 400 触发 SDK 的自动摘要，同一 SDK 会话接受摘要后继续成功。此验证没有真实模型调用，合成 token 排除。它只验证交接机制，不证明真实超长历史或摘要请求能容纳于 Codex 窗口；本地 Terra 窗口元数据 500000，而 SDK 原配置按 1m 处理。

这里区分两类压缩：会话历史由 SDK 发起、由后端模型生成摘要并由 SDK 替换历史；教师 Hint 仍由原 `compress_hint.py` 处理。失败请求若没有 CLI usage，记作 reported_usage_unknown，不能计作零。新的完整流程预实验独立于正式九题，仍不宣称 CLI 与原 API 严格等价。


## 2026-11-22：原代理的 SDK 用量回传修复（预实验候选）

只在 `source_parallel_09_checked/litellm_proxy/streaming_fix.py` 的异步路径，将现有 finish/usage 合并块移动到空 delta 丢弃判断之前。原交接包的同一分支也存在此问题：用量消息先被当作空消息丢弃，SDK 因此看到零用量。没有改 SSE 格式、token 数值、SDK、同步分支、压缩阈值或提示词。原交接目录与冻结 source_parallel_09 均不变；此候选暂只用于独立预实验。

四种实际模块前后对照通过，文本、双工具 ID/参数、finish reason 保持一致。实际 LiteLLM + 实际 SDK 的零模型门禁通过：SDK model_usage 的 10200 输入 + 60 输出与桥合成账本 10260 相等；Result.usage 不含摘要请求的 120，说明应按桥账本统一记账，不重复相加。Read、Bash 成功和 exit7 的三个回执正确，明确 400 仍能触发同会话自动摘要并继续。合成 token 及模型成本估算均不是真实消耗。完整差异/证据位于 preflight/exec_action_probe/native/usage_audit/。

另已验证摘要本身持续 400 的路径：SDK 两次摘要尝试、中间一次截短，最终明确 is_error=true / prompt_too_long，正常退出，无无限循环；0 真实模型调用。应按 is_error 判断技术中断，不能只看 subtype=success。证据位于 native/context_audit/summary_second_400/。


## 2026-11-22：真实模型预检暴露的两环境权限作用域混淆

首个完整 B 预检实际运行原 SDK，4 次模型请求均无接口错误，但学生以只读为由拒绝 Edit，补丁为空，测试仍 1/4 通过；原 SDK 记录为 bypassPermissions，提供 Edit/Write，无权限拒绝，/app 为可写层。教师初始阶段 5 次调用也拒绝向 /tmp 写 Hint，经原回退逻辑提取到文字。此 9 次调用、220869 已报告 tokens 全部单列保留，不计正式成绩。native只读说明为主要原因的判断有实际CLI抓包及SDK权限旁证，不声称读到了模型隐藏推理。

在原型桥的英文协议说明中只追加本地 Codex 决策进程与外部 SDK 执行环境的范围说明：本地只读限制适用于本地进程；外部操作继续遵循 SDK 消息和实际工具权限/拒绝。没有放宽本地隔离、改 SDK 权限、题目或解题指导。差异位于 preflight/exec_action_probe/native/permission_scope/bridge_scope.diff。相同的原 B 最后 messages/tools 在修复版重放一次，模型正常请求 Edit；这是一次决策验证，没有执行该 Edit，不能代替完整 SDK 验证。修复后原17项接口回归通过。

修复版完整流程使用 full_chain/bridge_scope_v2 独立账本：B=complete_sdk/attempt_04（lane5），教师/在线学生/复盘=full_chain/continuation/attempt_02（lane3），并行环境均8CPU/128GiB，题目/原提示不变。新增preflight controller仅提供 --lane 选择既有独立VM，不改变正式编排。旧源码快照与修复版快照分别保存；未做哈希验证。预检总上限由30登记调整为40（旧9+新31）；Ofox仍0，正式九题仍未启动。


## 2026-11-22：第二路线完整小夹具预检收尾

修复版真实SDK完成B读改测4/4、教师初始写Hint、原Hint压缩、I第20主工具检查与后续读改测4/4、同一教师SDK会话复盘。新流程19调用519537 tokens；旧权限失败9调用220869和一次决策重放25910均单列，本次总29调用766316。I真实教师合法选择no_hint_needed，真实注入不宣称已覆盖；另用原SDK/OnlineTeacher的零模型门禁验证20Read后的指导与20回执实际进入后续请求。完整表、request IDs和时长见 preflight/exec_action_probe/full_chain/audit.json 与README。

原SDK自动会话压缩保持启用；已验证明确400自动摘要并继续，以及摘要再次400有限重试后技术中断。最终17接口回归通过。六路CLI模拟门禁和两套真实SDK并行分别保留范围，不宣称严格API等价、长上下文压力通过或正式九题成绩。当前不部署到正式启动器。临时host服务与测试容器均已清理，原交接源码、冻结09及历史停止容器保留。

## 2026-11-22：stateless exec 接入正式候选 source_parallel_10

本次仅接入与验收，没有启动九题模型实验。原始交接目录、source_parallel_09、source_parallel_09_checked 及历史结果均保留。

相对 source_parallel_09_checked，仅改动 5 个源码文件：

| 文件 | 具体改动 |
|---|---|
| codex_cli_bridge.py | 接入已验证的 exec action 原型，移除对预检目录和旧原生 RPC 桥的依赖；复用已验证的 HTTP/SSE、错误类型和额度识别函数。每请求启动新的 ephemeral CLI，以 SDK 当前完整 messages/tools 获取结构化操作请求；仍由原 SDK 执行工具。另记录 exec_turns.jsonl。 |
| run_cc_sdk.py | 在既有 create_agent_options.env 统一增加 CLAUDE_CODE_AUTO_COMPACT_WINDOW=400000；继续使用原 SDK 压缩。 |
| run_codex_experiments.py | 记录新后端条件，传入独立日志目录；联调教师续接验收从原生 thread 编号改为 SDK session 编号及首轮最终回答确实存在于复盘请求历史。 |
| run_parallel_experiments.py | 记录真实后端及压缩条件；将独立 bridge/progress 日志目录传给每路 worker，避免 worker 报表读取旧批日志。 |
| report_codex_experiments.py | 汇总 exec_turns 的实际耗时，列出未上报用量的请求，避免把未知用量等同零；更正新后端的时间含义及新旧日志边界。 |

新入口 preflight/launch_parallel_10.py 复用旧六路启动器，默认只做服务/环境检查，显式 --launch 才启动实验。新增 tests_parallel_10、preflight/parallel_10_integration 及第 10 版配置、快照、差异和验收说明。

代理 streaming_fix.py 原样继承 checked 候选中已验证的异步 usage 传递修复。题目提示、教师/复盘/压缩提示、评测器、GT 只读约束、OnlineTeacher 策略、轮数、共用首轮和资源配置没有进一步修改。

验收：104 项离线回归通过；新桥实际启动六路 CLI、共 12 次本地模拟请求，78 个协议检查通过；真实 SDK/完整 LiteLLM 进程完成自动压缩、20 次工具调用后的 Hint 注入，以及关闭后恢复同一 SDK 会话；九题六路编排演练完成；六路资源、镜像和服务网关通过检查。模拟用量全部排除，本次新增真实模型请求及 Ofox 请求均为 0。

压缩首份用例未通过主动压缩判定，完整记录保存在 sdk_gate_attempt_01；该用例实际验证了上下文 400 经原 SDK 总结恢复。后续用逐步累积会话验证主动压缩通过，没有掩盖首次失败。

40 万窗口在当前 SDK 中实测为 38 万有效窗口、36.7 万触发阈值。原始 API 的温度、top_p 和 max_tokens 未映射，角色字段以 JSON 传入 CLI；这些差异明确列入新批配置，不声称与最原始 API 逐项等价。历史真实小例题证据单列，不能计作新批九题成绩。

复现及范围见 README_parallel_10.md；源码逐文件差异见 reports/parallel_10_source_changes.diff。

## 2026-11-23（北京时间）：parallel10 正式启动未通过，已保存停止

00:02:59 正式启动后，首批真实题目暴露两项未被局部验收覆盖的兼容问题：工具参数二次 JSON 字符串编码使正则反斜杠变成非法内层转义；Kea-B1 仍误把 CLI 本地只读理解为 SDK 工作区只读，未调用工具就结束。已保存并停止六路，未修改运行中源码，没有自动重跑。该批不能作为有效组间比较。

实际记录 32 次桥接请求、21 次有效桥接返回、11 次错误，28 次上报用量合计 1,440,804 token，另有 4 次被中止请求用量未知。Ofox 调用 0。没有新增完成的正式评测；运行中的尝试占位不能算作已完成。完整证据见 reports/parallel_10_startup_failure.json。此前 104 项离线回归和本地模拟检查通过的事实保留，同时明确它们不足以证明可以正式运行。

## 2026-11-23（北京时间）：仅修复 CLI 参数双层 JSON 的独立候选 source_parallel_11

相对已停止的 source_parallel_10，生产源码只改 codex_cli_bridge.py：在原有英文 INSTRUCTIONS 中说明新的结构化参数格式；action_schema 使用 entries 键值对象和递归 JSON 值；argument_value 将该结构还原成原 SDK 的参数对象；chat 在 API 边界统一 json.dumps。模型不再手写 JSON 编码字符串，生产路径没有修补错误转义或重采样逻辑。SDK 工具列表、可选参数缺省、显式 null、任意嵌套 JSON 值均保留。

新增 tests_parallel_11 及 preflight/parallel_11_arguments；7 个真实正则失败样例逐字回放通过；108 项离线回归通过；六路实际 CLI 对本地模拟服务的 84 项检查通过；原 SDK + 完整代理执行 6 个工具调用（含 1 个预期工具失败），读取、正则搜索、字面转义输出、修改及精确内容校验通过，桥接错误为 0。所有模型响应为本地模拟，新增真实模型调用和 Ofox 调用均为 0。

权限问题只完成诊断，没有修改：CLI 自动注入的原生 developer 指令声明宿主只读；SDK 学生使用 bypassPermissions，容器根文件系统可写且 /app 没有只读挂载。Kea 学生未发起工具调用就因只读拒绝，属于权限作用范围混淆，没有观察到实际工具写入拒绝。证据见 preflight/parallel_11_arguments/permission_audit.json。尚未实测真实模型对新输出结构的生成和接受情况，也没有修好权限误判；候选未接入正式启动器，不重启九题。

差异：reports/parallel_11_arguments.diff；验收：reports/parallel_11_arguments.json；中文说明：README_parallel_11.md。


## 2026-11-23（北京时间）：第 12 版 SDK 权限上下文修复

- 新增独立 `source_parallel_12`，复用第 11 版全部生产代码，仅改 `codex_cli_bridge.py` 的英文接口说明及传给 CLI 的执行上下文。含工具的请求显式说明原 SDK 容器位置、bypassPermissions、学生容器可写与教师仓库只读；原对话中的角色限制和工具拒绝继续生效。纯文本压缩不附加容器权限。最终 CLI 仍本地 read-only，原 SDK 执行和全部实验参数不变。第 11 版结构化参数修复继续保留。没有新重试框架、拒绝修补或哈希验证。
- 新增 `tests_parallel_12`，沿用原测试并更新源目录引用，增加纯文本压缩的权限上下文隔离检查，最终共 109 项通过。验证脚本在 `preflight/parallel_12_permissions`，复用既有六路 CLI 探针和 SDK 小题驱动。
- 两个未奏效的诊断版本留档：加强提示仍三次 Kea 拒绝；仅允许 CLI 请求目录可写仍两次因 .git 拒绝。最终方案恢复本地只读，通过结构化 SDK 容器元数据完成一次原 Kea 请求回放和一次只读子角色负例。
- 真实 SDK 学生完成读改测，5 次模型请求、6 次工具调用，测试从 1/4 到 4/4；教师权限探针沿用原系统提示，3 次模型请求读取代码/GT 并写出 Hint，仓库和 GT 只读挂载返回 EROFS，内容不变。六路真实 CLI 对本地模拟 provider 的 12 进程、84 项检查通过，不宣称六路真实模型正式实验已通过。
- 本次真实请求总数 24，已报告 610,978 token，包含无效诊断方案，Ofox 为零，无 GPU。逐次用量与耗时保留，不并入正式成绩。临时服务和两个容器已清理，六套环境运行中容器为零；旧实验数据与停止容器保留。
- 完整报告、差异、源码留档和范围见 `reports/parallel_12_permissions.json`、`reports/parallel_12_permissions.diff`、`reports/parallel_12_permissions_source.tar.gz` 与 `README_parallel_12.md`。正式九题没有重启，本候选未接入正式启动器。


## 2026-11-23T01:35:01.447783+08:00：第 12 版正式九题重新启动

用户明确要求重新开始正式实验。复用原启动器，仅将批次、源码、配置和输出路径更新为第 12 版；生产逻辑未再修改。六路服务与镜像/环境检查通过，新批次 `codex_parallel_12` 已启动。完整来源、配置及启动记录分别见 `reports/parallel_12_from_10.diff`、`reports/parallel_12_config.json` 与 `reports/parallel_12_launch.json`。首次准备检查误把运行时 pyc 缓存纳入源码差异，已排除缓存并保留日志，未产生模型请求或正式数据。没有哈希验证，旧源码、结果和停止容器保持原样。
