"""Exercise native automatic compaction with a loopback Responses fixture."""
import asyncio
import json
import os
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

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        number = len(RECORDS) + 1
        RECORDS.append({'at': time.time(), 'path': self.path, 'body': body})
        if self.path.endswith('/compact'):
            payload = {'id': 'cmp-fixture', 'object': 'response.compaction',
                       'created_at': int(time.time()), 'output': [
                           {'type': 'compaction', 'id': 'cmp-item',
                            'encrypted_content': 'OFFLINE_COMPACTED_CONTEXT'}],
                       'usage': {'input_tokens': 100, 'output_tokens': 20,
                                 'total_tokens': 120}}
            raw = json.dumps(payload).encode()
            content_type = 'application/json'
        else:
            is_compaction = any(item.get('type') == 'compaction_trigger' for item in body.get('input', []))
            responses = sum(not any(item.get('type') == 'compaction_trigger' for item in r['body'].get('input', [])) for r in RECORDS)
            if is_compaction:
                item = {'type': 'compaction', 'id': 'cmp-item',
                        'encrypted_content': 'OFFLINE_COMPACTED_CONTEXT'}
            elif responses == 2:
                item = {'type': 'custom_tool_call', 'id': 'tc-read', 'call_id': 'call-read',
                        'name': 'exec', 'status': 'completed',
                        'input': 'text(await tools.Read({path:"AFTER_COMPACTION"}));'}
            else:
                item = {'type': 'message', 'id': 'msg-' + str(number), 'role': 'assistant',
                        'status': 'completed', 'content': [{'type': 'output_text',
                        'text': 'OFFLINE_DONE_' + str(number), 'annotations': []}]}
            usage = {'input_tokens': 100 if is_compaction else (6000 if responses == 1 else 50),
                     'output_tokens': 20 if is_compaction else 5,
                     'total_tokens': 120 if is_compaction else (6005 if responses == 1 else 55),
                     'input_tokens_details': {'cached_tokens': 0},
                     'output_tokens_details': {'reasoning_tokens': 0}}
            response = {'id': 'resp-' + str(number), 'object': 'response',
                        'created_at': int(time.time()), 'status': 'completed',
                        'output': [item], 'usage': usage}
            events = [{'type': 'response.created', 'response': {**response, 'status': 'in_progress', 'output': []}},
                      {'type': 'response.output_item.added', 'output_index': 0, 'item': item},
                      {'type': 'response.output_item.done', 'output_index': 0, 'item': item},
                      {'type': 'response.completed', 'response': response}]
            raw = ''.join('event: ' + e['type'] + '\ndata: ' + json.dumps(e) + '\n\n' for e in events).encode()
            content_type = 'text/event-stream'
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

async def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    os.environ['HINT_LOCAL_PROBE_KEY'] = 'offline-local-fixture'
    address = 'http://127.0.0.1:' + str(server.server_address[1]) + '/v1'
    events, tool_calls, turns = [], [], []
    queue = asyncio.Queue()
    def record(event):
        events.append({'at': time.time(), 'event': event})
        queue.put_nowait(event)
    command = default_command() + ['-c', 'model_provider="hint_local_probe"',
        '-c', 'model_providers.hint_local_probe.name="Offline compaction fixture"',
        '-c', 'model_providers.hint_local_probe.base_url=' + json.dumps(address),
        '-c', 'model_providers.hint_local_probe.wire_api="responses"',
        '-c', 'model_providers.hint_local_probe.env_key="HINT_LOCAL_PROBE_KEY"',
        '-c', 'model_providers.hint_local_probe.requires_openai_auth=false',
        '-c', 'model_providers.hint_local_probe.request_max_retries=0',
        '-c', 'model_providers.hint_local_probe.stream_max_retries=0',
        '-c', 'model_providers.hint_local_probe.capabilities.remote_compaction="v2"',
        '-c', 'features.code_mode=true', '-c', 'features.code_mode_only=true',
        '-c', 'model_auto_compact_token_limit=5000']
    rpc = CodexRPCClient(command, record, OUT / 'stderr.log', OUT)
    result = {'real_model_calls': 0, 'synthetic_usage_excluded': True,
              'test_only_auto_compact_token_limit': 5000, 'started_at': time.time()}
    try:
        await asyncio.wait_for(rpc.start(), 20)
        thread = await rpc.request('thread/start', {'model': MODEL, 'allowProviderModelFallback': False,
            'baseInstructions': 'Offline native compaction fixture.', 'environments': [],
            'approvalPolicy': 'never', 'cwd': str(OUT), 'dynamicTools': [
            {'type': 'function', 'name': 'Read', 'description': 'Read a fixture.',
             'inputSchema': {'type': 'object', 'properties': {'path': {'type': 'string'}},
                             'required': ['path']}}]})
        tid = thread['thread']['id']
        result['thread_id'] = tid
        for n in (1, 2):
            started = await rpc.request('turn/start', {'threadId': tid, 'model': MODEL, 'effort': 'low',
                'input': [{'type': 'text', 'text': 'Run offline fixture turn ' + str(n)}], 'environments': []})
            turn_id = started['turn']['id']
            while True:
                event = await asyncio.wait_for(queue.get(), 35)
                if event.get('method') == 'item/tool/call':
                    tool_calls.append(event['params'])
                    await rpc.respond(event['id'], {'success': True, 'contentItems': [
                        {'type': 'inputText', 'text': 'ACTUAL_TOOL_RESULT_AFTER_COMPACTION'}]})
                elif event.get('method') == 'turn/completed' and event['params']['turn']['id'] == turn_id:
                    turns.append(event['params']['turn'])
                    break
        result['thread'] = await rpc.request('thread/read', {'threadId': tid, 'includeTurns': True})
        result['tool_calls'] = tool_calls
        result['turns'] = turns
        result['compact_requests'] = [r for r in RECORDS if any(i.get('type') == 'compaction_trigger' for i in r['body'].get('input', []))]
        result['context_events'] = [r for r in events if 'compact' in json.dumps(r).lower()]
        result['usage_events'] = [r for r in events if r['event'].get('method') == 'thread/tokenUsage/updated']
    except Exception as exc:
        result['error'] = repr(exc)
    finally:
        await rpc.close()
        server.shutdown()
        server.server_close()
        result['elapsed_seconds'] = time.time() - result['started_at']
        (OUT / 'requests.json').write_text(json.dumps(RECORDS, ensure_ascii=False))
        (OUT / 'events.json').write_text(json.dumps(events, ensure_ascii=False))
        (OUT / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({'error': result.get('error'), 'thread_id': result.get('thread_id'),
        'paths': [r['path'] for r in RECORDS], 'tool_calls': tool_calls,
        'elapsed_seconds': result['elapsed_seconds']}, ensure_ascii=False))

if __name__ == '__main__':
    asyncio.run(main())
