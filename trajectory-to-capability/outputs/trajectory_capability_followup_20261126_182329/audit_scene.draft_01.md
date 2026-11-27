# audit_scene.md｜Scene 证据审计报告

## 一、覆盖率、重复、未审范围与视觉采样

**本报告仅呈现既有审计，不更新能力库、学生或实验，也不新建 Blender 场景或宣称 Scene 有效。**以下覆盖率是清单所定义范围内的文件覆盖，不是服务器全部实验的覆盖率，也不是独立试验数。

| 范围 | 已记录覆盖 | 必须保留的边界 |
|---|---|---|
| 主轨迹 | `scene_full_audit_manifest.json` 记录 **360/360 个规范轨迹文件、571 个分块完成**，全文解码、无前缀截断 | 仅指该清单；文件不等于独立实验。较早的执行汇总称“仍在运行”，已被后来的完成清单在覆盖状态上更新，不能沿用其旧状态 |
| 工作档案轨迹 | 454 条路径：410 为原导出路径／账号脱敏后的副本，32 为解码文本完全副本，12 为额外不同内容；后者 **12/12 文件、12 分块完成** | 不是 360＋454＝814 次独立实验；比较未使用哈希。12 个额外内容的任务提示与参考图并非都存在 |
| 归档、执行与阶段记录 | 27 个 tar 包、13,085 个成员已索引；27 个归档控制审计分块完成。执行映射覆盖 1,483 个不同文件、1,644 条归档链接、161 条轨迹链接，未映射成员为零；73 个执行分块完成。另有 526 个选定控制文件及 722 个阶段／调用文件按完整文本分块审阅 | 161 个 tar 轨迹成员映射到已审轨迹，不应重复计试验。包中只有明确选定的控制、代码及验收记录全文审阅；**并非所有成员载荷均深审**。阶段／调用范围排除无关 grid-domain RSI 调用；部分其他原始 API sidecar 未逐项重读 |
| 新增视觉样本 | 6 案例 VX01–VX06、6 个参考任务 ID、18 个图像文件引用：6 参考、12 渲染引用；样本内实际为 **6 份不同参考文件内容、8 份不同渲染文件内容** | VX01、VX02、VX03、VX06 的首图和交付图内容相同；VX04、VX05 不同。`final.png` 可为选中步骤副本。任务 ID 不证明照片在全局唯一；另有旧有限视觉审计，**不是总渲染全审** |
| 几何 | 两个旧几何检查点涉及 874 个对象／48 个 mesh，属于所检查子集 | 不是全库统计；AABB 相邻、重叠或距离为零都不是表面接触、支撑或拓扑连通证明 |

清单与范围数字来自用户提供的 `scene_full_audit_manifest.json`、`scene_additional_full_audit_manifest.json`、`scene_bundle_audit_manifest.json`、`scene_execution_audit_manifest.json`、`scene_stage_event_audit_manifest.json`、`scene_work_archive_summary.json` 和 `scene_visual_expansion_manifest.json`；本次输入未给出这些清单的绝对路径，故不虚构路径或行号。原文件仍是权威来源。

**尚未逐项深审：**未选中的 tar 成员载荷、部分原始 API sidecar 和调用内容、全量参考及渲染像素、全部 `.blend` 二进制及精确网格关系；已索引、映射或档案保留不等于独立验证。未做新重建、新渲染、GPU 作业或独立 Scene 迁移实验。

## 二、判读与引用约定

- **直接观察**：原事件记载的代码、异常、执行、保存和选择；视觉观察仅指已有有限图像审阅。
- **语义推断**：由代码名称、组成和坐标推测场景或部件角色；不等于核实原始照片或目标。
- **待验证假设**：学生或教师报告的视觉缺陷、原因及预期改善，除非另有独立证据支持。
- **技术中断**：CLI 退出、服务暂停或超时；不能自动归因于几何算法、权限或空补丁。

下表中路径前缀均为**原始文件绝对路径**，相对后缀与行号组合后可直接复查；行号是原 JSONL 行，不是审计报告行。缺失原始事件号的材料只引用已给出的字段或行，不补造编号。

## 三、按版本与队列审查代表案例

### 1. Pilot、消融、外部和 replay

原始路径前缀 **P**：`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_pilot/`。

| 来源、路径及原行 | 实际目标、执行与结果 | 反馈、接受和未知 |
|---|---|---|
| **S0089** `P + results/external/scene_rsi_pilot/selected/external/bw_0005/trajectory.jsonl`，1、3–5、8–14、18–19、24–25 | 目标是由单图构建可编辑教室；三次非空 Blender 构建／渲染成功，学生两次改相机并选第 3 步。 | 学生判断窗和岛台过小、随后又裁切；是学生诊断而非教师发现。相机改动已执行，像素保真和改善未独立验证。 |
| **S0090** `P + results/external/fixed_h0/selected/external/bw_0005/trajectory.jsonl`，3–20 | 首次因 World 为 `None` 失败；学生收到 traceback 后加入条件创建，后续两次执行成功，也改了房间、材质、灯光及家具，最后 `DONE`。 | 错误及后续可执行有支持；各视觉改动效果未知。请求 64 样本而日志报 16，不能把代码意图当作实际渲染设置。 |
| **S0098、S0099** `P + results/external_followup/{scene_rsi_pilot,fixed_h0}/selected/external_followup/bw_0011/trajectory.jsonl`，各 3–18 | 洁净实验室目标。S0098 两次构建、保存、渲染成功，第二次改世界及光照，之后约 600 秒审阅超时；S0099 圆角越界、随后超时、再遇空对象数据，最终 guard 未执行。 | 前者是完成两步后中断，后者无成功图；学生对浅色表面及性能的解释未证实。不能把未执行修复当成功。 |
| **S0087、S0078** `P + results/ablation_r1/generic_same_structured_evidence/C1/development/commons_109923183/trajectory.jsonl`，5–6、11–18；`P + results/ablation_r1/ours_without_regression_guidance/C1/selection/commons_133800864/trajectory.jsonl`，17–22 | S0087 前两步渲染后第 3 步超时，保留第 2 步；S0078 第 3 步成功后最终明确选第 2 步。 | 反例：最新代码不一定被选；回退是流程进展，不是已证实的部分视觉正确。 |
| **S0095** `P + results/replay_s1_r1/M_descendant/C1/replay_selection/commons_29206714/trajectory.jsonl`，10–12、17–19、24–25 | 三步均渲染，结合相机、轮子和壁炉修改，最终选第 2 步。 | 比较提示来自 runner；未见独立教师建议或独立质量评定。 |

在这些学生轨迹中，未见可归属于独立教师的发现、诊断、更新、接收或采纳；这不证明别处不存在教师记录。runner 提示和 traceback 不能改称教师指导。

### 2. v2、v2.1、v2.2 与 v2.4

原始路径前缀 **O**：`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/`。

| 来源、原路径及行 | 执行与边界 |
|---|---|
| **S0027** `O + scene_rsi_v2/results/r2/fixed_h0/H0/development/commons_129095630/trajectory.jsonl`，3–19 | 初始空 World、第二次超时，第三份简化代码渲染并选中；多个改动同时发生，超时原因未知。最终 `DONE` 不证明图像匹配。 |
| **S0033** `O + scene_rsi_v2/results/r1/fixed_h0/H0/selection/commons_138884680/trajectory.jsonl`，3–18 | 圆角失败、超时、对象数据失败；最后的后代搜索修订无剩余执行次数。没有成功渲染，不能宣称最终修复有效。 |
| **S0225、S0231** `O + scene_rsi_v2_1/results/r1/scene_rsi_v2_1/C2/test/commons_80372956/trajectory.jsonl`，3–15；`O + scene_rsi_v2_1/results/r1/fixed_h0/H0/test/commons_80372956/trajectory.jsonl`，3–5 | 同一参考 ID 的不同记录：前者按学生对吊灯方向、构图和黄铜外观的判断修改，两次渲染后选第二步；后者非空程序执行超时、无图。结果不同不证明条件因果优势。 |
| **S0002、S0008** `O + scene_rsi_v2_2/results/r2/fixed_h/H0/fixed_version_test/commons_31294395/trajectory.jsonl`，3–13；`O + scene_rsi_v2_2/results/r2/fixed_h/r1_C2/fixed_version_test/commons_31294395/trajectory.jsonl`，5–15 | 同 ID 的卧室解释：S0002 圆角错误后推进到空 World，最终建议未运行；S0008 两次渲染，学生改床、家具、材质、光照和相机，选第二步。前者为局部执行进展，后者为技术完成；均非独立视觉成功。 |
| **S0025** `O + scene_rsi_v2_2/results/smoke/fixed_h/r1_C2/smoke/old_dev_excluded_smoke/trajectory.jsonl`，1、3–14 | 单图分离网格目标；`scene.bind` 拒绝不属于场景的端点，学生将字符串改为节点 `plant, table`，重跑成功并选中。 | 支持该次 API 错误修复，不证明植物与桌面真实接触。 |
| **S0273** `O + scene_rsi_v2_4/results/task02/active/C1/selection/commons_92056365/trajectory.jsonl`，5–11 | 吊灯绳 `rod` 位置参数错误，学生收到 traceback 后改关键字参数，重跑渲染并选中。首次无图，因此不是视觉指导修订；外观未知。 |
| **S0274** `O + scene_rsi_v2_4/results/smoke/active/C1/selection/commons_104864364/trajectory.jsonl`，3–15 | 学生的教室解释包含 22 组桌椅、包、舞台、板和风扇；两次渲染，学生报告地板材质名称选择失败，并同时改相机、位置、材质与光照。第二步选中，最后 `DONE`。 | 选择问题是学生诊断；修改实际执行，但命中与改善未独立验证。 |

v2.4 的失败汇编含 21 个轨迹文件，记录的是前述版本失败来源的审计材料，不能自动当作新增独立试验。例如 **S0239** `O + scene_rsi_v2_4/audit_sources/raw_failures/scene_rsi_v2_2/r1/fixed_h/H0/fixed_version_test/commons_104864364/trajectory.jsonl`，3–13：圆角修订后到达空 World，最终代码未运行；这不是部分视觉正确。

### 3. v3 H 队列与准备工作

原始路径前缀 **V**：`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v3/`。

| 来源、原路径及行 | 观察与反例 |
|---|---|
| **S0359** `V + results/H01/selection/bw_0031/1/trajectory.jsonl`，3–13 | 第一版控制室解释完成构建、渲染并选中；审阅请求后服务暂停，无诊断或第二版。成功渲染不意味着一定发生迭代。 |
| **S0279** `V + results/H03/selection/bw_0017/1/trajectory.jsonl`，6–8、10–16、18–27 | 首版因冻结导入契约拒绝 `json`；删除导入后成功渲染，学生再改相机、调色及细节并选第 3 步。一个估计传送带点投影 x＝−0.4319，而估计目标为 0.02。锚点对应本身未独立验证，选中不证明可见或匹配。 |
| **S0349** `V + results/H04/development/commons_109923183/1/trajectory.jsonl`，7–16、18–21、26–27 | 圆角参数失败后收到 runner traceback，改半径并成功渲染；第三步亦成功选中。该修复针对明确异常，不是教师视觉修复证明。 |
| **S0335** `V + results/H04/test/bw_0016/1/trajectory.jsonl`，2–4 | 模型 CLI 约 900 秒超时，未返回完整程序或开始 Blender；原因未知，不能称空补丁或几何失败。 |
| **S0354** `V + results/H06/selection/bw_0045/1/trajectory.jsonl`，3–4、11–19、23–30 | 三次构建和渲染，学生改相机与动物等几何，选第三步。最终估计口鼻误差由 0.418 降至 0.174、臀部由 0.469 降至 0.109；门与墙交点误差分别增大。局部数值改善与回归并存。 |
| **S0310** `V + results/H10/selection/bw_0017/1/trajectory.jsonl`，13–14、19、23–24、29–30 | 三次成功渲染并选第三步；设备位移试验后代码无条件重设所选位移，特定筛选机制未生效，但其他场景修改并非空补丁。最终水平残差改善同时垂直残差略增。 |
| **S0302** `V + results/historical_r1_C2_start/development/commons_105241439/1/trajectory.jsonl`，3–4、13–14、23–24、26、28–30 | 三次成功渲染并选第三步；最终代码将部分桌腿及椅部件置于地面以下，是成功渲染不能替代几何检查的反例。其视觉显著性未知。 |

以上 H 目录是运行标签，不自动证明某个 H 更新被接受或造成质量变化。原始阶段事件亦只证明执行：例如 **SE0243** `V + results/H10/selection/bw_0031/1/steps/001/stage_events.jsonl`，2–13，记录构建和渲染，不是机制更新或验收决定。

### 4. 教师人类试点的额外档案

原始路径前缀 **A**：`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/work/teacher_human_archive/public_package/teacher_self_evolution_human_pilot/tasks/`。

| 来源、路径及原行 | 直接观察与推断 |
|---|---|
| **A0001** `A + E01_M1_R2/trajectory.jsonl`，1、3–5、7–11 | 代码推测为绿色陈设房间；软垫圆角 `.08` 超过尺寸界限，改为 `.05` 后渲染成功并选第二步。原任务提示和参考图缺失；教师路径名不证明教师反馈。 |
| **A0006** `A + E01_M0_R2/trajectory.jsonl`，1、4–5、7–11 | 杆端点重合使构建失败；下一版删除重复路径点，同时改命名和玻璃顶点，之后成功渲染。重复点是合理但未隔离的原因假设。 |
| **A0005** `A + E02_M0_R1/trajectory.jsonl`，1、3–14 | 代码推测为木工室；第二版同时加程序木纹、改柜高、相机与灯光，第二次渲染成功并选中。没有可见教师诊断或图像比较，不能把改动归因于教师或宣称纹理改善。 |
| **A0011** `A + D02_M0_R2/trajectory.jsonl`，1、3–14 | 办公室是代码推断；两次渲染并选第二步，脚本请求 48／64 样本，日志均报 32。原因和视觉影响未知。 |

这 12 份额外内容的角色、原提示和参考图并不齐全。档案名称不是教师消息，也不是学生收到建议的证据。

## 四、教师、Meta-Agent、H/M 与候选接受

必须逐级区分：**教师发现 → 诊断获支持 → 针对性更新 → 学生接收并执行 → 候选接受 → 独立后测**。缺一环不能由下一环反推。

1. **有调用，不等于有更新。** **SE0139**：`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v2_4/metrics/calls.json`，885–924 行，记录完成的 initial-diagnosis 和 `shared_H_patch` 调用，返回模型未知、工具调用为零；这些字段未展示诊断、补丁正文、应用或接受。不能仅凭调用名声称 Meta-Agent 或 H 已有效更新。
2. **有实际学生修改，不等于教师诊断正确。** D01 阶段式教师记录提出植物可见性与显示器支撑问题；对应学生补丁与阶段事件显示实际创建／修改及重渲染。教师自己承认遮挡、画外和过曝等竞争解释。原始位置为 `O + stagewise_teaching_student_selfcheck_pilot/tasks/D01/stages/03/visual_revision_build/patch.py`，6–10、14–24、36–45、63–65 行，以及同目录 `stage_events.jsonl` 的事件 5；阶段 04 的 `review.json` 字段 `stage4_monitor` 和两个保存检查点的几何探针在提供的汇总中未附原始行号。显示器外壳与边框改变，抽样立柱和底座未变；因此“底座已接触桌面”未获支持。
3. **阶段重渲染可追溯，质量仍需分开。** **SE0073** `O + stagewise_teaching_student_selfcheck_pilot/tasks/T01/stages/01/visual_revision_build/stage_events.jsonl`，1–13 行：载入检查点、创建 1 个对象、修改 43 个对象并重渲染。**SE0080** `O + stagewise_teaching_student_selfcheck_pilot/tasks/T01/stages/02/initial_build/stage_events.jsonl`，1–5 行，随后载入该修订检查点。它们证明状态传递，不证明视觉改善。
4. **接受的层级不同。** 既有执行／教师汇总记载：部分 B11、B12 重试前提案为 `proposal_failed`、`M_changed: false`；B18、B19 的 `revalidation: accepted` 是提案复核，不自动等于 Selection 保留；B26 记载 r1 C1 被拒、其后代 M 仍指导 C2，C2 按记录接受，而 r2 选择 H0。H04 记录按资格和冻结 BW 增益规则保留，增益 3.2055（`V + rounds/04/record.json`，`selection`、`reason`）。这些是**既有汇总对字段的转述**；本次输入未提供 B11/B12/B18/B19/B26 对应原始成员绝对路径和事件号，不能补造，也不能把评分、候选接受或档案保留升级为独立几何／视觉验证。

## 五、五类问题的证据矩阵

符号：**见**＝所引记录中可见；**未见**＝该记录未记录，不是证明不存在；**未知**＝未独立验证。教师列与学生自评严格分开。

| 类别与来源 | 教师发现／诊断支持 | 更新是否针对、学生是否执行 | 接受与独立后验 |
|---|---|---|---|
| **多物体**：D01 第 03 阶段，`O + stagewise_teaching_student_selfcheck_pilot/tasks/D01/stages/03/visual_revision_build/patch.py`，6–10、14–24、36–45、63–65 行及 `stage_events.jsonl` 事件 5 | 教师报告前景植物不可见、后方叶冠稀疏；但画外、遮挡与真正缺失未区分，诊断仅部分支持。 | 移动植物父级、生成叶片；代码和事件支持实际修改。 | 教师后称前景可见、后方仍窄，后续又报告遮挡暖气片；该教师文字不是独立全物体清点，隐藏对象未知。 |
| **材质纹理**：**A0005**，`A + E02_M0_R1/trajectory.jsonl`，1、8、10–14；**S0285**，`V + results/historical_r1_C2_start/test/bw_0039/1/trajectory.jsonl`，13–14 | A0005 未见教师发现；S0285 中程序材质被创建但未赋予对象，是“创建即生效”的反例。 | A0005 实际加入噪声／色带并同时改相机和灯光；是否针对真实缺陷未知。 | 两次技术渲染和选择不验证纹理外观；材质、光照作用不可隔离。有限 VX02、VX03 审阅报告材质简化，但与此案例不是同一闭环。 |
| **部件接合**：**S0025**，`O + scene_rsi_v2_2/results/smoke/fixed_h/r1_C2/smoke/old_dev_excluded_smoke/trajectory.jsonl`，3–14；D01 第 04 阶段 `review.json` 的 `stage4_monitor` | S0025 未见教师发现；异常直接支持 bind 端点不合法，不支持物理接触判断。D01 教师发现支架难辨，但不能确定遮挡或过曝。 | S0025 节点修订执行并成功；D01 外壳、边框修改，抽样底座和立柱未动。 | 执行成功不证明接触。D01 AABB 下界变零不是接触或拓扑证明；底座是否坐在桌面未知。 |
| **位置方向**：**S0313**，`V + results/H02/selection/bw_0017/1/trajectory.jsonl`，13–14、23–24、29–30；E02 M1，`O + teacher_self_evolution_human_pilot/tasks/E02_M1_R2/steps/001/build.py`，36–39、144–146 行及 `O + teacher_self_evolution_human_pilot/tasks/E02_M1_R2/build.py`，29–30、113–115 行 | S0313 是学生发现，不是教师；其文字称镜头增大，代码却从 34 改为 32。E02 教师指出岛台方向、遮挡，但不确定唯一原因。 | E02 指导针对角点及遮挡；选中程序执行过，但学生称放大岛台时顶板尺寸仍为 `(2.18, 3.42, .105)`，实际相机／镜头变化。 | 选择第二步和技术成功不证实姿态或角点正确；M0/M1 历史不同，不是仅改变 M 的干净对照，最终质量 verdict 为空。 |
| **相机、光照、渲染**：**S0354**，`V + results/H06/selection/bw_0045/1/trajectory.jsonl`，11–19、23–30；**SE0183**，`V + results/historical_r1_C2_start/test/bw_0005/1/steps/001/stage_events.jsonl`，5–13 | S0354 为学生比较，非教师；多锚点数值有改善也有回归，估计对应未独立验证。 | 相机及几何修订已执行，但同时变化，不能隔离原因。SE0183 记录 CPU、16 样本与输出尺寸，而非质量检查。 | 第三步被选不证明构图、照明或轮廓匹配。VX05 的两幅图可见屋顶遮挡变化，但不能仅凭图像确定原因或教学效果。 |

新增视觉审阅还报告：VX01 工作台和工具群比参考稀疏；VX06 控制台简化，部分参考文字、图表和后方设备未清楚呈现；VX04 躺椅部件在投影中相邻但更简化。这些是**有限样本图像观察**，遮挡与分辨率限制隐藏物体判断；像素中的黑缝或相邻也不能确定真实网格断开或接触。输入未提供各图原始绝对路径或事件号，故不伪造；可从既有汇总定位 `audit/visual_VX01.md`、`visual_VX04.md`、`visual_VX06.md`，再回查原图。不得推广到 360 个文件总体。

## 六、结论与复查优先项

1. 已审清单支持大量**非空代码执行、具体异常、重试、保存、渲染和工作流选择**；它不支持“服务器所有实验均已审”或“所有重建成功”。CLI 退出、空日志超时、构建异常、服务暂停和未执行提案必须分别记录。
2. 有限教师案例显示发现、建议和部分实际修改；另有候选接受或拒绝记录。但学生轨迹常无可辨认教师消息，调用标签也不显示补丁内容。**教师文字、评分、候选接受与档案保留均不等于真实几何或视觉改善。**
3. 优先复查应分别连接：原教师消息及候选决定、学生收到的准确内容、实际补丁与执行日志、对应参考／首图／最终图，以及保存 `.blend` 的精确接触和拓扑检查。对现有两个几何检查点也不能以 AABB 代替表面检查。
4. 原始图像路径、部分调用正文、未选归档载荷和二进制尚未逐项深审；缺失正式评分为未知而非零。现有材料不建立跨版本因果优越、全场景迁移效果或 Scene 有效性。


## 操作记录补充：清单与图像的原始路径
以下是由实际清单直接导出的路径补充，仅补齐复查入口，不增加视觉判断。

- [scene_full_audit_manifest.json](config/scene_full_audit_manifest.json)
- [scene_additional_full_audit_manifest.json](config/scene_additional_full_audit_manifest.json)
- [scene_bundle_audit_manifest.json](config/scene_bundle_audit_manifest.json)
- [scene_execution_audit_manifest.json](config/scene_execution_audit_manifest.json)
- [scene_stage_event_audit_manifest.json](config/scene_stage_event_audit_manifest.json)
- [scene_work_archive_summary.json](config/scene_work_archive_summary.json)
- [scene_visual_expansion_manifest.json](config/scene_visual_expansion_manifest.json)

**VX01 / commons_129095630**

轨迹：[/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v2/results/r1/fixed_h0/H0/development/commons_129095630/trajectory.jsonl](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v2/results/r1/fixed_h0/H0/development/commons_129095630/trajectory.jsonl)

- [图像1](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v2/results/r1/fixed_h0/H0/development/commons_129095630/reference.png)
- [图像2](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v2/results/r1/fixed_h0/H0/development/commons_129095630/steps/002/final.png)
- [图像3](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v2/results/r1/fixed_h0/H0/development/commons_129095630/final.png)

**VX02 / commons_187101683**

轨迹：[/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v2_1/results/r1/fixed_h0/H0/development/commons_187101683/trajectory.jsonl](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v2_1/results/r1/fixed_h0/H0/development/commons_187101683/trajectory.jsonl)

- [图像1](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v2_1/results/r1/fixed_h0/H0/development/commons_187101683/reference.png)
- [图像2](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v2_1/results/r1/fixed_h0/H0/development/commons_187101683/steps/002/final.png)
- [图像3](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v2_1/results/r1/fixed_h0/H0/development/commons_187101683/final.png)

**VX03 / commons_31294395**

轨迹：[/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v2_2/results/r1/fixed_h/H0/fixed_version_test/commons_31294395/trajectory.jsonl](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v2_2/results/r1/fixed_h/H0/fixed_version_test/commons_31294395/trajectory.jsonl)

- [图像1](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v2_2/results/r1/fixed_h/H0/fixed_version_test/commons_31294395/reference.png)
- [图像2](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v2_2/results/r1/fixed_h/H0/fixed_version_test/commons_31294395/steps/002/final.png)
- [图像3](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v2_2/results/r1/fixed_h/H0/fixed_version_test/commons_31294395/final.png)

**VX04 / commons_109923183**

轨迹：[/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v3/preparation/second_smoke/historical_r1_C2_start/development/commons_109923183/1/trajectory.jsonl](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v3/preparation/second_smoke/historical_r1_C2_start/development/commons_109923183/1/trajectory.jsonl)

- [图像1](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v3/preparation/second_smoke/historical_r1_C2_start/development/commons_109923183/1/reference.png)
- [图像2](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v3/preparation/second_smoke/historical_r1_C2_start/development/commons_109923183/1/steps/001/final.png)
- [图像3](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v3/preparation/second_smoke/historical_r1_C2_start/development/commons_109923183/1/final.png)

**VX05 / bw_0017**

轨迹：[/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v3/results/H01/selection/bw_0017/1/trajectory.jsonl](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v3/results/H01/selection/bw_0017/1/trajectory.jsonl)

- [图像1](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v3/results/H01/selection/bw_0017/1/reference.png)
- [图像2](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v3/results/H01/selection/bw_0017/1/steps/001/final.png)
- [图像3](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v3/results/H01/selection/bw_0017/1/final.png)

**VX06 / bw_0031**

轨迹：[/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v3/results/H01/selection/bw_0031/1/trajectory.jsonl](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v3/results/H01/selection/bw_0031/1/trajectory.jsonl)

- [图像1](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v3/results/H01/selection/bw_0031/1/reference.png)
- [图像2](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v3/results/H01/selection/bw_0031/1/steps/001/final.png)
- [图像3](../../references/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v3/results/H01/selection/bw_0031/1/final.png)

