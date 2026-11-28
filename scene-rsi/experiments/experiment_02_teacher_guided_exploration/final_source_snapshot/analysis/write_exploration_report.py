"""Assemble measured tables and the reviewed Chinese interpretation, without invented ratings."""
import datetime
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'experiments/experiment_02_teacher_guided_exploration'


def number(value,digits=3):
    return '不可用' if value is None else f'{value:.{digits}f}'


def table(headers,rows):
    return '| '+' | '.join(headers)+' |\n| '+' | '.join('---' for _ in headers)+' |\n'+''.join('| '+' | '.join(str(x).replace('|','／').replace('\n',' ') for x in row)+' |\n' for row in rows)+'\n'


def main():
    result=json.loads((EXP/'analysis/results.json').read_text());runs=result['runs']
    usage=json.loads((EXP/'analysis/usage_summary.json').read_text())
    strategies=json.loads((EXP/'analysis/strategy_metrics.json').read_text())
    versions=json.loads((EXP/'runtime_versions.json').read_text())
    core=json.loads((EXP/'core_finished.json').read_text())
    repeat=json.loads((EXP/'repeat_finished.json').read_text()) if (EXP/'repeat_finished.json').exists() else None
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    exact=sum(r['image_metrics'].get('original_vs_regenerated',{}).get('pixel_identical',False) for r in runs)
    valid=sum(r.get('technical',{}).get('regeneration',{}).get('exit_code')==0
              and r['technical']['regenerated_blend'] and r['technical']['regenerated_render']
              and r['technical']['original_blend_opened'] and r['required_final_resolution_met'] for r in runs)
    by_name={r['run']:r for r in runs}
    matrix=[]
    for group in range(5):
        cells=['E'+str(group)]
        for scene in ('S01','S02','S03'):
            values=[]
            for repetition in (1,2):
                r=by_name[scene+'-E'+str(group)+'-R'+str(repetition)]
                if scene=='S01':
                    gaps=[c['gap'] for c in r['chairs']]
                    value='两椅均在容差内' if all(abs(g)<=.0001 for g in gaps) else ', '.join(number(g,3) for g in gaps)
                elif scene=='S02':value=number(r['door_mask_comparison']['gt_instance_iou'])
                else:
                    v=r['automated_visual_evaluation'];value=v['target_resolution']+'/'+v['target_change']
                values.append('R'+str(repetition)+': '+value)
            cells.append('；'.join(values))
        matrix.append(cells)
    headline=table(['组别','两椅支撑间隙（Blender 单位）','房门参考视角 IoU','厨房目标盲评'],matrix)
    doc=f'''# Scene RSI Experiment 02：教师引导的能力诊断与主动探索

报告生成：{now.strftime('%Y-%m-%d %H:%M:%S')}（北京时间）。

本批实际保存 {len(runs)} 次共同检查点分支运行：核心 15 次与额外完整重复分开记录。{valid} 次通过独立执行交付代码及随附资源、生成标准场景/图像并打开原始场景的技术检查，其中 {exact} 次独立再生成图像与交付图逐像素一致。技术完成度不等于目标缺陷解决或视觉恢复成功。

这不是完整 RSI、长期能力学习、教师自演化、Harness Evolution 或模型微调。本次固定教师没有经过真实人工审美对齐，人工评分全部为空。

最直接的结果是：具体指导能够改变本次任务中的建模与验证行为，效果依赖案例，没有呈现 E0→E4 单调改善。下表保留核心 R1 与额外重复 R2 的实际差异；支撑间隙、房门掩码和自动视觉判断是不同证据，不能相加为总分。

{headline}
椅子近零间隙不等于证明完整机械连接；门板 IoU 高也可能伴随不合理的门轴/墙体关系。具体方法、反例和十个研究问题见第 5 节。

## 1. 研究设计与实际复用

沿用 Experiment 01 的 Claude Agent SDK 执行循环、Codex CLI Bridge、多模态传递、Blender 执行、文件/网络隔离与被动记录。没有使用 Codex 原生 Agent 执行学生的文件工具，也没有继承 SceneEvolve 的重建策略。CLI 是底层模型决策后端，实际 Bash/Read/Write/Edit 及其结果由 SDK 维护。

每组从同一份代码、scene.blend、final.png、参考图和相关资源独立复制。所有会话全新，未恢复原学生对话，因此准确称为“共同场景检查点分支实验”。学生不知道其他组的执行结果，教师和学生都没有 GT 挂载或网络搜索权限；GT 只用于所有学生结束后的评价。

模型统一为 gpt-6.1-terra / low，实际 CLI 参数经过逐请求审计。运行版本：{versions['codex_version']}、Claude Agent SDK {versions['claude_agent_sdk']}、Blender 5.2.2。请求接受与记录的标识不能独立证明服务商内部权重版本。

| 案例 | 初始运行 | 本批共同目标 |
| --- | --- | --- |
| S01 | S01-R1 | 两把办公室椅子的支撑、轮子及底座关系 |
| S02 | S02-R3 | 卧室门板朝向、投影及前景遮挡 |
| S03 | S03-R2 | 厨房右台面的材质与纹理外观 |

初始检查点来自 Experiment 01，原结果未修改。本批源代码和固定输入分别见 source_at_formal_run、source_at_repeat_start、checkpoints 与 configs/cases.json；新增代码及真实修复另行保存。

## 2. 组别、Prompt、预算与冻结顺序

| 组别 | 实际追加指导 |
| --- | --- |
| E0 | 无额外指导，继续自主改善当前重建 |
| E1 | 通用比较、自检和修复要求，不指明错误物体或技术 |
| E2 | 教师给出的具体缺陷，不提供修复方法 |
| E3 | 与 E2 完全相同的缺陷文字，加一种策略和验证方向 |
| E4 | 与 E2 完全相同的缺陷文字，加至少两种不同假设或方法及比较要求 |

完整英文任务与实际指导保存在 prompts/ 和 hints/。Hint 位于初始用户消息的 Additional guidance 部分；SDK 系统提示保持相同。教师先读取参考图、当前渲染、代码、保存状态、原始轨迹和既有客观证据，再生成诊断与全部指导；未读取 GT .blend、精确坐标或隐藏结构。教师工作区的原始代码/场景/渲染均未被改动。

所有学生同为 1500 秒追加执行、最多 120 次进入 Bridge 的模型请求、120 SDK turn 上限、8 核 CPU、nice 15、每进程 32 GiB 地址空间上限，最终渲染 640×360。两路分别使用 32–39、40–47。允许自主提前结束；相同上限不等于实际消耗相同。没有设置可核验的模型采样 seed，也没有跨会话 Memory、Skill、持久知识或在线教师。

实际每次学生使用 4–21 次 Bridge 请求、66.0–491.8 秒 SDK 墙钟，30 次均以 sdk_exit 正常结束，没有触发时间或调用上限。残留缺陷发生在预算尚未耗尽时；这支持分析自主停止与复核行为，但不能推断强制执行更久就一定能够修复。

核心顺序在正式执行前冻结并交错场景。额外重复严格依据预先记录的时间条件启动，顺序反转，仍从原检查点开始；没有依据评价结果追加某个组。没有运行第二初始检查点或 E5。

各场景 E0–E4 的指导字数分别为：

'''
    hint_rows=[]
    for scene in ('S01','S02','S03'):
        h=json.loads((EXP/'hints'/(scene+'.json')).read_text());hint_rows.append([scene]+[h['word_counts']['E'+str(i)] for i in range(5)])
    doc+=table(['场景','E0','E1','E2','E3','E4'],hint_rows)
    doc+='提示长度与具体内容共同变化，不能把本批差异单独归因于“探索”二字或纯知识量。教师准备成本单列，没有假装为零。\n\n'
    doc+='## 3. 独立评价及证据边界\n\n'
    scenes=json.loads((ROOT/'configs/scenes.json').read_text())['scenes']
    doc+='继续使用 Experiment 01 已冻结、已验证的 IDEAL-Scenes 数据，不重新下载或挑选样本。来源与许可沿用其数据清单：\n\n'
    doc+=table(['匿名案例','原数据场景','记录许可','原始来源'],
               [[s['id'],Path(s['evaluation_directory']).name,s['license'],'[数据目录]('+s['source_url']+')'] for s in scenes])
    doc+='GT 的完整本地位置见 ../../configs/scenes.json 与本批 file_index.json 的 reused_ground_truth；原始 GT 保存在独立 data/evaluation_gt，学生和教师都只获得原参考 RGB 与学生检查点资料。\n\n'
    doc+='所有学生执行结束后，评价端才打开交付文件、独立再生成、提取真实检查点状态并执行几何/图像评价。视觉评价使用匿名随机编号，只看参考图、初始图与单个候选图，不看组别、Hint 或其他候选。视觉评价与轨迹标注都通过同一 SDK/Bridge/模型执行，属于自动评价，不能冒充人工评分。\n\n'
    visual_completed=sum(r['scope']=='automated_visual_evaluation' and r.get('status')=='completed' for r in usage['sessions'])
    technical_completed=sum(r['scope']=='trajectory_annotation' and r.get('status')=='completed' for r in usage['sessions'])
    doc+=f"实际得到 {sum('automated_visual_evaluation' in r for r in runs)} 份有效视觉评价、{len(strategies['raw_annotations'])} 份有效轨迹标注；对应正常结束的评价会话分别为 {visual_completed}、{technical_completed}。原始模型输出、重试与缺失用量均保留。\n\n"
    doc+='椅子使用实际评估后的世界空间网格，分开识别两把完整组件和局部地板。误差容忍 1e-4 个学生 Blender 单位；正间隙证明分离，近零或包围盒重叠不证明完整物理接触，穿入和组件连接另列。门记录可见/完整投影、门轴和框体；只有语义对应可靠时才计算 GT 辅助重叠。厨房保留初始相机、灯光、World 和显示参数下的辅助图，候选几何仍可能混杂材质判断。SSIM 仅为像素辅助指标。\n\n'
    doc+='Blender 原始退出码为 0 不一定意味着 Python 没有异常；学生原始日志和异常都保留，独立再生成统一使用 Python 异常退出设置，并核对真实产物。评价端测量不被计为学生实际做过的检查。\n\n'
    doc+='## 4. 每次运行的实际结果\n\n'
    for repetition in (1,2):
        selected=[r for r in runs if r['repetition']==repetition]
        if not selected:continue
        doc+='### '+('核心批次' if repetition==1 else '额外完整重复')+'\n\n'
        data=[]
        for r in selected:
            visual=r.get('automated_visual_evaluation',{})
            data.append([r['run'],r['status'],r['model_requests'],number(r['sdk_seconds']/60,2),
                         r['blender_python_traceback_captures'],len(r['sdk_tool_errors']),'是' if r['code_changed'] else '否',
                         visual.get('target_resolution','不可用'),visual.get('target_change','不可用'),
                         visual.get('overall_visual_change','不可用'),
                         number(r['image_metrics']['reference_vs_initial']['ssim_rgb_gaussian_auxiliary'])+' → '+number(r['image_metrics']['reference_vs_final']['ssim_rgb_gaussian_auxiliary'])])
        doc+=table(['运行','SDK 状态','Bridge 请求','SDK 分钟','Blender 日志异常','SDK 工具错误','代码修改','自动目标判定','自动目标变化','自动整体变化','辅助 SSIM 初始→最终'],data)
    doc+='自动判定保留原始英文类别；resolved/partial/unresolved/unknown 不是人工成功率。每个结果的具体理由和不确定性见 visual_reviews/ 与 analysis/results.json。\n\n'
    chair_rows=[]
    for r in runs:
        if 'chairs' not in r:continue
        for c in r['chairs']:
            chair_rows.append([r['run'],c['chair'],number(c['gap'],6),number(c['normalized_gap'],6),
                               ', '.join(number(v,6) for v in c['wheel_gaps']),c['wheels_with_below_floor_samples'],
                               number(min(c['wheel_axis_abs_z']))+'–'+number(max(c['wheel_axis_abs_z'])),
                               len(c['wheel_base_disconnections_sampled'])])
    doc+='### 两把椅子的局部支撑证据\n\n'+table(['运行','椅子','最小有符号间隙','间隙／椅高','各轮最低间隙','存在低于地板采样的轮子数','轮轴 Z 绝对值范围','轮—底座分离候选数'],chair_rows)
    doc+='初始两把椅子的间隙分别为 0.014999896、0.014999658；每份结果按当前中心柱位置识别两把完整组件，每把有五个轮子。本例脚轮为圆柱：轮轴 Z 绝对值接近 1 表示轴竖直，接近 0 表示轴水平。轮—底座分离候选指没有表面交叉且顶点到表面最小采样距离大于容差的情况；零候选不是完整物理连接证明。柱体—底座/椅壳和叉架连接的交叉对数及采样距离也分别保留在 results.json 与原始 geometry.json。被隐藏其他物体的诊断视角和原相机外观均保留，不把单一间隙值当作完整成功。\n\n'
    door=json.loads((EXP/'analysis/door/metrics.json').read_text())
    doc+='### 房门的参考视角投影\n\n'
    doc+='GT 提供的实例映射明确将 ID 24 对应到 PanelDoorFactory 房门，可见掩码为 18,209 像素。学生端按源码中 open door hinge 的真实子对象识别木质房门，排除柜子的玻璃门。初始房门掩码与 GT 的 IoU 为 0。统一使用最近邻将 GT 实例掩码缩放为 640×360，学生端以不透明发射材质生成可见投影；不执行三维坐标误差或隐藏结构评分。\n\n'
    doc+=table(['运行','房门可见像素','完整投影像素','可见／完整投影','GT 房门 IoU','GT 房门召回'],
               [[r['run'],r['visible']['pixels'],r['amodal']['pixels'],number(r['visible_fraction_of_projected_door']),
                 number(r['gt_instance_iou']),number(r['gt_recall'])] for r in door['runs']])
    doc+='掩码重合不能证明门轴/门框合理，也不是整体恢复度。相机和门的同时修改都会影响投影，不能把 IoU 的变化全部归因于门板建模。原始名称规则的误匹配及统一重测记录见 analysis/door_mapping_revision.json；旧测量保留。\n\n'
    doc+='### 台面真实材质与混杂因素\n\n'
    doc+=table(['运行','几何纹路线数','实际台面材质节点','相机或灯变化','World 变化','显示参数变化'],
        [[r['run'],r['countertop']['geometric_vein_objects'],
          ', '.join(n.removeprefix('ShaderNode') for ns in r['countertop']['output_connected_nodes'].values() for n in ns),
          r['countertop']['camera_or_light_changed'],r['countertop']['world_changed'],bool(r['countertop']['display_changes'])]
         for r in runs if 'countertop' in r])
    doc+='原检查点使用纯色台面和 15 条几何纹路。表中只列与 Material Output 连通的节点，完整节点与绑定仍在 analysis/results.json 和各次 final_state.json。S03-E2-R2 中间确实渲染过 Wave 材质，最终转回 Noise；Wave 节点虽仍留在文件中，已经不接入输出。固定初始相机/照明辅助图见各次 target_geometry/fixed_camera_lighting.png。新材质存在并不等于外观恢复成功。\n\n'
    doc+='## 5. 研究问题与案例解释\n\n'
    interpretation=EXP/'analysis/research_interpretation_zh.md'
    doc+=interpretation.read_text()+'\n\n' if interpretation.exists() else '研究解释尚未完成；此为自动生成草稿，不应作为最终结论。\n\n'
    doc+='## 6. 技术策略重合度与实际探索\n\n'
    data=[]
    for scene in ('S01','S02','S03'):
        for rep in (1,2):
            pairs=[p for p in strategies['pairs'] if p['scene']==scene and p['repetition']==rep and p['pair_kind']=='within_repeat_conditions']
            if not pairs:continue
            means=[]
            for key in ('all_jaccard','without_common_jaccard','target_jaccard'):
                values=[p[key] for p in pairs if p[key] is not None];means.append(number(sum(values)/len(values))+' (n='+str(len(values))+')' if values else '不可用 (n=0)')
            data.append([scene,rep,len(pairs)]+means)
    doc+=table(['场景','重复','组间配对数','完整标签均值','去共同标签均值','目标局部标签均值'],data)
    doc+='每对原始值见 analysis/strategy_metrics.csv；相同组跨重复也单列。n 为该口径下可计算的配对数；两个观测标签集合都为空时不强行定义相似度。命名采用预先给标注者的语义词表，标签需要实际代码、事件和场景证据。对同义垂直渐变材质标签及“仅有读图迭代、没有明确候选比较”的标注做了统一证据复核，原始标注与用于指标的派生标注分开保留，差异见 analysis/annotation_audit.json。未知或未标注不等于实际未采用；本表是已观测标签集合的重合度。完整集合中继承的建模代码会抬高重合度；去掉原实验的 12 个共同标签也不能解决所有粒度问题。这里只有三个独立参考任务，不将配对数当独立样本数，不做显著性或能力上限结论。\n\n'
    doc+='目标局部口径还受自动标注 scope 边界影响。低重合度也可能来自某些组没有观察到目标动作，不能直接视为有效探索更多。本表不能与 Experiment 01 的自然重建数值直接相减作为处理效应：两批的起始状态、指导条件、追加动作和标注任务不同。实际方法变化需由候选源码、执行与观察证据支持。\n\n'
    doc+='候选版本、失败、比较行为和最终保留方法分别见 technical_reviews/ 的 trajectory_annotation.json 及 analysis/exploration_summary.json。知识候选位于 analysis/candidate_knowledge.json，区分教师先验、原自然轨迹和本次实际分支发现；没有直接变成 Skill，也没有验证无教师新场景迁移。\n\n'
    doc+='## 7. Token、时间与资源\n\n'
    doc+='Token 以每个会话 bridge/token_usage.jsonl 中 CLI 返回的 usage 为准；SDK 自身的别名费用不作为实际账单。\n\n'
    condition_costs=[]
    for repetition,scope in [(1,'core'),(2,'extra_repeat')]:
        for group in range(5):
            selected=[r for r in usage['sessions'] if r['scope']==scope and '-E'+str(group)+'-' in r['run']]
            condition_costs.append(['核心' if repetition==1 else '额外重复','E'+str(group),len(selected),
                sum(r['requests'] for r in selected),sum(r['reported_tokens'].get('input_tokens',0) for r in selected),
                sum(r['reported_tokens'].get('output_tokens',0) for r in selected),
                number(sum(r.get('sdk_wall_seconds',0) for r in selected)/60,2)])
    doc+=table(['批次','组别','场景数','Bridge 请求','已报告输入','已报告输出','SDK 分钟之和'],condition_costs)
    doc+='这是每组三个场景的消耗之和，核心与额外重复分列；不是单位成功率的费用，也未把教师准备成本隐去或随意分摊。\n\n'
    data=[]
    for scope,row in usage['scopes'].items():
        tokens=row['known_tokens'];data.append([scope,row['sessions'],row['requests'],tokens.get('input_tokens',0),tokens.get('output_tokens',0),row['missing_usage_requests'],number(row['sdk_seconds']/60,2),number(row['reported_local_child_cpu_seconds'],2),number(row['maximum_sampled_rss_sum_mib'],1)])
    doc+=table(['范围','会话','Bridge 请求','已报告输入','已报告输出','用量缺失请求','SDK 分钟之和','已报告本地子进程 CPU 秒','最大抽样 RSS 和 MiB'],data)
    total=usage['all_known_tokens'];doc+=f"全部执行器已报告输入 {total.get('input_tokens',0)}、输出 {total.get('output_tokens',0)}，合计 {total.get('input_tokens',0)+total.get('output_tokens',0)} Token。其中缓存输入 {total.get('cached_input_tokens',0)}、推理输出 {total.get('reasoning_output_tokens',0)}，均为对应输入/输出的子集，不能重复相加。输入统计包含多次携带历史上下文与图像的请求，不能当成独立新文本量；存在缺失请求时总量仅为下界。没有调用 Ofox，Codex 实际美元费用不可从执行器核验，SDK 别名估价不当作账单。控制器聊天和服务商计算资源不在此计数内。\n\n"
    doc+=f"核心墙钟 {core['seconds']/60:.2f} 分钟；"+(f"额外重复墙钟 {repeat['seconds']/60:.2f} 分钟。" if repeat else '没有额外重复。')+'每次资源抽样、CPU 亲和性和子进程 OS 计时均保留。RSS 求和可能重复计算共享页。全部本地渲染为 CPU，没有占用 GPU；评价阶段两路各八线程，CPU 集合 48–55、56–63。\n\n'
    if (EXP/'completion.json').exists():
        completion=json.loads((EXP/'completion.json').read_text())
        doc+=f"从源码检查开始至本批完成记录共 {completion['elapsed_seconds']/60:.2f} 分钟，在六小时预算内。完整起止时间见 completion.json。各会话 SDK 分钟之和包含并行重叠，不能作为总体墙钟。上表子进程 CPU 为操作系统已报告值，未覆盖控制器全部活动及服务商计算，不冒充整台服务器的精确资源账单。\n\n"
    doc+='## 8. 工程变化、真实限制与人工材料\n\n'
    doc+='完整修复与受影响范围见 ENGINEERING_LOG.md。正式学生保留各自冻结源码；评价端的脚本异常识别、局部网格测量、材质状态扩展及图像对照单列。30 次学生共观察到 13 次 CLI 内部空 wait（核心 4、重复 9），没有非空接收者、其他 Agent、主机文件操作或跨会话结果的证据；原始事件保留，不能声称 native-tool-free 或完全等价于直接 API。全部学生结束后才部署 agents.enabled=false 与 multi_agent_v2=false，真实三图预检正确，后续评价使用该版本，没有重采样学生。Bridge 请求预算也不等于可独立观测的全部提供商内部往返。\n\n'
    doc+='文件/网络命名空间隔离了 GT、其他学生结果和实际 Hint 文件；原 Harness 的只读 /sdk、/harness 运行库源码仍可见，其中包括通用调度与提示模板。590 次实际工具请求未观察到对运行库/诊断源码路径的显式读取，但字符串路径审计不是所有间接访问均不存在的证明。本批没有额外缩小这部分源码挂载范围，详情见 analysis/runtime_access_audit.json。\n\n'
    doc+='其他限制包括：样本小；标签由单一自动模型辅助形成，未进行人工复核/标注一致性验证；教师、学生与自动评估使用同一基础模型，会话和输入隔离不等于判断误差相互独立；提示长度和实际成本不同；单图遮挡与三维结构不可辨识；名字对应与网格表面采样不等于完整碰撞/物理求解；厨房的几何与光照联动可能妨碍单独归因；新场景无教师迁移、长期学习与 Human-Aligned Teacher 均未验证。\n\n'
    doc+='匿名人工页面复用了 Experiment 01 的布局和本地导出逻辑，提供参考、初始、匿名结果、局部图及辅助视角。全部评分为空，不要求人类看代码或提供 Blender 技术方案。\n\n'
    doc+='![核心结果：参考图、初始场景、E0–E4](analysis/comparison_core.png)\n\n'
    if repeat:doc+='![额外重复：参考图、初始场景、E0–E4](analysis/comparison_repeat.png)\n\n'
    doc+='## 9. 复查入口\n\n- [冻结协议](PROTOCOL.md)、[实际设计](configs/frozen_design.json)、[追加依据](repeat_decision.json)。\n- [初始检查点](checkpoints)、[教师输入](teacher_inputs)、[真实诊断与完整会话](teachers)、[固定 Hint](hints)、[全部 Prompt](prompts)。\n- [学生原始记录与交付](runs)、[逐次结果](analysis/results.json)、[成本记录](analysis/usage_summary.json)、[策略逐对结果](analysis/strategy_metrics.csv)。\n- [正式启动时增量](source_changes.diff)、[最终源码来源](final_source_origin.json)、[后续源码增量](post_formal_source_changes.diff)、[工程修复](ENGINEERING_LOG.md)、[正式启动快照](source_at_formal_run)、[重复启动快照](source_at_repeat_start)。\n- [匿名人工评价页面](analysis/human_review/index.html)：下载后本地打开，未收集人工评分。\n'
    (EXP/'REPORT_DRAFT_ZH.md').write_text(doc)
    print('Wrote measured draft; complete the reviewed interpretation before final publication.')


if __name__=='__main__':main()
