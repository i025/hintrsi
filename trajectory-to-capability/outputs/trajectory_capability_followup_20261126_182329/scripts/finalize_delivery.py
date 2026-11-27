"""Record final file checks, actual CLI accounting and completed resource closure."""
import datetime
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

OUT = Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
rows = json.loads((OUT/'results/attempt_metrics.json').read_text())
conditions = json.loads((OUT/'results/model_condition_validation.json').read_text())
cleanup = json.loads((OUT/'logs/followup_cleanup.json').read_text())
resolution = json.loads((OUT/'audit/final_report_review_actions.json').read_text())
usage = json.loads((OUT/'results/actual_usage_summary.json').read_text())
now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))

posthocs = []
for row in rows:
    name = 'posthoc_'+row['stage']+'_'+row['task']+'_'+row['group']
    if 'matched_prompt' in row['run_name']:
        name = name.replace('posthoc_selection_', 'posthoc_selection_matched_', 1)
    path = OUT/'audit'/(name+'.md')
    job = path.with_suffix('.md.job.json')
    posthocs.append({'path': str(path), 'complete': path.exists() and job.exists() and json.loads(job.read_text())['completed']})
frozen = []
for name in ['knowledge_freeze.json', 'knowledge_freeze_hint.json']:
    for group, record in json.loads((OUT/'config'/name).read_text())['libraries'].items():
        frozen.append({'group': group, 'source': record['source'], 'frozen': record['path'],
                       'same_content': Path(record['source']).read_text() == Path(record['path']).read_text() == record['text']})
first = [c for task in conditions['matched_first_request_comparisons'] if task['stage'] in ('test', 'hint_transfer') for c in task['comparisons']]
first_keys = ['system_text_excluding_exact_capability_equals_B0', 'exact_tool_definitions_equal_B0', 'exact_non_system_messages_equal_B0']
required = ['research_report_zh.md', 'audit_hintrsi.md', 'audit_scene.md', 'trajectory_inventory.csv',
            'attempt_metrics.csv', 'additional_evaluation_metrics.csv', 'commands_used.md', 'config/task_split.json',
            'config/protocol.json', 'logs/engineering_fixes.json', 'audit/final_report_review.md', 'audit/final_report_review_followup.md']
report = OUT/'research_report_zh.md'
links = re.findall(r'\]\((/[^\n)]+)\)', report.read_text())
missing_links = [p for p in links if not Path(p.rsplit(':', 1)[0] if re.search(r':\d+$', p) else p).exists()]
sdk_ids = [r['sdk_session_id'] for r in rows if r.get('sdk_session_id')]
checks = {
    'all_29_complete_and_formally_evaluated': len(rows) == 29 and all(r['status'] == 'complete' and r['formal_success'] in (0, 1) for r in rows),
    'all_29_expected_posthocs_completed': len(posthocs) == 29 and all(p['complete'] for p in posthocs),
    'all_10_frozen_libraries_unchanged': len(frozen) == 10 and all(p['same_content'] for p in frozen),
    'all_18_Test_first_requests_match_public_conditions': len(first) == 18 and all(all(c.get(k) is True for k in first_keys) and c['native_sdk_Skill_in_tools'] is False for c in first),
    'all_knowledge_requests_contain_actual_library': all(r['capability_in_actual_prompt'] is True and r['capability_in_first_bridge_request'] is True for r in rows if r['group'] != 'B0'),
    'all_29_fresh_distinct_SDK_sessions': len(sdk_ids) == 29 and len(set(sdk_ids)) == 29,
    'no_recorded_model_or_effort_mismatch': not conditions['condition_mismatches'],
    'required_deliverables_exist': all((OUT/p).is_file() for p in required),
    'final_report_local_links_exist': not missing_links,
    'report_review_issues_resolved': resolution['blocking_issues_remaining'] == 0,
    'resource_cleanup_confirmed': cleanup['remaining_owned_processes'] == [],
}
verification = {'verified_at_beijing': now.isoformat(), 'checks': checks, 'all_checks_passed': all(checks.values()),
                'posthocs': posthocs, 'frozen_libraries': frozen, 'missing_report_local_links': missing_links,
                'limitations': ['State task retains the common pristine-base 60s statistical-test timeout; official scores are unchanged.',
                                'Two new independent Test tasks, no causal superiority or Scene-transfer claim.',
                                'Unreported CLI usage and settled billing remain unknown; root desktop orchestration is outside this experiment CLI ledger.',
                                'New posthocs have declared field/patch clipping; historical chunk audits and sampled visual/geometry reviews have separate coverage.']}
(OUT/'results/final_verification.json').write_text(json.dumps(verification, ensure_ascii=False, indent=2)+'\n')
if not verification['all_checks_passed']:
    raise RuntimeError('Inspect failed checks before marking complete: '+str([k for k,v in checks.items() if not v]))

def category(session):
    for stage in ['development', 'selection', 'test']:
        if session.startswith('capability_followup_v2_'+stage+'_'):
            return 'student_'+stage
    if session.startswith('capability_followup_hint_transfer_'): return 'student_hint_transfer'
    if session.startswith('followup-knowledge-'): return 'knowledge_extraction'
    if 'posthoc_' in session: return 'posthoc_audit'
    if session.startswith(('followup-audit-', 'followup-group-', 'followup-guidance-')): return 'historical_text_audit'
    if session.startswith('capability-final-report'): return 'final_reporting_review_corrections'
    return 'other_audit_visual_preflight'

costs = defaultdict(lambda: defaultdict(int))
for session, values in usage['by_session'].items():
    for key, value in values.items():
        if isinstance(value, (int, float)): costs[category(session)][key] += value
for path in (OUT/'logs').glob('*/model_requests.jsonl'):
    for line in path.open(): costs[category(json.loads(line)['session'])]['recorded_requests'] += 1
for request in usage['usage_unreported_requests']:
    costs[category(request['session'])]['usage_unreported_requests'] += 1
final_cost = {'as_of_beijing': now.isoformat(), 'by_category': dict(costs),
              'recorded_requests': usage['recorded_bridge_or_native_cli_requests'],
              'usage_reported_totals': usage['actual_cli_usage'], 'usage_unreported_requests': len(usage['usage_unreported_requests']),
              'settled_USD': None, 'scope': 'Includes actual final writer/review/correction CLI calls. Input already includes cached input. Root desktop orchestration and inaccessible historical costs are not imputed.'}
(OUT/'results/final_cost_breakdown.json').write_text(json.dumps(final_cost, indent=2)+'\n')
manifest_path = OUT/'config/run_manifest.json'
manifest = json.loads(manifest_path.read_text())
manifest.update(status='complete', finished_at_beijing=now.isoformat(), finished_at_utc=now.astimezone(datetime.timezone.utc).isoformat(),
                final_verification=str(OUT/'results/final_verification.json'), cleanup=str(OUT/'logs/followup_cleanup.json'))
started = datetime.datetime.fromisoformat(manifest['started_at_utc'].replace('Z', '+00:00'))
manifest['actual_followup_wall_seconds'] = (now-started).total_seconds()
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
stage_path = OUT/'config/final_stages_process.json'
stage = json.loads(stage_path.read_text())
shutil.copy2(stage_path, OUT/'evidence/final_stages_before_delivery_closure.json')
if 'error' in stage: stage['resolved_historical_error'] = stage.pop('error')
stage.update(status='complete', fully_finished_at_beijing=now.isoformat(), final_verification=manifest['final_verification'])
stage_path.write_text(json.dumps(stage, indent=2)+'\n')
tokens = usage['actual_cli_usage']
addendum = '\n\n## 最终操作核验与成本附记\n\n'
addendum += f'北京时间 {now.isoformat()} 完成交付核验。原六小时封存窗口不变；本次用户授权扩展从北京时间 2026-11-26 18:23:29 持续至此，实际跨度 {manifest["actual_followup_wall_seconds"]/3600:.3f} 小时，包含接入故障、监控空窗和报告收尾，不冒充六小时内完成。29 次预定学生尝试、29 份对应事后审阅及全部正式评价已结束。\n\n'
addendum += f'最后一次报告复核／纠正调用之后的实际 CLI 账本共 {final_cost["recorded_requests"]:,} 个请求，{tokens["model_calls_with_usage"]:,} 个回报用量，另 {final_cost["usage_unreported_requests"]} 个未报告用量；已报告 Input {tokens["input_tokens"]:,}、Output {tokens["output_tokens"]:,}、Cached Input {tokens["cached_input_tokens"]:,}。Cached 已包含在 Input 中。上述不是完整已结算账单，未报告用量与美元费用保持未知；本聊天操作开销未计入实验 CLI 账本。逐角色成本见 [最终成本分类]('+str(OUT/'results/final_cost_breakdown.json')+')。\n\n'
addendum += '实际关闭了本次恢复的三台 VM、对应隧道、模型桥接、进度服务和资源监控；关闭前无运行中的本实验容器，关闭后自有目标进程剩余 0。保留覆盖层、任务镜像、源码和全部原始失败记录。见 [实际关闭记录]('+str(OUT/'logs/followup_cleanup.json')+')、[交付核验]('+str(OUT/'results/final_verification.json')+')。共享服务器其他用户进程不在关闭范围。状态机共同基线超时的根因仍未查清；它作为限制保留，未改正式成绩，也未排除测试。\n'
(OUT/'final_accounting_zh.md').write_text(addendum.lstrip())
with report.open('a') as stream: stream.write(addendum)
print(json.dumps({'checks': checks, 'final_usage': tokens, 'finished_at_beijing': now.isoformat()}, ensure_ascii=False))
