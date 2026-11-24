"""Exercise the real Codex process and bridge concurrently with a local provider."""
import asyncio
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / 'native_bridge'
SOURCE = ROOT / 'source_parallel_09'
sys.path.insert(0, str(SOURCE))
from codex_cli_bridge import CodexBridge, CodexRPCClient, MODEL, default_command

RECORDS = []
LOCK = threading.Lock()


def marker(body):
    values = []
    for item in body['input']:
        if item.get('role') == 'user':
            values.extend(re.findall(r'AUDIT_LANE_[0-5]_PHASE_[01]', json.dumps(item)))
    return values[-1]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        current = marker(body)
        outputs = [item for item in body['input'] if item.get('type') == 'function_call_output'
                   and item.get('call_id', '').startswith(current)]
        with LOCK:
            RECORDS.append({'marker': current, 'body': body})
            number = len(RECORDS)
        if not outputs:
            items = [{'type': 'function_call', 'id': 'fc-' + current + '-' + str(index),
                      'call_id': current + '-' + str(index), 'name': 'Read',
                      'arguments': json.dumps({'path': current + '/' + str(index) + '/café Ω "quote" \\'}),
                      'status': 'completed'} for index in range(3)]
        else:
            assert len(outputs) == 3, outputs
            for item in outputs:
                assert 'RESULT:' + item['call_id'] in json.dumps(item['output']), item
            items = [{'type': 'message', 'id': 'msg-' + str(number), 'role': 'assistant',
                      'status': 'completed', 'content': [{'type': 'output_text',
                      'text': 'DONE:' + current, 'annotations': []}]}]
        response = {'id': 'resp-' + str(number), 'object': 'response', 'created_at': int(time.time()),
                    'status': 'completed', 'output': items,
                    'usage': {'input_tokens': 20, 'output_tokens': 5, 'total_tokens': 25,
                              'input_tokens_details': {'cached_tokens': 0},
                              'output_tokens_details': {'reasoning_tokens': 0}}}
        events = [{'type': 'response.created', 'response': {**response, 'status': 'in_progress', 'output': []}}]
        for index, item in enumerate(items):
            events.extend([{'type': 'response.output_item.added', 'output_index': index,
                            'item': {**item, 'status': 'in_progress'}},
                           {'type': 'response.output_item.done', 'output_index': index, 'item': item}])
        events.append({'type': 'response.completed', 'response': response})
        raw = ''.join('event: ' + event['type'] + '\ndata: ' + json.dumps(event) + '\n\n'
                      for event in events).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


async def run_lane(bridge, lane):
    route = {'session': 'audit_lane' + str(lane), 'role': 'teacher', 'phase': 'initial'}
    body = {'model': MODEL, 'messages': [{'role': 'system', 'content': 'Offline protocol fixture.'}],
            'tools': [{'type': 'function', 'function': {'name': 'Read', 'description': 'Read the fixture.',
                       'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}},
                                      'required': ['path'], 'additionalProperties': False}}}]}
    phases = []
    for phase in range(2):
        current = f'AUDIT_LANE_{lane}_PHASE_{phase}'
        route['phase'] = 'initial' if phase == 0 else 'review'
        body['messages'].append({'role': 'user', 'content': current})
        seen = []
        while True:
            reply = await asyncio.wait_for(bridge.chat(body, route=route), 60)
            message = reply['choices'][0]['message']
            body['messages'].append(message)
            calls = message.get('tool_calls', [])
            if not calls:
                assert message['content'] == 'DONE:' + current, message
                break
            await asyncio.sleep((5 - lane) * 0.03)
            for call in reversed(calls):
                assert call['id'].startswith(current), call
                assert current in json.loads(call['function']['arguments'])['path']
                seen.append(call['id'])
                body['messages'].append({'role': 'tool', 'tool_call_id': call['id'],
                                         'content': 'RESULT:' + call['id'] + '\n' + 'x' * 70000})
        assert set(seen) == {current + '-' + str(i) for i in range(3)}, seen
        phases.append({'phase': phase, 'tool_calls': seen, 'passed': True})
    states = [state for state in bridge.sessions.values() if state.session_id == route['session']]
    assert len(states) == 1
    state = states[0]
    assert all(tool.completed for tool in state.pending.values())
    assert state.usage_total['totalTokens'] == 100, state.usage_total
    return {'lane': lane, 'thread': state.thread_id, 'phases': phases,
            'synthetic_tokens': state.usage_total['totalTokens']}


async def main():
    OUT.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    os.environ['HINT_LOCAL_PROBE_KEY'] = 'offline-local-fixture'
    address = 'http://127.0.0.1:' + str(server.server_address[1]) + '/v1'
    command = default_command() + ['-c', 'model_provider="hint_local_probe"',
        '-c', 'model_providers.hint_local_probe.name="Offline loopback probe"',
        '-c', 'model_providers.hint_local_probe.base_url=' + json.dumps(address),
        '-c', 'model_providers.hint_local_probe.wire_api="responses"',
        '-c', 'model_providers.hint_local_probe.env_key="HINT_LOCAL_PROBE_KEY"',
        '-c', 'model_providers.hint_local_probe.requires_openai_auth=false',
        '-c', 'model_providers.hint_local_probe.request_max_retries=0',
        '-c', 'model_providers.hint_local_probe.stream_max_retries=0']
    rpc = CodexRPCClient(command=command, stderr_path=OUT / 'stderr.log', cwd=OUT)
    bridge = CodexBridge(OUT / 'bridge', rpc=rpc)
    result = {'passed': False, 'real_model_calls': 0, 'synthetic_usage_excluded': True,
              'source': str(SOURCE), 'provider_base_url': address, 'started_at': time.time()}
    try:
        await asyncio.wait_for(bridge.start(), 30)
        result['lanes'] = await asyncio.wait_for(asyncio.gather(*(run_lane(bridge, i) for i in range(6))), 180)
        assert len({row['thread'] for row in result['lanes']}) == 6
        assert not bridge.stopped
        usage = [json.loads(line) for line in (OUT / 'bridge/token_usage.jsonl').read_text().splitlines()]
        assert sum(row['delta']['totalTokens'] for row in usage) == 600
        result.update(passed=True, sdk_tool_calls=36, real_cli_threads=6, real_cli_turns=12,
                      provider_requests=len(RECORDS), synthetic_tokens=600,
                      native_tool_names=sorted({t.get('name', t.get('type', ''))
                                               for r in RECORDS for t in r['body'].get('tools', [])}))
    except Exception as exc:
        result['error'] = repr(exc)
    finally:
        await bridge.close()
        server.shutdown()
        server.server_close()
        result['finished_at'] = time.time()
        (OUT / 'requests.json').write_text(json.dumps(RECORDS, ensure_ascii=False))
        (OUT / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
