"""Build the final evidence packet only after the saved experiment queues finish."""
import datetime
import json
from collections import defaultdict
from pathlib import Path

OUT=Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
OLD=OUT.parent/'trajectory_capability_20261126_020200'
state=json.loads((OUT/'config/final_stages_process.json').read_text())
if state['status']!='experiment_queues_complete_reports_pending':raise RuntimeError('Finish saved queues and posthocs before preparing the final research report')
rows=json.loads((OUT/'results/attempt_metrics.json').read_text())
if len(rows)!=29 or any(r['status'] in ('not_started','running') for r in rows):raise RuntimeError('All planned rows must have actual terminal records')
if not (OUT/'audit_scene.md').exists():raise RuntimeError('Finish the Scene audit first')
usage=json.loads((OUT/'results/actual_usage_summary.json').read_text())
costs=defaultdict(lambda:defaultdict(int))
def category(session):
    for stage in ['development','selection','test']:
        if session.startswith('capability_followup_v2_'+stage+'_'):return 'student_'+stage
    if session.startswith('capability_followup_hint_transfer_'):return 'student_hint_transfer'
    if session.startswith('followup-knowledge-'):return 'knowledge_extraction'
    if 'posthoc_' in session:return 'posthoc_audit'
    if session.startswith(('followup-audit-','followup-group-','followup-guidance-')):return 'historical_text_audit'
    return 'other_audit_visual_preflight_reporting'
for session,values in usage['by_session'].items():
    for key,value in values.items():
        if isinstance(value,(int,float)):costs[category(session)][key]+=value
summary=defaultdict(lambda:{'planned':0,'started':0,'complete_formal':0,'successes':0,'technical_or_missing':0})
for row in rows:
    if row['stage'] not in ('test','hint_transfer'):continue
    x=summary[row['stage']+'/'+row['group']];x['planned']+=1;x['started']+=row['status']!='not_started'
    valid=row['status']=='complete' and isinstance(row['formal_success'],int)
    x['complete_formal']+=valid;x['successes']+=int(valid and row['formal_success']==1);x['technical_or_missing']+=not valid
for x in summary.values():x['success_fraction_among_complete_formal']=str(x['successes'])+'/'+str(x['complete_formal']) if x['complete_formal'] else None
fields=['stage','task','group','status','outcome','formal_success','observed_verifier_reward','f2p_passed','f2p_total','p2p_passed','p2p_total','patch_bytes','model_requests','model_calls_with_usage','usage_missing','input_tokens','output_tokens','cached_input_tokens','tool_calls_requested','tool_calls_with_returns','wall_seconds','initial_wall_seconds','end_to_end_seconds','sdk_seconds','student_execution_seconds','verifier_elapsed_seconds','diagnostic_evaluation_seconds','uniform_evaluation_repair_seconds','evaluation_attempts','observed_verifier_timeout_seconds','stop_reason','notes','eval_path','trajectory_path','loaded_knowledge_path','capability_in_actual_prompt','capability_in_first_bridge_request']
facts={'prepared_at_beijing':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
    'followup_root':str(OUT),'closed_six_hour_root':str(OLD),'all_29_planned_rows':[{k:r[k] for k in fields} for r in rows],
    'new_test_summary':dict(summary),'cost_by_reported_category':dict(costs),
    'CLI_usage_as_of_packet':usage['actual_cli_usage'],'recorded_CLI_requests':usage['recorded_bridge_or_native_cli_requests'],
    'usage_unreported_requests':usage['usage_unreported_requests'],'settled_USD':None,
    'new_attempt_posthoc_scope':'Per-field character cap 1800 and final patch cap 30000 in the existing posthoc helper. Complete raw trajectories are saved, but these new attempt posthocs are not full untruncated trajectory audits. Historical full-chunk review is a separate declared cohort.',
    'report_cost_note':'Final report/review calls may occur after this snapshot. The final ledger and dated operator addendum supersede this cost snapshot; no invented fee or zero for unreported use.'}
for name in ['run_manifest.json','protocol.json','task_split.json','knowledge_freeze.json','verification_budget_revision.json','model_access_incident.json','historical_cost_recovery.json','historical_attempt_record_inventory.json','v2_extraction_inputs.json','expanded_history_contact_check.json','source_hint_snapshots.json','observed_attempt_notes.json']:
    data=json.loads((OUT/'config'/name).read_text())
    if name=='historical_attempt_record_inventory.json':data.pop('source_files',None)
    facts[name]=data
facts['all_delivered_libraries']={p.stem:{'path':str(p),'words':len(p.read_text().split()),'text':p.read_text()} for p in sorted((OUT/'knowledge').glob('*.md')) if p.stem in ['K0_v1','K0_v2','K1_v1','K1_v2','K2_v1','K2_v2','HT_NoHint','HT_Error','HT_Strategy','HT_Exploration']}
facts['delivery_records']=[json.loads(p.read_text()) for p in sorted((OUT/'knowledge').glob('*_delivery.json'))]
facts['deadline_patch_first_evaluations']=[{'path':str(p),'record':json.loads(p.read_text())} for p in sorted((OUT/'runs').glob('*/budget_stop_evaluation.json'))]
facts['additional_evaluation_diagnostics']=json.loads((OUT/'results/additional_evaluation_metrics.json').read_text())
facts['model_conditions']=json.loads((OUT/'results/model_condition_validation.json').read_text())
facts['resource_observations']=json.loads((OUT/'results/resource_summary.json').read_text())
facts['statemachine_observed_existing_test_failures']=json.loads((OUT/'results/statemachine_baseline_failure_inventory.json').read_text())
facts['observed_container_resource_limits']=json.loads((OUT/'results/live_container_resource_limits.json').read_text())
facts['host_resource_point_observations']=[json.loads(line) for line in (OUT/'logs/host_resource_snapshots.jsonl').read_text().splitlines()]
(OUT/'config/final_report_facts.json').write_text(json.dumps(facts,ensure_ascii=False,indent=2)+'\n')
cost_file=OUT/'results/reported_cost_breakdown.json';cost_file.write_text(json.dumps({'by_category':dict(costs),'new_test_summary':dict(summary),'usage_snapshot':usage['actual_cli_usage']},indent=2)+'\n')
reports=[OUT/'audit_hintrsi.md',OUT/'audit_scene.md',OUT/'audit/library_mechanism_comparison_pretest.md',OUT/'audit/methods_pretest_zh.md',OUT/'audit/related_work_fulltext_zh.md',OUT/'audit/nohint_evaluator_triage_zh.md',OLD/'research_report_zh.md']
reports += [OUT/'audit'/name for name in ['public_duplicate_screen.md','library_review_initial.md','library_review_v2.md','scene_report_review.md','statemachine_baseline_timeout_diagnosis_zh.md'] if (OUT/'audit'/name).exists()]
reports+=sorted((OUT/'audit').glob('posthoc_*.md'))
files=[OUT/'logs/engineering_fixes.json',OUT/'results/source_changes_vs_closed_six_hour.json',OUT/'results/source_changes_vs_closed_six_hour.diff']
text='''请据以下真实事实、CLI审阅及原始文件入口生成最终中文研究报告，最多18000汉字。标题使用“Trajectory-to-Capability RSI：六小时封存实验与后续扩展报告”。新报告写作/复核时资源尚未最终关闭；只写截至事实快照的已完成状态，关闭记录、最后两次报告调用及最终成本由后续真实操作附记补充，不得提前声称新实验VM/服务已关闭。输出可直接保存为research_report_zh.md的完整文稿，保留A-G结构。不得继续实验、修改能力库/学生/评测或编写新任务解答。
必须覆盖：A两个工程审计的精确文件/分块覆盖、原交接不可访问范围、元数据/副本/未审API侧录/像素/二进制限制，以及具体成功/失败/部分/教师干预事实；B基于source_parallel_13派生的实际改动、原框架关系、真实CLI模型low、实际命令入口和工程修复；C K0/K1/K2与全部库版本、来源、共同预算与实际差异、K2状态单元相对普通总结具体差异；D原六小时已封存结果与扩展29计划全部实际结果分开，逐题组列正式成绩、F2P/P2P、Input/Output/Cached、模型/工具调用、耗时、技术异常和额外代价；E根据实际事件分析采纳、行为改变、冗余/退化/迁移失败及普通总结已有的知识；F仅提出值得迁移Scene的机制和待验证条件，不把代码结果当Scene实证；G对九项近邻工作划清边界，逐项给官方arxiv链接，不能把多轨迹总结、教师指导、验证、固定模型自改进宣称新颖贡献。
在D中将全部29条扩展尝试的详细数表位置写为独立一行 <<ALL_PLANNED_ATTEMPTS_TABLE>>。渲染程序将从真实指标原样插入全部结果、成本及异常表，不要再次手抄全部详细数值；仍需写正式成功的逐组汇总和有证据的解释。该占位符必须保留一次，不要放进代码块。
首段先给实际结果对四个研究问题提供/未提供什么证据，不预设正面结论。n很小，无正式统计显著性；多个参数化测试不是多个独立任务。V1K1/K2相同D01-D08，V2是各自on-policy不同轨迹，不能单独归因状态对齐。K0本身已包含许多相同通用知识。K2原707词按事先规则交付505词3单元，K1V2为619词4单元，不能说等长或恢复缺失单元。所有7字段以名称标题+6标签满足。
Selection保留理由按冻结记录逐字义解释：K0 V2改善正式全解，K1 V2正式成功相同且F2P/P2P均未退化，K2 V2不满足预先不退化规则而保留V1；不是根据Test成绩或解题成本选择。请分别报告匹配的V1对V1，以及Selection事先选中的部署版本；选中版本可能混用K1 V2和K2 V1，不能把这种混合版本比较当成状态对齐的纯因果效果。HT_NoHint仍加载从旧无Hint开发轨迹提取的知识，并不是B0；四个HT名称表示知识来源，新的迁移测试都没有在线Hint。本次HT是历史四条开发轨迹所提知识的冻结迁移比较，没有重新执行相同预算的四种主动Hint生成试验，也没有实现共同中间状态的反事实回放；不能把它写成已完成新的主动Hint随机对照。
区分观测、语义推断、分析假设、行为一致与因果采纳。新的正式Test未用在线教师/GT/旧会话，只加载各自冻结库；这不是脱离所有记忆后的参数能力证明。未训练权重，只保证实际请求模型标识/effort相同，服务端checkpoint不可见。不把技术缺失评价或中断计成普通算法失败。缺失数据为空；部分正确不代替正式全解；正式通过不保证完整真实世界契约。
新任务未见性的核查只覆盖本机可访问历史元数据、精确任务ID以及公开需求和仓库的明显重复；没有读取Test GT做参考实现的完整语义去重，也不保证不可访问历史或模型预训练未接触，不能扩大为无条件的全历史严格未见保证。
状态机Test的未修改基础代码也在既有统计测试出现60秒超时，必须按最新诊断区分共同基线问题与学生引入的P2P退化；保留原正式成绩，F2P仅作辅助，不另行排除该测试制造全通过。外层3600秒与任务内部测试时限分别说明。冻结后的这次工程诊断不是K2学生或提取方法的发现，不能当作K2迁移收益。空补丁、一次请求零工具的提前结束与实际算法实现失败分列，不把低成本提前结束当作效率提升。
扩展首个Selection原900秒评价与一次900秒诊断均保留，按统一3600秒上限补一次同补丁正式评价，学生未重跑；最终66/66、30014/30014。wall_seconds保留初次活动跨度，end_to_end_seconds包括到恢复正式成绩的真实等待；额外评测两列单列，不隐匿成本。所有新Selection/Test正式上限统一3600，学生1800；旧Development900另报。NoHint旧任务的900秒诊断仍未知，已知好补丁对照可通过，不能宣称根因查清。最初model_not_in_accessible_catalog不叫额度耗尽；恢复前登录文件更新但操作者未改认证，因果未定，未换型号。监控中断空窗保留，不声称全时连续覆盖。
历史117学生文件中108可关联CLI Token、仅56有逐request用量ID；native CLI turn、Token更新和SDK请求不同，不能混算。原SDK美元不是真实CLI费用；Input已含Cached，不再次相加；未报告用量不能填0；报告生成/复核后最终账本附记优先，不虚构结算美元。历史152表1130元数据记录包含计划/汇总/共享引用，不是独立尝试数。
旧报告17/117等是原六小时截止时事实，当前覆盖以扩展审计清单更新；不反写旧报告。较早posthoc的未知成绩按后附日期更新和最终指标解释。所有实际失败和未完成均列出，参考原始CSV与case路径事件号，不能仅报成功案例。不要大段复述论文或引用超过25个原文词。使用绝对路径Markdown链接，简明但完整，给核心表与所有详细表/库/轨迹/命令/修复日志入口。最终结束段说明已实现的初步证据和仍未验证内容，不作营销式总结。
学生达到1800秒截止后保存的补丁若因原编排器提前退出而没有进入正式评价，只继续其首次同补丁正式评价，不是重跑学生或重复评测；保留原技术中断/取消记录和恢复等待成本。budget_stop_evaluation记录及最终行明确区分student_timeout与正常end_turn，即使截止补丁正式通过也不能称学生正常完成。薄队列恢复机制对后续确认的同类截止统一适用，原学生工具/模型/权限/1800秒、冻结库和正式测试不变；原正在运行的队列进程可能仍使用旧调度代码，发生同类截止时也按相同政策保留并继续首次评测，不给额外解题机会。监控控制器因原子进程PID退出而单独恢复，不是学生重新开始。\nFACTS\n'''+json.dumps(facts,ensure_ascii=False)+'\nEVIDENCE REPORTS\n'+''.join('\nFILE '+str(p)+'\n'+p.read_text() for p in reports+files)
if len(text)>700000:raise RuntimeError('Final report packet exceeds cap; split reports without silently clipping evidence')
(OUT/'config/final_report_prompt.txt').write_text(text)
(OUT/'config/final_report_packet.json').write_text(json.dumps({'characters':len(text),'reports':len(reports),'facts_path':str(cost_file),'prepared_at_beijing':facts['prepared_at_beijing']},indent=2)+'\n')
print(json.dumps({'packet_characters':len(text),'source_reports':len(reports),'planned_rows':len(rows)}))
