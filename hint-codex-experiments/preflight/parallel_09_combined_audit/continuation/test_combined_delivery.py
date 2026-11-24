"""Combined checked bridge interactions and explicit API-contract probes; zero model."""
import asyncio
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'source_parallel_09_checked/codex_cli_bridge.py'
spec = importlib.util.spec_from_file_location('checked_delivery_bridge', SOURCE)
bridge_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bridge_module
spec.loader.exec_module(bridge_module)


class RecoveryRPC:
    def __init__(self):
        self.event_callback = None
        self.calls = []
        self.responses = []
        self.outputs = []
        self.thread = 'combined-thread'
        self.turn = None
        self.cancelled = set()
        self.received = set()
        self.tool_count = 1
        self.retry_recovery = False
        self.total = 0

    async def start(self):
        pass

    async def close(self):
        pass

    def emit(self, method, params, rpc_id=None):
        event = {'method': method, 'params': params}
        if rpc_id is not None:
            event['id'] = rpc_id
        self.event_callback(event)

    async def request(self, method, params):
        self.calls.append((method, copy.deepcopy(params)))
        if method == 'thread/start':
            return {'thread': {'id': self.thread}, 'model': bridge_module.MODEL}
        if method == 'turn/start':
            self.turn = 'turn-' + str(sum(m == method for m, _ in self.calls))
            self.emit('turn/started', {'threadId': self.thread, 'turn': {'id': self.turn}})
            if params.get('toolOutput'):
                self.outputs.append(copy.deepcopy(params['toolOutput']))
                if self.retry_recovery:
                    self.emit('error', {'threadId': self.thread, 'turnId': self.turn,
                        'willRetry': True, 'error': {'message': 'Reconnecting...',
                        'codexErrorInfo': {'responseStreamDisconnected': {'httpStatusCode': None}}}})
                await asyncio.sleep(.01)
                self.finish('ACTUAL_RESULT_' + str(len(self.outputs)))
            elif not self.tool_count:
                self.finish('ORIGINAL_ASSISTANT_TEXT')
            else:
                for index in range(self.tool_count):
                    call = 'call-' + str(index)
                    self.emit('item/tool/call', {'threadId': self.thread, 'turnId': self.turn,
                        'callId': call, 'tool': 'Read', 'arguments': {'path': '/app/' + call}}, 'rpc-' + call)
            return {'turn': {'id': self.turn}}
        return {}

    async def respond(self, rpc_id, result):
        self.responses.append((rpc_id, copy.deepcopy(result)))
        call = rpc_id[4:]
        self.received.add(call)
        self.emit('item/completed', {'threadId': self.thread, 'turnId': self.turn,
            'item': {'type': 'dynamicToolCall', 'id': call, 'status': 'completed',
                     'success': result['success'], 'contentItems': result['contentItems']}})
        await asyncio.sleep(0)
        if len(self.received) == self.tool_count and not self.cancelled:
            self.finish('NORMAL_RESULTS')

    def cancel(self, call):
        self.cancelled.add(call)
        self.emit('item/completed', {'threadId': self.thread, 'turnId': self.turn,
            'item': {'type': 'dynamicToolCall', 'id': call, 'status': 'failed',
                     'success': False, 'contentItems': []}})

    def finish(self, text):
        self.total += 25
        tokens = {'inputTokens': self.total - 5, 'outputTokens': 5, 'totalTokens': self.total}
        self.emit('thread/tokenUsage/updated', {'threadId': self.thread, 'turnId': self.turn,
            'tokenUsage': {'last': tokens, 'total': tokens}})
        self.emit('item/completed', {'threadId': self.thread, 'turnId': self.turn,
            'item': {'type': 'agentMessage', 'text': text}})
        self.emit('turn/completed', {'threadId': self.thread,
                                   'turn': {'id': self.turn, 'status': 'completed'}})


def request():
    return {'model': bridge_module.MODEL, 'messages': [
        {'role': 'system', 'content': 'ORIGINAL_SYSTEM'}, {'role': 'user', 'content': 'Original task'}],
        'tools': [{'type': 'function', 'function': {'name': 'Read', 'description': 'Read files',
                    'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}}}}}]}


class CombinedDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rpc = RecoveryRPC()
        self.bridge = bridge_module.CodexBridge(self.tmp.name, rpc=self.rpc)
        self.body = request()
        self.route = {'session': 'combined', 'role': 'teacher', 'phase': 'generate'}

    async def asyncTearDown(self):
        await self.bridge.close()
        self.tmp.cleanup()

    async def chat(self):
        return await asyncio.wait_for(self.bridge.chat(self.body, route=self.route), 2)

    def add_result(self, call, error=False):
        self.body['messages'].append({'role': 'tool', 'tool_call_id': call,
            'content': 'ACTUAL_OUTPUT_' + call, 'is_error': error})

    def ledger(self):
        path = Path(self.tmp.name) / 'token_usage.jsonl'
        return path.read_text() if path.exists() else ''

    async def test_cancel_after_lost_tool_response_replays_then_recovers_once(self):
        first = await self.chat()
        self.rpc.cancel('call-0')
        self.rpc.finish('EARLY_FINAL')
        replay = await self.chat()
        self.assertEqual(replay, first)
        self.assertEqual(self.rpc.outputs, [])
        self.body['messages'].append(replay['choices'][0]['message'])
        self.add_result('call-0', True)
        final = await self.chat()
        self.assertEqual(final['choices'][0]['message']['content'], 'ACTUAL_RESULT_1')
        ledger = self.ledger()
        self.assertEqual(await self.chat(), final)
        self.assertEqual(self.ledger(), ledger)
        self.assertEqual(len(self.rpc.outputs), 1)
        self.assertTrue(json.loads(self.rpc.outputs[0]['output'])['is_error'])
        self.assertEqual(self.rpc.responses, [])
        self.assertEqual(sum(m == 'thread/start' for m, _ in self.rpc.calls), 1)

    async def test_partial_response_cancellation_only_resends_missing_original_call(self):
        self.rpc.tool_count = 3
        first = await self.chat()
        calls = first['choices'][0]['message']['tool_calls']
        self.rpc.cancel('call-2')
        self.body['messages'].append({'role': 'assistant', 'content': None, 'tool_calls': calls[:2]})
        missing = await self.chat()
        self.assertEqual(missing['choices'][0]['message']['tool_calls'], calls[2:])
        self.assertEqual(await self.chat(), missing)
        self.body['messages'].append(missing['choices'][0]['message'])
        for index in range(3):
            self.add_result('call-' + str(index))
        final = await self.chat()
        self.assertEqual(final['choices'][0]['message']['content'], 'ACTUAL_RESULT_1')
        self.assertEqual([rpc_id for rpc_id, _ in self.rpc.responses], ['rpc-call-0', 'rpc-call-1'])
        self.assertEqual(len(self.rpc.outputs), 1)
        self.assertEqual(json.loads(self.rpc.outputs[0]['output'])['tool_call_id'], 'call-2')

    async def test_concurrent_retries_during_recovery_return_identical_final(self):
        first = await self.chat()
        self.body['messages'].append(first['choices'][0]['message'])
        self.rpc.cancel('call-0')
        self.add_result('call-0')
        results = await asyncio.wait_for(asyncio.gather(*(self.chat() for _ in range(3))), 2)
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])
        self.assertEqual(results[0]['choices'][0]['message']['content'], 'ACTUAL_RESULT_1')
        self.assertEqual(len(self.rpc.outputs), 1)
        self.assertEqual(sum(m == 'turn/start' for m, _ in self.rpc.calls), 2)
        recoveries = (Path(self.tmp.name) / 'tool_result_recoveries.jsonl').read_text().splitlines()
        self.assertEqual(len(recoveries), 1)

    async def test_native_retry_during_late_result_recovery_preserves_final(self):
        self.rpc.retry_recovery = True
        first = await self.chat()
        self.body['messages'].append(first['choices'][0]['message'])
        self.rpc.cancel('call-0')
        self.rpc.finish('EARLY_FINAL')
        self.add_result('call-0')
        final = await self.chat()
        self.assertEqual(final['choices'][0]['message']['content'], 'ACTUAL_RESULT_1')
        self.assertEqual(await self.chat(), final)
        self.assertFalse(next(iter(self.bridge.sessions.values())).error)
        self.assertFalse(self.bridge.stopped)
        self.assertEqual(len(self.rpc.outputs), 1)

    async def test_global_stop_precedes_cached_tool_response_and_recovery(self):
        await self.chat()
        self.rpc.cancel('call-0')
        self.bridge.stop('Quota stop before response retry')
        with self.assertRaises(bridge_module.CodexBridgeError):
            await self.chat()
        self.assertEqual(self.rpc.outputs, [])
        self.assertEqual(sum(m == 'turn/start' for m, _ in self.rpc.calls), 1)

    async def test_checkpoint_excludes_replay_and_accepts_legacy_state_defaults(self):
        first = await self.chat()
        self.body['messages'].append(first['choices'][0]['message'])
        self.add_result('call-0')
        await self.chat()
        state = json.loads((Path(self.tmp.name) / 'bridge_recovery.json').read_text())[0]['state']
        self.assertNotIn('last_request', state)
        self.assertNotIn('last_response', state)
        self.assertIn('recovered_tool_results', state)
        legacy = bridge_module.Session('old-session', 'teacher', 'generate', '', bridge_module.MODEL)
        tool = bridge_module.ToolRequest('old-call', 7, 'Read', {'path': '/app/old'})
        self.assertFalse(legacy.recovered_tool_results)
        self.assertIsNone(legacy.last_response)
        self.assertFalse(tool.cancelled)
        self.assertIsNone(tool.result)

    async def test_input_contract_system_and_assistant_changes_are_not_forwarded(self):
        self.rpc.tool_count = 0
        self.body.pop('tools')
        first = await self.chat()
        self.body['messages'][0]['content'] = 'UPDATED_SYSTEM'
        self.body['messages'].extend([
            {'role': 'assistant', 'content': 'SDK_REPLACED_ASSISTANT'},
            {'role': 'user', 'content': 'Next user message'}])
        self.body.update(temperature=.3, max_tokens=16384)
        await self.chat()
        opened = [p for method, p in self.rpc.calls if method == 'thread/start']
        turns = [p for method, p in self.rpc.calls if method == 'turn/start']
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0]['baseInstructions'], 'ORIGINAL_SYSTEM')
        self.assertEqual(turns[-1]['input'], [{'type': 'text', 'text': 'Next user message'}])
        self.assertNotIn('UPDATED_SYSTEM', json.dumps(self.rpc.calls))
        self.assertNotIn('SDK_REPLACED_ASSISTANT', json.dumps(self.rpc.calls))
        self.assertNotIn('temperature', turns[-1])
        self.assertNotIn('max_tokens', turns[-1])
        self.assertEqual(first['choices'][0]['message']['content'], 'ORIGINAL_ASSISTANT_TEXT')

    async def test_tool_hook_user_suffix_is_steered_without_replaying_old_user(self):
        first = await self.chat()
        self.body['messages'].append(first['choices'][0]['message'])
        self.add_result('call-0')
        self.body['messages'][1]['content'] += '\nTeacher guidance: inspect the edge case.'
        final = await self.chat()
        steers = [params for method, params in self.rpc.calls if method == 'turn/steer']
        self.assertEqual(len(steers), 1)
        self.assertEqual(steers[0]['input'], [{'type': 'text', 'text': '\nTeacher guidance: inspect the edge case.'}])
        self.assertEqual(final['choices'][0]['message']['content'], 'NORMAL_RESULTS')
        self.assertEqual(sum(m == 'thread/start' for m, _ in self.rpc.calls), 1)


if __name__ == '__main__':
    out = Path(__file__).parent
    with (out / 'combined_tests.log').open('w') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(CombinedDeliveryTests))
    record = {'passed': result.wasSuccessful(), 'tests': result.testsRun,
              'failures': len(result.failures), 'errors': len(result.errors),
              'actual_bridge_module': bridge_module.__file__, 'real_model_calls': 0,
              'frozen_or_checked_sources_modified': False,
              'contract_test_note': 'The system/assistant/parameter test confirms a difference from stateless full-message APIs; it does not certify equivalence.'}
    (out / 'combined_tests.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
