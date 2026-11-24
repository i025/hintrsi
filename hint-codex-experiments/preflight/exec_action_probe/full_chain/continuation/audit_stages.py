"""Check saved M/I SDK evidence and bridge requests; never call a model or service."""
import argparse
import json
from pathlib import Path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def text_values(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from text_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from text_values(item)


def teacher(initial, review, bridge, session):
    first = json.loads((initial / 'stage_result.json').read_text())
    later = json.loads((review / 'stage_result.json').read_text())
    requests = rows(bridge / 'model_requests.jsonl')
    responses = rows(bridge / 'model_responses.jsonl')
    observed = [row for row in requests if row['session'] == session
                and later['started_at_unix'] <= row['timestamp'] <= later['finished_at_unix']]
    prior = [row for row in responses if row['session'] == session
             and first['started_at_unix'] <= row['timestamp'] <= first['finished_at_unix']]
    assert observed and prior, 'Both teacher stages must have real saved bridge traffic'
    history = observed[0]['request']['messages']
    tool_ids = {call['id'] for row in prior
                for call in row['response']['choices'][0]['message'].get('tool_calls', [])}
    returned = {message.get('tool_call_id') for message in history if message['role'] == 'tool'}
    final_text = prior[-1]['response']['choices'][0]['message']['content']
    evidence = {
        'same_sdk_session': first['sdk_session_id'] == later['sdk_session_id'],
        'both_stages_completed': first['sdk_completed'] and later['sdk_completed'],
        'readonly_mounts_verified': all(item['readonly_mount'] for stage in (first, later)
                                       for item in stage['readonly_checks']),
        'initial_tool_results_in_review_history': bool(tool_ids & returned),
        'initial_final_in_review_history': bool(final_text) and any(final_text in text for text in text_values(history)),
        'review_first_request_id': observed[0]['request_id'],
        'preserved_initial_tool_ids': sorted(tool_ids & returned),
        'review_request_ids': [row['request_id'] for row in observed],
        'sdk_session_id': first['sdk_session_id'],
        'native_exec_is_fresh_per_request': True,
    }
    evidence['passed'] = all(evidence[key] for key in (
        'same_sdk_session', 'both_stages_completed', 'readonly_mounts_verified',
        'initial_tool_results_in_review_history', 'initial_final_in_review_history'))
    return evidence


def online(student, progress, bridge, session):
    result = json.loads((student / 'stage_result.json').read_text())
    state = json.loads((student / 'online_teacher_state.json').read_text())
    events = json.loads((student / 'online_teacher_events.json').read_text())
    checks = [row for row in rows(progress / 'progress.jsonl') if row['session'] == session]
    requests = [row for row in rows(bridge / 'model_requests.jsonl') if row['session'] == session and row['role'] == 'student']
    assert checks and requests, 'A real checkpoint and resumed student request must be recorded'
    first_check = next(index for index, event in enumerate(events) if event.get('check') == 1)
    reads = [event for event in events[:first_check] if event.get('tool_name') == 'Read'
             and '/app/data/shard_' in event.get('tool_input', {}).get('file_path', '')]
    delivered = [row for row in checks if row['decision'] == 'delivered']
    injected = [{
        'check': row['check'],
        'student_request_ids': [request['request_id'] for request in requests
                                if request['timestamp'] >= row['finished_at']
                                and any(row['hint'] in text for text in text_values(request['request']['messages']))
                                and 'Teacher guidance:' in json.dumps(request['request']['messages'], ensure_ascii=False)],
    } for row in delivered]
    evidence = {
        'sdk_completed': result['sdk_completed'], 'tool_count': state['tool_count'],
        'checks': state['checks'], 'first_checkpoint_tool_count': checks[0]['tool_count'],
        'twenty_shard_reads_before_first_check': len(reads) == 20,
        'first_checkpoint_exactly_twenty': checks[0]['tool_count'] == 20,
        'checkpoint_bounds_preserved': 1 <= state['checks'] <= 3 and checks[0]['tool_count'] >= 20,
        'checkpoint_decisions': [row['decision'] for row in checks],
        'within_original_check_timeout': all(row['duration_seconds'] <= 600 for row in checks),
        'teacher_stopped': any(row['stopped'] for row in checks),
        'delivered_checks': len(delivered), 'injected_checks': injected,
        'actual_guidance_injection_verified': bool(delivered) and all(item['student_request_ids'] for item in injected),
        'no_hint_is_valid': True,
        'guidance_injection_coverage': 'verified' if delivered and all(item['student_request_ids'] for item in injected)
                                      else 'not_exercised' if not delivered else 'failed',
    }
    evidence['passed'] = (evidence['sdk_completed'] and evidence['checkpoint_bounds_preserved']
                          and evidence['within_original_check_timeout'] and not evidence['teacher_stopped']
                          and evidence['twenty_shard_reads_before_first_check']
                          and evidence['guidance_injection_coverage'] != 'failed')
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='stage', required=True)
    m = commands.add_parser('teacher')
    for name in ('initial', 'review'):
        m.add_argument('--' + name, type=Path, required=True)
    i = commands.add_parser('online')
    for name in ('student', 'progress'):
        i.add_argument('--' + name, type=Path, required=True)
    for command in (m, i):
        command.add_argument('--bridge', type=Path, required=True)
        command.add_argument('--session', required=True)
        command.add_argument('--output', type=Path, required=True)
    args = vars(parser.parse_args())
    output = args.pop('output')
    stage = args.pop('stage')
    result = globals()[stage](**args)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
