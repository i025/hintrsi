"""Meaningful contract tests against the real candidate, using only a fake process."""
import asyncio
import copy
import importlib.util
import json
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('exec_action_candidate', OUT / 'codex_exec_bridge.py')
candidate = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = candidate
spec.loader.exec_module(candidate)


def body(text='Original task'):
    return {'model': 'sdk-model-alias', 'messages': [
        {'role': 'system', 'content': 'SYSTEM_ORIGINAL'},
        {'role': 'developer', 'content': [{'type': 'text', 'text': 'Developer task rules'}]},
        {'role': 'user', 'content': text},
        {'role': 'assistant', 'content': 'I inspected the task.', 'tool_calls': [{
            'id': 'historical-call', 'type': 'function',
            'function': {'name': 'Read', 'arguments': '{"file_path":"/app/file.py"}'}}]},
        {'role': 'tool', 'tool_call_id': 'historical-call', 'content': 'Actual file content: café Ω', 'is_error': False}],
        'tools': [{'type': 'function', 'function': {'name': name, 'description': 'Original SDK ' + name,
                  'parameters': {'type': 'object', 'properties': {'file_path': {'type': 'string'}}}}}
                  for name in ('Read', 'Grep', 'Glob')]}


class ObservedBridge(candidate.CodexExecBridge):
    def __init__(self, directory, mode='final'):
        super().__init__(directory, command=[sys.executable, '-B', str(OUT / 'fixture_exec.py'), '--fixture-mode', mode])
        self.active = 0
        self.max_active = 0

    async def execute(self, *args):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            return await super().execute(*args)
        finally:
            self.active -= 1


class ExecActionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bridge = ObservedBridge(self.tmp.name)
        self.route = {'session': 'test-session', 'role': 'student', 'phase': 'solve'}

    async def asyncTearDown(self):
        await self.bridge.close()
        self.tmp.cleanup()

    def mode(self, value):
        self.bridge.command[-1] = value

    async def chat(self, request=None, route=None):
        return await asyncio.wait_for(self.bridge.chat(request or body(), route=route or self.route), 3)

    def rows(self, name):
        path = Path(self.tmp.name) / name
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def captures(self):
        return {p.parent.name: json.loads(p.read_text()) for p in Path(self.tmp.name).glob('*/fixture_capture.json')}

    async def test_full_history_and_sdk_compaction_replace_prior_messages(self):
        first = body()
        await self.chat(first)
        second = body('Compacted task summary')
        second['messages'] = [
            {'role': 'system', 'content': 'SYSTEM_UPDATED'},
            {'role': 'user', 'content': [{'type': 'text', 'text': 'Compacted task summary'},
                {'type': 'text', 'text': 'Teacher guidance: inspect the boundary.'}]},
            {'role': 'assistant', 'content': 'Current SDK summary'},
            {'role': 'tool', 'tool_call_id': 'current-call', 'content': [{'type': 'text', 'text': 'Latest failed output'}], 'is_error': True}]
        second['tool_choice'] = 'auto'
        second['parallel_tool_calls'] = False
        await self.chat(second)
        requests = self.rows('model_requests.jsonl')
        captures = self.captures()
        self.assertEqual(captures[requests[0]['request_id']]['payload']['messages'], first['messages'])
        current = captures[requests[1]['request_id']]['payload']
        self.assertEqual(current['messages'], second['messages'])
        self.assertEqual(current['tools'], second['tools'])
        self.assertEqual(current['tool_choice'], 'auto')
        self.assertIs(current['parallel_tool_calls'], False)
        self.assertNotIn('SYSTEM_ORIGINAL', json.dumps(current))
        self.assertNotIn('historical-call', json.dumps(current))
        self.assertEqual(len({row['thread_id'] for row in self.rows('model_responses.jsonl')}), 2)

    async def test_subagent_history_is_forwarded_without_native_fork(self):
        request = body()
        request['messages'].extend([
            {'role': 'tool', 'tool_call_id': 'agent-parent-call', 'content': 'Fork started — that fork is you.'},
            {'role': 'user', 'content': '<fork-boilerplate>Perform the SDK child task.</fork-boilerplate>'}])
        await self.chat(request)
        capture = next(iter(self.captures().values()))
        self.assertEqual(capture['payload']['messages'], request['messages'])
        self.assertNotIn('resume', capture['argv'])
        self.assertNotIn('--last', capture['argv'])
        self.assertNotIn('fork', capture['argv'])

    async def test_batch_conversion_sse_and_real_results_in_next_request(self):
        self.mode('batch')
        request = body()
        reply = await self.chat(request)
        message = reply['choices'][0]['message']
        calls = message['tool_calls']
        self.assertEqual(reply['choices'][0]['finish_reason'], 'tool_calls')
        self.assertEqual([c['function']['name'] for c in calls], ['Read', 'Grep', 'Glob'])
        self.assertEqual(len({c['id'] for c in calls}), 3)
        self.assertEqual(json.loads(calls[0]['function']['arguments'])['text'], 'line one\nline two')
        from codex_cli_bridge import _sse
        chunks = [chunk async for chunk in _sse(reply)]
        events = [json.loads(chunk[6:]) for chunk in chunks[:-1]]
        tool_deltas = [e['choices'][0]['delta']['tool_calls'] for e in events
                       if e['choices'][0]['delta'].get('tool_calls')]
        self.assertEqual([len(c) for c in tool_deltas], [1, 1, 1])
        self.assertEqual([c[0]['index'] for c in tool_deltas], [0, 1, 2])
        self.assertEqual(events[-1]['usage'], reply['usage'])
        request['messages'].append(message)
        request['messages'].extend({'role': 'tool', 'tool_call_id': call['id'],
            'content': 'ACTUAL_RESULT_' + call['id'], 'is_error': index == 1}
            for index, call in enumerate(reversed(calls)))
        self.mode('final')
        final = await self.chat(request)
        row = self.rows('model_requests.jsonl')[-1]
        self.assertEqual(self.captures()[row['request_id']]['payload']['messages'], request['messages'])
        self.assertEqual(final['choices'][0]['finish_reason'], 'stop')

    async def test_six_interleaved_routes_keep_payload_usage_and_files_separate(self):
        routes = [{'session': 'lane' + str(i), 'role': 'teacher', 'phase': 'generate'} for i in range(6)]
        requests = [body('Identical task LANE_' + str(i)) for i in range(6)]
        replies = await asyncio.gather(*(self.chat(request, route) for request, route in zip(requests, routes)))
        self.assertEqual(self.bridge.max_active, 6)
        self.assertEqual(len({reply['id'] for reply in replies}), 6)
        for index, reply in enumerate(replies):
            self.assertIn('LANE_' + str(index), reply['choices'][0]['message']['content'])
            self.assertEqual(reply['usage']['total_tokens'], 107 + index)
        rows = self.rows('token_usage.jsonl')
        self.assertEqual({row['session']: row['delta']['totalTokens'] for row in rows},
                         {'lane' + str(i): 107 + i for i in range(6)})
        captures = self.captures()
        self.assertEqual(len({c['output'] for c in captures.values()}), 6)
        self.assertEqual(len({row['thread_id'] for row in rows}), 6)
        self.assertEqual(self.bridge.processes, {})

    async def test_usage_cached_tokens_and_elapsed_are_recorded_once(self):
        reply = await self.chat()
        self.assertEqual(reply['usage'], {'prompt_tokens': 100, 'completion_tokens': 7, 'total_tokens': 107,
            'prompt_tokens_details': {'cached_tokens': 20}, 'completion_tokens_details': {'reasoning_tokens': 3}})
        usage = self.rows('token_usage.jsonl')
        self.assertEqual(len(usage), 1)
        self.assertEqual(usage[0]['delta']['totalTokens'], 107)
        self.assertEqual(usage[0]['delta']['cachedInputTokens'], 20)
        self.assertGreater(self.rows('model_responses.jsonl')[0]['elapsed_seconds'], 0)

    async def test_repeated_http_request_uses_new_exec_and_counts_both(self):
        first = await self.chat()
        second = await self.chat()
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(sum(row['delta']['totalTokens'] for row in self.rows('token_usage.jsonl')), 214)
        self.assertEqual(len(self.captures()), 2)

    async def test_invalid_action_variants_are_explicit_technical_errors(self):
        for mode in ('empty', 'whitespace', 'invalid_json', 'invalid_args', 'args_array', 'unknown_tool'):
            with self.subTest(mode=mode):
                self.mode(mode)
                with self.assertRaises(candidate.CodexBridgeError) as caught:
                    await self.chat()
                self.assertEqual(caught.exception.status, 422)
        self.assertEqual(self.rows('model_responses.jsonl'), [])
        self.assertEqual(len(self.rows('token_usage.jsonl')), 6)

    async def test_cli_failure_keeps_observed_usage(self):
        self.mode('failure')
        with self.assertRaises(candidate.CodexBridgeError) as caught:
            await self.chat()
        self.assertEqual(caught.exception.code, 'exec_failed')
        self.assertEqual(len(self.rows('token_usage.jsonl')), 1)
        self.assertEqual(self.rows('model_responses.jsonl'), [])
        self.assertFalse(self.bridge.stopped)
        self.assertEqual(self.bridge.processes, {})

    async def test_failed_turn_is_rejected_even_with_valid_output_and_zero_exit(self):
        self.mode('failed_zero')
        with self.assertRaises(candidate.CodexBridgeError) as caught:
            await self.chat()
        self.assertEqual(caught.exception.code, 'exec_failed')
        self.assertEqual(self.rows('model_responses.jsonl'), [])
        self.assertEqual(self.bridge.processes, {})
        self.assertEqual(len(list(Path(self.tmp.name).glob('*/final.json'))), 1)

    async def test_named_single_tool_and_no_tools_final_are_valid(self):
        self.mode('batch')
        request = body()
        request['tools'] = request['tools'][:1]
        request['tool_choice'] = {'type': 'function', 'function': {'name': 'Read'}}
        request['parallel_tool_calls'] = False
        reply = await self.chat(request)
        self.assertEqual(len(reply['choices'][0]['message']['tool_calls']), 1)
        self.mode('final')
        request = body();request['tools'] = []
        final = await self.chat(request)
        self.assertEqual(final['choices'][0]['finish_reason'], 'stop')
        self.assertNotIn('tool_calls', final['choices'][0]['message'])

    async def test_retry_notice_followed_by_success_is_not_fatal(self):
        self.mode('transient_success')
        reply = await self.chat()
        self.assertEqual(reply['choices'][0]['finish_reason'], 'stop')
        self.assertFalse(self.bridge.stopped)
        self.assertEqual(len(self.rows('token_usage.jsonl')), 1)

    async def test_cancelled_http_wait_terminates_only_its_process(self):
        self.mode('sleep')
        task = asyncio.create_task(self.bridge.chat(body(), route=self.route))
        for _ in range(100):
            if self.bridge.processes:
                break
            await asyncio.sleep(.005)
        process = next(iter(self.bridge.processes.values()))
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertIsNotNone(process.returncode)
        self.assertEqual(self.bridge.processes, {})
        self.assertFalse(self.bridge.stopped)
        errors = self.rows('model_errors.jsonl')
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]['code'], 'request_cancelled')
        self.assertEqual(errors[0]['request_id'], self.rows('model_requests.jsonl')[0]['request_id'])
        for key in ('session', 'role', 'phase'):
            self.assertEqual(errors[0][key], self.route[key])
        self.assertGreater(errors[0]['elapsed_seconds'], 0)
        self.assertNotIn('usage', errors[0])
        self.assertEqual(self.rows('token_usage.jsonl'), [])
        self.assertEqual(self.rows('model_responses.jsonl'), [])
        self.mode('final')
        self.assertEqual((await self.chat())['choices'][0]['finish_reason'], 'stop')

    async def test_stop_during_process_creation_does_not_send_prompt(self):
        spawned = asyncio.Event()
        release = asyncio.Event()
        start_process = asyncio.create_subprocess_exec
        async def delayed_registration(*args, **kwargs):
            process = await start_process(*args, **kwargs)
            spawned.set()
            await release.wait()
            return process
        with patch.object(candidate.asyncio, 'create_subprocess_exec', delayed_registration):
            task = asyncio.create_task(self.bridge.chat(body(), route=self.route))
            await asyncio.wait_for(spawned.wait(), 2)
            self.assertEqual(self.bridge.processes, {})
            self.bridge.stop('Quota stop while child process is starting')
            release.set()
            with self.assertRaises(candidate.CodexBridgeError):
                await asyncio.wait_for(task, 2)
        self.assertEqual(self.bridge.processes, {})
        self.assertEqual(self.captures(), {})
        self.assertEqual(self.rows('token_usage.jsonl'), [])

    async def test_quota_stops_concurrent_requests(self):
        self.mode('controlled')
        tasks = [asyncio.create_task(self.bridge.chat(body(text), route={**self.route, 'session': text}))
                 for text in ('SLEEP_A', 'QUOTA', 'SLEEP_B')]
        results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 3)
        self.assertTrue(all(isinstance(result, candidate.CodexBridgeError) for result in results))
        self.assertTrue(self.bridge.stopped)
        self.assertEqual(self.bridge.processes, {})

    async def test_present_tool_choice_and_parallel_fields_are_enforced(self):
        scenarios = [('none', True, 'batch', False), ('required', True, 'final', False),
                     ({'type': 'function', 'function': {'name': 'Read'}}, True, 'batch', False),
                     ('auto', False, 'batch', False), ('auto', True, 'batch', True),
                     ('none', False, 'final', True), ('required', True, 'batch', True)]
        for choice, parallel, mode, valid in scenarios:
            with self.subTest(choice=choice, parallel=parallel, mode=mode):
                self.mode(mode)
                request = body();request.update(tool_choice=choice, parallel_tool_calls=parallel)
                if valid:
                    await self.chat(request)
                else:
                    with self.assertRaises(candidate.CodexBridgeError) as caught:
                        await self.chat(request)
                    self.assertEqual(caught.exception.status, 422)

    async def test_existing_http_app_returns_stream_and_explicit_errors(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=candidate.create_app(self.bridge)), base_url='http://fixture') as client:
            self.mode('batch')
            response = await client.post('/sessions/http-lane/teacher/generate/v1/chat/completions', json={**body(), 'stream': True})
            self.assertEqual(response.status_code, 200)
            self.assertIn('data: [DONE]', response.text)
            self.assertEqual(response.text.count('"tool_calls": [{'), 3)
            self.assertEqual(self.rows('model_requests.jsonl')[-1]['session'], 'http-lane')
            self.mode('invalid_json')
            bad = await client.post('/v1/chat/completions', json=body())
            self.assertEqual(bad.status_code, 422)
            self.assertEqual(bad.json()['error']['type'], 'invalid_action')

    def test_default_command_is_fresh_and_schema_limits_tool_names(self):
        command = candidate.default_command()
        self.assertEqual(command[:2], ['codex', 'exec'])
        for flag in ('--ephemeral', '--json', '--ignore-user-config', '--ignore-rules'):
            self.assertIn(flag, command)
        for value in ('resume', 'fork', '--last', '--timeout', '--cwd'):
            self.assertNotIn(value, command)
        self.assertIn('skills.bundled.enabled=false', command)
        schema = candidate.action_schema(body()['tools'])
        self.assertEqual(schema['properties']['tool_calls']['items']['properties']['name']['enum'], ['Read', 'Grep', 'Glob'])
        self.assertEqual(candidate.action_schema([])['properties']['tool_calls']['maxItems'], 0)


if __name__ == '__main__':
    started = time.monotonic()
    with (OUT / 'action_contract_tests.log').open('w') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(ExecActionTests))
    record = {'passed': result.wasSuccessful(), 'tests': result.testsRun, 'failures': len(result.failures),
              'errors': len(result.errors), 'elapsed_seconds': time.monotonic() - started,
              'candidate_source': candidate.__file__, 'real_model_calls': 0, 'real_codex_processes': 0,
              'subprocess_fixture': str(OUT / 'fixture_exec.py'),
              'scope': 'Actual bridge subprocess/stdin/JSONL/HTTP/SSE execution; fake Python child supplies model decisions.'}
    (OUT / 'action_contract_tests.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
