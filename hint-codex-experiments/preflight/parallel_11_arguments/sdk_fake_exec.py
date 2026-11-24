"""Local model fixture; original SDK executes every emitted operation."""
import json
import os
import sys
from pathlib import Path
import jsonschema


def entries(value):
    if isinstance(value,dict):return {'entries':[{'key':k,'value':entries(v)} for k,v in value.items()]}
    if isinstance(value,list):return [entries(v) for v in value]
    return value

payload=json.load(sys.stdin)
cases=json.loads(Path('/tmp/sdk_cases.json').read_text())['cases']
observations=[m for m in payload['messages'] if m['role']=='tool']
if not observations:phase='initial'
elif len(observations)==4:phase='edit'
elif len(observations)==5:phase='verify'
else:phase='final'
action={'content':'OFFLINE_ARGUMENTS_COMPLETE' if phase=='final' else 'Execute controlled '+phase+' operations.',
        'tool_calls':[{'name':t['name'],'arguments':entries(t['arguments'])} for t in cases.get(phase,[])]}
jsonschema.validate(action,json.loads(Path(sys.argv[sys.argv.index('--output-schema')+1]).read_text()))
Path('phase.txt').write_text(phase)
Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text(json.dumps(action,ensure_ascii=False))
print(json.dumps({'type':'thread.started','thread_id':'offline-arguments-'+str(os.getpid())}),flush=True)
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':100,'output_tokens':20,'cached_input_tokens':0}}),flush=True)
