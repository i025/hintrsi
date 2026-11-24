"""Return controlled decisions; capture each independent command's full input."""
import json
import os
import shlex
import sys
import time
from pathlib import Path

FIXTURE = '/app/fixture Ω "quoted".txt'
COMMENTARY = 'Run the independent checks; preserve café Ω, quotes, and backslashes.'
payload = json.loads(sys.stdin.read())
Path('stdin.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2))
Path('invocation.json').write_text(json.dumps({'pid': os.getpid(), 'argv': sys.argv, 'timestamp': time.time()}))
text = json.dumps(payload['messages'], ensure_ascii=False)


def command(program):
    return '/opt/python3.12-tmp/bin/python3 -c ' + shlex.quote(program)


def tool(name, arguments):
    return {'name': name, 'arguments': json.dumps(arguments, ensure_ascii=False)}


def write_after(delay):
    program = 'import json,time; from pathlib import Path; started=time.time(); time.sleep(' + str(delay) + '); Path("/app/initial-' + str(delay) + '.json").write_text(json.dumps({"started":started,"finished":time.time()})); print("WRITE_' + str(delay) + '_OK")'
    return tool('Bash', {'command': command(program), 'description': 'Write independent timing fixture ' + str(delay), 'timeout': 30000})


if 'Your task is to create a detailed summary of the conversation so far' in text:
    phase = 'compact'
    content = '<analysis>The local transport checks completed.</analysis><summary>COMPACTED_HISTORY_ONLY. Read the escaped fixture, performed two timed writes, verified their outputs, and observed expected missing-file and exit-seven failures. Continue the local transport check.</summary>'
    calls = []
elif 'OFFLINE_DYNAMIC_' in text:
    phase = 'dynamic'
    content = 'OFFLINE_DYNAMIC_COMPLETE'
    calls = []
else:
    phase = 'continued' if 'OFFLINE_EXEC_CONTINUED' in text else 'resume' if 'OFFLINE_EXEC_RESUME' in text else 'initial'
    history_calls = [call for msg in payload['messages'] for call in msg.get('tool_calls', [])]
    arguments = [json.loads(call['function']['arguments']) for call in history_calls]
    content = COMMENTARY
    if phase == 'initial' and not any(a.get('file_path') == '/app/definitely_missing.txt' for a in arguments):
        calls = [tool('Read', {'file_path': FIXTURE}), write_after(2), write_after(5), tool('Read', {'file_path': '/app/definitely_missing.txt'})]
    elif phase == 'initial' and not any(a.get('file_path') == '/app/initial-2.json' for a in arguments):
        calls = [tool('Read', {'file_path': '/app/initial-2.json'}), tool('Read', {'file_path': '/app/initial-5.json'})]
    elif phase == 'resume' and not any(a.get('description') == 'Expected failure in resumed session' for a in arguments):
        calls = [tool('Read', {'file_path': FIXTURE}), tool('Bash', {'command': command('from pathlib import Path; print(Path(' + repr(FIXTURE) + ').read_text(),end="")'), 'description': 'Inspect escaped fixture in resumed session', 'timeout': 30000}), tool('Bash', {'command': command('print("EXPECTED_EXIT_SEVEN"); raise SystemExit(7)'), 'description': 'Expected failure in resumed session', 'timeout': 30000})]
    elif phase == 'continued' and not any(a.get('description') == 'Read after SDK compaction' for a in arguments):
        calls = [tool('Bash', {'command': command('from pathlib import Path; print(Path(' + repr(FIXTURE) + ').read_text(),end="")'), 'description': 'Read after SDK compaction', 'timeout': 30000})]
    else:
        calls = []
        content = 'OFFLINE_EXEC_COMPLETE_' + phase.upper()
action = {'content': content, 'tool_calls': calls}
Path('fixture_phase.txt').write_text(phase)
out = Path(sys.argv[sys.argv.index('--output-last-message') + 1])
out.write_text(json.dumps(action, ensure_ascii=False))
print(json.dumps({'type': 'thread.started', 'thread_id': 'offline-exec-' + str(os.getpid())}), flush=True)
print(json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 100 + len(payload['messages']), 'output_tokens': 20, 'cached_input_tokens': 0}}), flush=True)
