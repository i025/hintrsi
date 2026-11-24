"""Exercise the unchanged OnlineTeacher hook with a local fake progress service."""
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

OUT = Path('/tmp/transport_audit_out')
OUT.mkdir()
HINT = 'Before concluding, compare the boundary conditions in the collected observations and verify that the relevant cases are covered.'


def progress(text):
    with (OUT / 'progress.log').open('a') as output:
        output.write(str(time.time()) + ' ' + text + '\n')
    print(text, flush=True)


progress('Starting isolated bridge and fake teacher progress service')
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
sys.path.insert(0, '/tmp/probe/preflight/exec_action_probe')
from codex_exec_bridge import CodexExecBridge, create_app
from sdk_script import OnlineTeacher, create_agent_options

bridge = CodexExecBridge(OUT / 'bridge', command=['/opt/python3.12-tmp/bin/python3', '/tmp/fake_exec.py'])
app = create_app(bridge)
entry_requests = []


@app.middleware('http')
async def limit_fixture_requests(request, call_next):
    if request.url.path.endswith('/chat/completions'):
        entry_requests.append({'timestamp': time.time(), 'path': request.url.path})
        (OUT / 'entry_requests.json').write_text(json.dumps(entry_requests, indent=2))
        if len(entry_requests) > 6:
            return JSONResponse({'error': {'message': 'Offline fixture request cap reached'}}, status_code=503)
    return await call_next(request)


teacher_app = FastAPI()
teacher_requests = []


@teacher_app.post('/experiment/progress')
async def teacher_progress(request: Request):
    payload = await request.json()
    teacher_requests.append({'timestamp': time.time(), 'payload': payload})
    (OUT / 'teacher_requests.json').write_text(json.dumps(teacher_requests, indent=2))
    return {'hint': HINT, 'stopped': False}


servers = [uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8767, log_level='warning')),
           uvicorn.Server(uvicorn.Config(teacher_app, host='127.0.0.1', port=8766, log_level='warning'))]
for server in servers:
    threading.Thread(target=server.run, daemon=True).start()
folder = Path('/app/observations')
folder.mkdir()
for i in range(20):
    (folder / ('observation_' + str(i).zfill(2) + '.txt')).write_text('OFFLINE_OBSERVATION_' + str(i).zfill(2) + ': A controlled observation for the transport fixture.\n')
student = OUT / 'student'
student.mkdir()
teacher = OnlineTeacher('http://127.0.0.1:8766/experiment/progress', 'offline-online-hint', 'offline-injection-fixture', student)
proxy_log = (OUT / 'proxy.log').open('wb')
proxy = subprocess.Popen(['/opt/python3.12-tmp/bin/litellm', '--config', '/tmp/config.yaml', '--host', '127.0.0.1', '--port', '8768'], env=dict(os.environ, PYTHONPATH='/tmp', PYTHONUNBUFFERED='1', LITELLM_LOCAL_MODEL_COST_MAP='True'), stdout=proxy_log, stderr=subprocess.STDOUT)
result = {'passed': False, 'real_model_calls': 0, 'synthetic_usage_excluded': True, 'network': 'none', 'scope': 'mechanical hint injection, not real teacher selection or hint effectiveness', 'model_request_cap': 6, 'sdk_timeout_seconds': 90, 'sdk_version': importlib.metadata.version('claude-agent-sdk'), 'litellm_version': importlib.metadata.version('litellm'), 'sdk_source_unchanged': True, 'teacher_policy_unchanged': True, 'disable_auto_compact_env': os.getenv('DISABLE_AUTO_COMPACT')}


async def run_sdk():
    from claude_agent_sdk import ClaudeSDKClient
    options = create_agent_options('/app', online_teacher=teacher)
    options.extra_args = {'debug-file': str(OUT / 'sdk_debug.log')}
    rows = []
    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query('Read each numbered observation file in /app/observations and report completion after any runtime guidance. This is an offline transport fixture.')
            async for message in client.receive_response():
                rows.append({'type': type(message).__name__, 'message': asdict(message)})
    finally:
        (OUT / 'sdk_messages.json').write_text(json.dumps(rows, indent=2))
    return rows


try:
    started = time.monotonic()
    for waited in range(600):
        assert proxy.poll() is None, ('Proxy exit', proxy.returncode)
        try:
            urllib.request.urlopen('http://127.0.0.1:8768/health/liveliness', timeout=1).read()
            break
        except OSError:
            if waited % 30 == 0:
                progress('Waiting for local proxy: ' + str(waited) + ' seconds')
            time.sleep(1)
    else:
        raise AssertionError('Proxy startup timeout')
    result['proxy_startup_seconds'] = time.monotonic() - started
    progress('Proxy ready; executing 20 real SDK Read tools')
    started = time.monotonic()
    rows = asyncio.run(asyncio.wait_for(run_sdk(), 90))
    result['sdk_wall_seconds'] = time.monotonic() - started
    finals = [row['message'] for row in rows if row['type'] == 'ResultMessage']
    requests = [json.loads(x) for x in (OUT / 'bridge/model_requests.jsonl').read_text().splitlines()]
    responses = [json.loads(x) for x in (OUT / 'bridge/model_responses.jsonl').read_text().splitlines()]
    usage = [json.loads(x) for x in (OUT / 'bridge/token_usage.jsonl').read_text().splitlines()]
    assert finals and not finals[-1]['is_error'] and finals[-1]['result'] == 'OFFLINE_INJECTION_COMPLETE', finals
    assert len(requests) == len(entry_requests) == 2
    assert len(teacher_requests) == 1 and teacher_requests[0]['payload']['tool_count'] == 20, teacher_requests
    assert teacher.tool_count == 20 and teacher.checks == 1 and not teacher.error and not teacher.inflight
    messages = requests[1]['request']['messages']
    text = json.dumps(messages)
    observations = [m for m in messages if m['role'] == 'tool']
    calls = {call['id']: call for call in responses[0]['response']['choices'][0]['message']['tool_calls']}
    assert len(observations) == 20 and {m['tool_call_id'] for m in observations} == set(calls)
    assert all(call['function']['name'] == 'Read' for call in calls.values())
    assert all(not m.get('is_error') for m in observations)
    assert all('OFFLINE_OBSERVATION_' + str(i).zfill(2) in text for i in range(20))
    assert 'Teacher guidance:' in text and HINT in text
    assert sum(HINT in json.dumps(m) for m in messages) == 1
    assert len(usage) == 2 and sum(u['delta']['totalTokens'] for u in usage) == 240
    assert finals[-1]['usage']['input_tokens'] == 200 and finals[-1]['usage']['output_tokens'] == 40
    assert not bridge.stopped and not bridge.processes
    result.update(passed=True, sdk_final=finals[-1], teacher_state=json.loads((student / 'online_teacher_state.json').read_text()), teacher_request_count=len(teacher_requests), request_count=len(requests), next_request_id=requests[1]['request_id'], matching_tool_ids=sorted(calls), all_twenty_observations_present=True, hint_present_once=True, hint=HINT, synthetic_tokens=240)
finally:
    result['proxy_exit_before_cleanup'] = proxy.poll()
    proxy.terminate()
    proxy.wait(timeout=15)
    proxy_log.close()
    for server in servers:
        server.should_exit = True
    (OUT / 'result.json').write_text(json.dumps(result, indent=2))
    progress('Online hint injection gate finished: ' + str(result['passed']))
