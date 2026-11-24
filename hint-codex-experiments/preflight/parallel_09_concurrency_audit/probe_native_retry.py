"""A real local Codex process retries one truncated loopback provider stream."""
import asyncio
import importlib.util
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

OUT = Path(__file__).resolve().parent / 'native_retry'
SOURCE = Path(__file__).resolve().parent / 'candidate/codex_cli_bridge.py'
spec = importlib.util.spec_from_file_location('native_retry_candidate', SOURCE)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
REQUESTS = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        REQUESTS.append({'path': self.path, 'body': body})
        number = len(REQUESTS)
        item = {'type': 'message', 'id': 'msg-retried', 'role': 'assistant',
                'status': 'completed', 'content': [{'type': 'output_text',
                'text': 'RECOVERED_SAME_TURN', 'annotations': []}]}
        response = {'id': 'resp-' + str(number), 'object': 'response', 'created_at': int(time.time()),
                    'status': 'completed', 'output': [item],
                    'usage': {'input_tokens': 20, 'output_tokens': 5, 'total_tokens': 25,
                              'input_tokens_details': {'cached_tokens': 0},
                              'output_tokens_details': {'reasoning_tokens': 0}}}
        events = [{'type': 'response.created', 'response': {
            **response, 'status': 'in_progress', 'output': []}}]
        if number > 1:
            events.extend([
                {'type': 'response.output_item.added', 'output_index': 0,
                 'item': {**item, 'status': 'in_progress'}},
                {'type': 'response.output_item.done', 'output_index': 0, 'item': item},
                {'type': 'response.completed', 'response': response}])
        raw = ''.join('event: ' + event['type'] + '\ndata: ' + json.dumps(event) + '\n\n'
                      for event in events).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


async def main():
    OUT.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    os.environ['HINT_RETRY_PROBE_KEY'] = 'offline-loopback-fixture'
    address = 'http://127.0.0.1:' + str(server.server_address[1]) + '/v1'
    command = module.default_command() + [
        '-c', 'skills.bundled.enabled=false',
        '-c', 'model_provider="hint_retry_probe"',
        '-c', 'model_providers.hint_retry_probe.name="Offline stream retry fixture"',
        '-c', 'model_providers.hint_retry_probe.base_url=' + json.dumps(address),
        '-c', 'model_providers.hint_retry_probe.wire_api="responses"',
        '-c', 'model_providers.hint_retry_probe.env_key="HINT_RETRY_PROBE_KEY"',
        '-c', 'model_providers.hint_retry_probe.requires_openai_auth=false',
        '-c', 'model_providers.hint_retry_probe.request_max_retries=0',
        '-c', 'model_providers.hint_retry_probe.stream_max_retries=1']
    rpc = module.CodexRPCClient(command=command, stderr_path=OUT / 'stderr.log', cwd=OUT)
    bridge = module.CodexBridge(OUT / 'bridge', rpc=rpc)
    result = {'passed': False, 'real_model_calls': 0, 'source': str(SOURCE),
              'provider_base_url': address, 'synthetic_usage_excluded': True,
              'started_at': time.time(), 'fixture': 'First response ends after response.created; retry completes.'}
    try:
        response = await asyncio.wait_for(bridge.chat({
            'model': module.MODEL, 'messages': [{'role': 'user', 'content': 'LOCAL_RETRY_PROTOCOL_FIXTURE'}]},
            route={'session': 'native-retry', 'role': 'teacher', 'phase': 'generate'}), 60)
        events = [json.loads(line)['event'] for line in (OUT / 'bridge/codex_events.jsonl').read_text().splitlines()]
        errors = [event['params'] for event in events if event.get('method') == 'error']
        starts = [event for event in events if event.get('method') == 'turn/started']
        state = next(iter(bridge.sessions.values()))
        assert len(REQUESTS) == 2, len(REQUESTS)
        assert len(errors) == 1 and errors[0]['willRetry'] is True, errors
        assert response['choices'][0]['message']['content'] == 'RECOVERED_SAME_TURN', response
        assert len(starts) == 1, starts
        assert not state.error and not bridge.stopped
        usage = [json.loads(line) for line in (OUT / 'bridge/token_usage.jsonl').read_text().splitlines()]
        assert sum(row['delta']['totalTokens'] for row in usage) == 25, usage
        result.update(passed=True, provider_requests=len(REQUESTS), native_turn_starts=len(starts),
                      error_notifications=errors, final_response=response, synthetic_tokens=25,
                      bridge_stopped=bridge.stopped, session_error=state.error)
    except Exception as exc:
        result['error'] = repr(exc)
    finally:
        await bridge.close()
        server.shutdown()
        server.server_close()
        result['finished_at'] = time.time()
        (OUT / 'requests.json').write_text(json.dumps(REQUESTS, ensure_ascii=False, indent=2) + '\n')
        (OUT / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
