"""Complete the historical Scene synthesis after all indexed chunks finish."""
import json
import os
import subprocess
import time
from pathlib import Path

ROOT=Path.cwd()
OUT=Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
PYTHON='/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
state_path=OUT/'config/scene_synthesis_process.json'
if state_path.exists():raise FileExistsError(state_path)
state={'pid':os.getpid(),'started_at':time.time(),'status':'waiting_for_full_chunks'}
def save():state_path.write_text(json.dumps(state,indent=2)+'\n')
def run(name,*args):
    subprocess.run([PYTHON,'-u','-B',str(ROOT/'work_followup'/name),*args],check=True)
save()
try:
    while True:
        manifest=json.loads((OUT/'config/scene_full_audit_manifest.json').read_text())
        if manifest.get('status')=='complete':break
        process=next(x for x in json.loads((OUT/'config/recovered_processes_20261126_2226.json').read_text()) if x['name']=='scene_audit_recovered')
        proc=Path(f"/proc/{process['pid']}/status")
        if not proc.exists() or b'\nState:\tZ' in proc.read_bytes():raise RuntimeError('Full Scene chunk audit stopped before complete')
        time.sleep(30)
    state['status']='group_synthesis';save()
    run('aggregate_audits.py','--project','scene')
    groups=sorted((OUT/'audit/scene_groups').glob('*.md'))
    evidence=groups+sorted((OUT/'audit/scene_additional').glob('*.md'))+sorted((OUT/'audit/scene_stage_events').glob('*.md'))
    evidence += [OUT/'audit/scene_execution_teaching_synthesis_zh.md']
    facts={}
    for name in ['scene_full_audit_manifest.json','scene_additional_full_audit_manifest.json','scene_bundle_audit_manifest.json','scene_execution_audit_manifest.json','scene_stage_event_audit_manifest.json','scene_work_archive_summary.json','scene_visual_expansion_manifest.json']:
        p=OUT/'config'/name
        if p.exists():
            data=json.loads(p.read_text())
            facts[name]={k:v for k,v in data.items() if k not in ('files','chunks','jobs','cases','bundles','rows','records')}
    facts['new_visual_exact_file_coverage']=json.loads((OUT/'results/scene_visual_file_coverage.json').read_text())
    facts['canonical_full_audit']={'files':len(manifest['files']),'complete_files':manifest['complete_files'],'chunks':manifest['completed_chunks'],'full_content_without_prefix_clipping':True}
    facts['scope_notes']='360 canonical trajectory files plus 454 work-archive paths: 442 work copies and 12 additional nonduplicate document contents; not 814 independent experiments. 161 tar trajectory members are mapped copies. 27 tar bundles contain 13085 indexed members, not all member payloads deeply reviewed. 526 selected control files, 1483 execution/build/status files, 722 stage/call files reviewed in full chunks. Some other raw API sidecars are not independently reread. No new Blender reconstruction, render, GPU job, or independent Scene transfer experiment.'
    sections=['\nFILE '+str(p)+'\n'+p.read_text() for p in evidence]
    prompt='''请生成中文 audit_scene.md，最多12000汉字，作为证据审计报告，不更新能力库或学生。先精确说明覆盖率、重复、部分未审范围与视觉采样；不得笼统声称服务器所有实验全部已审。分版本/队列审查代表成功、失败、部分与教师干预：学生实际目标、Blender代码/执行/渲染/几何变化、Meta-Agent与H/M更新、候选接受。对多物体、材质纹理、部件接合、位置方向、相机灯光渲染分别给证据矩阵，严格分开教师是否发现、诊断是否获支持、更新是否针对、学生是否执行、后续是否独立验证。教师文字/评分/候选接受不等于真实几何/视觉改善。所有判断引用原始文件绝对路径、来源ID、原始事件/行号；缺失事件号不能造。显式区分直接观察、语义推断、待验证假设、技术中断。反例与未知不可省略。不得把少数图像观察推广到360文件总体。六个新增案例18图像附件引用实际包含6参考照片与8份不同渲染文件内容，另有旧有限视觉审计；并非总渲染全审。两个旧几何检查点的874对象/48mesh只是子集，AABB相邻不是接触或拓扑证明。说明哪些原始调用/图像/二进制尚未逐项深审。档案保留不等于独立验证。不生成新Blender答案或Scene有效性宣称。正文要可供之后复查，中文表格易读。\nFACTS\n'''+json.dumps(facts,ensure_ascii=False)+'\nMODEL-REVIEWED EVIDENCE\n'+''.join(sections)
    if len(prompt)>700000:raise RuntimeError('Scene synthesis packet exceeds saved input cap; split rather than silently omit evidence')
    packet=OUT/'config/final_scene_audit_prompt.txt';packet.write_text(prompt)
    state.update(status='chinese_audit',input_characters=len(prompt),source_reports=len(evidence));save()
    run('model_job.py','followup-final-scene-audit-zh',str(packet),str(OUT/'audit_scene.md'),'--presentation_language','zh')
    state['status']='complete'
except BaseException as error:
    state.update(status='needs_engineering_review',error=str(error));raise
finally:
    state['finished_at']=time.time();save()
