"""Check late SDK output through the supported turn/start toolOutput API."""
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
OUT = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'source_parallel_09'))
from codex_cli_bridge import CodexRPCClient, MODEL, default_command
RECORDS = []
CASE = ''

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass
    def do_GET(self):
        self.send_response(404)
        self.end_headers()
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        RECORDS.append({'case': CASE, 'body': body})
        number = sum(r['case'] == CASE for r in RECORDS)
        if number == 1:
            item = {'type': 'custom_tool_call', 'id': 'tc-exec', 'call_id': 'call-exec', 'name': 'exec',
                    'input': '// @exec: {"yield_time_ms": 1000}\ntext(await tools.Read({path:"delayed-fixture"}));',
                    'status': 'completed'}
        elif number == 2:
            cell = re.search(r'Script running with cell ID (\d+)', json.dumps(body['input']))
            item = {'type': 'function_call', 'id': 'fc-wait', 'call_id': 'call-wait', 'name': 'wait',
                    'arguments': json.dumps({'cell_id': cell.group(1), 'terminate': True}), 'status': 'completed'}
        else:
            if CASE == 'output_while_active' and number == 3:
                time.sleep(4)
            item = {'type': 'message', 'id': 'msg-done', 'role': 'assistant', 'status': 'completed',
                    'content': [{'type': 'output_text', 'text': 'AFTER_ACTUAL_RESULT' if 'LATE_SDK_TOOL_RESULT' in json.dumps(body['input']) else 'EARLY_FINAL', 'annotations': []}]}
        response = {'id': 'resp-' + str(number), 'object': 'response', 'created_at': int(time.time()),
                    'status': 'completed', 'output': [item], 'usage': {'input_tokens': 20,
                    'output_tokens': 5, 'total_tokens': 25, 'input_tokens_details': {'cached_tokens': 0},
                    'output_tokens_details': {'reasoning_tokens': 0}}}
        events = [{'type': 'response.created', 'response': {**response, 'status': 'in_progress', 'output': []}},
                  {'type': 'response.output_item.added', 'output_index': 0, 'item': item},
                  {'type': 'response.output_item.done', 'output_index': 0, 'item': item},
                  {'type': 'response.completed', 'response': response}]
        raw = ''.join('event: '+e['type']+'\ndata: '+json.dumps(e)+'\n\n' for e in events).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

async def main():
    global CASE
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    os.environ['HINT_LOCAL_PROBE_KEY'] = 'offline-local-fixture'
    address = 'http://127.0.0.1:' + str(server.server_address[1]) + '/v1'
    results = []
    try:
        for active in (False, True):
            CASE = 'output_while_active' if active else 'output_after_final'
            interrupt = True
            events, replies = [], []
            queue = asyncio.Queue()
            def record(event):
                events.append({'timestamp': time.time(), 'event': event})
                queue.put_nowait(event)
            command = default_command() + ['-c', 'model_provider="hint_local_probe"',
                '-c', 'model_providers.hint_local_probe.name="Offline loopback probe"',
                '-c', 'model_providers.hint_local_probe.base_url=' + json.dumps(address),
                '-c', 'model_providers.hint_local_probe.wire_api="responses"',
                '-c', 'model_providers.hint_local_probe.env_key="HINT_LOCAL_PROBE_KEY"',
                '-c', 'model_providers.hint_local_probe.requires_openai_auth=false',
                '-c', 'model_providers.hint_local_probe.request_max_retries=0',
                '-c', 'model_providers.hint_local_probe.stream_max_retries=0',
                '-c', 'features.code_mode=true', '-c', 'features.code_mode_only=true',
                '-c', 'features.code_mode_interrupt=' + str(interrupt).lower()]
            rpc = CodexRPCClient(command, record, OUT / (CASE + '_stderr.log'), OUT)
            case = {'case': CASE, 'started_at': time.time()}
            async def delayed_reply(event):
                await asyncio.sleep(4)
                case['late_reply_sent_at'] = time.time()
                result = await rpc.request('turn/start', {'threadId': tid, 'model': MODEL,
                    'effort': 'low', 'input': [], 'environments': [],
                    'toolOutput': {'name': 'Read', 'output': 'LATE_SDK_TOOL_RESULT', 'retain': True}})
                case['tool_output_turn'] = result
            try:
                await asyncio.wait_for(rpc.start(), 20)
                thread = await rpc.request('thread/start', {'model': MODEL, 'allowProviderModelFallback': False,
                    'baseInstructions': 'Offline protocol fixture.', 'environments': [], 'approvalPolicy': 'never',
                    'cwd': str(OUT), 'dynamicTools': [{'type': 'function', 'name': 'Read',
                    'description': 'Read a fixture.', 'inputSchema': {'type': 'object',
                    'properties': {'path': {'type': 'string'}}, 'required': ['path']}}]})
                tid = thread['thread']['id']
                await rpc.request('turn/start', {'threadId': tid, 'model': MODEL, 'effort': 'low',
                    'input': [{'type': 'text', 'text': 'Run the offline termination fixture.'}], 'environments': []})
                while True:
                    event = await asyncio.wait_for(queue.get(), 25)
                    if event.get('method') == 'item/tool/call':
                        replies.append(asyncio.create_task(delayed_reply(event)))
                    elif event.get('method') == 'turn/completed':
                        case.setdefault('completed_turns', []).append(event['params']['turn'])
                        messages = [item.get('text') for item in event['params']['turn'].get('items', [])
                                    if item.get('type') == 'agentMessage']
                        if 'AFTER_ACTUAL_RESULT' in messages:
                            case['turn_completed_at'] = time.time()
                            break
                await asyncio.gather(*replies)
                await asyncio.sleep(.1)
                history = await rpc.request('thread/read', {'threadId': tid, 'includeTurns': True})
                case['late_result_in_history'] = 'LATE_SDK_TOOL_RESULT' in json.dumps(history)
                case['dynamic_completions'] = [e['event']['params']['item'] for e in events
                    if e['event'].get('method') == 'item/completed'
                    and e['event']['params']['item'].get('type') == 'dynamicToolCall']
                case['provider_request_count'] = sum(r['case'] == CASE for r in RECORDS)
                case['delivered_items'] = [[i for i in r['body']['input']
                    if 'LATE_SDK_TOOL_RESULT' in json.dumps(i)] for r in RECORDS if r['case'] == CASE]
            except Exception as exc:
                case['error'] = repr(exc)
            finally:
                await rpc.close()
                case['elapsed_seconds'] = time.time() - case['started_at']
                results.append(case)
                (OUT / (CASE + '_events.json')).write_text(json.dumps(events, ensure_ascii=False))
    finally:
        server.shutdown()
        server.server_close()
        (OUT / 'tool_output_requests.json').write_text(json.dumps(RECORDS, ensure_ascii=False))
        (OUT / 'tool_output_result.json').write_text(json.dumps({'real_model_calls': 0,
            'synthetic_usage_excluded': True, 'cases': results}, indent=2))
    print(json.dumps(results, indent=2))

if __name__ == '__main__':
    asyncio.run(main())
