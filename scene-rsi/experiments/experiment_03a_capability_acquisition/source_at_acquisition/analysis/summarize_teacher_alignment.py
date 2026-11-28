"""Mechanical aggregates and request audits for frozen teacher predictions."""
from collections import Counter
import datetime
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / 'experiments/experiment_03b_teacher_alignment'
sys.path.insert(0, str(ROOT / 'analysis'))
from summarize_run import summarize, rows


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def audit(directory):
    requests = rows(directory / 'bridge/model_requests.jsonl')
    images = []
    for path in (directory / 'bridge').glob('*/image_attachments.json'):
        attachments = json.loads(path.read_text())
        images.append({'request_id': path.parent.name, 'attachments': [
            {key: item[key] for key in ('attachment_index', 'media_type', 'bytes', 'associations')} for item in attachments]})
    commands = [json.loads(path.read_text()) for path in (directory / 'bridge').glob('*/command.json')]
    model_matches = all(row.get('actual_model') == 'gpt-6.1-terra' and row.get('reasoning_effort') == 'low' for row in requests)
    events = rows(directory / 'bridge/codex_events.jsonl')
    native = []
    for event in events:
        value = event.get('event', event)
        item = value.get('item', {}) if isinstance(value, dict) else {}
        if item.get('type') in ('command_execution', 'file_change', 'mcp_tool_call', 'collab_tool_call'):
            native.append(value)
    provenance_hidden = []
    config = json.loads((directory / 'inputs/session.json').read_text())
    if directory.parent.name == 'reviews':
        for request in requests:
            text = json.dumps(request['request'])
            forbidden = ('selection_reason', 'source_workspace', 'teacher_diagnosis', 'door projection overlap', 'E2-R2', 'E4-R1', 'GT.json')
            provenance_hidden += [{'request_id': request['request_id'], 'matched_text': word} for word in forbidden if word in text]
    return {'id': directory.name, 'request_count': len(requests), 'model_and_effort_all_match': model_matches,
            'command_count': len(commands), 'cli_multi_agent_disabled': all('agents.enabled=false' in command and 'features.multi_agent_v2=false' in command for command in commands),
            'actual_image_requests': images, 'initial_real_image_count': len(images[0]['attachments']) if images else None,
            'copied_auth_removed': not (directory / 'backend_home/auth.json').exists(),
            'readonly_mounts': config.get('readonly_mounts', []), 'persistent_capability_enabled': config.get('persistent_capability_enabled', False),
            'explicit_provenance_text_matches': provenance_hidden, 'native_tool_events': native,
            'audit_scope': 'Explicit request text and observed tool events; no formal security or backend-weight proof.'}


def main():
    all_cases = []
    for split in ('development', 'independent'):
        path = EXP / 'configs' / (split + '_cases.json')
        if path.exists(): all_cases += json.loads(path.read_text())
    by_split, pairs = {}, []
    for case in all_cases:
        identifier = case['anonymous_id']
        outputs = {}
        for condition in ('T0', 'T1'):
            path = EXP / 'predictions' / (identifier + '-' + condition + '.json')
            if path.exists(): outputs[condition] = json.loads(path.read_text())
        if len(outputs) != 2: continue
        score_difference = outputs['T1']['overall_fidelity_estimate'] - outputs['T0']['overall_fidelity_estimate']
        priority = {condition: [item['category'] for item in sorted(output['main_defects'], key=lambda item: item['priority'])]
                    for condition, output in outputs.items()}
        row = {**case, 'T0': outputs['T0'], 'T1': outputs['T1'], 'score_T1_minus_T0': score_difference,
               'top_priority_categories': priority, 'top_priority_category_changed': priority['T0'][:1] != priority['T1'][:1],
               'human_rating': None}
        pairs.append(row)
        by_split.setdefault(case['split'], []).append(row)
    statistics = {}
    for split, records in by_split.items():
        statistics[split] = {'cases': len(records), 'reference_scenes': len({row['reference_group'] for row in records}),
             'mean_score_T0': sum(row['T0']['overall_fidelity_estimate'] for row in records) / len(records),
             'mean_score_T1': sum(row['T1']['overall_fidelity_estimate'] for row in records) / len(records),
             'mean_score_change': sum(row['score_T1_minus_T0'] for row in records) / len(records),
             'top_category_changes': sum(row['top_priority_category_changed'] for row in records),
             'score_changes': [{'anonymous_id': row['anonymous_id'], 'T0': row['T0']['overall_fidelity_estimate'],
                                'T1': row['T1']['overall_fidelity_estimate'], 'difference': row['score_T1_minus_T0']} for row in records],
             'top3_category_counts': {condition: dict(Counter(category for row in records for category in row['top_priority_categories'][condition][:3])) for condition in ('T0', 'T1')},
             'interpretation': 'Automated response changes only. Scores are not objective quality changes or evidence of improved human agreement.'}
    write(EXP / 'analysis/paired_predictions.json', pairs)
    write(EXP / 'analysis/prediction_summary.json', statistics)
    audits, sessions, totals, scopes = [], [], Counter(), {}
    for scope in ('reviews', 'base_students', 'research_analyses', 'pre_runtime_isolation_fix/reviews'):
        for directory in sorted((EXP / scope).glob('*')):
            if not (directory / 'status.json').exists(): continue
            status = json.loads((directory / 'status.json').read_text())
            if 'finished_at' not in status: continue
            result = summarize(directory)
            audits.append({'scope': scope, **audit(directory)})
            requests = result['model_requests']
            counts = result['tokens']
            totals.update(counts)
            item = {'id': directory.name, 'scope': scope, 'status': status['status'], 'sdk_status': status.get('sdk_status'),
                    'requests': requests, 'usage_records': len(rows(directory / 'bridge/token_usage.jsonl')),
                    'tokens': counts, 'seconds': status['total_seconds'], 'sdk_seconds': status.get('student_seconds'),
                    'stop_reason': status.get('stop_reason'), 'errors': result['model_errors'], 'tool_calls': result['tool_calls']}
            sessions.append(item)
            counts_by_scope = scopes.setdefault(scope, {'sessions': 0, 'requests': 0, 'usage_records': 0, 'tokens': Counter(), 'total_session_seconds': 0})
            counts_by_scope['sessions'] += 1; counts_by_scope['requests'] += requests
            counts_by_scope['usage_records'] += item['usage_records']; counts_by_scope['tokens'].update(counts)
            counts_by_scope['total_session_seconds'] += status['total_seconds']
    write(EXP / 'analysis/request_audit.json', audits)
    write(EXP / 'analysis/usage_summary.json', {'generated_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'sessions': sessions, 'scopes': scopes, 'all_known_tokens': dict(totals),
          'known_input_plus_output': totals['input_tokens'] + totals['output_tokens'],
          'cached_input_and_reasoning_output_are_subsets': True,
          'missing_usage_requests': sum(row['requests'] - row['usage_records'] for row in sessions),
          'ofox_api_calls': 0, 'actual_codex_billing_usd': None,
          'billing_note': 'No direct dollar charge can be inferred from Codex subscription token counters.'})
    print('Summarized paired predictions:', len(pairs), 'sessions:', len(sessions))


if __name__ == '__main__': main()
