"""Zero-model regressions for cancelled dynamic-tool observations."""
import asyncio
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

OUT = Path(__file__).parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT / 'source_parallel_09_checked'))
from codex_cli_bridge import CodexBridge, CodexBridgeError
sys.path.insert(0, str(ROOT / 'tests_parallel_09_checked'))
from test_codex_cli_bridge import FakeRPC, body, usage

class OutputRPC(FakeRPC):
    def __init__(self):
        super().__init__()
        self.outputs = []
        self.active_output = False

    async def request(self, method, params=None):
        if method == 'turn/start' and params.get('toolOutput'):
            self.calls.append((method, params))
            if not self.active_output:
                self.turn = 'recovery-' + str(len(self.outputs) + 1)
                self.emit('turn/started', {'threadId': self.thread, 'turn': {'id': self.turn}})
            else:
                self.emit('item/completed', {'threadId': self.thread, 'turnId': self.turn,
                    'item': {'type': 'agentMessage', 'id': 'old', 'text': 'EARLY_FINAL'}})
            self.outputs.append(params['toolOutput'])
            self.tokens(usage(100 + len(self.outputs) * 20, 20 + len(self.outputs) * 5))
            self.finish('AFTER_ACTUAL_RESULT_' + str(len(self.outputs)))
            return {'turn': {'id': self.turn}}
        return await super().request(method, params)

    def cancelled(self, call_id):
        self.emit('item/completed', {'threadId': self.thread, 'turnId': self.turn,
            'item': {'type': 'dynamicToolCall', 'id': call_id, 'status': 'failed',
                     'success': False, 'contentItems': []}})

class LateResultTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rpc = OutputRPC()
        self.bridge = CodexBridge(self.tmp.name, rpc=self.rpc)
        self.route = {'session': 'fixture', 'role': 'student', 'phase': 'solve'}
        self.request = body(tools=True)

    async def asyncTearDown(self):
        await self.bridge.close()
        self.tmp.cleanup()

    async def initial(self, multiple=False):
        def start(rpc):
            rpc.tool()
            if multiple:
                rpc.tool('call-b', 71, {'path': '/app/second'})
        self.rpc.on_turn = start
        response = await self.bridge.chat(self.request, route=self.route)
        self.request['messages'].append(response['choices'][0]['message'])

    async def late(self, active=False, multiple=False):
        await self.initial(multiple)
        self.rpc.cancelled('call-a')
        if multiple:
            self.rpc.cancelled('call-b')
        self.rpc.active_output = active
        if not active:
            self.rpc.finish('EARLY_FINAL')
        self.request['messages'].append({'role': 'tool', 'tool_call_id': 'call-a',
                                        'content': 'exit code 7: actual failed command', 'is_error': True})
        if multiple:
            self.request['messages'].append({'role': 'tool', 'tool_call_id': 'call-b',
                                            'content': 'actual successful output', 'is_error': False})
        response = await self.bridge.chat(self.request, route=self.route)
        expected = 2 if multiple else 1
        self.assertEqual(response['choices'][0]['message']['content'], 'AFTER_ACTUAL_RESULT_' + str(expected))
        self.assertEqual(response['choices'][0]['finish_reason'], 'stop')
        self.assertEqual(len(self.rpc.outputs), expected)
        result = json.loads(self.rpc.outputs[0]['output'])
        self.assertEqual(result['tool_call_id'], 'call-a')
        self.assertTrue(result['is_error'])
        self.assertEqual(result['output'], 'exit code 7: actual failed command')
        self.assertEqual(result['arguments'], {'path': '/app/file.py'})
        self.assertTrue(self.rpc.outputs[0]['retain'])
        self.assertEqual(sum(m == 'thread/start' for m, _ in self.rpc.calls), 1)
        self.assertEqual(len(self.rpc.responses), 0)
        # Replaying the same SDK body must not inject or execute either operation again.
        await self.bridge.chat(self.request, route=self.route)
        self.assertEqual(len(self.rpc.outputs), expected)
        self.assertEqual(len(self.rpc.responses), 0)
        ledger = [json.loads(l) for l in (Path(self.tmp.name) / 'token_usage.jsonl').read_text().splitlines()]
        total = sum(row['delta']['totalTokens'] for row in ledger)
        self.assertEqual(total, 120 + expected * 25)
        recovery = [json.loads(l) for l in (Path(self.tmp.name) / 'tool_result_recoveries.jsonl').read_text().splitlines()]
        self.assertEqual(len(recovery), expected)
        self.assertTrue(all(tool.result is None for state in self.bridge.sessions.values()
                            for tool in state.pending.values()))

    async def test_cancelled_result_after_native_final(self):
        await self.late()

    async def test_cancelled_result_during_native_generation(self):
        await self.late(active=True)

    async def test_multiple_cancelled_results_in_one_sdk_batch(self):
        await self.late(multiple=True)

    async def test_multiple_results_with_active_native_turn(self):
        await self.late(active=True, multiple=True)

    async def test_normal_failed_result_does_not_start_recovery(self):
        await self.initial()
        def respond(rpc, request_id):
            rpc.emit('item/completed', {'threadId': rpc.thread, 'turnId': rpc.turn,
                'item': {'type': 'dynamicToolCall', 'id': 'call-a', 'status': 'failed',
                         'success': False, 'contentItems': [{'type': 'inputText', 'text': 'exit 7'}]}})
            rpc.finish('NORMAL_FAILURE_OBSERVED')
        self.rpc.on_response = respond
        self.request['messages'].append({'role': 'tool', 'tool_call_id': 'call-a',
                                        'content': 'exit 7', 'is_error': True})
        response = await self.bridge.chat(self.request, route=self.route)
        self.assertEqual(response['choices'][0]['message']['content'], 'NORMAL_FAILURE_OBSERVED')
        self.assertEqual(self.rpc.outputs, [])
        self.assertFalse(self.rpc.responses[0][1]['success'])
        self.assertEqual(sum(m == 'turn/start' for m, _ in self.rpc.calls), 1)
        self.assertIsNone(next(iter(self.bridge.sessions.values())).pending['call-a'].result)

    async def test_stop_during_result_write_does_not_recover(self):
        await self.initial()
        def respond(rpc, request_id):
            rpc.cancelled('call-a')
            self.bridge.stop('fixture account stop')
            rpc.finish('EARLY_FINAL')
        self.rpc.on_response = respond
        self.request['messages'].append({'role': 'tool', 'tool_call_id': 'call-a', 'content': 'Actual output'})
        with self.assertRaises(CodexBridgeError):
            await self.bridge.chat(self.request, route=self.route)
        self.assertEqual(self.rpc.outputs, [])
        self.assertEqual(sum(m == 'turn/start' for m, _ in self.rpc.calls), 1)

    async def test_cancellation_observed_during_result_write(self):
        await self.initial()
        def respond(rpc, request_id):
            rpc.cancelled('call-a')
            rpc.finish('EARLY_FINAL')
        self.rpc.on_response = respond
        self.request['messages'].append({'role': 'tool', 'tool_call_id': 'call-a', 'content': 'Actual output'})
        response = await self.bridge.chat(self.request, route=self.route)
        self.assertEqual(response['choices'][0]['message']['content'], 'AFTER_ACTUAL_RESULT_1')
        self.assertEqual(len(self.rpc.outputs), 1)
        self.assertEqual(len(self.rpc.responses), 1)

if __name__ == '__main__':
    unittest.main()
