"""Check literal arguments through candidate, full proxy and actual SDK offline."""
import asyncio
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import asdict
from pathlib import Path
import uvicorn

OUT=Path('/tmp/transport_audit_out');OUT.mkdir()
sys.path.insert(0,'/tmp/production')
from codex_cli_bridge import CodexBridge,create_app
from sdk_script import create_agent_options
cases=json.loads(Path('/tmp/sdk_cases.json').read_text())
Path('/app/fixture.txt').write_text(cases['original'])
bridge=CodexBridge(OUT/'bridge',command=['/opt/python3.12-tmp/bin/python3','/tmp/fake_exec.py'])
server=uvicorn.Server(uvicorn.Config(create_app(bridge),host='127.0.0.1',port=8767,log_level='warning'))
threading.Thread(target=server.run,daemon=True).start()
stream=(OUT/'proxy.log').open('wb')
proxy=subprocess.Popen(['/opt/python3.12-tmp/bin/litellm','--config','/tmp/config.yaml','--host','127.0.0.1','--port','8768'],env=dict(os.environ,PYTHONPATH='/tmp',PYTHONUNBUFFERED='1',LITELLM_LOCAL_MODEL_COST_MAP='True'),stdout=stream,stderr=subprocess.STDOUT)
record={'passed':False,'real_model_calls':0,'network':'none','synthetic_usage_excluded':True,'source':'source_parallel_11'}

async def run():
    from claude_agent_sdk import ClaudeSDKClient
    messages=[]
    try:
        async with ClaudeSDKClient(options=create_agent_options('/app')) as client:
            await client.query('Read the fixture, search literal regular-expression characters, update its quoted line and verify the exact resulting content. This is an offline argument transport test.')
            async for message in client.receive_response():messages.append({'type':type(message).__name__,'message':asdict(message)})
    finally:(OUT/'sdk_messages.json').write_text(json.dumps(messages,ensure_ascii=False,indent=2))
    return messages

try:
    start=time.monotonic()
    for waited in range(600):
        assert proxy.poll() is None,proxy.returncode
        try:urllib.request.urlopen('http://127.0.0.1:8768/health/liveliness',timeout=1).read();break
        except OSError:
            if waited%30==0:print('Waiting for proxy:',waited,flush=True)
            time.sleep(1)
    else:raise AssertionError('Proxy startup timeout')
    record['proxy_startup_seconds']=time.monotonic()-start
    start=time.monotonic();messages=asyncio.run(asyncio.wait_for(run(),180));record['sdk_wall_seconds']=time.monotonic()-start
    def rows(name):return [json.loads(x) for x in (OUT/'bridge'/name).read_text().splitlines()]
    requests=rows('model_requests.jsonl');responses=rows('model_responses.jsonl');usage=rows('token_usage.jsonl')
    phases=[(OUT/'bridge'/q['request_id']/'phase.txt').read_text() for q in requests]
    calls=[c for q in responses for c in q['response']['choices'][0]['message'].get('tool_calls',[])]
    expected=[c for phase in ('initial','edit','verify') for c in cases['cases'][phase]]
    assert phases==['initial','edit','verify','final'],phases
    assert [{'name':c['function']['name'],'arguments':json.loads(c['function']['arguments'])} for c in calls]==expected
    results=[block for q in messages for block in q['message'].get('content',[]) if isinstance(block,dict) and 'tool_use_id' in block]
    assert len(results)==6 and {b['tool_use_id'] for b in results}=={c['id'] for c in calls},results
    failures=[b for b in results if b.get('is_error')]
    assert len(failures)==1 and 'EXPECTED_FAILURE' in json.dumps(failures),failures
    assert 'executeChat(' in json.dumps(results) and 'CLAUDE.md' in json.dumps(results)
    assert any('SDK_ARGUMENTS_CHECK_OK' in json.dumps(b) for b in results),results
    final=next(m['message'] for m in messages if m['type']=='ResultMessage')
    assert not final['is_error'] and final['result']=='OFFLINE_ARGUMENTS_COMPLETE',final
    assert Path('/app/fixture.txt').read_text()==cases['expected']
    assert len(usage)==4 and sum(u['delta']['totalTokens'] for u in usage)==480
    errors=OUT/'bridge/model_errors.jsonl';assert not errors.exists() or not errors.read_text().strip()
    record.update(passed=True,request_count=4,tool_count=6,expected_tool_failures=1,bridge_errors=0,
                  exact_arguments_preserved=True,exact_edit_verified=True,phases=phases,synthetic_tokens=480,sdk_final=final)
finally:
    proxy.terminate();proxy.wait(timeout=15);stream.close();server.should_exit=True
    (OUT/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in record.items() if k!='sdk_final'}),flush=True)
