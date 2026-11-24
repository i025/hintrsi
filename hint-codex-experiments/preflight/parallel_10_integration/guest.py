"""Check context-error restoration through the actual LiteLLM proxy and SDK."""
import asyncio
import importlib.metadata
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import asdict
from pathlib import Path

OUT=Path('/tmp/transport_audit_out'); OUT.mkdir()
def progress(text):
    with (OUT/'progress.log').open('a') as f:f.write(str(time.time())+' '+text+'\n')
    print(text,flush=True)
progress('Importing candidate and starting local bridge')
import uvicorn
sys.path.insert(0,'/tmp/production')
from codex_cli_bridge import CodexBridge,create_app
bridge=CodexBridge(OUT/'bridge',command=['/opt/python3.12-tmp/bin/python3','/tmp/fake_exec.py'])
app=create_app(bridge)
@app.middleware('http')
async def record_status(request,call_next):
    response=await call_next(request)
    with (OUT/'http_outcomes.jsonl').open('a') as f:f.write(json.dumps({'path':request.url.path,'status':response.status_code})+'\n')
    return response
server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8767,log_level='warning'))
threading.Thread(target=server.run,daemon=True).start()
Path('/app/fixture.txt').write_text('READ_BEFORE_REACTIVE_COMPACT\n')
proxy_log=(OUT/'proxy.log').open('wb')
proxy=subprocess.Popen(['/opt/python3.12-tmp/bin/litellm','--config','/tmp/config.yaml','--host','127.0.0.1','--port','8768'],env=dict(os.environ,PYTHONPATH='/tmp',PYTHONUNBUFFERED='1',LITELLM_LOCAL_MODEL_COST_MAP='True'),stdout=proxy_log,stderr=subprocess.STDOUT)
result={'passed':False,'real_model_calls':0,'synthetic_usage_excluded':True,'network':'none','disable_auto_compact_env':os.getenv('DISABLE_AUTO_COMPACT'),'auto_compact_window_env':'400000','trigger':'SDK proactively compacts accumulated assistant/tool history using production configured window=400000; no context error or manual compact','sdk_version':importlib.metadata.version('claude-agent-sdk'),'litellm_version':importlib.metadata.version('litellm')}
async def run_sdk():
    from claude_agent_sdk import ClaudeSDKClient
    from sdk_script import create_agent_options
    options=create_agent_options('/app');options.extra_args={'debug-file':str(OUT/'sdk_debug.log')}
    rows=[]
    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query('Read /app/fixture.txt and report completion. This is an offline compaction transport fixture.')
            async for message in client.receive_response():
                rows.append({'type':type(message).__name__,'message':asdict(message)})
    finally:
        (OUT/'sdk_messages.json').write_text(json.dumps(rows,indent=2))
    return rows
try:
    started=time.monotonic()
    for waited in range(600):
        assert proxy.poll() is None,('Proxy exit',proxy.returncode)
        try:
            urllib.request.urlopen('http://127.0.0.1:8768/health/liveliness',timeout=1).read();break
        except OSError:
            if waited%30==0:progress('Waiting for local proxy: '+str(waited)+' seconds')
            time.sleep(1)
    else:raise AssertionError('Proxy startup timeout')
    result['proxy_startup_seconds']=time.monotonic()-started
    progress('Proxy ready; testing production SDK proactive auto compaction')
    rows=asyncio.run(asyncio.wait_for(run_sdk(),600))
    boundaries=[r['message']['data'] for r in rows if r['type']=='SystemMessage' and r['message']['subtype']=='compact_boundary']
    finals=[r['message'] for r in rows if r['type']=='ResultMessage']
    requests=[json.loads(x) for x in (OUT/'bridge/model_requests.jsonl').read_text().splitlines()]
    phases=[(OUT/'bridge'/r['request_id']/'phase.txt').read_text() for r in requests]
    outcomes=[json.loads(x) for x in (OUT/'http_outcomes.jsonl').read_text().splitlines()]
    usage=[json.loads(x) for x in (OUT/'bridge/token_usage.jsonl').read_text().splitlines()]
    result.update(compact_boundaries=boundaries,finals=finals,request_phases=phases,http_outcomes=outcomes,usage_event_count=len(usage),synthetic_tokens=sum(u['delta']['totalTokens'] for u in usage))
    assert boundaries and all(b['compact_metadata']['trigger']=='auto' for b in boundaries),boundaries
    assert finals and not finals[-1]['is_error'] and 'OFFLINE_REACTIVE_COMPLETE' in finals[-1]['result'],finals
    assert all(r['status']==200 for r in outcomes),outcomes
    assert phases[0]=='accumulate_1' and phases[-2:]==['compact','after_compact'],phases
    assert boundaries[0]['compact_metadata']['pre_tokens']>=350000,boundaries
    assert 'compact' in phases and phases[-1]=='after_compact',phases
    sdk_usage=finals[-1]['usage']
    assert sdk_usage['input_tokens']>0 and sdk_usage['output_tokens']>0,sdk_usage
    responses=[json.loads(x) for x in (OUT/'bridge/model_responses.jsonl').read_text().splitlines()]
    calls={call['id']:call for response in responses for call in response['response']['choices'][0]['message'].get('tool_calls',[])}
    returned=[block for row in rows for block in row['message'].get('content',[]) if isinstance(block,dict) and 'tool_use_id' in block]
    assert len(returned)>=10 and {block['tool_use_id'] for block in returned}==set(calls),(calls,returned)
    for block in returned:
        args=json.loads(calls[block['tool_use_id']]['function']['arguments'])
        assert bool(block.get('is_error'))==('exit 7' in args.get('command','')),block
    assert any('OFFLINE_BASH_OK' in json.dumps(block) for block in returned),returned
    assert any('OFFLINE_BASH_FAIL' in json.dumps(block) for block in returned),returned
    result.update(sdk_usage=sdk_usage,tool_calls=calls,tool_results=returned,reported_usage_unknown=[r['request_id'] for r in requests if r['request_id'] not in {u['request_id'] for u in usage}])
    result['passed']=True
finally:
    result['proxy_exit_before_cleanup']=proxy.poll()
    proxy.terminate();proxy.wait(timeout=15);proxy_log.close();server.should_exit=True
    (OUT/'result.json').write_text(json.dumps(result,indent=2))
    progress('Context gate finished: '+str(result['passed']))
