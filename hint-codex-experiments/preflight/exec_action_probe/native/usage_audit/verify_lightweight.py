"""Verify the real LiteLLM stream before and after the isolated async usage fix."""
import copy
import json
from pathlib import Path

root = Path(__file__).resolve().parent
before = json.loads((root / 'before.json').read_text())
after = json.loads((root / 'after.json').read_text())


def without_usage(events):
    events = copy.deepcopy(events)
    for event in events:
        if event['type'] == 'message_start':
            event['message']['id'] = 'message-id'
        if event['type'] == 'message_delta':
            event.pop('usage', None)
    return events


checks = {}
for name, original in before.items():
    fixed = after[name]
    assert 'error' not in original and 'error' not in fixed
    assert without_usage(original['anthropic_events']) == without_usage(fixed['anthropic_events']), name
    assert [e['usage'] for e in original['anthropic_events'] if e['type'] == 'message_delta'] == [{'input_tokens': 0, 'output_tokens': 0}], name
    assert [e['usage'] for e in fixed['anthropic_events'] if e['type'] == 'message_delta'] == [{'input_tokens': 123, 'output_tokens': 17}], name
    if name.startswith('tools_'):
        tool_ids = [e['content_block']['id'] for e in fixed['anthropic_events'] if e['type'] == 'content_block_start' and e['content_block']['type'] == 'tool_use']
        assert tool_ids == ['call-read-1', 'call-bash-2'], tool_ids
    checks[name] = True
result = {'passed': True, 'real_model_calls': 0, 'checks': checks, 'only_changed_semantics': 'reported usage reaches the existing message_delta'}
(root / 'lightweight_result.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
