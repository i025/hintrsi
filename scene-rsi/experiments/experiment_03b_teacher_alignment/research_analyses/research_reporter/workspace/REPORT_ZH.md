# Scene RSI 实验 03-B：感知批评基线的冻结比较

## 摘要与结论边界

本报告是**自动化研究分析，不是人工评分**。实际完成 12 个开发案例、3 个旧参考场景，以及 4 个独立案例、2 个新参考场景；每个案例各有一次 T0 和一次 T1 冻结判断，共 32 次正式批评会话。没有收到真实人类标签。T0 已能自主提出位置、朝向、比例和材质等与用户暂定原则同类的问题；但这不证明它在任何具体案例上与人一致。T1 加入原则后，一些优先级、类别、严重度和分数发生变化，也有不变、反向及描述冲突的情况。没有证据表明 T1 更符合人类，或自动分数较高意味着重建有所改善。

本报告只比较已保存的模型判断，不把其文字转化为新的像素真值。对应原始记录见[配对预测](analysis/paired_predictions.json)、[统计摘要](analysis/prediction_summary.json)及每例冻结预测；分析结构化结果见 [teacher_comparison.json](teacher_comparison.json)。

## 设计与场景划分

T0 是通用、独立的 RGB 重建保真批评者。T1 在同一基础指令和 JSON 规范上，只增加用户对少量已观察例子的暂定原则：相对位置、朝向、空间关系／比例和材质／纹理往往比极小支撑间隙更重要。这不是正式人类评分、普遍权重或对齐训练所得教师。每个批评者是新 SDK 会话，只收到真实参考图和一个真实候选图，没有 GT、代码、先前分数、教师意见、来源组别或其他候选；其 JSON 是估计，不是视觉真值。[协议](PROTOCOL.md)

开发集：S01 的 D001、D002、D007、D011；S02 的 D006、D008、D009、D012；S03 的 D003、D004、D005、D010。旧场景用户已经看过，仅供开发。独立集：新教室 B-T01 的 I001、I003；新会议室 B-T02 的 I002、I004，各两次 Base 重建；参考与 03-A 测试不重叠。独立 Base 不含学习所得能力库、教师提示或 hint。同一参考的版本相关，不能把 16 个案例当作 16 个独立场景。新参考来自 IDEAL-Scenes，CC-BY-4.0；准备阶段曾打开完整 GT 场景并 CPU 重渲染验证来源、无缺失外部图像，但进入学生和感知批评者工作区的只有匿名颜色图，而非 GT、标注或相机。[工程记录](ENGINEERING_LOG.md)

![开发集参考与重建图集](analysis/development_gallery.png)

![独立集参考与重建图集](analysis/independent_gallery.png)

## T0 已能发现什么

T0 不需要 T1 的原则即可命名其强调的宽泛缺陷类别。例如 [D001 T0](predictions/D001-T0.json) 的 `main_defects` 将门的 `relative_proportion` 排第 2、地面等的 `material_texture` 排第 3；[D007 T0](predictions/D007-T0.json) 把门的 `orientation` 排第 1；[I001 T0](predictions/I001-T0.json) 将桌椅的 `relative_position_layout` 排第 3。它还报告构图、几何部件、物体可见性及光照，而不是只检查支撑缝隙。

但「命名同类」不等于发现正确，更不等于知道人对具体案例的判断。[D002 T0](predictions/D002-T0.json) 第 2 项说门在图中不可辨，同时承认可能被遮挡或侧视；[D009 T0](predictions/D009-T0.json) 对窄门及右侧结构给出具体描述，也承认相机、裁切和物体身份不确定。[I003 T0](predictions/I003-T0.json) 将远处外部剖视与室内视角之别列为第 1 项。以上是记录中的模型陈述，不能直接断言物体缺失或实际 3D 尺寸错误。

## T1 实际改变了什么

汇总中，开发集 `overall_fidelity_estimate` 均值 T0 64.0、T1 64.17；独立集分别 52.25、52.5。开发集第 1 类别改变 1/12，独立集 1/4。开发集前三项的类别计数中，`geometry_parts_connections` 从 3 到 7，`material_texture` 从 12 到 10，`lighting_shadow` 从 5 到 0，`orientation` 从 1 到 3。这些是输出类别计数，不是学习到的权重；一次／条件也不能排除会话随机性。[统计](analysis/prediction_summary.json)

- [D006 T0](predictions/D006-T0.json) 与 [T1](predictions/D006-T1.json)：柜子 `geometry_parts_connections` 第 4 升至第 2，`material_texture` 第 2 降至第 4，T1 的 `relative_proportion` 第 3；分数 66→65。原则并非简单地让材质始终上升。
- [D008 T0](predictions/D008-T0.json) 与 [T1](predictions/D008-T1.json)：T0 的 `lighting_shadow` 第 2，T1 降至第 5，并把门的 `orientation` 放第 2。两者第 1 项都为构图，却分别描述床在画面中占更多位置和更小；这是需要人工核对的**实际冲突**，不能以其中一个模型解决。
- [D007 T0](predictions/D007-T0.json) 第 1 项为门朝向，[T1](predictions/D007-T1.json) 第 1 项为构图，其前五项不再单列原先门朝向诊断。分数 66→65；原则并未保证提高每一种朝向问题的优先级。
- [D009 T0](predictions/D009-T0.json) 与 [T1](predictions/D009-T1.json) 都为 55、都将构图列第 1、窄门列第 2、材质列第 3，但门由 `geometry_parts_connections` 改标为 `orientation`。分数不变不代表诊断完全不变。
- [I002 T0](predictions/I002-T0.json) 和 [T1](predictions/I002-T1.json) 五项类别顺序完全相同，分数却 55→57；[I004 T0](predictions/I004-T0.json) 和 [T1](predictions/I004-T1.json) 则把构图与未见门的前两项互换，64→62。两者都承认门可能在视野外。
- [I003 T0](predictions/I003-T0.json) 与 [T1](predictions/I003-T1.json) 同列构图、材质为前两项，但第 3 项从光照变为比例，42→43；[D012 T0](predictions/D012-T0.json) 第 2 项关注右侧家具，[T1](predictions/D012-T1.json) 第 3 项关注柜子，且右侧被裁切家具的身份不确定。

开发集逐例 T0→T1：D001 66→66、D002 55→57、D003 65→65、D004 64→66、D005 64→62、D006 66→65、D007 66→65、D008 67→66、D009 55→55、D010 65→68、D011 67→65、D012 68→70。独立集 I001 48→48、I002 55→57、I003 42→43、I004 64→62。数字只是对同一图像对的自动判断，不代表发生了重建变化。

## 运行、审计和工程中断

所有实际研究模型会话使用 Claude Agent SDK 0.2.186 → 既有 Codex CLI Bridge 0.163.0 → `gpt-6.1-terra`，`low`；CLI 内部多智能体关闭，SDK 执行 Read/Write。每个批评会话上限 300 秒、24 次 Bridge 请求，单 worker，CPU 48–55，端口 19265、nice 15、既有每进程 32 GiB 限制；批评者不需要 Blender 或 GPU。固定随机种子 2026112803，案例顺序洗牌、T0/T1 顺序交替。Python 3.12.16，shared_v2；自动记忆关闭、skills 与 MCP 为空，SDK 自动压缩窗口 400000、目录上下文 500000。离线分析使用已有环境 Pillow 11.3.0、numpy 1.26.0、scipy 1.11.4；Blender 5.2.2 LTS。未安装新包或改变环境。[运行版本](runtime_versions.json)、[协议](PROTOCOL.md)

复用 Experiment02 独立 SDK 视觉复核机制；本实验修改编排、选择、感知提示、单 worker 调度与冻结位置，不创建新的 Agent 执行循环。技术诊断和探索接口复用 Experiment02 的提示／JSON 形式并泛化目标选择。[来源索引](source_origin.json)、[模块接口](configs/module_interfaces.json)、[同步清单](sync_manifest.json)

先前整个 `/harness` 挂载意外暴露了研究编排源，其中包括 T1 原则与选择理由；旧工具事件未观察到对其读取，但可见性违反盲评隔离。修复前保留 5 个完成和 1 个中断会话及其费用；将挂载统一收窄为 `sdk_student.py` 和 `socket_tunnel.py`，真实 SDK Read 负向检查后，以不变图片、提示和预算整体重启全部 24 个开发会话，并非按结果挑选。中断终端使原 supervisor 未走 finally；进程命名空间退出、端口关闭后控制器移除了唯一残留复制凭据，后续增加 STOP 文件及正常清理。详见[隔离修复记录](pre_runtime_isolation_fix/README.md)和[工程日志](ENGINEERING_LOG.md)。

正式 32 次批评均完成、每次 2 次请求；开发 24 次在独立 Base 生成前完成并冻结，之后扩展冻结未改旧输出。请求审计记录真实图像附件：每个批评会话最初两张，参考以 JPEG、候选以 PNG 传输；学生最初一张参考图，B-T02-R2 后续还有工具返回图像。审计覆盖显式请求文本及已观察工具事件，不是形式化安全证明或后端权重证明。[请求审计](analysis/request_audit.json)

独立学生 B-T02-R1 两次请求出现 `workspace routing discovery failed`，均有保留，最终会话完成；14 次学生请求只有 12 条 usage 记录，不能把未知费用视作零。SDK 环境缺 Pillow/scipy，离线分析改用已有环境，未改变学生或批评运行环境。无证据表明这些中断被按结果重采样。[使用记录](analysis/usage_summary.json)、[工程日志](ENGINEERING_LOG.md)

## 独立 Base 技术完成与资源成本

[技术复现](analysis/base_reproduction.json)显示四个 Base 会话完成；四个原始场景均成功打开，从仅源代码、无外部能力库、无 GT、无控制器修复的条件重新生成 `.blend` 与 640×360 渲染，退出码均为 0、无超时或 Python traceback，未见缺失外部图像。四张再生成图与对应交付图 RGB/RGBA 像素一致；这只证明交付复现一致性，不证明与参考的语义保真或 3D 正确性。未进行语义 GT 匹配，3D 对齐误差为空；AABB 重叠只是候选，不能当作实际碰撞。四次技术检查总墙钟时间分别约 10.41、9.77、6.99、8.74 秒。

提供的[使用账本](analysis/usage_summary.json)生成于本报告会话之前，**不含本报告会话**；控制器之后会追加其最终数字账本。已知正式批评 32 会话、64 请求、396889 输入及 47395 输出 token，累计会话 1847.54 秒；学生 4 会话、14 请求、110307 输入及 11556 输出 token，497.42 秒，另有 2 次请求无 usage；隔离修复前 6 会话、12 请求、72843 输入及 9326 输出 token，383.28 秒。全部已知输入 580039、输出 68277，合计 648316；缓存输入 0、推理输出 1511，分别是输入和输出的子集，不应重复相加。首次至末次会话墙钟 2816.23 秒；已知子进程用户 CPU 335.41 秒、系统 CPU 64.50 秒，最大采样进程树 RSS 和 1197.22 MiB（共享页可能重复计数）。美元计费未知，不能由订阅 token 推算；Ofox 调用为 0。

## 人工表单与未来对齐

真实评审者可离线打开[开发表单](human_review/development/index.html)和[独立表单](human_review/independent/index.html)，依据图像独立填写 0–100 粗分、最多三个按优先级排列的视觉缺陷、可选严重度／文字及同参考两两偏好，分别导出 JSON。表单隐藏实验组、教师分数、GT、自动指标和预期结果，并在浏览器本地自动保存。先完成独立判断再与冻结预测比较，尤其核对 D008 床的描述冲突、D007 门与构图优先级、I004 门是否仅在视野外以及 I003 比例与光照。不要用模型代填，当前所有人工字段为空。

收到真实导出后可用 `analysis/human_teacher_alignment.py import --input /absolute/path/to/export.json` 导入；后续 `prepare-followup` 仅用于开发数据。T2 需要真实开发标注，T3 需要实际人机分歧及单独的未来选择划分；两者均仅为接口、尚未运行。独立场景标签不得用于教师调整；先冻结新教师再用独立集评价，并按场景和评审者报告分歧及不确定性。单一评审者只能支持与该评审者的对齐，不能推断普遍人类偏好。

当前实际运行的仅是 RGB 感知批评 T0/T1。Technical Diagnostician 和 Exploration Teacher 都只是接口：将来前者可在无 GT 或明确授权的开发期只读 GT 模式检查代码、状态和轨迹，后者可基于有证据的诊断生成探索指导；技术诊断的 GT 辅助不同于 RGB-only 人类对齐。本批没有在线指导、能力习得或对齐训练。[接口](configs/module_interfaces.json)

## 主要限制

样本少且同场景版本相关，旧场景非独立；独立集仅两个场景。每个条件仅一次会话，无法量化重复性或将所有变化可靠归因于原则。相机、裁切、遮挡、曝光和材质混杂，模型描述可能相互冲突，隐藏几何无法凭单视图验证。学生、批评者和本分析使用同一基础模型，可能存在相关偏差；模型分数、模型间一致及像素复现均不能替代真实人类标注，也不能证明 3D 正确。
