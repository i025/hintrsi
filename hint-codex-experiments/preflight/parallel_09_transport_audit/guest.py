"""Run the real proxy, bridge HTTP endpoint, and SDK against controlled RPC events."""
import importlib.metadata
import json
import os
import shlex
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

OUT = Path('/tmp/transport_audit_out')
OUT.mkdir()

def progress(text):
    with (OUT / 'progress.log').open('a') as output:
        output.write(str(time.time()) + ' ' + text + '\n')
    print(text, flush=True)

progress('Importing the actual bridge HTTP server')
import uvicorn
from codex_cli_bridge import CodexBridge, create_app

FIXTURE = '/app/fixture Ω "quoted".txt'
TEXT = 'OFFLINE_READ_OK café Ω\nLiteral "quotes" and backslash \\ preserved.\n'
COMMENTARY = 'Run the independent checks; preserve café Ω, quotes, and backslashes.'


def command(program):
    return '/opt/python3.12-tmp/bin/python3 -c ' + shlex.quote(program)


def write_after(phase, delay):
    name = '/app/' + phase + '-' + str(delay) + '.json'
    program = 'import json,time; from pathlib import Path; started=time.time(); time.sleep(' + str(delay) + '); Path(' + repr(name) + ').write_text(json.dumps({"started":started,"finished":time.time()})); print("WRITE_' + str(delay) + '_OK")'
    return {'command': command(program), 'description': 'Write an independent timing fixture', 'timeout': 30000}


class ControlledRPC:
    def __init__(self):
        self.event_callback = None
        self.threads = {}
        self.calls = {}
        self.next_id = 100
        self.ledger = []

    def record(self, kind, value):
        row = {'timestamp': time.time(), 'kind': kind, **value}
        self.ledger.append(row)
        with (OUT / 'rpc_ledger.jsonl').open('a') as output:
            output.write(json.dumps(row, ensure_ascii=False) + '\n')

    def emit(self, event):
        self.event_callback(event)

    async def start(self):
        self.record('start', {})

    async def close(self):
        pass

    async def request(self, method, params):
        self.record('request', {'method': method, 'params': params})
        if method == 'thread/start':
            thread = 'offline-thread-' + str(len(self.threads))
            names = [tool['name'] for tool in params['dynamicTools']]
            self.threads[thread] = {'turns': 0, 'main': 'Read' in names and 'Bash' in names}
            return {'thread': {'id': thread}, 'model': 'gpt-6.1-terra'}
        if method == 'turn/start':
            thread = params['threadId']
            state = self.threads[thread]
            state['turns'] += 1
            state['turn'] = thread + '-turn-' + str(state['turns'])
            state['phase'] = 'initial' if state['turns'] == 1 else 'resume'
            state['stage'] = 0
            self.emit({'method': 'turn/started', 'params': {'threadId': thread, 'turn': {'id': state['turn']}}})
            self.emit_stage(thread)
            return {'turn': {'id': state['turn']}}
        if method == 'turn/steer':
            return {'turnId': params['expectedTurnId']}
        if method == 'turn/interrupt':
            return {}
        raise AssertionError('Unexpected offline RPC: ' + method)

    def emit_stage(self, thread):
        state = self.threads[thread]
        phase = state['phase']
        stage = state['stage']
        tools = []
        if state['main'] and stage == 0:
            self.emit({'method': 'item/completed', 'params': {'threadId': thread, 'turnId': state['turn'], 'item': {'type': 'agentMessage', 'text': COMMENTARY}}})
            if phase == 'initial':
                tools = [('read', 'Read', {'file_path': FIXTURE}),
                         ('write8', 'Bash', write_after(phase, 8)),
                         ('write20', 'Bash', write_after(phase, 20)),
                         ('missing', 'Read', {'file_path': '/app/definitely_missing.txt'})]
            else:
                tools = [('read', 'Read', {'file_path': FIXTURE}),
                         ('inspect', 'Bash', {'command': command('from pathlib import Path; print(Path(' + repr(FIXTURE) + ').read_text(),end="")'), 'description': 'Read the escaped fixture', 'timeout': 30000}),
                         ('fail', 'Bash', {'command': command('print("EXPECTED_EXIT_SEVEN"); raise SystemExit(7)'), 'description': 'Check an expected command failure', 'timeout': 30000})]
        elif state['main'] and stage == 1 and phase == 'initial':
            tools = [('verify8', 'Read', {'file_path': '/app/initial-8.json'}),
                     ('verify20', 'Read', {'file_path': '/app/initial-20.json'})]
        if tools:
            state['waiting'] = set()
            for suffix, name, arguments in tools:
                self.next_id += 1
                call_id = phase + '-' + suffix
                request_id = self.next_id
                state['waiting'].add(request_id)
                self.calls[request_id] = {'thread': thread, 'call_id': call_id, 'tool': name, 'arguments': arguments}
                self.emit({'id': request_id, 'method': 'item/tool/call', 'params': {'threadId': thread, 'turnId': state['turn'], 'callId': call_id, 'tool': name, 'arguments': arguments}})
            return
        self.emit({'method': 'item/completed', 'params': {'threadId': thread, 'turnId': state['turn'], 'item': {'type': 'agentMessage', 'text': 'OFFLINE_FULL_PROXY_COMPLETE_' + phase.upper()}}})
        self.emit({'method': 'turn/completed', 'params': {'threadId': thread, 'turn': {'id': state['turn'], 'status': 'completed', 'error': None}}})

    async def respond(self, request_id, result):
        call = self.calls[request_id]
        self.record('tool_response', {'request_id': request_id, **call, 'result': result})
        state = self.threads[call['thread']]
        state['waiting'].remove(request_id)
        if not state['waiting']:
            state['stage'] += 1
            self.emit_stage(call['thread'])


subprocess.run(['git', 'init', '-q', '/app'], check=True)
subprocess.run(['git', '-C', '/app', 'config', 'user.email', 'offline@example.invalid'], check=True)
subprocess.run(['git', '-C', '/app', 'config', 'user.name', 'Offline fixture'], check=True)
Path(FIXTURE).write_text(TEXT)
subprocess.run(['git', '-C', '/app', 'add', '.'], check=True)
subprocess.run(['git', '-C', '/app', 'commit', '-qm', 'Offline fixture'], check=True)
base = subprocess.check_output(['git', '-C', '/app', 'rev-parse', 'HEAD'], text=True).strip()
rpc = ControlledRPC()
bridge = CodexBridge(OUT / 'bridge', rpc=rpc)
server = uvicorn.Server(uvicorn.Config(create_app(bridge), host='127.0.0.1', port=8767, log_level='warning'))
threading.Thread(target=server.run, daemon=True).start()
proxy_log = (OUT / 'proxy.log').open('wb')
progress('Starting the actual LiteLLM proxy CLI')
proxy = subprocess.Popen(['/opt/python3.12-tmp/bin/litellm', '--config', '/tmp/config.yaml', '--host', '127.0.0.1', '--port', '8768'], env=dict(os.environ, PYTHONPATH='/tmp', PYTHONUNBUFFERED='1', LITELLM_LOCAL_MODEL_COST_MAP='True'), stdout=proxy_log, stderr=subprocess.STDOUT)
result = {'passed': False, 'real_model_calls': 0, 'synthetic_usage_excluded': True, 'network': 'none', 'validation_scope': 'real SDK -> actual LiteLLM proxy CLI -> actual bridge.chat/_sse -> controlled RPC; no real Codex model', 'litellm_version': importlib.metadata.version('litellm'), 'sdk_version': importlib.metadata.version('claude-agent-sdk'), 'phases': []}
try:
    proxy_started = time.monotonic()
    for _ in range(360):
        assert proxy.poll() is None, ('Proxy startup exit', proxy.returncode)
        try:
            urllib.request.urlopen('http://127.0.0.1:8768/health/liveliness', timeout=1).read()
            break
        except OSError:
            time.sleep(1)
    else:
        raise AssertionError('Full proxy did not become ready within the startup window')
    result['proxy_startup_seconds'] = time.monotonic() - proxy_started
    progress('Actual proxy ready; starting the SDK')
    session = None
    for phase in ('initial', 'resume'):
        prompt = Path('/tmp/' + phase + '_prompt.txt')
        prompt.write_text('Run the controlled local checks and report completion. This is an offline transport test.\n')
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
        assert any(block.get('text') == COMMENTARY for block in blocks)
        assert 'OFFLINE_FULL_PROXY_COMPLETE_' + phase.upper() in meta['ResultMessage']['result']
        result['phases'].append({'phase': phase, 'sdk_session_id': current, 'completed': True, 'wall_seconds': time.monotonic() - started})
        progress('SDK phase passed: ' + phase)
    returned = [row for row in rpc.ledger if row['kind'] == 'tool_response']
    expected_ids = {'initial-read', 'initial-write8', 'initial-write20', 'initial-missing', 'initial-verify8', 'initial-verify20', 'resume-read', 'resume-inspect', 'resume-fail'}
    assert {row['call_id'] for row in returned} == expected_ids
    assert len(returned) == len(expected_ids), 'Duplicate tool responses reached RPC'
    by_id = {row['call_id']: row for row in returned}
    for call_id, row in by_id.items():
        expected_success = call_id not in {'initial-missing', 'resume-fail'}
        assert row['result']['success'] == expected_success, row
    assert 'EXPECTED_EXIT_SEVEN' in json.dumps(by_id['resume-fail']['result'])
    assert 'OFFLINE_READ_OK café Ω' in json.dumps(by_id['resume-inspect']['result'], ensure_ascii=False)
    timing = {delay: json.loads(Path('/app/initial-' + str(delay) + '.json').read_text()) for delay in (8, 20)}
    for delay, values in timing.items():
        assert values['finished'] - values['started'] >= delay - 0.2
    result['tool_results'] = returned
    result['timing_fixtures'] = timing
    result['bridge_state'] = bridge.status()
    assert not bridge.stopped
    assert all(not state['pending'] and not state['active'] and not state['error'] for state in bridge.status()['sessions'])
    mains = [state for state in rpc.threads.values() if state['main']]
    assert len(mains) == 1 and mains[0]['turns'] == 2, mains
    requests = [json.loads(line) for line in (OUT / 'bridge/model_requests.jsonl').read_text().splitlines()]
    main_requests = [row['request'] for row in requests if 'Read' in {tool['function']['name'] for tool in row['request'].get('tools', [])}]
    assert all(body['tools'] == main_requests[0]['tools'] for body in main_requests)
    result['stable_tools'] = True
    result['main_requests'] = len(main_requests)
    result['passed'] = True
finally:
    result['proxy_exit_before_cleanup'] = proxy.poll()
    proxy.terminate()
    proxy.wait(timeout=15)
    proxy_log.close()
    server.should_exit = True
    (OUT / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    progress('Full proxy gate finished; passed=' + str(result['passed']))
