"""Exercise the actual proxy and SDK with isolated, stateless fake exec commands."""
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


def progress(text):
    with (OUT / 'progress.log').open('a') as output:
        output.write(str(time.time()) + ' ' + text + '\n')
    print(text, flush=True)


progress('Importing the candidate HTTP bridge')
import uvicorn
sys.path.insert(0, '/tmp/probe/preflight/exec_action_probe')
from codex_exec_bridge import CodexExecBridge, create_app

FIXTURE = '/app/fixture Ω "quoted".txt'
TEXT = 'OFFLINE_READ_OK café Ω\nLiteral "quotes" and backslash \\ preserved.\n'
COMMENTARY = 'Run the independent checks; preserve café Ω, quotes, and backslashes.'
subprocess.run(['git', 'init', '-q', '/app'], check=True)
subprocess.run(['git', '-C', '/app', 'config', 'user.email', 'offline@example.invalid'], check=True)
subprocess.run(['git', '-C', '/app', 'config', 'user.name', 'Offline fixture'], check=True)
Path(FIXTURE).write_text(TEXT)
subprocess.run(['git', '-C', '/app', 'add', '.'], check=True)
subprocess.run(['git', '-C', '/app', 'commit', '-qm', 'Offline fixture'], check=True)
base = subprocess.check_output(['git', '-C', '/app', 'rev-parse', 'HEAD'], text=True).strip()
bridge = CodexExecBridge(OUT / 'bridge', command=['/opt/python3.12-tmp/bin/python3', '/tmp/fake_exec.py'])
server = uvicorn.Server(uvicorn.Config(create_app(bridge), host='127.0.0.1', port=8767, log_level='warning'))
threading.Thread(target=server.run, daemon=True).start()
proxy_log = (OUT / 'proxy.log').open('wb')
progress('Starting the actual LiteLLM proxy CLI')
proxy = subprocess.Popen(['/opt/python3.12-tmp/bin/litellm', '--config', '/tmp/config.yaml', '--host', '127.0.0.1', '--port', '8768'], env=dict(os.environ, PYTHONPATH='/tmp', PYTHONUNBUFFERED='1', LITELLM_LOCAL_MODEL_COST_MAP='True'), stdout=proxy_log, stderr=subprocess.STDOUT)
result = {'passed': False, 'real_model_calls': 0, 'synthetic_usage_excluded': True, 'network': 'none', 'validation_scope': 'real Claude SDK -> actual LiteLLM proxy CLI -> unchanged exec action adapter -> independent fake local commands', 'litellm_version': importlib.metadata.version('litellm'), 'sdk_version': importlib.metadata.version('claude-agent-sdk'), 'disable_auto_compact_env': os.getenv('DISABLE_AUTO_COMPACT'), 'phases': []}
all_blocks = []


async def compact_and_continue(session):
    from claude_agent_sdk import ClaudeSDKClient
    from sdk_script import create_agent_options
    options = create_agent_options('/app', resume_session_id=session)
    options.extra_args = {'debug-file': str(OUT / 'compact_sdk_debug.log')}
    rows = []
    async with ClaudeSDKClient(options=options) as client:
        for phase, prompt in [('compact', '/compact'), ('continued', 'OFFLINE_EXEC_CONTINUED: Read the escaped fixture after compaction and report completion.')]:
            started = time.monotonic()
            await client.query(prompt)
            phase_rows = []
            async for message in client.receive_response():
                row = {'phase': phase, 'type': type(message).__name__, 'message': asdict(message)}
                rows.append(row)
                phase_rows.append(row)
            finals = [row['message'] for row in phase_rows if row['type'] == 'ResultMessage']
            assert finals and all(not value['is_error'] for value in finals), phase_rows
            assert all(value['session_id'] == session for value in finals)
            if phase == 'compact':
                assert any(row['type'] == 'SystemMessage' and row['message']['subtype'] == 'compact_boundary' for row in phase_rows), phase_rows
            else:
                assert 'OFFLINE_EXEC_COMPLETE_CONTINUED' in finals[-1]['result'], finals
            result['phases'].append({'phase': phase, 'sdk_session_id': session, 'completed': True, 'wall_seconds': time.monotonic() - started})
            progress('SDK phase passed: ' + phase)
    (OUT / 'compact_sdk_messages.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    return rows


def request_dynamic(tools, messages):
    body = {'model': 'gpt-6.1-terra', 'messages': messages, 'tools': tools, 'stream': False, 'tool_choice': 'auto'}
    request = urllib.request.Request('http://127.0.0.1:8767/sessions/offline-dynamic/teacher/review/v1/chat/completions', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return body, json.load(response)


try:
    proxy_started = time.monotonic()
    for waited in range(600):
        assert proxy.poll() is None, ('Proxy startup exit', proxy.returncode)
        try:
            urllib.request.urlopen('http://127.0.0.1:8768/health/liveliness', timeout=1).read()
            break
        except OSError:
            if waited % 30 == 0:
                progress('Waiting for actual proxy startup: ' + str(waited) + ' seconds')
            time.sleep(1)
    else:
        raise AssertionError('Full proxy did not become ready within 600 seconds')
    result['proxy_startup_seconds'] = time.monotonic() - proxy_started
    progress('Actual proxy ready; starting SDK initial and resume phases')
    session = None
    for phase in ('initial', 'resume'):
        prompt = Path('/tmp/' + phase + '_prompt.txt')
        prompt.write_text('OFFLINE_EXEC_' + phase.upper() + ': Run the controlled local checks and report completion. This is an offline transport test.\n')
        output = OUT / phase
        args = ['/opt/python3.12-tmp/bin/python3', '/tmp/sdk_script.py', '--cwd', '/app', '--base_commit', base, '--output_dir', str(output), '--log_path', str(OUT / (phase + '.log'))]
        args += ['--resume_session_id', session, '--extra_message_file', str(prompt)] if session else ['--problem_statement_file', str(prompt)]
        started = time.monotonic()
        completed = subprocess.run(args, capture_output=True, timeout=240)
        (OUT / (phase + '_stdout.log')).write_bytes(completed.stdout + completed.stderr)
        assert completed.returncode == 0, completed.stderr[-2000:]
        trajs = json.loads((output / 'trajs.json').read_text())
        meta = trajs['metadata']
        assert meta['status'] == 'completed' and not meta['ResultMessage']['is_error'], meta
        current = meta['ResultMessage']['session_id']
        if session:
            assert session == current
        session = current
        rows = [json.loads(line) for line in trajs['trajectories']['main_agent'].splitlines()]
        blocks = [block for row in rows for block in row['message'].get('content', []) if isinstance(block, dict)]
        all_blocks.extend(blocks)
        assert any(block.get('text') == COMMENTARY for block in blocks)
        assert 'OFFLINE_EXEC_COMPLETE_' + phase.upper() in meta['ResultMessage']['result']
        result['phases'].append({'phase': phase, 'sdk_session_id': current, 'completed': True, 'wall_seconds': time.monotonic() - started})
        progress('SDK phase passed: ' + phase)
    compact_rows = asyncio.run(compact_and_continue(session))
    all_blocks.extend(block for row in compact_rows for block in row['message'].get('content', []) if isinstance(block, dict))
    requests = [json.loads(line) for line in (OUT / 'bridge/model_requests.jsonl').read_text().splitlines()]
    first_tools = [tool for tool in requests[0]['request']['tools'] if tool['function']['name'] != 'Monitor']
    monitor = {'type': 'function', 'function': {'name': 'Monitor', 'description': 'Observe a controlled offline fixture.', 'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}}, 'required': ['path']}}}
    one, response_one = request_dynamic(first_tools, [{'role': 'user', 'content': 'OFFLINE_DYNAMIC_ONE'}])
    two, response_two = request_dynamic(first_tools + [monitor], one['messages'] + [response_one['choices'][0]['message'], {'role': 'user', 'content': 'OFFLINE_DYNAMIC_TWO'}])
    assert response_two['choices'][0]['message']['content'] == 'OFFLINE_DYNAMIC_COMPLETE'
    result['dynamic_tool_change'] = {'before_count': len(first_tools), 'after_count': len(first_tools) + 1, 'passed': True}
    requests = [json.loads(line) for line in (OUT / 'bridge/model_requests.jsonl').read_text().splitlines()]
    responses = [json.loads(line) for line in (OUT / 'bridge/model_responses.jsonl').read_text().splitlines()]
    calls = {call['id']: call for row in responses for call in row['response']['choices'][0]['message'].get('tool_calls', [])}
    returned = [block for block in all_blocks if 'tool_use_id' in block]
    assert len(returned) == 10 and {block['tool_use_id'] for block in returned} == set(calls), (len(returned), calls, returned)
    for block in returned:
        arguments = json.loads(calls[block['tool_use_id']]['function']['arguments'])
        failed = arguments.get('file_path') == '/app/definitely_missing.txt' or arguments.get('description') == 'Expected failure in resumed session'
        assert bool(block.get('is_error')) == failed, block
    assert any('EXPECTED_EXIT_SEVEN' in json.dumps(block) for block in returned)
    assert any('OFFLINE_READ_OK café Ω' in json.dumps(block, ensure_ascii=False) for block in returned)
    pids = []
    compacted_requests = []
    request_phases = []
    for row in requests:
        directory = OUT / 'bridge' / row['request_id']
        payload = json.loads((directory / 'stdin.json').read_text())
        body = row['request']
        expected = {'messages': body['messages'], 'tools': body.get('tools') or []}
        if 'tool_choice' in body:
            expected['tool_choice'] = body['tool_choice']
        assert payload == expected, row['request_id']
        invocation = json.loads((directory / 'invocation.json').read_text())
        pids.append(invocation['pid'])
        phase = (directory / 'fixture_phase.txt').read_text()
        request_phases.append(phase)
        if phase == 'continued':
            text = json.dumps(payload['messages'], ensure_ascii=False)
            assert 'COMPACTED_HISTORY_ONLY' in text
            assert 'OFFLINE_EXEC_INITIAL' not in text and 'OFFLINE_EXEC_RESUME' not in text
            compacted_requests.append(row['request_id'])
    assert len(pids) == len(set(pids)) == len(responses), pids
    assert len(compacted_requests) == 2
    assert request_phases.count('compact') == 1
    usage = [json.loads(line) for line in (OUT / 'bridge/token_usage.jsonl').read_text().splitlines()]
    assert len(usage) == len(requests)
    timings = {delay: json.loads(Path('/app/initial-' + str(delay) + '.json').read_text()) for delay in (2, 5)}
    assert all(values['finished'] - values['started'] >= delay - .2 for delay, values in timings.items())
    assert not bridge.stopped and not bridge.processes
    result.update(passed=True, sdk_session_id=session, sdk_tool_results=returned, request_count=len(requests), independent_exec_pids=pids, complete_payload_equality=True, compacted_requests=compacted_requests, request_phases=request_phases, synthetic_usage_events=len(usage), timing_fixtures=timings, bridge_state=bridge.status())
finally:
    result['proxy_exit_before_cleanup'] = proxy.poll()
    proxy.terminate()
    proxy.wait(timeout=15)
    proxy_log.close()
    server.should_exit = True
    (OUT / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    progress('Exec action full transport gate finished; passed=' + str(result['passed']))
