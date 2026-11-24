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
else:
    index=1+sum(message.get('role')=='assistant' for message in payload['messages'])
    phase='accumulate_'+str(index)
    padding='Observed fixture history entry. '*3200
    calls=[{'name':'Read','arguments':json.dumps({'file_path':'/app/fixture.txt'})}]
    if index==1:
        calls += [{'name':'Bash','arguments':json.dumps({'command':'printf OFFLINE_BASH_OK','description':'Successful offline tool','timeout':30000})}, {'name':'Bash','arguments':json.dumps({'command':'printf OFFLINE_BASH_FAIL; exit 7','description':'Expected offline failure','timeout':30000})}]
    action={'content':padding,'tool_calls':calls}
Path('phase.txt').write_text(phase)
Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text(json.dumps(action))
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':20000+(index-1)*25000 if phase.startswith('accumulate_') else 100,'output_tokens':25000 if phase.startswith('accumulate_') else 20,'cached_input_tokens':0}}),flush=True)
