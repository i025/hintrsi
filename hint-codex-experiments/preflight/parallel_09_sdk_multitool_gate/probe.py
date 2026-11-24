"""Exercise the real LiteLLM converter and SDK offline, without the proxy CLI startup."""

import ast
import io
import json
import os
import tarfile
import time
from pathlib import Path

import docker
import pyarrow.parquet as pq

ROOT = Path('/srv/lab-disks/disk2/users/xymo/hint-codex-experiments')
OUT = ROOT / 'preflight/parallel_09_sdk_multitool_gate' / os.environ.get('MULTITOOL_GATE_ATTEMPT', 'attempt_01')
SOURCE = ROOT / 'source_parallel_09'
CANDIDATE = SOURCE / 'codex_cli_bridge.py'
PYTHON = '/opt/python3.12-tmp/bin/python3'

GUEST = r'''
import ast, asyncio, importlib.metadata, json, os, shlex, subprocess, threading, time, urllib.request
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

OUT = Path('/tmp/multitool_out')
OUT.mkdir()
(OUT / 'adapter_init.log').write_text('Importing the actual LiteLLM converter.\n')
from litellm.types.utils import ModelResponse, ModelResponseStream
from litellm.llms.anthropic.experimental_pass_through.adapters.streaming_iterator import AnthropicStreamWrapper
from litellm.llms.anthropic.experimental_pass_through.adapters.transformation import AnthropicAdapter
import streaming_fix
streaming_fix.apply()
(OUT / 'adapter_init.log').write_text('Actual LiteLLM converter and original streaming_fix loaded.\n')
requests = []
raw_requests = []
transport_records = []
responses = []
plans = []
request_lock = threading.Lock()
ns = {'json': json}
exec(compile(ast.parse(Path('/tmp/candidate_sse.py').read_text()), '/tmp/candidate_sse.py', 'exec'), ns)
sse = ns['_sse']

async def render_stream(response):
    chunks = [chunk async for chunk in sse(response)]
    async def models():
        for chunk in chunks:
            for line in chunk.splitlines():
                if line.startswith('data: ') and line != 'data: [DONE]':
                    yield ModelResponseStream(**json.loads(line[6:]))
    wrapper = AnthropicStreamWrapper(models(), model='gpt-6.1-terra')
    payload = b''.join([chunk async for chunk in wrapper.async_anthropic_sse_wrapper()])
    transport_records.append({'response_id': response['id'], 'openai_sse': ''.join(chunks), 'anthropic_sse': payload.decode()})
    return payload

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        raw = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        raw_requests.append(raw)
        if 'count_tokens' in self.path:
            payload = json.dumps({'input_tokens': 100}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        body = AnthropicAdapter().translate_completion_input_params(dict(raw))
        with request_lock:
            requests.append(body)
            names = {t.get('function', {}).get('name') for t in body.get('tools', [])}
            main = 'Read' in names and 'Bash' in names
            if main:
                assert plans, 'Unexpected extra main-model request'
                message = plans.pop(0)
            else:
                message = {'role': 'assistant', 'content': 'OFFLINE_AUXILIARY_COMPLETE'}
            calls = message.get('tool_calls')
            response = {
                'id': 'chatcmpl-offline-' + str(len(responses)),
                'object': 'chat.completion', 'created': int(time.time()),
                'model': 'gpt-6.1-terra',
                'choices': [{'index': 0, 'message': message, 'finish_reason': 'tool_calls' if calls else 'stop'}],
                'usage': {'prompt_tokens': 100, 'completion_tokens': 25, 'total_tokens': 125},
            }
            responses.append({'path': self.path, 'main': main, 'response': response})
        if body.get('stream'):
            payload = asyncio.run(render_stream(response))
            kind = 'text/event-stream'
        else:
            payload = json.dumps(AnthropicAdapter().translate_completion_output_params(ModelResponse(**response))).encode()
            kind = 'application/json'
        self.send_response(200)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def tool(call_id, name, values):
    return {'id': call_id, 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(values, ensure_ascii=False)}}


def python_command(program):
    return '/opt/python3.12-tmp/bin/python3 -c ' + shlex.quote(program)


subprocess.run(['git', 'init', '-q', '/app'], check=True)
subprocess.run(['git', '-C', '/app', 'config', 'user.email', 'offline@example.invalid'], check=True)
subprocess.run(['git', '-C', '/app', 'config', 'user.name', 'Offline fixture'], check=True)
fixture = Path('/app/fixture Ω "quoted".txt')
fixture_text = 'OFFLINE_READ_OK café Ω\nLiteral "quotes", backslash \\ and a second line.\n'
fixture.write_text(fixture_text)
subprocess.run(['git', '-C', '/app', 'add', '.'], check=True)
subprocess.run(['git', '-C', '/app', 'commit', '-qm', 'Offline fixture'], check=True)
base = subprocess.check_output(['git', '-C', '/app', 'rev-parse', 'HEAD'], text=True).strip()
server = ThreadingHTTPServer(('127.0.0.1', 8767), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
result = {'passed': False, 'real_model_calls': 0, 'network': 'none', 'api_hosts': ['127.0.0.1:8767'], 'validation_scope': 'candidate SSE -> actual LiteLLM converter with original streaming_fix -> real Claude SDK; proxy CLI startup excluded', 'synthetic_usage_excluded': True, 'litellm_version': importlib.metadata.version('litellm'), 'sdk_version': importlib.metadata.version('claude-agent-sdk'), 'phases': []}
try:
    session = None
    for phase in ('initial', 'resume'):
        phase_start = len(requests)
        marker_text = phase + ' marker café Ω\nA literal "quote" and backslash \\ preserved.\n'
        marker_path = Path('/app/' + phase + '_marker.txt')
        read_path = fixture if phase == 'initial' else Path('/app/initial_marker.txt')
        read_expected = fixture_text if phase == 'initial' else initial_marker_text
        calls = [
            tool(phase + '-read', 'Read', {'file_path': str(read_path)}),
            tool(phase + '-inspect', 'Bash', {'command': python_command('from pathlib import Path; print(Path(' + repr(str(fixture)) + ').read_text(), end="")'), 'description': 'Read the independent Unicode fixture', 'timeout': 30000}),
            tool(phase + '-write', 'Bash', {'command': python_command('from pathlib import Path; Path(' + repr(str(marker_path)) + ').write_text(' + repr(marker_text) + '); print("OFFLINE_WRITE_OK")'), 'description': 'Write an independent escaped-text fixture', 'timeout': 30000}),
        ]
        commentary = 'Execute the three independent local checks; preserve café Ω, quotes, and backslashes.'
        plans[:] = [
            {'role': 'assistant', 'content': commentary, 'tool_calls': calls},
            {'role': 'assistant', 'content': 'OFFLINE_MULTITOOL_COMPLETE_' + phase.upper()},
        ]
        prompt = Path('/tmp/' + phase + '_prompt.txt')
        prompt.write_text('Run the three local fixture checks and report completion. This is an offline protocol test.\n')
        output = OUT / phase
        command = ['/opt/python3.12-tmp/bin/python3', '/tmp/sdk_script.py', '--cwd', '/app', '--base_commit', base, '--output_dir', str(output), '--log_path', str(OUT / (phase + '.log'))]
        if session:
            command += ['--resume_session_id', session, '--extra_message_file', str(prompt)]
        else:
            command += ['--problem_statement_file', str(prompt)]
        started = time.monotonic()
        completed = subprocess.run(command, capture_output=True, timeout=200)
        (OUT / (phase + '_stdout.log')).write_bytes(completed.stdout + completed.stderr)
        assert completed.returncode == 0, completed.stderr[-3000:]
        trajs = json.loads((output / 'trajs.json').read_text())
        meta = trajs['metadata']
        current_session = meta['ResultMessage']['session_id']
        assert meta['status'] == 'completed' and not meta['ResultMessage']['is_error'], meta
        if session:
            assert session == current_session
        session = current_session
        assert not plans, 'The SDK did not finish both planned responses'
        phase_requests = requests[phase_start:]
        expected_ids = {call['id'] for call in calls}
        results = {m['tool_call_id']: m for body in phase_requests for m in body.get('messages', []) if m.get('role') == 'tool' and m.get('tool_call_id') in expected_ids}
        assert set(results) == expected_ids, results
        assert all(not m.get('is_error') for m in results.values()), results
        assert all(line in results[phase + '-read']['content'] for line in read_expected.splitlines()), results[phase + '-read']
        assert fixture_text.strip() in results[phase + '-inspect']['content']
        assert 'OFFLINE_WRITE_OK' in results[phase + '-write']['content']
        assert marker_path.read_text() == marker_text
        assistant_messages = [m for body in phase_requests for m in body.get('messages', []) if m.get('role') == 'assistant']
        received = {call['id']: call for m in assistant_messages for call in m.get('tool_calls', []) if call['id'] in expected_ids}
        assert set(received) == expected_ids
        for expected in calls:
            actual = received[expected['id']]
            assert actual['function']['name'] == expected['function']['name']
            actual_input = json.loads(actual['function']['arguments'])
            for key, value in json.loads(expected['function']['arguments']).items():
                assert actual_input[key] == value, (key, actual_input, expected)
        assert commentary in trajs['trajectories']['main_agent']
        assert 'OFFLINE_MULTITOOL_COMPLETE_' + phase.upper() in meta['ResultMessage']['result']
        assert '__unparsedToolInput' not in json.dumps(phase_requests)
        initial_marker_text = marker_text
        result['phases'].append({'phase': phase, 'sdk_session_id': session, 'tool_results': results, 'tool_ids': sorted(expected_ids), 'arguments_preserved': True, 'commentary_preserved': True, 'marker_file_exact': True, 'sdk_completed': True, 'wall_seconds': time.monotonic() - started})
        print(json.dumps({'phase': phase, 'passed': True}), flush=True)
    main_requests = [body for body in requests if 'Read' in {t.get('function', {}).get('name') for t in body.get('tools', [])}]
    result['main_requests'] = len(main_requests)
    result['tool_names'] = [t['function']['name'] for t in main_requests[0]['tools']]
    result['tool_schema_stable'] = all(body['tools'] == main_requests[0]['tools'] for body in main_requests)
    assert result['tool_schema_stable']
    result['passed'] = True
finally:
    server.shutdown()
    server.server_close()
    (OUT / 'raw_sdk_requests.json').write_text(json.dumps(raw_requests, ensure_ascii=False, indent=2))
    (OUT / 'transport_records.json').write_text(json.dumps(transport_records, ensure_ascii=False, indent=2))
    (OUT / 'captured_requests.json').write_text(json.dumps(requests, ensure_ascii=False, indent=2))
    (OUT / 'synthetic_responses.json').write_text(json.dumps(responses, ensure_ascii=False, indent=2))
    (OUT / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False), flush=True)
'''


def put(container, path, data):
    data = data.encode() if isinstance(data, str) else data
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        item = tarfile.TarInfo(Path(path).name)
        item.size = len(data)
        archive.addfile(item, io.BytesIO(data))
    container.put_archive(str(Path(path).parent), stream.getvalue())


def selected_function(path, name):
    tree = ast.parse(path.read_text())
    node = next(node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name)
    return ast.unparse(node) + '\n'


def main():
    OUT.mkdir()
    client = docker.DockerClient(base_url='unix://' + str(ROOT / 'vm/docker.sock'), timeout=600)
    row = next(row for row in pq.read_table(ROOT.parent / 'hint-baseline-run/data/deep_swe_tasks.parquet').to_pylist() if row['instance_id'] == 'obsidian-linter-auto-table-of-contents')
    image = client.images.get(row['image_name'])
    env = {value.split('=', 1)[0]: 'offline-fixture' for value in image.attrs['Config'].get('Env', []) if any(word in value.split('=', 1)[0].upper() for word in ('KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'ANTHROPIC', 'OPENAI', 'OFOX', 'HUBROUTER'))}
    env.update(ANTHROPIC_BASE_URL='http://127.0.0.1:8767', ANTHROPIC_AUTH_TOKEN='offline-fixture', ANTHROPIC_MODEL='gpt-6.1-terra', ANTHROPIC_SMALL_FAST_MODEL='gpt-6.1-terra', CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1', IS_SANDBOX='1', API_TIMEOUT_MS='60000', PYTHONDONTWRITEBYTECODE='1', SYSTEM_PROMPT_FILE='', HTTP_PROXY='', HTTPS_PROXY='', ALL_PROXY='', http_proxy='', https_proxy='', all_proxy='', NO_PROXY='*', BUN_JSC_useJIT='0', LITELLM_LOCAL_MODEL_COST_MAP='True', LITELLM_TELEMETRY='False')
    container = client.containers.run(image.id, name='codex-parallel09-multitool-offline', entrypoint='', command=['tail', '-f', '/dev/null'], detach=True, mem_limit='128g', nano_cpus=8_000_000_000, privileged=True, network_mode='none', environment=env, labels={'hint.experiment_name': 'preflight_parallel_09_sdk_multitool_gate'}, volumes={'/opt/hint-codex-runtime/python': {'bind': '/opt/python3.12-tmp', 'mode': 'ro'}})
    record = {'started_at_unix': time.time(), 'real_model_calls': 0, 'network': 'none', 'container': container.id, 'candidate': str(CANDIDATE), 'sdk_source': str(SOURCE / 'run_cc_sdk.py')}
    try:
        code, output = container.exec_run(['bash', '-c', 'rm -rf /app /root/.claude; mkdir -p /app'])
        assert code == 0, output
        for path, target in [(SOURCE / 'run_cc_sdk.py', '/tmp/sdk_script.py'), (SOURCE / 'logging_utils.py', '/tmp/logging_utils.py'), (SOURCE / 'litellm_proxy/claude_code_proxy.py', '/tmp/litellm_call_backs.py'), (SOURCE / 'litellm_proxy/streaming_fix.py', '/tmp/streaming_fix.py')]:
            put(container, target, path.read_bytes())
        put(container, '/tmp/candidate_sse.py', selected_function(CANDIDATE, '_sse'))
        put(container, '/tmp/probe_multitool.py', GUEST)
        started = time.monotonic()
        code, output = container.exec_run(['timeout', '--signal=INT', '--kill-after=20', '650', PYTHON, '/tmp/probe_multitool.py'], workdir='/app')
        (OUT / 'stdout.log').write_bytes(output)
        chunks, _ = container.get_archive('/tmp/multitool_out')
        with tarfile.open(fileobj=io.BytesIO(b''.join(chunks))) as archive:
            for item in archive.getmembers():
                if item.isfile():
                    target = OUT / Path(item.name).relative_to('multitool_out')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.extractfile(item).read())
        result = json.loads((OUT / 'result.json').read_text())
        record.update(exit_code=code, passed=code == 0 and result['passed'], host_exec_seconds=time.monotonic() - started)
    finally:
        container.remove(force=True)
        client.close()
        record.update(container_removed=True, finished_at_unix=time.time())
        (OUT / 'host_result.json').write_text(json.dumps(record, indent=2) + '\n')
    if record.get('passed'):
        (OUT.parent / 'result.json').write_bytes((OUT / 'result.json').read_bytes())
        (OUT.parent / 'host_result.json').write_bytes((OUT / 'host_result.json').read_bytes())
    print(json.dumps(record), flush=True)
    return 0 if record.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
