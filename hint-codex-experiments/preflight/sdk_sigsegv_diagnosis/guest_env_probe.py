#!/usr/bin/env python3
"""Check only the selected CLI flag in an actual offline SDK Bash child."""

import asyncio
import json
import sys
import threading
from dataclasses import asdict
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, '/tmp')
from hook_fixture import Handler as OriginalHandler, sse_body
from sdk_script import create_agent_options
from claude_agent_sdk import ClaudeSDKClient

OUT = Path('/tmp/env_probe_out')
OUT.mkdir(exist_ok=True)
REQUESTS = []
MESSAGES = []
ISSUED = False


class Handler(OriginalHandler):
    def do_POST(self):
        global ISSUED
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        REQUESTS.append({'path': self.path, 'body': data})
        if 'count_tokens' in self.path:
            payload, kind = json.dumps({'input_tokens': 100}).encode(), 'application/json'
        else:
            main = 'Read' in {tool.get('name') for tool in data.get('tools', [])}
            if main and not ISSUED:
                ISSUED = True
                command = '/opt/python3.12-tmp/bin/python3 -c "import os; print(\'BUN_JSC_useJIT=\' + os.environ.get(\'BUN_JSC_useJIT\', \'<unset>\'))"'
                content = [{'type': 'tool_use', 'id': 'env-check-bash', 'name': 'Bash',
                            'input': {'command': command, 'description': 'Read only the selected runtime flag'}}]
                stop = 'tool_use'
            else:
                content, stop = [{'type': 'text', 'text': 'OFFLINE_ENV_CHECK_COMPLETE'}], 'end_turn'
            if data.get('stream'):
                payload, kind = sse_body(content, stop), 'text/event-stream'
            else:
                payload = json.dumps({'id': 'msg_env_probe', 'type': 'message', 'role': 'assistant',
                    'model': 'gpt-6.1-terra', 'content': content, 'stop_reason': stop, 'stop_sequence': None,
                    'usage': {'input_tokens': 100, 'output_tokens': 20}}).encode()
                kind = 'application/json'
        self.send_response(200)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


async def run():
    options = create_agent_options('/app')
    options.env['BUN_JSC_useJIT'] = '0'
    options.stderr = lambda line: (OUT / 'stderr.log').open('a').write(line + '\n')
    options.extra_args = {'debug-file': str(OUT / 'debug.log')}
    async with ClaudeSDKClient(options=options) as client:
        await client.query(Path('/tmp/env_original_prompt.txt').read_text())
        async for message in client.receive_response():
            MESSAGES.append({'type': type(message).__name__, 'message': asdict(message)})
    tools = [block for item in MESSAGES for block in item['message'].get('content', [])
             if isinstance(block, dict) and block.get('tool_use_id') == 'env-check-bash']
    assert len(tools) == 1 and not tools[0].get('is_error')
    content = tools[0]['content']
    selected = [line for line in content.splitlines() if line.startswith('BUN_JSC_useJIT=')]
    assert len(selected) == 1
    value = selected[0].split('=', 1)[1]
    return {'passed': True, 'selected_key': 'BUN_JSC_useJIT', 'child_value': value,
            'flag_propagates_to_tools': value == '0',
            'real_model_calls': 0, 'full_environment_read': False, 'tool_result': tools[0]}


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 8767), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    result = {'passed': False, 'real_model_calls': 0}
    try:
        result = asyncio.run(asyncio.wait_for(run(), 200))
    except BaseException as exc:
        result['error'] = str(exc) or type(exc).__name__
    finally:
        server.shutdown()
        server.server_close()
        (OUT / 'result.json').write_text(json.dumps(result, indent=2))
        (OUT / 'sdk_messages.json').write_text(json.dumps(MESSAGES, indent=2))
        (OUT / 'captured_requests.json').write_text(json.dumps(REQUESTS, indent=2))
        print(json.dumps(result))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
