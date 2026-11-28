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
    doc=f'''# Scene RSI Experiment 02：教师引导的能力诊断与主动探索

报告生成：{now.strftime('%Y-%m-%d %H:%M:%S')}（北京时间）。

本批实际保存 {len(runs)} 次共同检查点分支运行：核心 15 次与额外完整重复分开记录。{valid} 次通过独立执行代码、生成标准场景/图像并打开原始场景的技术检查，其中 {exact} 次独立再生成图像与交付图逐像素一致。技术完成度不等于目标缺陷解决或视觉恢复成功。

这不是完整 RSI、长期能力学习、教师自演化、Harness Evolution 或模型微调。本次固定教师没有经过真实人工审美对齐，人工评分全部为空。

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

核心顺序在正式执行前冻结并交错场景。额外重复严格依据预先记录的时间条件启动，顺序反转，仍从原检查点开始；没有依据评价结果追加某个组。没有运行第二初始检查点或 E5。

各场景 E0–E4 的指导字数分别为：

'''
    hint_rows=[]
    for scene in ('S01','S02','S03'):
        h=json.loads((EXP/'hints'/(scene+'.json')).read_text());hint_rows.append([scene]+[h['word_counts']['E'+str(i)] for i in range(5)])
    doc+=table(['场景','E0','E1','E2','E3','E4'],hint_rows)
    doc+='提示长度与具体内容共同变化，不能把本批差异单独归因于“探索”二字或纯知识量。教师准备成本单列，没有假装为零。\n\n'
    doc+='## 3. 独立评价及证据边界\n\n'
    doc+='所有学生执行结束后，评价端才打开交付文件、独立再生成、提取真实检查点状态并执行几何/图像评价。视觉评价使用匿名随机编号，只看参考图、初始图与单个候选图，不看组别、Hint 或其他候选。视觉评价与轨迹标注都通过同一 SDK/Bridge/模型执行，属于自动评价，不能冒充人工评分。\n\n'
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
                         r['blender_python_traceback_captures'],'是' if r['code_changed'] else '否',
                         visual.get('target_resolution','不可用'),visual.get('target_change','不可用'),
                         visual.get('overall_visual_change','不可用'),
                         number(r['image_metrics']['reference_vs_final']['ssim_rgb_gaussian_auxiliary'])])
        doc+=table(['运行','SDK 状态','Bridge 请求','SDK 分钟','Python 异常捕获','代码修改','自动目标判定','自动目标变化','自动整体变化','辅助 SSIM'],data)
    doc+='自动判定保留原始英文类别；resolved/partial/unresolved/unknown 不是人工成功率。每个结果的具体理由和不确定性见 visual_reviews/ 与 analysis/results.json。\n\n'
    chair_rows=[]
    for r in runs:
        if 'chairs' not in r:continue
        for c in r['chairs']:
            chair_rows.append([r['run'],c['chair'],number(c['gap'],6),number(c['normalized_gap'],6),
                               ', '.join(number(v,6) for v in c['wheel_gaps']),c['floor_penetration_samples']])
    doc+='### 两把椅子的局部支撑证据\n\n'+table(['运行','椅子','最小有符号间隙','间隙／椅高','各轮最低间隙','轮子低于地板的采样数'],chair_rows)
    doc+='连接关系、轮轴方向、被隐藏其他物体的诊断视角和原相机外观分别保留，不把单一间隙值当作完整成功。\n\n'
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
                values=[p[key] for p in pairs if p[key] is not None];means.append(number(sum(values)/len(values)) if values else '不可用')
            data.append([scene,rep,len(pairs)]+means)
    doc+=table(['场景','重复','组间配对数','完整标签均值','去共同标签均值','目标局部标签均值'],data)
    doc+='每对原始值见 analysis/strategy_metrics.csv；相同组跨重复也单列。命名采用预先给标注者的语义词表，标签需要实际代码、事件和场景证据。完整集合中继承的建模代码会抬高重合度；去掉原实验的 12 个共同标签也不能解决所有粒度问题。这里只有三个独立参考任务，不将配对数当独立样本数，不做显著性或能力上限结论。\n\n'
    doc+='候选版本、失败、比较行为和最终保留方法分别见 technical_reviews/ 的 trajectory_annotation.json。知识候选位于 analysis/candidate_knowledge.json，区分教师先验、原自然轨迹和本次实际分支发现；没有直接变成 Skill，也没有验证无教师新场景迁移。\n\n'
    doc+='## 7. Token、时间与资源\n\n'
    data=[]
    for scope,row in usage['scopes'].items():
        tokens=row['known_tokens'];data.append([scope,row['sessions'],row['requests'],tokens.get('input_tokens',0),tokens.get('output_tokens',0),row['missing_usage_requests'],number(row['sdk_seconds']/60,2)])
    doc+=table(['范围','会话','Bridge 请求','已报告输入','已报告输出','用量缺失请求','SDK 分钟之和'],data)
    total=usage['all_known_tokens'];doc+=f"全部执行器已报告输入 {total.get('input_tokens',0)}、输出 {total.get('output_tokens',0)}，合计 {total.get('input_tokens',0)+total.get('output_tokens',0)} Token。缓存输入与推理输出都是子集，不能重复相加；存在缺失请求时总量仅为下界。没有调用 Ofox，Codex 实际美元费用不可从执行器核验，SDK 别名估价不当作账单。控制器聊天和服务商计算资源不在此计数内。\n\n"
    doc+=f"核心墙钟 {core['seconds']/60:.2f} 分钟；"+(f"额外重复墙钟 {repeat['seconds']/60:.2f} 分钟。" if repeat else '没有额外重复。')+'每次资源抽样、CPU 亲和性和子进程 OS 计时均保留。RSS 求和可能重复计算共享页。全部本地渲染为 CPU，没有占用 GPU；评价阶段两路各八线程，CPU 集合 48–55、56–63。\n\n'
    doc+='## 8. 工程变化、真实限制与人工材料\n\n'
    doc+='完整修复与受影响范围见 ENGINEERING_LOG.md。正式学生保留各自冻结源码；评价端的脚本异常识别、局部网格测量、材质状态扩展及图像对照单列。核心事件审计观察到少量 CLI 内部空 wait，未涉及其他 Agent、文件操作或跨会话数据；原始事件保留，不能声称 native-tool-free 或完全等价于直接 API。Bridge 请求预算也不等于可独立观测的全部提供商内部往返。\n\n'
    doc+='其他限制包括：样本小；标签由单一自动模型辅助形成，未进行人工复核/标注一致性验证；提示长度和实际成本不同；单图遮挡与三维结构不可辨识；名字对应与网格表面采样不等于完整碰撞/物理求解；厨房的几何与光照联动可能妨碍单独归因；新场景无教师迁移、长期学习与 Human-Aligned Teacher 均未验证。\n\n'
    doc+='匿名人工页面复用了 Experiment 01 的布局和本地导出逻辑，提供参考、初始、匿名结果、局部图及辅助视角。全部评分为空，不要求人类看代码或提供 Blender 技术方案。\n\n'
    doc+='![核心结果：参考图、初始场景、E0–E4](analysis/comparison_core.png)\n\n'
    if repeat:doc+='![额外重复：参考图、初始场景、E0–E4](analysis/comparison_repeat.png)\n\n'
    doc+='## 9. 复查入口\n\n- [冻结协议](PROTOCOL.md)、[实际设计](configs/frozen_design.json)、[追加依据](repeat_decision.json)。\n- [初始检查点](checkpoints)、[教师输入](teacher_inputs)、[真实诊断与完整会话](teachers)、[固定 Hint](hints)、[全部 Prompt](prompts)。\n- [学生原始记录与交付](runs)、[逐次结果](analysis/results.json)、[成本记录](analysis/usage_summary.json)、[策略逐对结果](analysis/strategy_metrics.csv)。\n- [实际新增/修改源码](source_changes.diff)、[工程修复](ENGINEERING_LOG.md)、[正式启动快照](source_at_formal_run)、[重复启动快照](source_at_repeat_start)。\n- [匿名人工评价页面](analysis/human_review/index.html)：下载后本地打开，未收集人工评分。\n'
    (EXP/'REPORT_DRAFT_ZH.md').write_text(doc)
    print('Wrote measured draft; complete the reviewed interpretation before final publication.')


if __name__=='__main__':main()
