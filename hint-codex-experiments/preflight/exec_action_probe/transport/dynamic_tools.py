"""Check a real 17-to-18 tool change in independent fake exec requests."""
import asyncio
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / 'dynamic_tools'
OUT.mkdir(exist_ok=True)
spec = importlib.util.spec_from_file_location('exec_candidate', ROOT / 'preflight/exec_action_probe/codex_exec_bridge.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
script = OUT / 'fake_dynamic.py'
script.write_text('''import json,sys,os
from pathlib import Path
p=json.loads(sys.stdin.read());Path("stdin.json").write_text(json.dumps(p));text=json.dumps(p["messages"])
calls=[{"name":"Monitor","arguments":"{\\"command\\":\\"echo offline\\"}"}] if "REQUEST_MONITOR" in text else []
Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text(json.dumps({"content":"OFFLINE_DYNAMIC_COMPLETE","tool_calls":calls}))
print(json.dumps({"type":"thread.started","thread_id":"offline-"+str(os.getpid())}))
print(json.dumps({"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":20}}))
''')

async def main():
    source = ROOT / 'preflight/parallel_09_transport_audit/attempt_01/bridge/model_requests.jsonl'
    tools = json.loads(source.read_text().splitlines()[0])['request']['tools']
    without = [t for t in tools if t['function']['name'] != 'Monitor']
    assert len(tools) == 18 and len(without) == 17
    bridge = module.CodexExecBridge(OUT / 'bridge', command=[sys.executable, str(script)])
    one = {'messages': [{'role': 'user', 'content': 'OFFLINE_DYNAMIC_NO_MONITOR'}], 'tools': without, 'tool_choice': 'auto'}
    r1 = await bridge.chat(one)
    two = {'messages': one['messages'] + [r1['choices'][0]['message'], {'role': 'user', 'content': 'REQUEST_MONITOR'}], 'tools': tools, 'tool_choice': 'auto'}
    r2 = await bridge.chat(two)
    assert r2['choices'][0]['message']['tool_calls'][0]['function']['name'] == 'Monitor'
    rejected = False
    try:
        await bridge.chat({'messages': [{'role': 'user', 'content': 'REQUEST_MONITOR'}], 'tools': without})
    except module.CodexBridgeError as error:
        assert 'Unavailable SDK tool: Monitor' in str(error)
        rejected = True
    assert rejected
    requests = [json.loads(line) for line in (OUT / 'bridge/model_requests.jsonl').read_text().splitlines()]
    for row in requests:
        body = row['request']
        expected = {'messages': body['messages'], 'tools': body['tools']}
        if 'tool_choice' in body:
            expected['tool_choice'] = body['tool_choice']
        assert json.loads((OUT / 'bridge' / row['request_id'] / 'stdin.json').read_text()) == expected
    result = {'passed': True, 'real_model_calls': 0, 'network_used': False, 'before_tools': 17, 'after_tools': 18, 'new_monitor_action_accepted': True, 'unavailable_monitor_rejected': True, 'complete_payload_equality': True, 'scope': 'actual adapter subprocess boundary, fake exec, no SDK tool execution in this supplemental probe'}
    (OUT / 'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
    await bridge.close()

asyncio.run(main())
