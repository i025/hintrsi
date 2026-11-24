"""Protocol error notifications during interleaved native turns; no real model."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from test_concurrency import InterleavedRPC, request, add_results
from test_response_delivery import candidate


def error_event(thread, turn, will_retry, quota=False):
    return {'threadId': thread, 'turnId': turn, 'willRetry': will_retry, 'error': {
        'message': 'Account usage limit reached' if quota else 'Response stream disconnected',
        'codexErrorInfo': 'usageLimitExceeded' if quota else {
            'responseStreamDisconnected': {'httpStatusCode': 502}}}}


class RetryNotificationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rpc = InterleavedRPC()
        self.bridge = candidate.CodexBridge(self.tmp.name, rpc=self.rpc)

    async def asyncTearDown(self):
        await self.bridge.close()
        self.tmp.cleanup()

    async def waiting_lanes(self):
        self.rpc.hold_completion = True
        routes = [{'session': f'error-lane{i}', 'role': 'student', 'phase': 'solve'} for i in range(6)]
        bodies = [request(f'Error task {i}') for i in range(6)]
        responses = await asyncio.gather(*[self.bridge.chat(body, route=route)
                                          for body, route in zip(bodies, routes)])
        for body, response, route in zip(bodies, responses, routes):
            add_results(body, response, route['session'])
        waiting = [asyncio.create_task(self.bridge.chat(body, route=route))
                   for body, route in zip(bodies, routes)]
        for _ in range(100):
            if len(self.rpc.responses) == 12:
                break
            await asyncio.sleep(.001)
        self.assertEqual(len(self.rpc.responses), 12)
        states = sorted(self.bridge.sessions.values(), key=lambda s: s.session_id)
        return states, waiting

    async def test_retryable_error_before_tools_preserves_same_native_turn(self):
        issue_tools = self.rpc.issue_tools
        async def recovering_stream(thread, turn):
            self.rpc.emit('error', error_event(thread, turn, True))
            await asyncio.sleep(.01)
            await issue_tools(thread, turn)
        self.rpc.issue_tools = recovering_stream
        body = request('Recover before external tool requests')
        route = {'session': 'retry-tools', 'role': 'teacher', 'phase': 'generate'}
        tools = await asyncio.wait_for(self.bridge.chat(body, route=route), 2)
        add_results(body, tools, 'Actual SDK result')
        final = await asyncio.wait_for(self.bridge.chat(body, route=route), 2)
        state = next(iter(self.bridge.sessions.values()))
        self.assertEqual(final['choices'][0]['finish_reason'], 'stop')
        self.assertEqual(final['usage']['total_tokens'], 110)
        self.assertFalse(state.error)
        self.assertFalse(self.bridge.stopped)
        self.assertEqual(sum(m == 'turn/start' for m, _ in self.rpc.calls), 1)
        self.assertEqual(len(self.rpc.responses), 2)
        events = [json.loads(line)['event'] for line in
                  (Path(self.tmp.name) / 'codex_events.jsonl').read_text().splitlines()]
        self.assertEqual(sum(e['method'] == 'error' for e in events), 1)

    async def test_retryable_error_during_six_waits_does_not_poison_completion(self):
        states, waiting = await self.waiting_lanes()
        target = states[2]
        self.rpc.emit('error', error_event(target.thread_id, target.turn_id, True))
        await asyncio.sleep(.01)
        self.assertTrue(all(not job.done() for job in waiting))
        self.assertTrue(all(not state.error for state in states))
        for state in reversed(states):
            self.rpc.finish(state.thread_id)
        results = await asyncio.wait_for(asyncio.gather(*waiting), 2)
        for result, state in zip(results, states):
            self.assertIn(state.thread_id, result['choices'][0]['message']['content'])
        self.assertEqual(sum(m == 'turn/start' for m, _ in self.rpc.calls), 6)
        self.assertFalse(any(m == 'turn/interrupt' for m, _ in self.rpc.calls))
        self.assertFalse(self.bridge.stopped)

    async def test_nonretryable_error_fails_only_its_session(self):
        states, waiting = await self.waiting_lanes()
        target = states[2]
        self.rpc.emit('error', error_event(target.thread_id, target.turn_id, False))
        with self.assertRaises(candidate.CodexBridgeError):
            await asyncio.wait_for(waiting[2], 2)
        for state in reversed(states):
            if state is not target:
                self.rpc.finish(state.thread_id)
        results = await asyncio.wait_for(asyncio.gather(*waiting, return_exceptions=True), 2)
        self.assertIsInstance(results[2], candidate.CodexBridgeError)
        self.assertEqual(sum(isinstance(value, dict) for value in results), 5)
        self.assertTrue(target.error)
        self.assertTrue(all(not state.error for state in states if state is not target))
        self.assertFalse(self.bridge.stopped)
        self.assertFalse(any(m == 'turn/interrupt' for m, _ in self.rpc.calls))

    async def quota_stops_all(self, will_retry):
        states, waiting = await self.waiting_lanes()
        exact = {(state.thread_id, state.turn_id) for state in states}
        target = states[2]
        self.rpc.emit('error', error_event(target.thread_id, target.turn_id, will_retry, quota=True))
        results = await asyncio.wait_for(asyncio.gather(*waiting, return_exceptions=True), 2)
        await asyncio.sleep(0)
        self.assertTrue(all(isinstance(value, candidate.CodexBridgeError) for value in results))
        self.assertTrue(self.bridge.stopped)
        interrupts = [(params['threadId'], params['turnId']) for method, params in self.rpc.calls
                      if method == 'turn/interrupt']
        self.assertEqual(set(interrupts), exact)
        self.assertEqual(len(interrupts), 6)
        self.assertEqual(sum(m == 'turn/start' for m, _ in self.rpc.calls), 6)

    async def test_quota_with_will_retry_true_still_stops_all_six(self):
        await self.quota_stops_all(True)

    async def test_quota_with_will_retry_false_still_stops_all_six(self):
        await self.quota_stops_all(False)


if __name__ == '__main__':
    unittest.main(verbosity=2)
