#!/usr/bin/env python3
"""Exercise the unchanged SDK against an offline scripted Anthropic endpoint."""

import asyncio
import copy
import json
import os
import shutil
import sys
import threading
import time
import traceback
from dataclasses import asdict
from pathlib import Path
from http.server import ThreadingHTTPServer

sys.path.insert(0, '/tmp')
from hook_fixture import Handler as OriginalHandler, sse_body
from sdk_script import OnlineTeacher, create_agent_options
from claude_agent_sdk import ClaudeSDKClient, ResultMessage, SystemMessage

CASE = json.loads(Path(sys.argv[1]).read_text())
OUT = Path('/tmp/stress_out') / CASE['name']
OUT.mkdir(parents=True, exist_ok=True)
REQUESTS = []
MESSAGES = []
PLANS = []
MARKER = 'OFFLINE_BACKEND_CONTEXT_MARKER_P31'


class Handler(OriginalHandler):
    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        REQUESTS.append({'path': self.path, 'body': data, 'timestamp': time.time()})
        if 'count_tokens' in self.path:
            payload = json.dumps({'input_tokens': 100}).encode()
            content_type = 'application/json'
        else:
            main = 'Read' in {tool.get('name') for tool in data.get('tools', [])}
            content = PLANS.pop(0) if main and PLANS else [{'type': 'text', 'text': 'OFFLINE_BACKEND_COMPLETE'}]
            stop = 'tool_use' if any(block['type'] == 'tool_use' for block in content) else 'end_turn'
            if data.get('stream'):
                payload, content_type = sse_body(content, stop), 'text/event-stream'
            else:
                payload = json.dumps({'id': 'msg_offline_backend', 'type': 'message', 'role': 'assistant',
                    'model': 'gpt-6.1-terra', 'content': content, 'stop_reason': stop,
                    'stop_sequence': None, 'usage': {'input_tokens': 100, 'output_tokens': 20}}).encode()
                content_type = 'application/json'
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def tool(name, values, identifier):
    return {'type': 'tool_use', 'id': identifier, 'name': name, 'input': values}


def set_plan(phase):
    PLANS.clear()
    count = 20 if CASE['hook'] and phase == 'initial' else 1
    PLANS.append([tool('Read', {'file_path': '/app/counter.py'}, f'{phase}-read-{i}') for i in range(count)])
    old = 'return a - b' if phase == 'initial' else 'return a + b'
    new = 'return a + b' if phase == 'initial' else 'return a + b\n\ndef multiply(a, b):\n    return a * b'
    PLANS.append([tool('Edit', {'file_path': '/app/counter.py', 'old_string': old, 'new_string': new}, phase + '-edit')])
    check = 'assert counter.add(3, 2) == 5'
    if phase == 'resume':
        check += '; assert counter.multiply(3, 4) == 12'
    command = '/opt/python3.12-tmp/bin/python3 -c "import counter; ' + check + '; print(\'LOCAL_TEST_PASSED\')"'
    PLANS.append([tool('Bash', {'command': command, 'description': 'Run the offline local function checks'}, phase + '-test')])
    PLANS.append([{'type': 'text', 'text': 'OFFLINE_BACKEND_COMPLETE'}])


async def run_case():
    started = time.monotonic()
    sessions = []
    teacher = OnlineTeacher('http://127.0.0.1:8766/experiment/progress', CASE['name'], 'offline-backend', OUT) if CASE['hook'] else None
    if teacher is not None:
        teacher.request_hint = lambda payload: {'hint': MARKER, 'stopped': False, 'stop_reason': None}
    for phase in ['initial', 'resume'] if CASE['resume'] else ['initial']:
        set_plan(phase)
        options = create_agent_options('/app', resume_session_id=sessions[0] if sessions else None,
                                       online_teacher=teacher)
        options.extra_args = {'debug-file': str(OUT / (phase + '_debug.log'))}
        options.stderr = lambda line, phase=phase: (OUT / (phase + '_stderr.log')).open('a').write(line + '\n')
        if CASE['jit_off']:
            options.env['BUN_JSC_useJIT'] = '0'
        records = []
        prompt = Path('/tmp/prompts/' + CASE['mode'] + '.txt').read_text() if phase == 'initial' else 'Preserve the completed add fix and continue the same offline local session.'
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            async for message in client.receive_response():
                record = {'type': type(message).__name__, 'message': asdict(message), 'phase': phase}
                MESSAGES.append(record)
                records.append(record)
                if isinstance(message, SystemMessage) and message.subtype == 'init':
                    sessions.append(message.data['session_id'])
        result = next(item['message'] for item in reversed(records) if item['type'] == 'ResultMessage')
        assert not result['is_error'] and result['result'] == 'OFFLINE_BACKEND_COMPLETE'
        assert not PLANS, 'The expected real SDK tool sequence did not finish'
        tools = [block for item in records for block in item['message'].get('content', [])
                 if isinstance(block, dict) and block.get('tool_use_id')]
        assert tools and all(not block.get('is_error') for block in tools), tools
        source = Path('/app/counter.py').read_text()
        assert 'return a + b' in source
        if phase == 'resume':
            assert 'def multiply(a, b)' in source
    if CASE['resume']:
        assert len(sessions) == 2 and sessions[0] == sessions[1]
    hook = {'tool_count': teacher.tool_count, 'checks': teacher.checks,
            'events': teacher.events, 'error': teacher.error} if teacher else None
    if teacher is not None:
        assert teacher.tool_count >= 22 and teacher.checks == 1 and not teacher.error
        assert sum(json.dumps(row['body']).count(MARKER) for row in REQUESTS) >= 1
    return {'passed': True, 'sessions': sessions, 'hook': hook, 'wall_seconds': time.monotonic() - started}


def main():
    shutil.rmtree('/root/.claude', ignore_errors=True)
    Path('/app/counter.py').write_text('def add(a, b):\n    return a - b\n')
    Path('/app/__pycache__').mkdir(exist_ok=True)
    for path in Path('/app/__pycache__').glob('*'):
        path.unlink()
    server = ThreadingHTTPServer(('127.0.0.1', 8767), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    result = {'case': CASE, 'real_model_calls': 0, 'synthetic_usage_excluded': True, 'passed': False,
              'started_at_unix': time.time()}
    try:
        result.update(asyncio.run(asyncio.wait_for(run_case(), 200)))
    except BaseException as exc:
        result.update({'error': str(exc) or type(exc).__name__, 'error_type': type(exc).__name__,
                       'traceback': traceback.format_exc()})
    finally:
        server.shutdown()
        server.server_close()
        result['finished_at_unix'] = time.time()
        result['fake_http_requests'] = len(REQUESTS)
        result['main_fake_requests'] = sum('Read' in {t.get('name') for t in row['body'].get('tools', [])} for row in REQUESTS)
        (OUT / 'captured_requests.json').write_text(json.dumps(REQUESTS, indent=2))
        (OUT / 'sdk_messages.json').write_text(json.dumps(MESSAGES, indent=2))
        (OUT / 'result.json').write_text(json.dumps(result, indent=2))
        print(json.dumps({key: result.get(key) for key in ['case', 'passed', 'error', 'fake_http_requests', 'main_fake_requests']}), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
