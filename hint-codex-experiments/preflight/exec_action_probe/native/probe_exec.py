"""Run independent Codex exec processes against a loopback Responses fixture."""
import asyncio
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

OUT = Path(__file__).resolve().parent
MODEL = 'gpt-6.1-terra'
RECORDS = []
SCHEMA = {'type': 'object', 'properties': {
    'content': {'type': 'string'},
    'tool_calls': {'type': 'array', 'items': {'type': 'object', 'properties': {
        'name': {'type': 'string'}, 'arguments': {'type': 'string'}},
        'required': ['name', 'arguments'], 'additionalProperties': False}}},
    'required': ['content', 'tool_calls'], 'additionalProperties': False}
DISABLED_FEATURES = ('shell_tool', 'view_image', 'multi_agent', 'multi_agent_v2',
    'plugins', 'apps', 'skill_search', 'skill_mcp_dependency_install', 'remote_plugin',
    'goals', 'sleep_tool', 'browser_use', 'browser_use_external', 'computer_use',
    'image_generation', 'hooks', 'workspace_dependencies', 'memories',
    'request_permissions_tool', 'default_mode_request_user_input')

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        case = self.path.split('/')[1]
        RECORDS.append({'timestamp': time.time(), 'case': case, 'path': self.path, 'body': body})
        time.sleep(.5)
        action = {'content': 'ACTION_' + case,
                  'tool_calls': [{'name': 'Read', 'arguments': json.dumps({'path': case + '.txt'})}]}
        item = {'type': 'message', 'id': 'msg-' + case, 'role': 'assistant', 'status': 'completed',
                'content': [{'type': 'output_text', 'text': json.dumps(action), 'annotations': []}]}
        response = {'id': 'resp-' + case, 'object': 'response', 'created_at': int(time.time()),
                    'status': 'completed', 'output': [item], 'usage': {'input_tokens': 123,
                    'output_tokens': 17, 'total_tokens': 140,
                    'input_tokens_details': {'cached_tokens': 23},
                    'output_tokens_details': {'reasoning_tokens': 3}}}
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

async def run_case(case, address):
    path = OUT / case
    path.mkdir(exist_ok=True)
    history = {'messages': [
        {'role': 'system', 'content': 'SYSTEM_' + case + ': Return one action as JSON; external runtime executes tools.'},
        {'role': 'user', 'content': 'USER_' + case + ': inspect the local example.'},
        {'role': 'assistant', 'content': 'ASSISTANT_' + case,
         'tool_calls': [{'id': 'old-' + case, 'type': 'function',
                         'function': {'name': 'Read', 'arguments': '{"path":"prior.txt"}'}}]},
        {'role': 'tool', 'tool_call_id': 'old-' + case, 'content': 'TOOL_RESULT_' + case},
        {'role': 'user', 'content': 'HOOK_' + case + ': continue using the exact observations above.'}],
        'tools': [{'type': 'function', 'function': {'name': 'Read', 'description': 'Read a file.',
                   'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}},
                                  'required': ['path']}}}]}
    prompt = 'Return exactly one JSON action for this external agent request.\n' + json.dumps(history)
    (path / 'stdin.txt').write_text(prompt)
    command = ['/home/xymo/.local/bin/codex', 'exec', '--ignore-user-config', '--ignore-rules',
        '--ephemeral', '--json', '--skip-git-repo-check', '--sandbox', 'read-only',
        '--model', MODEL, '--cd', str(path), '--output-schema', str(OUT / 'action_schema.json'),
        '--output-last-message', str(path / 'final.json'), '-c', 'model_provider="hint_exec_probe"',
        '-c', 'model_providers.hint_exec_probe.name="Offline exec probe"',
        '-c', 'model_providers.hint_exec_probe.base_url=' + json.dumps(address + '/' + case + '/v1'),
        '-c', 'model_providers.hint_exec_probe.wire_api="responses"',
        '-c', 'model_providers.hint_exec_probe.env_key="HINT_EXEC_PROBE_KEY"',
        '-c', 'model_providers.hint_exec_probe.requires_openai_auth=false',
        '-c', 'model_providers.hint_exec_probe.request_max_retries=0',
        '-c', 'model_providers.hint_exec_probe.stream_max_retries=0',
        '-c', 'web_search="disabled"', '-c', 'project_doc_max_bytes=0', '-c', 'mcp_servers={}',
        '-c', 'features.code_mode=true', '-c', 'features.code_mode_only=true',
        '-c', 'features.skip_host_skill_discovery=true']
    for name in DISABLED_FEATURES:
        command += ['-c', 'features.' + name + '=false']
    command += ['-']
    (path / 'command.json').write_text(json.dumps(command, indent=2))
    started = time.time()
    env = dict(os.environ, HINT_EXEC_PROBE_KEY='offline-local-fixture')
    process = await asyncio.create_subprocess_exec(*command, cwd=path, env=env,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(prompt.encode()), 35)
    except asyncio.TimeoutError:
        process.kill()
        stdout, stderr = await process.communicate()
    (path / 'stdout.jsonl').write_bytes(stdout)
    (path / 'stderr.log').write_bytes(stderr)
    events = [json.loads(line) for line in stdout.decode().splitlines() if line.startswith('{')]
    requests = [r for r in RECORDS if r['case'] == case]
    final = json.loads((path / 'final.json').read_text()) if (path / 'final.json').exists() else None
    return {'case': case, 'pid': process.pid, 'exit_code': process.returncode,
            'started_at': started, 'finished_at': time.time(), 'elapsed_seconds': time.time() - started,
            'thread_ids': [x['thread_id'] for x in events if x.get('type') == 'thread.started'],
            'final': final, 'usage': [x for x in events if x.get('type') == 'turn.completed'],
            'provider_requests': len(requests),
            'stdin_preserved_verbatim': any(prompt in json.dumps(r['body']['input'], ensure_ascii=False) or
                any(i.get('text') == prompt for m in r['body']['input'] for i in m.get('content',[]) if isinstance(i,dict)) for r in requests),
            'actual_text_format': [r['body'].get('text') for r in requests],
            'native_tools': [[{'type':t.get('type'),'name':t.get('name')} for t in r['body'].get('tools',[])] for r in requests],
            'foreign_case_in_input': any(('USER_case_b' if case == 'case_a' else 'USER_case_a') in json.dumps(r['body']['input']) for r in requests)}

async def main():
    (OUT / 'action_schema.json').write_text(json.dumps(SCHEMA, indent=2))
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    address = 'http://127.0.0.1:' + str(server.server_address[1])
    try:
        cases = await asyncio.gather(run_case('case_a', address), run_case('case_b', address))
    finally:
        server.shutdown()
        server.server_close()
        (OUT / 'requests.json').write_text(json.dumps(RECORDS))
    result = {'real_model_calls': 0, 'formal_config_changed': False,
              'synthetic_usage_excluded': True, 'cases': cases}
    (OUT / 'result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    asyncio.run(main())
