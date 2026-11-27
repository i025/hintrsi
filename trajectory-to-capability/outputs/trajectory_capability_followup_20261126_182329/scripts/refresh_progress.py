"""Write a factual progress page and export the actual research helper sources."""
import datetime
import json
import shutil
from collections import Counter
from pathlib import Path

OUT=Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
rows=json.loads((OUT/'results/attempt_metrics.json').read_text())
hint=json.loads((OUT/'config/hintrsi_full_audit_manifest.json').read_text())
scene=json.loads((OUT/'config/scene_full_audit_manifest.json').read_text())
counts=Counter(r['status'] for r in rows)
now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
record={'updated_at_beijing':now,'planned_student_attempts':len(rows),'statuses':dict(counts),
    'formal_grades_available':sum(r['formal_success']!='' for r in rows),
    'hintrsi_complete_files':hint['complete_files'],'hintrsi_total_files':len(hint['files']),
    'scene_complete_files':scene['complete_files'],'scene_total_files':len(scene['files']),
    'main_knowledge_frozen':(OUT/'config/knowledge_freeze.json').exists(),
    'new_test_started':any(r['stage'] in ('test','hint_transfer') and r['status']!='not_started' for r in rows)}
manifest_path=OUT/'config/run_manifest.json'
manifest=json.loads(manifest_path.read_text())
manifest.update(updated_at_beijing=now,new_test_started=record['new_test_started'])
pipeline_path=OUT/'config/final_stages_process.json'
if manifest['status']!='complete' and pipeline_path.exists():
    manifest['status']=json.loads(pipeline_path.read_text())['status']
for stage in ['development','selection','test','hint_transfer']:
    manifest['completed_'+stage+'_attempts']=sum(r['stage']==stage and r['status']=='complete' for r in rows)
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
closure='本轮已完成，收尾记录见 logs/followup_cleanup.json。' if manifest['status']=='complete' else '本轮尚未完成。'
(OUT/'results/current_queue_status.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
text=f'''# Trajectory-to-Capability RSI 扩展实验

原六小时实验已封存；本目录记录用户授权续做的扩展工作，不覆盖原结果。更新于北京时间 {now}。

{closure}预定学生尝试29次（Development 4、Selection 7、Test 14、Hint来源独立迁移4），目前状态：{json.dumps(dict(counts),ensure_ascii=False)}。已有完整正式成绩 {record['formal_grades_available']} 条，未知成绩保持空值。

实际模型为原有 Codex CLI `gpt-6.1-terra / low`。四次新增Development已完成；V2、四份Hint来源能力库已生成并审查。主能力库冻结状态：{record['main_knowledge_frozen']}；新独立终测开始状态：{record['new_test_started']}。

历史Hint完整文本审阅 {hint['complete_files']}/{len(hint['files'])} 文件；Scene规范范围完整文本审阅 {scene['complete_files']}/{len(scene['files'])} 文件。Scene另有12份非重复归档内容，以及实际执行代码、教师控制与阶段事件补审；复制文件、归档成员和独立实验数分别统计，不能互换。

此前指定模型出现账户目录访问错误，原始失败保留；北京时间22:21同型号请求恢复。恢复前22:16登录文件元数据发生更新，操作者未改认证或模型；完整原因未验证。详见 `config/model_access_incident.json`。

首个Selection学生正常提交后，900秒正式评测超时；一次900秒同补丁诊断独立保留。后续Selection与所有新Test统一使用3600秒正式评测上限，并对首个补丁仅补一次同上限评测。学生解题时限仍为1800秒，没有修改答案、测试或能力库。见 `config/verification_budget_revision.json`；旧Development评价上限为900秒，须分阶段解释成本。

主要交付入口：

- `attempt_metrics.csv`：全部29个计划格子，含未开始、未知、额外评价次数和实际成本。
- `trajectory_inventory.csv`：真实轨迹与复制来源索引；不是独立试验计数表。
- `audit_hintrsi.md`、`audit_scene.md`：中文证据审计。
- `audit/`：逐块、分组、图像、几何、Hint采用及论文审阅。
- `config/task_split.json`、`config/protocol.json`：预定任务、顺序、预算与规则；正式修订另存旧版本。
- `knowledge/`：全部候选、交付文本和冻结库；审计输出不回流学生。
- `runs/`、`logs/bridge/`：真实学生轨迹、补丁、正式评价及模型原始调用。
- `logs/monitor.jsonl`：持续观测；中断空窗明确保留，不声称全时连续覆盖。
- `logs/engineering_fixes.json`：实际工程问题与处理。
- `results/actual_usage_summary.json`：实际CLI Token；未报告用量不填零，结算美元费用未知。
- `source/`、`scripts/`：实际工程源码与研究辅助脚本，不包含认证文件。

未运行任务不能填成功或失败，技术中断不能当普通算法失败。最终研究报告入口为 research_report_zh.md，实际完成状态以本页首段和收尾核验为准；方法稿与中间审计不能替代最终结果。
'''
(OUT/'README.md').write_text(text)
directory=OUT/'scripts';directory.mkdir(exist_ok=True)
for p in Path(__file__).parent.iterdir():
    if p.is_file() and p.suffix in ('.py','.txt','.md'):shutil.copy2(p,directory/p.name)
print(json.dumps(record,ensure_ascii=False))
