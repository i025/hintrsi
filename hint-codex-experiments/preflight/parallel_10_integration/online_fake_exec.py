"""Return controlled decisions for the real SDK's 20-tool hint checkpoint."""
import json
import os
import sys
from pathlib import Path

payload = json.loads(sys.stdin.read())
Path('stdin.json').write_text(json.dumps(payload, indent=2))
Path('invocation.json').write_text(json.dumps({'pid': os.getpid(), 'argv': sys.argv}))
observations = [m for m in payload['messages'] if m['role'] == 'tool']
text = json.dumps(payload['messages'])
if 'OFFLINE_RESUME_CHECK' in text:
    phase = 'resume'
    preserved = ('OFFLINE_INJECTION_COMPLETE' in text and len(observations)==20 and 'Teacher guidance:' in text)
    action = {'content':'OFFLINE_RESUME_COMPLETE' if preserved else 'OFFLINE_RESUME_LOST_HISTORY', 'tool_calls':[]}
elif not observations:
    phase = 'read_twenty'
    calls = [{'name': 'Read', 'arguments': json.dumps({'file_path': '/app/observations/observation_' + str(i).zfill(2) + '.txt'})} for i in range(20)]
    action = {'content': 'Read the observation files.', 'tool_calls': calls}
else:
    phase = 'after_hint'
    complete = (len(observations) == 20 and 'Teacher guidance:' in text and
                'Before concluding, compare the boundary conditions in the collected observations and verify that the relevant cases are covered.' in text and
                all('OFFLINE_OBSERVATION_' + str(i).zfill(2) in text for i in range(20)))
    action = {'content': 'OFFLINE_INJECTION_COMPLETE' if complete else 'OFFLINE_INJECTION_MISSING_CONTEXT', 'tool_calls': []}
Path('phase.txt').write_text(phase)
Path(sys.argv[sys.argv.index('--output-last-message') + 1]).write_text(json.dumps(action))
print(json.dumps({'type': 'thread.started', 'thread_id': 'offline-online-hint-' + str(os.getpid())}), flush=True)
print(json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 100, 'output_tokens': 20, 'cached_input_tokens': 0}}), flush=True)
