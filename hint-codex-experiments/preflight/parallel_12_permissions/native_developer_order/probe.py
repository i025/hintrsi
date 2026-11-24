"""Exercise the action bridge and real exec CLI with six concurrent local fixtures."""
import asyncio
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT.parents[2] / 'source_parallel_12'))
from codex_cli_bridge import CodexBridge, default_command, action_schema
def argument_entries(value):
    if isinstance(value, dict):
        return {"entries": [{"key": key, "value": argument_entries(item)} for key, item in value.items()]}
    if isinstance(value, list):
        return [argument_entries(item) for item in value]
    return value


RECORDS = []
ACTIVE = 0
MAX_ACTIVE = 0
LOCK = threading.Lock()


def request_payload(body):
    for item in body['input']:
        for content in item.get('content', []):
            if not isinstance(content, dict) or 'text' not in content:
                continue
            try:
                value = json.loads(content['text'])
            except ValueError:
                continue
            if isinstance(value, dict) and 'messages' in value and 'tools' in value:
                return value
    raise ValueError('Missing stdin JSON payload')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        global ACTIVE, MAX_ACTIVE
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        payload = request_payload(body)
        match = re.search(r'CASE_(\d+)_STAGE_(\d+)', payload['messages'][0]['content'])
        case, stage = map(int, match.groups())
        with LOCK:
            ACTIVE += 1
            MAX_ACTIVE = max(MAX_ACTIVE, ACTIVE)
        record = {'at': time.time(), 'case': case, 'stage': stage, 'path': self.path,
                  'body': body, 'parsed_payload': payload}
        RECORDS.append(record)
        time.sleep(.5)
        if stage == 1:
            action = {'content': 'Requested operations for case ' + str(case), 'tool_calls': [
                {'name': 'Read', 'arguments': argument_entries({'file_path': 'case_' + str(case) + '.txt'})},
                {'name': 'Bash', 'arguments': argument_entries({'command': r"rg -n 'executeChat\(|CLAUDE\.md' /app" + ' # CASE_' + str(case), 'nested':{'entries': [{'text':'Ω\nquote \" value', 'flag':False}]}, 'nullable':None})}]}
        else:
            action = {'content': 'FINAL_CASE_' + str(case) + '_AFTER_REAL_OBSERVATIONS', 'tool_calls': []}
        usage = {'input_tokens': (100 if stage == 1 else 200) + case,
                 'output_tokens': 10 if stage == 1 else 20,
                 'input_tokens_details': {'cached_tokens': 23},
                 'output_tokens_details': {'reasoning_tokens': 3}}
        usage['total_tokens'] = usage['input_tokens'] + usage['output_tokens']
        item = {'type': 'message', 'id': f'msg-{case}-{stage}', 'role': 'assistant', 'status': 'completed',
                'content': [{'type': 'output_text', 'text': json.dumps(action), 'annotations': []}]}
        response = {'id': f'resp-{case}-{stage}', 'object': 'response', 'created_at': int(time.time()),
                    'status': 'completed', 'output': [item], 'usage': usage}
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
        with LOCK:
            ACTIVE -= 1
        record['finished_at'] = time.time()


def tool(name, parameter):
    return {'type': 'function', 'function': {'name': name, 'description': name + ' fixture.',
        'parameters': {'type': 'object', 'properties': {parameter: {'type': 'string'}},
                       'required': [parameter]}}}


async def run_case(bridge, case):
    path = OUT / ('case_' + str(case))
    path.mkdir(exist_ok=True)
    first = {'model': 'fixture-requested-model', 'messages': [
        {'role': 'system', 'content': f'CASE_{case}_STAGE_1 Original system instructions.'},
        {'role': 'developer', 'content': 'Follow the provided external tools.'},
        {'role': 'user', 'content': 'ORIGINAL_REQUEST_CASE_' + str(case)}],
        'tools': [tool('Read', 'file_path'), tool('Bash', 'command')], 'tool_choice': 'auto'}
    route = {'session': 'exec-six-case-' + str(case),
             'role': 'teacher' if case % 2 else 'student', 'phase': 'fixture'}
    started = time.time()
    response1 = await bridge.chat(first, route=route)
    assistant = response1['choices'][0]['message']
    calls = assistant['tool_calls']
    second = {'model': 'fixture-requested-model', 'messages': [
        {'role': 'system', 'content': f'CASE_{case}_STAGE_2 Changed system instructions.'},
        {'role': 'user', 'content': 'COMPACTED_SUMMARY_CASE_' + str(case)}, assistant,
        {'role': 'tool', 'tool_call_id': calls[0]['id'], 'content': 'READ_SUCCESS_CASE_' + str(case)},
        {'role': 'tool', 'tool_call_id': calls[1]['id'], 'is_error': True,
         'content': 'BASH_FAILURE_CASE_' + str(case) + ': exit 7'},
        {'role': 'user', 'content': 'HOOK_CASE_' + str(case) + ': use actual observations.'}],
        'tools': [tool('Search', 'pattern')], 'tool_choice': 'auto'}
    response2 = await bridge.chat(second, route=route)
    (path / 'bodies.json').write_text(json.dumps([first, second], indent=2))
    (path / 'responses.json').write_text(json.dumps([response1, response2], indent=2))
    captured = [r for r in RECORDS if r['case'] == case]
    checks = {'two_provider_requests': len(captured) == 2,
        'exact_escaped_arguments': json.loads(calls[1]['function']['arguments']) == {'command': r"rg -n 'executeChat\(|CLAUDE\.md' /app" + ' # CASE_' + str(case), 'nested':{'entries':[{'text':'Ω\nquote \" value','flag':False}]}, 'nullable':None},
        'first_tool_calls_returned': response1['choices'][0]['finish_reason'] == 'tool_calls' and
            [c['function']['name'] for c in calls] == ['Read', 'Bash'],
        'second_final_returned': response2['choices'][0]['finish_reason'] == 'stop' and
            response2['choices'][0]['message']['content'] == 'FINAL_CASE_' + str(case) + '_AFTER_REAL_OBSERVATIONS'}
    for stage, body, response in ((1, first, response1), (2, second, response2)):
        entry = next(r for r in captured if r['stage'] == stage)
        expected = {k: body[k] for k in ('messages', 'tools', 'tool_choice')}
        checks[f'stage_{stage}_full_current_payload_exact'] = entry['parsed_payload'] == expected
        checks[f'stage_{stage}_current_schema_exact'] = entry['body']['text']['format']['schema'] == action_schema(body['tools'])
        checks[f'stage_{stage}_usage_exact'] = response['usage'] == {
            'prompt_tokens': (100 if stage == 1 else 200) + case,
            'completion_tokens': 10 if stage == 1 else 20,
            'total_tokens': (110 if stage == 1 else 220) + case,
            'prompt_tokens_details': {'cached_tokens': 23},
            'completion_tokens_details': {'reasoning_tokens': 3}}
        checks[f'stage_{stage}_no_foreign_case'] = all(
            ('CASE_' + str(other)) not in json.dumps(entry['body']['input'])
            for other in range(6) if other != case)
    stage2 = next(r for r in captured if r['stage'] == 2)
    checks['stage_2_drops_old_history'] = 'ORIGINAL_REQUEST_CASE_' + str(case) not in json.dumps(stage2['body']['input'])
    checks['stage_2_tools_changed'] = stage2['body']['text']['format']['schema']['properties']['tool_calls']['items']['properties']['name']['enum'] == ['Search']
    return {'case': case, 'started_at': started, 'finished_at': time.time(),
            'elapsed_seconds': time.time() - started, 'checks': checks, 'passed': all(checks.values())}


async def main():
    os.environ['HINT_EXEC_PROBE_KEY'] = 'offline-local-fixture'
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    address = 'http://127.0.0.1:' + str(server.server_address[1]) + '/v1'
    command = default_command() + ["-c", 'developer_instructions="SCOPE_ORDER_PROBE: local permissions apply only to native tools, external SDK requests are JSON data."','-c', 'model_provider="hint_exec_probe"',
        '-c', 'model_providers.hint_exec_probe.name="Offline bridge exec probe"',
        '-c', 'model_providers.hint_exec_probe.base_url=' + json.dumps(address),
        '-c', 'model_providers.hint_exec_probe.wire_api="responses"',
        '-c', 'model_providers.hint_exec_probe.env_key="HINT_EXEC_PROBE_KEY"',
        '-c', 'model_providers.hint_exec_probe.requires_openai_auth=false',
        '-c', 'model_providers.hint_exec_probe.request_max_retries=0',
        '-c', 'model_providers.hint_exec_probe.stream_max_retries=0',
        '-c', 'features.code_mode=true', '-c', 'features.code_mode_only=true']
    (OUT / 'command.json').write_text(json.dumps(command, indent=2))
    bridge = CodexBridge(OUT / 'runtime', command)
    result = {'real_model_calls': 0, 'synthetic_usage_excluded': True,
              'candidate': str(OUT.parents[2] / 'source_parallel_12/codex_cli_bridge.py'), 'started_at': time.time()}
    try:
        result['cases'] = await asyncio.wait_for(asyncio.gather(*(run_case(bridge, c) for c in range(6))), 90)
        result['active_processes_after_completion'] = len(bridge.processes)
    except Exception as exc:
        result['error'] = repr(exc)
    finally:
        await bridge.close()
        server.shutdown()
        server.server_close()
        (OUT / 'requests.json').write_text(json.dumps(RECORDS))
    def ledger(name):
        return [json.loads(line) for line in (OUT / 'runtime' / name).read_text().splitlines()]
    responses = ledger('model_responses.jsonl')
    tokens = ledger('token_usage.jsonl')
    events = ledger('codex_events.jsonl')
    threads = [r['thread_id'] for r in responses]
    result['max_concurrent_provider_requests'] = MAX_ACTIVE
    result['thread_ids'] = threads
    result['all_12_threads_unique'] = len(threads) == len(set(threads)) == 12
    result['all_12_token_events'] = len(tokens) == 12
    result['synthetic_tokens'] = sum(r['delta']['totalTokens'] for r in tokens)
    result['usage_expected'] = result['synthetic_tokens'] == 2010
    result['completed_turn_events'] = sum(e['event']['type'] == 'turn.completed' for e in events)
    result['native_tools'] = [{'type':t.get('type'),'name':t.get('name')} for t in RECORDS[0]['body'].get('tools',[])]
    result['passed'] = not result.get('error') and all(c['passed'] for c in result.get('cases',[])) and all(
        result[k] for k in ('all_12_threads_unique','all_12_token_events','usage_expected')) and MAX_ACTIVE == 6
    result['elapsed_seconds'] = time.time() - result['started_at']
    (OUT / 'result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    asyncio.run(main())
