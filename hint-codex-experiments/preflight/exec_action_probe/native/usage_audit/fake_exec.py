"""Emit exact CLI errors and summary actions for an offline SDK compaction gate."""
import json
import os
import sys
from pathlib import Path

payload=json.loads(sys.stdin.read())
Path('stdin.json').write_text(json.dumps(payload))
Path('invocation.json').write_text(json.dumps({'pid':os.getpid(),'argv':sys.argv}))
text=json.dumps(payload['messages'])
print(json.dumps({'type':'thread.started','thread_id':'offline-context-'+str(os.getpid())}),flush=True)
if 'Your task is to create a detailed summary of the conversation so far' in text:
    phase='compact'
    action={'content':'<summary>COMPACTED_CONTEXT_GATE. The fixture was read successfully. Complete the task by reporting OFFLINE_REACTIVE_COMPLETE.</summary>', 'tool_calls':[]}
elif 'COMPACTED_CONTEXT_GATE' in text:
    phase='after_compact'
    action={'content':'OFFLINE_REACTIVE_COMPLETE', 'tool_calls':[]}
elif any(m.get('role')=='tool' for m in payload['messages']):
    phase='context_error'
    Path('phase.txt').write_text(phase)
    provider={'error':{'type':'invalid_request_error','code':'context_length_exceeded',
        'message':'Your input exceeds the context window of this model. Please adjust your input and try again.','param':'input'}}
    print(json.dumps({'type':'turn.failed','error':{'message':json.dumps(provider)}}),flush=True)
    raise SystemExit(1)
else:
    phase='initial'
    action={'content':'Read the fixture.', 'tool_calls':[{'name':'Read','arguments':json.dumps({'file_path':'/app/fixture.txt'})}, {'name':'Bash','arguments':json.dumps({'command':'printf OFFLINE_BASH_OK','description':'Successful offline tool','timeout':30000})}, {'name':'Bash','arguments':json.dumps({'command':'printf OFFLINE_BASH_FAIL; exit 7','description':'Expected offline failure','timeout':30000})}]}
Path('phase.txt').write_text(phase)
Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text(json.dumps(action))
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':10000 if phase=='initial' else 100,'output_tokens':20,'cached_input_tokens':0}}),flush=True)
