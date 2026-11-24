"""Run the candidate bridge and real CLI against the offline cancellation provider."""
import asyncio
import json
import os
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

OUT = Path(__file__).parent
sys.path.insert(0, str(OUT / 'candidate'))
from codex_cli_bridge import CodexBridge, CodexRPCClient, MODEL, default_command
import probe_tool_output as fixture

async def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), fixture.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    os.environ['HINT_LOCAL_PROBE_KEY'] = 'offline-local-fixture'
    address = 'http://127.0.0.1:' + str(server.server_address[1]) + '/v1'
    results = []
    try:
        for active in (False, True):
            fixture.CASE = 'output_while_active' if active else 'output_after_final'
            run_dir = OUT / 'candidate_native' / fixture.CASE
            run_dir.mkdir(parents=True, exist_ok=True)
            command = default_command() + ['-c', 'model_provider="hint_local_probe"',
                '-c', 'model_providers.hint_local_probe.name="Offline loopback probe"',
                '-c', 'model_providers.hint_local_probe.base_url=' + json.dumps(address),
                '-c', 'model_providers.hint_local_probe.wire_api="responses"',
                '-c', 'model_providers.hint_local_probe.env_key="HINT_LOCAL_PROBE_KEY"',
                '-c', 'model_providers.hint_local_probe.requires_openai_auth=false',
                '-c', 'model_providers.hint_local_probe.request_max_retries=0',
                '-c', 'model_providers.hint_local_probe.stream_max_retries=0',
                '-c', 'features.code_mode=true', '-c', 'features.code_mode_only=true']
            rpc = CodexRPCClient(command, stderr_path=run_dir / 'stderr.log', cwd=run_dir)
            bridge = CodexBridge(run_dir / 'bridge', rpc)
            body = {'model': MODEL, 'messages': [{'role': 'system', 'content': 'Offline protocol fixture.'},
                    {'role': 'user', 'content': 'Run the offline termination fixture.'}],
                    'tools': [{'type': 'function', 'function': {'name': 'Read', 'description': 'Read a fixture.',
                        'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}},
                                       'required': ['path']}}}]}
            route = {'session': fixture.CASE, 'role': 'student', 'phase': 'solve'}
            row = {'case': fixture.CASE, 'passed': False, 'started_at': time.time()}
            try:
                first = await asyncio.wait_for(bridge.chat(body, route=route), 20)
                tool = first['choices'][0]['message']['tool_calls'][0]
                body['messages'].append(first['choices'][0]['message'])
                await asyncio.sleep(4)
                state = next(iter(bridge.sessions.values()))
                row['native_active_before_sdk_result'] = state.active
                row['original_thread_id'] = state.thread_id
                row['original_turn_id'] = state.turn_id
                body['messages'].append({'role': 'tool', 'tool_call_id': tool['id'],
                    'content': 'LATE_SDK_TOOL_RESULT', 'is_error': True})
                row['sdk_result_received_at'] = time.time()
                final = await asyncio.wait_for(bridge.chat(body, route=route), 20)
                row['returned_at'] = time.time()
                message = final['choices'][0]['message']
                assert message['content'] == 'AFTER_ACTUAL_RESULT', message
                assert final['choices'][0]['finish_reason'] == 'stop'
                assert state.thread_id == row['original_thread_id']
                assert state.pending[tool['id']].result is None
                history = await rpc.request('thread/read', {'threadId': state.thread_id, 'includeTurns': True})
                assert 'LATE_SDK_TOOL_RESULT' in json.dumps(history)
                requests = [r for r in fixture.RECORDS if r['case'] == fixture.CASE]
                delivered = [i for i in requests[-1]['body']['input']
                             if i.get('type') == 'function_call_output' and i.get('name') == 'Read']
                assert len(delivered) == 1, delivered
                actual = json.loads(delivered[0]['output'])
                assert actual['tool_call_id'] == tool['id']
                assert actual['is_error'] is True
                assert actual['output'] == 'LATE_SDK_TOOL_RESULT'
                count = len(fixture.RECORDS)
                await bridge.chat(body, route=route)
                assert len(fixture.RECORDS) == count
                events = [json.loads(l) for l in (run_dir / 'bridge/codex_events.jsonl').read_text().splitlines()]
                tools = [e for e in events if e['event'].get('method') == 'item/tool/call']
                assert len(tools) == 1
                usage = [json.loads(l) for l in (run_dir / 'bridge/token_usage.jsonl').read_text().splitlines()]
                total = sum(r['delta']['totalTokens'] for r in usage)
                assert total == state.usage_total['totalTokens'] == 100
                row.update(passed=True, sdk_returned_content=message['content'], tool_executions=len(tools),
                    final_thread_id=state.thread_id, final_turn_id=state.turn_id,
                    actual_result_visible_in_native_history=True, actual_result=actual,
                    provider_request_count=len(requests), synthetic_tokens=total,
                    recovery_records=[json.loads(l) for l in (run_dir / 'bridge/tool_result_recoveries.jsonl').read_text().splitlines()])
            except Exception as exc:
                row['error'] = repr(exc)
            finally:
                await bridge.close()
                row['elapsed_seconds'] = time.time() - row['started_at']
                results.append(row)
    finally:
        server.shutdown()
        server.server_close()
        target = OUT / 'candidate_native'
        target.mkdir(exist_ok=True)
        (target / 'requests.json').write_text(json.dumps(fixture.RECORDS, ensure_ascii=False))
        (target / 'result.json').write_text(json.dumps({'real_model_calls': 0,
            'synthetic_usage_excluded': True, 'cases': results}, indent=2))
    print(json.dumps(results, indent=2))
    return 0 if all(row['passed'] for row in results) else 1

if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
