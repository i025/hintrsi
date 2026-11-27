# 从历史轨迹提取可迁移能力：最终研究汇报

**主 Test 的实际结果并不支持“轨迹知识一定优于基线”这一预设。**在两道独立 Test 任务、每组每题一次的正式评价中，K0 两题均成功，K2 一题成功，B0 和 K1 均未取得完整成功；各组仍有不同程度的局部正确性。尤其是 K2 在 TOML 任务仅差一项 F2P，但正式成功仍为零；HTTPX 的 B0 和 K1 全部 F2P 通过，却各有一项 P2P 回归。这个样本只有每组两题，不能据此断言显著性、稳定排序或知识的因果收益。

主 Selection 与 Test 的计划单元已有结果，以下称为**核心结果闭合**；这不等于六小时监测窗口、可选工作和清理核算已经结束。本报告仅呈现已供给的完成证据，不修改实验。最终监测、资源清理及完整账目以文末追加材料为准。

## A. 历史证据审计：覆盖、关键失败与教师链

### 覆盖边界

历史清单共索引 **257 条文件记录**：学生 117、教师 104、其他历史预检轨迹 36。它是文件清单，不是 257 次独立尝试，也绝不是 257 个文件均已深审。学生中深审 10 个文件、共 913 个事件；其中进入开发知识池的 D01—D08 是 8 条完整序列、397 个事件。另有冻结后只用于补充审计的 E01、E02，共 516 个事件：245 和 271 个事件 ID 均纳入，但长字符串截至 1,800 字符；它们未输入知识生成或学生。教师文件中深审 4 个完整文件、49 个事件；另有 107 个学生文件和 100 个教师文件未深审。历史预检文件也不能因被索引而视为逐事件审计。出版目录 `hintrsi` 是别名或副本，不是新尝试。

首次逐案审计包没有提供完整历史原始任务描述，因而当时只能依据轨迹、实际提示和评价重建目标；成功完成的[教师链补充审计](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/audit/audit_teacher_chain_reduced.md)后来补入了任务描述，澄清了委派、Igel 和 SQLfmt 的要求。不能把后补材料说成首次逐案审计已经看到，也不能把后来完整审计中可见的失败细节反向归入当时的知识输入。

### 必审代码案例

- **Claude 委派 B/H/M/I。**D01/B1 调用了要求遇到非 Anthropic 标记时停下询问的 skill，检查到其他提供者后请求澄清，空补丁；这是有行为证据的指令遵循，不是已尝试算法的失败。D02/H1 的实际系统提示含参考指导；事件 30—33 的模拟续接复现先失败，34—53 修改接口、处理器和适配器，59—61 同一复现通过，但正式 F2P 6/7、P2P 31/31，空文本子代理场景未通过，完整原因未确定。生成文件缺失导致类型检查受阻，测试、清理和提交未完成。D03/M2 声称受只读权限约束并空补丁，但没有可见工具拒绝，不能把其自述当作已证实的权限故障。D04/I1 因 skill 的提供者歧义停下询问，未实现或测试，正式 0/7、31/31；已有参考提示不等于实现被采纳。
- **Claude I2 的失败—诊断—修复链。**D05 事件 27—28 首先复现委派链未续接。第一次在线教师检查要求查看已有上下文与新指令或图像的真实请求；事件 49—51 的探针显示新输入被丢弃，52—57 修改续接条件，95—97 再检查普通请求和续接消息。98—100 又修改保存的图像上下文，但展示的探针没有单独覆盖这最后一次修改。第二次教师检查要求比较成功、工作者失败和未知目标的反馈与调用 ID；事件 84—85 的模拟检查确实比较了结果、错误标志和 ID。最终三文件提交，正式 7/7、31/31；与此同时，本地 handler 测试仍有失败，学生在该环境的基线上也观察到同一失败，另一个提供者套件无法转换。正式通过不能抹去这些局限，时序一致也不是随机对照因果证明。
- **Igel B3。**D06 事件 25—26 的复现显示选择特征未生效，后续实现原始 schema 的保存、加载、别名和错误传播。根目录测试失败，从预期测试目录运行则两项通过；正式 23/24、2/2，奖励 0。完整审计可见失败是描述中保存的 `feature_schema.joblib` 路径被测试直接加载时找不到，而补丁自身按描述文件目录解析相对路径；这是该记录支持的具体路径契约不一致，不应冒充当初截断抽取包中已知的教训。D07/H1 则因要求的 `main` 不可用而询问，空补丁；D06 选择 `master` 并披露。补充任务描述确认确有从 `main` 建分支并提交的要求，但不能据此推断 D07 若继续就会成功。
- **SQLfmt source 13。**D08 事件 18—21 发现 CREATE TABLE 被当作不透明 DATA，52—57 遇到并处理基于物理行的安全等价检查不匹配，随后检查样例和幂等，事件 78—79 的聚焦套件通过。正式却为 F2P 30/32、P2P 1271/1273，奖励 0；完整审计中一个可见格式差异为 `in (` 与期望 `in(`，其他截断失败不能臆断。局部修复和大量本地通过不等于完整语义或回归覆盖。

教师链显示，最初教师读参考 diff、handler、适配器和测试后形成完整 Hint，再压缩为实际注入的参考；H1 复核指出续接已出现但验证不足，I1 复核提出处理 skill 歧义，I2 初始提示增加“不必因此替换其他提供者”的提醒，之后两次在线检查对应了上面的实际探针。教师的参考比较不是对正式失败根因的证明；提示中要求不归因于参考，也不能作为学生独立发明的证据。

历史 Ofox 使用的是 `deepseek/deepseek-v4.1-flash-1017`，10 次模型尝试为 3 成功、3 失败、4 不完整，另有 2 次模型前基础设施启动；不能与新 Terra 学生作控制比较。历史 batch 12 的新段 53 个已评分中 1 成功、52 正式未解，另有 3 中断和 3 个任务未开始；停止原因是意外原生操作 `mcp_tool_call`，不能把全部结果归因于算法缺陷。

## B. 原工程复用、真实条件与工程修复

实验基于原始 `source_parallel_13`，公开提交为 `c0132d7e381ff660354d7a4403e29ee6107354f9`；37 个比对文件与公开检出逐内容一致，未做下载或哈希验证。结果目录是增量副本：沿用原 SDK、Bridge、评价器、验证过的 VM、外层容器和防火墙隔离，而非另造学生或评分器。原 SDK 内层 `bwrap`/`socat` 可用性限制仍在，不能声称已解决。

实际修改集中在能力文件路径的编排转发、SDK 系统提示追加，以及评价日志保存：`run_cc_sdk.py` 的小修复让 B0 走已有 preset+append 路径并获得**空 reminder**，不向 B0 添加知识，非空知识路径代码保持不变；编排层把 `capability_path` 从误放的 `step_get_hint` 移到真正的 `step_solve`；`eval_deep_swe.py` 仅在容器命令**结束后**另存完整 stdout/stderr，不改评分、测试、命令或环境。元数据投影和清单统计也修正了字段读取：正式 F2P/P2P 原来在顶层，第一次抽取投影只保留 reward、exit、stderr，修复后两组知识重新生成。未手工修补任何学生解答。

全局默认原为不同的 `gpt-6.1-sol/xhigh`，但实际 Bridge 忽略用户配置并显式指定 **`gpt-6.1-terra/low`**。真实入口、服务、Selection/Test 队列和完整 CLI 参数见[实际命令记录](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/commands_used.md)。其基础形式是 `codex exec --ephemeral --json --ignore-user-config --sandbox read-only --model gpt-6.1-terra -c 'model_reasoning_effort="low"'`，并禁用原生 shell、浏览器、插件、原生 skill 等；原 SDK 消息和工具被序列化到新的 CLI 请求，不能宣称与原生 API 的角色和采样设置完全等价。学生每次预算 1,800 秒、8 CPU、128 GiB，单轮；温度等沿 CLI 默认。

**生产转发故障及两次统一复核。**中性 SDK fixture 证明了下游追加机制，却没有覆盖完整编排适配器。真实 Selection K0 初始化时发现 `capability_path` 未到达 `solve_r1`：旧 B0 已正式成功，K0 在任何模型请求前中止；两条均保留，不计入当前核心比较。修复转发后，四组按统一软件重跑。审计教师包也曾以 1,153,690 字符超过 1,048,576 上限，在模型响应前失败；随后仅省去 D05 已完整审计的重复在线事件上下文，四条教师轨迹仍在精简包中，成功完成教师链补充审计。失败请求无用量回报，不能计作零成本的正常回答。

随后实际请求显示，SDK 空追加与非空追加路径的身份句不同：旧 B0 为“a Claude agent”，知识组为“Claude Code … running within the Claude Agent SDK”。因此旧 `capability_v1` 四组 Selection 及对应审计、分数均保留为**被取代的输入条件证据**；四组按预存顺序再次以 `capability_v1_matched_prompt` 复核，而不是只重跑某个成绩。最早启动的 TOML K1 和 HTTPX K2 用的仍是未改动的非空路径，予以保留。实际首请求逐文本比较表明，三个任务各组在精确移除知识文本后，公共系统文本、工具定义和非系统消息均与 B0 相同；见[条件核验](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/results/model_condition_validation.json)。中性 fixture 的计费头版本后缀与历史生产不同，故不宣称 fixture 全字节相同；实际主组比较包含生产计费头。匹配首请求不代表随机生成轨迹相同。

**K2 Selection 评价异常。**原结果保留奖励 0、F2P 0/80、P2P 80/116，但 `new-ctrf.json` 缺失，报告没有完整列出测试，不能说 80 项断言执行后失败。首次诊断启动器因归档后找不到顶层补丁而未运行评价，约 0.206 秒；随后仅一次实际诊断以直接内容相同的 13,143 字节补丁、相同环境重新评价，首份完整报告为 80/80、116/116，奖励 1。不是多次试验择优，没有学生重试、代码或知识改进。原始输出仅留 8,000 字符尾部，根因未知，Node/JIT 并非已证实原因。诊断评价约 89.220 秒；恢复后的 1,476.782 秒墙钟包含排查和恢复，不是技能效率效应，也不能再把诊断时间重复相加。[异常及恢复审计](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/audit/evaluation_diagnostic_selection_K2.md)与原始结果均保留。

## C. 知识构造、对照与冻结

B0 不加载能力；K0 只用开发任务描述和教师自身一般先验，不读取学生轨迹、实现或测试；K1 对相同原始轨迹按时间线蒸馏；K2 先区分**推断子目标**与**实际观察状态**，再按功能目标或测试类别对齐，最后生成库。K2 没有额外 GT、隐藏测试或额外学生尝试。

K1/K2 均使用 D01—D08 的同一机械过滤输入、相同 615,929 字符原始来源、相同模型与每组两次生成调用；单次上限在看到分数前设为 700,000 字符。逐字符串、工具输入和补丁均有固定截断，因此并非每个源文件的所有细节都进入模型。元数据修复前 K1/K2 各两次调用及原始输出保留为额外成本，修复后各再两次；不是根据 Selection 或 Test 分数重写。统一交付规则在任何 Selection 分数及知识组尝试前确定：保留生成顺序中的前四个完整能力单元，不改写。最终 K0/K1/K2 分别为 **644/578/526 词**；K2 原始候选 810 词被截为 526，因此没有更长 K2 的交付优势，但内容和长度仍不相等，不能把差异解释为纯粹的表格组织效应。

每个条件只有一个 V1 候选。预定规则仅在泄露答案、未注入、格式无效或有明确因果证据的退化时淘汰；库审查未发现泄露或格式问题，旧 Selection 的单次差异不足以证明由库导致退化，故均保留。知识在较早 Selection 后、任何 Test 前于 19:37:13 UTC 冻结；后来的匹配复核和 Test 反馈均未更新它们。没有 V2、递归更新或权重训练。所有原始候选、修复前版本、中间分析和冻结副本保留。

## D. 正式结果、额外启动与成本

正式成功是评价器的完整二元标准；F2P 是新需求测试的辅助指标，P2P 是所测已有行为保持情况，二者都不等于全部可能行为。缺报告和模型前技术中止不应作为普通算法失败。Selection 是开发选择证据，Test 是冻结后的独立任务结果，不能合并成同一成功率。

<<CORE_RESULTS_TABLE>>

<<EXTRA_RESULTS_TABLE>>

匹配 Selection 中 B0、K1 和恢复评价后的 K2 正式通过，K0 的一个 `classFilter` 与 cause 消毒交互未通过；旧 Selection 与新复核结果不同本身提醒我们，单次生成波动和输入修复都会影响观察。Test 的两题每组仅一次：K0 为 2/2，K2 为 1/2，B0 与 K1 为 0/2。这些描述不构成显著性检验，也不证明 K0 或 K2 的知识导致结果。HTTPX 每组 P2P 另有三项跳过，有限通过并非完整兼容性证明。

核心表逐行给出真实工具请求及返回、模型请求、输入、输出、缓存子集和墙钟／SDK 时间；缓存已包含在输入内，不可再相加。例如 TOML K2 为 61 次工具返回、34 次模型请求、2,315,718 输入、9,295 输出、其中 549,632 缓存输入，墙钟 1,088.810 秒；HTTPX K2 为 24 次工具返回、17 次模型请求、1,047,020 输入、5,872 输出、其中 306,432 缓存输入，墙钟 1,653.912 秒。它们是实际单次成本，不是稳定效率差。各评估诊断是仅评价成本，首次无补丁启动甚至未执行评价；两者均不是新学生尝试。

知识生成成本也不能忽略：修复前 K1 和 K2 各两次调用，分别记录输入 188,824 和 189,425 token；修复后各两次，分别 189,020 和 189,788。K0 两次输入 7,320。上述均有输出和各自缓存子集；完整分类账见索引。SDK 报告美元是代理估计，真实结算 CLI 美元未知，不能与 CLI token 账重复相加。部分 SDK 与尝试指标的缓存字段不一致，应保留各自口径而非强行调和。

### 条件性 Hint 探索

<<OPTIONAL_HINT_RESULTS>>

该探索若有结果，也只是开发任务上的即时观察：各变体从相同初始代码、独立新会话开始，并非恢复到共同中间状态的严格反事实重放；没有独立 Hint 迁移测试，不应声称 Hint 迁移收益。主 Test 冻结库不从该探索更新。

## E. 行为、采纳、修复与迁移边界

**先证明输入，再看行为，再限制归因。**实际首请求和 `loaded_capabilities.md` 证明 K0/K1/K2 的文本进入学生请求；它们不证明学生依赖该文本。匹配 Selection 的 K1 在事件 13—15 先做失败复现，27—29 检查边界往返；K2 在 42—44、62—65 检查序列化、反序列化和嵌套 Map。这与各自规则一致，但 B0 的事件 19—22 也在无库条件下做了失败 frames 复现。Test 中 TOML B0 检查了点分键及往返，HTTPX B0 检查请求和重定向路径；因此“观察到检查”不能自动升级为“知识造成检查”。历史 D05 两次在线教师指令后紧接的针对性探针，是较强的同次采纳证据，但仍无隔离教师效应的对照。

K2 不只是把 K1 排成更漂亮的表。K2 明确提出安全等价比较应针对**有意义的表示单元**，物理布局可能过严或过松，而且不能为一类表示关闭其他类别的安全检查；K1 有语义保持、幂等和安全验证，但没有同样明确的比较粒度与范围限定。K2 还明确区分新输入和续接状态。这是实质性的可迁移限定，不等于全新研究概念，也未证明本次 Test 因此成功。两库都覆盖边界追踪、下游输入和转换验证，文字、长度与内容差异共同混杂。

修复与失败应按真实轨迹解释。TOML K2 在事件 66—72、80—88、97—119 修正空表、注释和嵌套转换等中间问题，却仍在正式测试输出 `server .host`，语义往返不能代替精确格式契约。K0 同样经历局部语法和注释修复后通过两套正式测试；这不是证明它的库必然更好。HTTPX K2 事件 23—28 本地发现并修正导出顺序，正式通过；B0 和 K1 的同一导出顺序 P2P 失败，恰好反对把 K1 失败简单归因于其知识。若测试输出只给出部分尾部，不应发明隐藏测试诊断。

开销也有正反两面：重复套件和定制探针消耗时间，却常发现实际问题；HTTPX K2 重复确认缺失符号、K1 的宽泛搜索进入 `/proc` 是可观察的额外工作，但没有证据说明它们由库造成。Selection 多组本地性能阈值失败，没有可比的修改前计时，不能宣称补丁导致性能回归。没有源轨迹消融，混合池也不支持给 D01—D08 各自的学习价值或边际迁移贡献排名。

## F. Scene 证据链与可迁移方案

Scene 的证据范围不同于代码实验：初始审计 136 个唯一文本文件，补充四个完整文本后共 **140 个，132 个全文、8 个仅前缀**；另有两个旧二进制 checkpoint 只读探测。六个原始轨迹 JSONL 均只审前缀，另审 25 个完整阶段事件日志、21 个增量补丁、10 个构建文件；三个有限视觉案例涉及六张渲染图和两张不同参考照片。T01 与 E02 的参考是同一历史厨房，不能当作两个独立场景。27 个 bundle 仅索引，未深审内容；输出和公开归档可能是复制件，文件数不是独立尝试数。

**识别—诊断—更新—采纳链。**历史 D01 第 4 阶段，教师指出显示器背板与浅色背景难以区分，希望改变对比和方向并让支架坐在桌面，同时承认无法区分洗白与遮挡。实际视觉修订补丁修改背板材质并旋转面板和边框；阶段记录和保存状态支持这些操作确实发生。教师随后报告面板更清楚但支撑仍难辨，状态只是 `advance_with_issue`，不是质量验收。第 5 阶段相机及天花板调整后，教师又报告椅子裁切、植物遮住暖气等新问题；一次修订可改善局部而带来其他退化。

[SG01 只读几何补充](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/audit/audit_SG01.md)用原 Blender 4.2.10、单线程、无 GPU、无渲染加载两个已有保存状态，不保存原文件。每个状态记录 874 个对象，选取 48 个语义相关网格及 1,128 对 AABB 下界。面板材质与包围盒改变，支架直立件和底座包围盒不变，相机也不变；这支持执行事实，不证明桌面接触、物体连接或视觉质量。正的 AABB 距离下界只说明该对包围盒分离；零下界既不证明接触也不证明正确。不同部件分离或不同建模实现也不自动是错误。

其他历史链中，H04 在既定 Selection 规则下被保留，后续两个学生构建实际执行了地标投影及相机试探；数值投影支持特定点的屏幕位置，不证明可见轮廓或照片匹配。M07 的只读材质诊断被执行和复用，H08 则按既定规则被拒绝；诊断工具复用不是学生质量改善。M0/M1 的厨房记录有不同既往提示和结果，不能将最终图差异归因于 M1。尤其，相机位置或焦距变化可以合法改变投影大小，而几何尺寸完全不变；不能把未缩放几何误称为实现错误。

**可行的迁移表达，而非已完成试验：**把程序行为映射为三维语义状态及其前后变化；把行为约束映射为几何、支撑、遮挡和对象关系；把单元测试映射为几何检查与渲染检查的组合；把跨任务对齐改为跨对象、跨场景功能对齐。每条规则应区分图像观察、三维诊断假设、实际补丁和独立验证，保留相机—几何—材质—光照的混杂。这里没有实施新的 Scene 重建、学习、质量迁移试验或审美教师；代码任务成绩不是这些库能改善 Scene 的证据。

## G. 文献重叠与贡献边界

本次实际打开的是以下论文**摘要页**，并非全文系统综述。多轨迹归纳和可复用技能已有 [Trace2Skill](https://arxiv.org/abs/2603.25158)；学生失败与教师轨迹对照、用重跑验证技能已有 [SKILL-KD](https://arxiv.org/abs/2607.28048)，修复与退化的实证评估已有 [SkillGen](https://arxiv.org/abs/2605.10999)。因此，多轨迹总结和技能验证都不是本工作的首创。

教师指导与新会话练习复用见 [Socratic Skill Learning](https://arxiv.org/abs/2610.17860)，面向学生的诊断及匹配开发集准入见 [Teaching the Harness](https://arxiv.org/abs/2611.13144)。本例 D05 的具体贡献只是可追溯地显示提示后的请求检查和反馈检查，不是证明教师指导本身新颖。调试假说需要有针对性的干预、且同一失败可能有不同修复，与 [DoVer](https://arxiv.org/abs/2512.06749) 的摘要范围重叠；本报告没有把事后相似性当作干预验证。自然语言反思和测试更新也与 [GEPA](https://arxiv.org/abs/2507.19457) 重叠。

在三维方面，[SceneEvolve](https://arxiv.org/abs/2610.37046) 摘要涉及固定模型、动作和后端下的可执行 3D 代码及教师驱动 harness 演化；[SimWorld Studio](https://arxiv.org/abs/2605.09423) 摘要涉及验证反馈支持的 3D 环境代码工具、技能与课程演化。冻结模型自我改进、教师引导或 harness 验证均不应宣称为新颖。最审慎的定位是：本研究在极小、单次的条件下，为**显式状态对齐、尽量独立于实现的知识表述**提供了有限探索性证据；K2 有可指出的实质限定，但其独立效果、效率和 Scene 迁移均未被证明。

## 交付物索引

以下均为结果根目录下的绝对路径；原始英文材料保持原样。

1. [协议与任务划分](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/config/protocol.json)；[任务划分及接触检查](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/config/task_split.json)。所谓未见仅限可访问的已记录历史，不能排除账户范围未记录接触。
2. [历史清单摘要](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/audit/inventory_summary.json)、[教师链补充](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/audit/audit_teacher_chain_reduced.md)、[D05](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/audit/audit_D05.md)、[D06](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/audit/audit_D06.md)、[D08](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/audit/audit_D08.md)。
3. [冻结记录](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/config/knowledge_freeze.json)、[交付规则](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/config/library_delivery.json)、[K1 冻结库](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/knowledge/frozen_v1/K1_v1.md)、[K2 冻结库](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/knowledge/frozen_v1/K2_v1.md)。
4. [匹配 Selection 汇总](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/audit/pooled_selection_matched.md)、[Test 汇总](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/audit/pooled_test.md)、[条件核验](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/results/model_condition_validation.json)、[评价异常记录](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/config/evaluation_triage.json)。注意个别单案审计写作时没有其他组或恢复报告；以汇总和恢复补充纠正其局部结论。
5. [Scene 清单](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/audit/scene_inventory_summary.json)、[SG01 审计](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/audit/audit_SG01.md)、[几何探测执行记录](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/evidence/scene_geometry/execution_records.json)。
6. [成本分类快照](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/results/cost_breakdown_summary.json)、[资源采样快照](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/results/resource_summary.json)和[实际命令](file:///srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/commands_used.md)。这些快照不是报告调用之后的最终总额；采样也可能漏掉短峰值。

## 最终核算与清理

账目范围是本实验启动的 CLI 调用及旧证据的新审计；历史原始求解成本另列，本监测聊天自身的编排用量在 spawned-CLI 账本之外。未知用量不按零填充；SDK 美元估算不等于实际结算。窗口结束后的最终总额、剩余进程及清理状态以以下追加证据为准：

<<FINAL_ACCOUNTING>>
