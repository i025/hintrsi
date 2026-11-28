"""Build readable evidence indexes without changing student observations."""
import argparse
from collections import Counter
import json
from pathlib import Path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def compact(value):
    if isinstance(value, dict):
        if value.get('type') == 'image':
            source = value.get('source', {})
            return {'type': 'image', 'media_type': source.get('media_type'),
                    'base64_characters': len(source.get('data', ''))}
        return {key: compact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [compact(item) for item in value]
    return value


def summarize(directory):
    directory = Path(directory)
    requests = rows(directory / 'bridge/model_requests.jsonl')
    responses = rows(directory / 'bridge/model_responses.jsonl')
    usage = rows(directory / 'bridge/token_usage.jsonl')
    totals = Counter()
    for record in usage:
        totals.update(record['usage'])
    events = []
    tools = Counter()
    trajectory = directory / 'capture/trajs.json'
    metadata = {}
    if trajectory.exists():
        recorded = json.loads(trajectory.read_text())
        metadata = recorded['metadata']
        for index, line in enumerate(recorded['trajectories']['main_agent'].splitlines()):
            message = json.loads(line)
            events.append({'event_index': index, **compact(message)})
            if message['type'] == 'assistant':
                for block in message['message'].get('content', []):
                    if 'name' in block:
                        tools[block['name']] += 1
    executions = []
    for capture in sorted((directory / 'capture').glob('blender_*')):
        executions.append({'capture': str(capture.relative_to(directory)),
                           'command': json.loads((capture / 'command.json').read_text()),
                           'result': json.loads((capture / 'result.json').read_text()) if (capture / 'result.json').exists() else None,
                           'code': [str(p.relative_to(directory)) for p in (capture / 'code').rglob('*.py')],
                           'artifacts': [str(p.relative_to(directory)) for p in (capture / 'artifacts').rglob('*') if p.is_file()]})
    result = {'run': directory.name, 'status': json.loads((directory / 'status.json').read_text()),
              'model_requests': len(requests), 'model_responses': len(responses),
              'model_errors': rows(directory / 'bridge/model_errors.jsonl'),
              'tokens': dict(totals), 'sdk_result': metadata.get('ResultMessage'),
              'actual_billing_usd': None,
              'billing_note': 'SDK cost is an alias-based estimate, not Codex subscription billing. No Ofox API was used.',
              'tool_calls': dict(tools), 'blender_executions': executions,
              'artifacts': [{'path': str(p.relative_to(directory)), 'bytes': p.stat().st_size}
                            for p in (directory / 'workspace').rglob('*') if p.is_file() and '.git' not in p.parts],
              'image_requests': [{'request_id': p.parent.name, 'attachments': json.loads(p.read_text())}
                                 for p in (directory / 'bridge').glob('*/image_attachments.json')]}
    output = directory / 'analysis'
    output.mkdir(exist_ok=True)
    (output / 'evidence_index.json').write_text(json.dumps(result, indent=2))
    (output / 'sdk_events.json').write_text(json.dumps(events, ensure_ascii=False, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directories', nargs='+')
    args = parser.parse_args()
    for directory in args.directories:
        result = summarize(directory)
        print(result['run'], result['model_requests'], result['tokens'])
