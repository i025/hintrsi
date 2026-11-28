"""Local subprocess fixture for the exec bridge. It never invokes Codex or a model."""
import json
import re
import sys
import time
from pathlib import Path

def argument_entries(value):
    if isinstance(value, dict):
        return {"entries": [{"key": key, "value": argument_entries(item)} for key, item in value.items()]}
    if isinstance(value, list):
        return [argument_entries(item) for item in value]
    return value


args = sys.argv[1:]
mode = args[args.index('--fixture-mode') + 1]
payload = json.load(sys.stdin)
directory = Path.cwd()
output = Path(args[args.index('--output-last-message') + 1])
schema = Path(args[args.index('--output-schema') + 1])
users = [message.get('content') for message in payload['messages'] if message['role'] == 'user']
last = json.dumps(users[-1], ensure_ascii=False) if users else ''
lane = int(re.search(r'LANE_(\d)', last).group(1)) if 'LANE_' in last else 0
capture = {'argv': args, 'cwd': str(directory), 'payload': payload,
           'schema': json.loads(schema.read_text()), 'output': str(output)}
(directory / 'fixture_capture.json').write_text(json.dumps(capture, ensure_ascii=False, indent=2))

def emit(event):
    print(json.dumps(event), flush=True)

emit({'type': 'thread.started', 'thread_id': 'fixture-' + directory.name})
emit({'type': 'turn.started'})
if mode == 'stderr_input_limit':
    print('Error: turn/start failed: Input exceeds the maximum length of 1048576 characters. '
          '(code -32602), data: {"input_error_code":"input_too_large","max_chars":1048576,"actual_chars":1135014}', file=sys.stderr)
    raise SystemExit(1)
if mode == 'controlled':
    mode = 'quota' if 'QUOTA' in last else 'sleep'
if mode == 'sleep':
    time.sleep(10)
if 'LANE_' in last:
    time.sleep(.12 + .03 * (5 - lane))
if mode == 'quota':
    time.sleep(.15)
    emit({'type': 'error', 'message': 'Usage limit reached'})
    raise SystemExit(3)
if mode == 'transient_success':
    emit({'type': 'error', 'message': 'Reconnecting... 1/1'})
usage = {'input_tokens': 100 + lane, 'cached_input_tokens': 20, 'output_tokens': 7,
         'reasoning_output_tokens': 3}
if mode == 'failure':
    emit({'type': 'turn.completed', 'usage': usage})
    print('Fixture process failure', file=sys.stderr)
    raise SystemExit(3)
names = [tool['function']['name'] for tool in payload['tools']]
content = 'RESULT:' + last
calls = []
if mode == 'batch':
    content = 'Inspect these files.'
    calls = [{'name': name, 'arguments': argument_entries({'file_path': '/app/café Ω "quote" \\ ' + str(i),
              'text': 'line one\nline two'})} for i, name in enumerate(names[:3])]
elif mode in ('invalid_args', 'args_array', 'unknown_tool'):
    calls = [{'name': 'MissingTool' if mode == 'unknown_tool' else names[0],
              'arguments': '{broken' if mode == 'invalid_args' else '[]' if mode == 'args_array' else argument_entries({})}]
elif mode == 'provided':
    calls = json.loads(last)["fixture_tool_calls"]
elif mode == 'empty':
    content = ''
elif mode == 'whitespace':
    content = ' \n\t '
action = {'content': content, 'tool_calls': calls}
output.write_text('{broken' if mode == 'invalid_json' else json.dumps(action, ensure_ascii=False))
emit({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(action)}})
if mode == 'failed_zero':
    emit({'type': 'turn.failed', 'error': {'message': 'Fixture final turn failed'}})
    raise SystemExit(0)
emit({'type': 'turn.completed', 'usage': usage})
