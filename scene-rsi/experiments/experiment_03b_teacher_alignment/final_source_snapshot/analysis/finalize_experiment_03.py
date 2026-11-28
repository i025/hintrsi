"""Close the recorded experiments with observed usage and preservation facts."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import socket

from review_capability_acquisition import observed_research_usage, summarize_reviews
from summarize_run import rows

ROOT = Path(__file__).resolve().parents[1]
A = ROOT / 'experiments/experiment_03a_capability_acquisition'
B = ROOT / 'experiments/experiment_03b_teacher_alignment'


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def session_facts(directory):
    status = json.loads((directory / 'status.json').read_text())
    requests = rows(directory / 'bridge/model_requests.jsonl')
    usage = rows(directory / 'bridge/token_usage.jsonl')
    reported = {row['request_id'] for row in usage}
    commands = [json.loads(path.read_text()) for path in (directory / 'bridge').glob('*/command.json')]
    session = json.loads((directory / 'inputs/session.json').read_text())
    trajectory = directory / 'capture/trajs.json'
    compact = None
    if trajectory.exists():
        events = json.loads(trajectory.read_text())['trajectories']['main_agent'].splitlines()
        compact = [event for line in events if (event := json.loads(line)).get('subtype') == 'compact_boundary']
    native = []; item_types = Counter()
    for event in rows(directory / 'bridge/codex_events.jsonl'):
        item = event.get('event', event).get('item', {})
        if item.get('type'):
            item_types[item['type']] += 1
        if item.get('type') in ('command_execution', 'file_change', 'mcp_tool_call', 'collab_tool_call', 'web_search'):
            native.append(event)
    return {'directory': str(directory.relative_to(ROOT)), 'status': status['status'],
            'finished_at': status.get('finished_at'), 'owned_processes_stopped': status.get('owned_processes_stopped'),
            'copied_auth_present': (directory / 'backend_home/auth.json').exists(),
            'requests': len(requests), 'requests_without_usage': len([row for row in requests if row['request_id'] not in reported]),
            'actual_models': sorted({row['actual_model'] for row in requests}),
            'actual_reasoning_efforts': sorted({row['reasoning_effort'] for row in requests}),
            'cli_multi_agent_disabled': all('agents.enabled=false' in command and 'features.multi_agent_v2=false' in command for command in commands),
            'configured_sdk_auto_compact_window': session.get('auto_compact_window', 400000),
            'actual_sdk_compaction_boundaries': compact,
            'compaction_event_source': 'capture/trajs.json when preserved; null means unavailable, not zero events.',
            'native_tool_events': native,
            'actual_cli_item_types': dict(item_types),
            'user_cpu_seconds': status.get('child_user_cpu_seconds'),
            'system_cpu_seconds': status.get('child_system_cpu_seconds'),
            'peak_sampled_rss_sum_mib': status.get('peak_sampled_rss_sum_mib'),
            'session_seconds': status.get('total_seconds')}


def main():
    summarize_reviews()
    usage = observed_research_usage()
    a_facts = [session_facts(Path(row['source_directory'])) for row in usage['sessions']]
    b_usage = json.loads((B / 'analysis/usage_summary.json').read_text())
    b_facts = [session_facts(B / row['scope'] / row['id']) for row in b_usage['sessions']]
    totals = Counter()
    for row in usage['sessions']:
        totals.update(row['known_tokens'])
    a_cost = {'sessions': len(a_facts), 'requests': sum(row['requests'] for row in a_facts),
              'known_tokens': dict(totals), 'known_input_plus_output': totals['input_tokens'] + totals['output_tokens'],
              'requests_without_usage': sum(row['requests_without_usage'] for row in a_facts),
              'known_child_user_cpu_seconds': sum(row['user_cpu_seconds'] or 0 for row in a_facts),
              'known_child_system_cpu_seconds': sum(row['system_cpu_seconds'] or 0 for row in a_facts),
              'largest_session_sampled_rss_sum_mib': max(row['peak_sampled_rss_sum_mib'] or 0 for row in a_facts),
              'session_seconds_sum': sum(row['session_seconds'] or 0 for row in a_facts),
              'actual_billing_usd': None, 'ofox_requests': 0}
    write(A / 'analysis/final_usage_summary.json', a_cost)
    original = json.loads((A / 'configs/previous_experiments_inventory.json').read_text())['files']
    differences = []
    for row in original:
        path = ROOT / row['path']
        if not path.exists() or path.stat().st_size != row['bytes'] or path.stat().st_mtime_ns != row['mtime_ns']:
            differences.append(row['path'])
    library_changes = []
    for library in json.loads((A / 'configs/frozen_libraries.json').read_text())['libraries']:
        for name in library['files']:
            relative = Path(library['condition']) / name
            if (A / 'libraries' / relative).read_bytes() != (A / 'source_at_formal_tests/frozen_libraries' / relative).read_bytes():
                library_changes.append(str(relative))
    ports = {}
    for port in [19164, 19165, 19166, 19167, 19168, 19265, 19365, 19366, 19367, 19368, 19465, 19466, 19467, 19468, 19565, 19566, 19567, 19568]:
        with socket.socket() as connection:
            connection.settimeout(.1)
            ports[str(port)] = connection.connect_ex(('127.0.0.1', port)) == 0
    finished = datetime.now(timezone.utc)
    started = json.loads((A / 'start.json').read_text())
    audit = {'checked_at_utc': finished.isoformat(), 'sessions': {'03A': a_facts, '03B': b_facts},
             'previous_experiments_files_checked': len(original), 'previous_experiments_metadata_differences': differences,
             'frozen_library_byte_differences': library_changes, 'known_bridge_ports_accepting_connections': ports,
             'scope': 'Recorded requests, commands, native events, process-owner flags, file bytes/metadata and local ports; not a formal security or model-weight proof.'}
    write(A / 'analysis/final_execution_audit.json', audit)
    combined = {'recorded_at_utc': finished.isoformat(), '03A': a_cost,
                '03B': {'sessions': len(b_facts), 'requests': sum(row['requests'] for row in b_facts),
                        'known_input_plus_output': b_usage['known_input_plus_output'],
                        'requests_without_usage': b_usage['missing_usage_requests']},
                'joint_wall_seconds': finished.timestamp() - started['started_at_epoch'],
                'known_input_plus_output': a_cost['known_input_plus_output'] + b_usage['known_input_plus_output'],
                'requests_without_usage': a_cost['requests_without_usage'] + b_usage['missing_usage_requests'],
                'actual_billing_usd': None, 'ofox_requests': 0,
                'limitations': ['Missing returned usage is unknown. Cached input and reasoning output are subsets.',
                               'Controller chat usage is outside these scientific SDK session counters.',
                               'CPU counters are SDK child-process observations; offline Blender stages have separate logs.',
                               'Sampled RSS sums may count shared pages more than once. Joint elapsed time includes parallel work.']}
    write(ROOT / 'experiments/experiment_03_usage_summary.json', combined)
    raw_report = A / 'acquisition_reviews/report/REPORT/workspace/REPORT_ZH.md'
    text = raw_report.read_text()
    failed_timing = json.loads((A / 'runs/A-T04-A2/status.json').read_text())
    corrections = {
        'A-T04-A2 约 12 秒': f"A-T04-A2 的 SDK 执行约 {failed_timing['student_seconds']:.1f} 秒、总会话 {failed_timing['total_seconds']:.2f} 秒",
        '03-A 正式学习者/学生未受该修复影响': '该修复在 03-A 正式学习前完成，全部正式学习者和学生使用统一修复后的运行环境'}
    applied = []
    for before, after in corrections.items():
        if before in text:
            text = text.replace(before, after)
            applied.append({'before': before, 'after': after})
    write(A / 'analysis/report_fact_checks.json', {'original_model_report': str(raw_report),
          'scope': 'Timing/parameter scope clarification and observed final arithmetic only; research interpretation unchanged.',
          'applied': applied})
    text += '\n\n## 报告结束后补记：实际数值账本\n\n'
    text += '控制器在报告会话结束后仅补入实际计数；上文研究判断保留，原始报告在 acquisition_reviews/report/REPORT/workspace/REPORT_ZH.md。\n\n'
    text += f"03-A 共 {a_cost['sessions']} 个已记录 SDK 会话、{a_cost['requests']} 次请求，已知输入＋输出 {a_cost['known_input_plus_output']:,} Token，另有 {a_cost['requests_without_usage']} 次请求缺失用量返回。缓存输入和推理输出为子集，没有重复相加。Ofox 调用为 0，Codex 实际美元账单未知。\n\n"
    text += '|范围|会话|请求|已知输入 Token|已知输出 Token|缺失用量请求|\n|---|---:|---:|---:|---:|---:|\n'
    for scope, row in usage['scopes'].items():
        token = row['known_tokens']
        text += f"|{scope}|{row['sessions']}|{row['model_requests']}|{token.get('input_tokens', 0)}|{token.get('output_tokens', 0)}|{row['requests_without_usage']}|\n"
    projection = json.loads((A / 'analysis/projection_summary.json').read_text())
    pairs = json.loads((A / 'analysis/paired_projection_differences.json').read_text())['paired_contrasts']
    counts = Counter(item['status'] for run in projection['runs'] for item in run['mappings'])
    text += f"\n实际投影记录保留全部 {len(projection['runs'])} 个计划运行、{sum(counts.values())} 条候选对应：{counts['measured']} 条测量、{counts['unknown']} 条未知。{len(pairs)} 个预设场景／组对照中，{sum(bool(pair['shared_measured_entities']) for pair in pairs)} 个具有相同 GT 实例集合的双侧测量，共 {sum(len(pair['shared_measured_entities']) for pair in pairs)} 个对象配对。候选对应与身份复核是自动模型判断，未经人工确认。\n"
    report_config = json.loads((A / 'acquisition_reviews/report/REPORT/inputs/session.json').read_text())
    text += f"\n报告重试单独使用 SDK 自动压缩窗 {report_config['auto_compact_window']}、工具 {', '.join(report_config['tools'])} 和机械精简输入；此前报告失败会话也计入账本。该调整没有改变已完成学生或学习条件；各会话实际配置、压缩事件及原生 CLI 事件类型见最终执行检查。\n"
    text += f"\n记录到的 SDK 子进程用户 CPU 秒 {a_cost['known_child_user_cpu_seconds']:.1f}、系统 CPU 秒 {a_cost['known_child_system_cpu_seconds']:.1f}，单会话采样 RSS 加和最大 {a_cost['largest_session_sampled_rss_sum_mib']:.1f} MiB；共享页可能重复计数，离线 Blender 另有日志。会话秒之和 {a_cost['session_seconds_sum']:.1f} 不是总研究墙钟。\n\n"
    text += '完整分项见 [最终用量](analysis/final_usage_summary.json)、[原始分阶段账本](analysis/acquisition_review_research_usage.json)、[最终执行检查](analysis/final_execution_audit.json)。\n'
    (A / 'REPORT_ZH.md').write_text(text)
    provenance = A / 'infrastructure/acquisition_review_report_provenance.json'
    record = json.loads(provenance.read_text())
    record['controller_action'] = 'Copy original SDK research report, clarify timing/runtime scopes as recorded in report_fact_checks.json, append observed final numerical ledger; research interpretation unchanged.'
    write(provenance, record)
    print(json.dumps({'03A': a_cost, 'joint_known_tokens': combined['known_input_plus_output'],
                      'old_file_differences': differences, 'library_differences': library_changes,
                      'open_known_ports': [key for key, value in ports.items() if value]}, indent=2))


if __name__ == '__main__':
    main()
