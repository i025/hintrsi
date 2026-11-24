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
sys.path.insert(0,'/tmp/probe/preflight/exec_action_probe')
from codex_exec_bridge import CodexExecBridge,create_app
bridge=CodexExecBridge(OUT/'bridge',command=['/opt/python3.12-tmp/bin/python3','/tmp/fake_exec.py'])
app=create_app(bridge)
request_limit=threading.Event()
accepted_requests=0
@app.middleware('http')
async def record_status(request,call_next):
    global accepted_requests
    if accepted_requests >= 10:
        from fastapi.responses import JSONResponse
        request_limit.set()
        return JSONResponse({'error':{'message':'Offline fixture request cap reached'}},status_code=400)
    accepted_requests += 1
    response=await call_next(request)
    if accepted_requests >= 10:
        request_limit.set()
    with (OUT/'http_outcomes.jsonl').open('a') as f:f.write(json.dumps({'path':request.url.path,'status':response.status_code})+'\n')
    return response
server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8767,log_level='warning'))
threading.Thread(target=server.run,daemon=True).start()
Path('/app/fixture.txt').write_text('READ_BEFORE_REACTIVE_COMPACT\n')
proxy_log=(OUT/'proxy.log').open('wb')
proxy=subprocess.Popen(['/opt/python3.12-tmp/bin/litellm','--config','/tmp/config.yaml','--host','127.0.0.1','--port','8768'],env=dict(os.environ,PYTHONPATH='/tmp',PYTHONUNBUFFERED='1',LITELLM_LOCAL_MODEL_COST_MAP='True'),stdout=proxy_log,stderr=subprocess.STDOUT)
result={'passed':False,'real_model_calls':0,'synthetic_usage_excluded':True,'network':'none','disable_auto_compact_env':os.getenv('DISABLE_AUTO_COMPACT'),'auto_compact_window_env':os.getenv('CLAUDE_CODE_AUTO_COMPACT_WINDOW'),'trigger':'initial Read then context 400; every SDK summary request also returns explicit context 400; no manual /compact','sdk_version':importlib.metadata.version('claude-agent-sdk'),'litellm_version':importlib.metadata.version('litellm')}
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
async def run_bounded_sdk():
    task=asyncio.create_task(run_sdk())
    started=time.monotonic()
    while not task.done():
        if request_limit.is_set() or time.monotonic()-started >= 90:
            reason='fixture_request_limit' if request_limit.is_set() else 'fixture_90_second_timeout'
            result['fixture_stop_reason']=reason
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception) as exc:
                result['cancel_exception']=type(exc).__name__
            return json.loads((OUT/'sdk_messages.json').read_text())
        await asyncio.wait({task},timeout=.1)
    result['sdk_wall_seconds']=time.monotonic()-started
    try:
        return task.result()
    except Exception as exc:
        result['sdk_exception']={'type':type(exc).__name__,'message':str(exc)}
        return json.loads((OUT/'sdk_messages.json').read_text())
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
    progress('Proxy ready; testing SDK reactive auto compaction')
    rows=asyncio.run(run_bounded_sdk())
    boundaries=[r['message']['data'] for r in rows if r['type']=='SystemMessage' and r['message']['subtype']=='compact_boundary']
    finals=[r['message'] for r in rows if r['type']=='ResultMessage']
    requests=[json.loads(x) for x in (OUT/'bridge/model_requests.jsonl').read_text().splitlines()]
    phases=[(OUT/'bridge'/r['request_id']/'phase.txt').read_text() for r in requests]
    outcomes=[json.loads(x) for x in (OUT/'http_outcomes.jsonl').read_text().splitlines()]
    usage=[json.loads(x) for x in (OUT/'bridge/token_usage.jsonl').read_text().splitlines()]
    result.update(compact_boundaries=boundaries,finals=finals,request_phases=phases,http_outcomes=outcomes,usage_event_count=len(usage),synthetic_tokens=sum(u['delta']['totalTokens'] for u in usage))
    known={row['request_id'] for row in usage}
    result['reported_usage_unknown']=[row['request_id'] for row in requests if row['request_id'] not in known]
    result['request_details']=[{'request_id':row['request_id'],'phase':phase,'message_count':len(row['request']['messages']),'message_characters':len(json.dumps(row['request']['messages']))} for row,phase in zip(requests,phases)]
    result['normal_sdk_error_final']=bool(finals and finals[-1]['is_error'])
    result['accepted_model_requests']=accepted_requests
    result['bridge_processes_remaining']=len(bridge.processes)
    result['passed']='context_error' in phases and 'compact_context_error' in phases and len(requests)<=10 and not any(not x['is_error'] for x in finals)
    assert result['passed'],result
finally:
    result['proxy_exit_before_cleanup']=proxy.poll()
    proxy.terminate();proxy.wait(timeout=15);proxy_log.close();server.should_exit=True
    (OUT/'result.json').write_text(json.dumps(result,indent=2))
    progress('Context gate finished: '+str(result['passed']))
