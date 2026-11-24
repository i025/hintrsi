"""Concurrent integration checks of checked09; no external model or Codex process."""
import asyncio
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
os.environ['TELEMETRY'] = 'False'
ROOT = Path('/srv/lab-disks/disk2/users/xymo/hint-codex-experiments')
sys.path.insert(0, str(ROOT / 'source_parallel_09_checked'))
import httpx
from codex_cli_bridge import CodexBridge, CodexBridgeError, MODEL, create_app
from teacher_progress import TeacherProgress


def request(text, source='sdk-main'):
    return {'model': MODEL, 'user': source, 'messages': [
        {'role': 'system', 'content': 'Use the external task tools.'},
        {'role': 'user', 'content': text}], 'tools': [{'type': 'function', 'function': {
            'name': 'Read', 'description': 'Read the task file',
            'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}}}}}]}


class InterleavedRPC:
    def __init__(self):
        self.event_callback = None
        self.calls = []
        self.responses = []
        self.threads = {}
        self.tools = {}
        self.jobs = []
        self.starts = 0
        self.max_active = 0
        self.opening = 0
        self.max_opening = 0
        self.hold_completion = False

    async def start(self):
        await asyncio.sleep(0)
        self.starts += 1

    async def close(self):
        await asyncio.gather(*self.jobs)

    def emit(self, method, params, rpc_id=None):
        event = {'method': method, 'params': params}
        if rpc_id is not None:
            event['id'] = rpc_id
        self.event_callback(event)

    async def request(self, method, params):
        self.calls.append((method, params))
        if method == 'thread/start':
            self.opening += 1
            self.max_opening = max(self.max_opening, self.opening)
            thread = 'thread-' + str(len(self.threads) + 1)
            self.threads[thread] = {'number': len(self.threads) + 1, 'round': 0,
                                    'active': False, 'received': {}, 'total': 0}
            await asyncio.sleep(.001)
            self.emit('thread/started', {'thread': {'id': thread}})
            self.opening -= 1
            return {'thread': {'id': thread}, 'model': MODEL}
        if method == 'turn/start':
            thread = params['threadId']
            state = self.threads[thread]
            state.update(round=state['round'] + 1, active=True, received={})
            turn = thread + '-turn-' + str(state['round'])
            state['turn'] = turn
            self.max_active = max(self.max_active, sum(s['active'] for s in self.threads.values()))
            self.emit('turn/started', {'threadId': thread, 'turn': {'id': turn}})
            self.jobs.append(asyncio.create_task(self.issue_tools(thread, turn)))
            return {'turn': {'id': turn}}
        if method == 'turn/interrupt':
            self.threads[params['threadId']]['active'] = False
        return {}

    async def issue_tools(self, thread, turn):
        await asyncio.sleep(.001 * (7 - self.threads[thread]['number'] % 6))
        for index in (1, 0):
            call = turn + '-tool-' + str(index)
            rpc_id = 'rpc-' + call
            self.tools[rpc_id] = (thread, turn, call)
            self.emit('item/tool/call', {'threadId': thread, 'turnId': turn,
                'callId': call, 'tool': 'Read', 'arguments': {'path': '/app/' + call}}, rpc_id)

    async def respond(self, rpc_id, result):
        self.responses.append((rpc_id, result))
        thread, turn, call = self.tools[rpc_id]
        state = self.threads[thread]
        state['received'][call] = result['contentItems'][0]['text']
        await asyncio.sleep(0)
        if len(state['received']) == 2 and not self.hold_completion and state['active']:
            self.finish(thread)

    def finish(self, thread):
        state = self.threads[thread]
        turn = state['turn']
        state['total'] += 100 * state['number'] + 10
        total = {'inputTokens': state['total'] - 10 * state['round'],
                 'outputTokens': 10 * state['round'], 'totalTokens': state['total'],
                 'cachedInputTokens': 0, 'reasoningOutputTokens': 0}
        self.emit('thread/tokenUsage/updated', {'threadId': thread, 'turnId': turn,
            'tokenUsage': {'last': total, 'total': total}})
        self.emit('item/completed', {'threadId': thread, 'turnId': turn, 'item': {
            'type': 'agentMessage', 'text': 'Final ' + thread + ' ' + json.dumps(state['received'], sort_keys=True)}})
        state['active'] = False
        self.emit('turn/completed', {'threadId': thread, 'turn': {'id': turn, 'status': 'completed'}})


def add_results(body, response, marker):
    message = response['choices'][0]['message']
    body['messages'].append(message)
    for tool in reversed(message['tool_calls']):
        body['messages'].append({'role': 'tool', 'tool_call_id': tool['id'],
                                 'content': marker + ':' + tool['id']})


class ConcurrentBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rpc = InterleavedRPC()
        self.bridge = CodexBridge(self.tmp.name, rpc=self.rpc)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(self.bridge)),
                                       base_url='http://offline')

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.bridge.close()
        self.tmp.cleanup()

    async def post(self, route, body):
        path = '/sessions/{session}/{role}/{phase}/v1/chat/completions'.format(**route)
        response = await self.client.post(path, json=body)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def finish_batch(self, routes, bodies):
        first = await asyncio.wait_for(asyncio.gather(*[
            self.post(route, body) for route, body in zip(routes, bodies)]), 5)
        for index, (body, response) in enumerate(zip(bodies, first)):
            self.assertEqual(len(response['choices'][0]['message']['tool_calls']), 2)
            add_results(body, response, routes[index]['session'])
        finals = await asyncio.wait_for(asyncio.gather(*[
            self.post(routes[index], bodies[index]) for index in reversed(range(len(routes)))]), 5)
        return first, list(reversed(finals))

    async def test_six_http_sessions_interleave_exact_tools_usage_and_timing(self):
        routes = [{'session': f'lane{i}-task-I-r1', 'role': 'student', 'phase': 'solve'} for i in range(6)]
        bodies = [request(f'Task lane{i}') for i in range(6)]
        first, finals = await self.finish_batch(routes, bodies)
        self.assertEqual(self.rpc.starts, 1)
        self.assertEqual(self.rpc.max_opening, 1)
        self.assertEqual(self.rpc.max_active, 6)
        self.assertEqual(len(self.bridge.sessions), 6)
        for route, response in zip(routes, finals):
            state = next(s for s in self.bridge.sessions.values() if s.session_id == route['session'])
            self.assertTrue(all(t.completed for t in state.pending.values()))
            self.assertEqual(response['usage']['total_tokens'], 100 * self.rpc.threads[state.thread_id]['number'] + 10)
            for call, text in self.rpc.threads[state.thread_id]['received'].items():
                self.assertEqual(text, route['session'] + ':' + call)
        rows = [json.loads(line) for line in (Path(self.tmp.name)/'model_responses.jsonl').read_text().splitlines()]
        self.assertEqual(len(rows), 12)
        self.assertTrue(all(row['elapsed_seconds'] >= 0 for row in rows))
        usage = [json.loads(line) for line in (Path(self.tmp.name)/'token_usage.jsonl').read_text().splitlines()]
        self.assertEqual(len(usage), 6)
        self.assertEqual({r['session'] for r in usage}, {r['session'] for r in routes})
        self.assertFalse(self.bridge.stopped)

    async def test_six_persistent_teachers_keep_threads_across_interleaved_rounds(self):
        routes = [{'session': f'lane{i}-task-shared', 'role': 'teacher', 'phase': 'generate'} for i in range(6)]
        bodies = [request(f'Initial teacher lane{i}', f'teacher-sdk{i}') for i in range(6)]
        _, finals = await self.finish_batch(routes, bodies)
        initial = {s.session_id: s.thread_id for s in self.bridge.sessions.values()}
        for round_num in (1, 2):
            for index, body in enumerate(bodies):
                body['messages'].extend([finals[index]['choices'][0]['message'],
                    {'role': 'user', 'content': f'Review lane{index} round{round_num}'}])
                routes[index]['phase'] = f'review_r{round_num}'
            _, finals = await self.finish_batch(routes, bodies)
            self.assertEqual({s.session_id:s.thread_id for s in self.bridge.sessions.values()}, initial)
        self.assertEqual(sum(method=='thread/start' for method,_ in self.rpc.calls), 6)
        self.assertEqual(sum(method=='turn/start' for method,_ in self.rpc.calls), 18)
        self.assertTrue(all(s.phase=='review_r2' and len(s.pending)==6 for s in self.bridge.sessions.values()))
        rows = [json.loads(line) for line in (Path(self.tmp.name)/'token_usage.jsonl').read_text().splitlines()]
        for session, thread in initial.items():
            own=[row for row in rows if row['session']==session]
            self.assertEqual([row['phase'] for row in own], ['generate','review_r1','review_r2'])
            self.assertEqual(sum(row['delta']['totalTokens'] for row in own), self.rpc.threads[thread]['total'])

    async def test_fresh_student_and_h_teacher_rounds_do_not_reuse_threads(self):
        histories = []
        for round_num in (1,2):
            routes=[]
            bodies=[]
            for lane in range(6):
                for group in ('H','I'):
                    routes.append({'session':f'lane{lane}-task-{group}-r{round_num}','role':'student','phase':'solve'})
                    bodies.append(request('Identical task prompt', f'sdk-lane{lane}'))
                routes.append({'session':f'lane{lane}-task-H-review-r{round_num}','role':'teacher','phase':f'review_r{round_num}'})
                bodies.append(request('Identical teacher review prompt',f'teacher-sdk{lane}'))
            await self.finish_batch(routes,bodies)
            histories.extend(routes)
        self.assertEqual(len(self.bridge.sessions),36)
        self.assertEqual(len({s.thread_id for s in self.bridge.sessions.values()}),36)
        self.assertEqual({s.session_id for s in self.bridge.sessions.values()},{r['session'] for r in histories})

    async def test_cancelled_http_wait_does_not_cancel_other_lanes(self):
        self.rpc.hold_completion=True
        routes=[{'session':f'cancel-lane{i}','role':'student','phase':'solve'} for i in range(6)]
        bodies=[request(f'Cancel task {i}') for i in range(6)]
        first=await asyncio.gather(*[self.post(route,body) for route,body in zip(routes,bodies)])
        for index,(body,response) in enumerate(zip(bodies,first)):add_results(body,response,routes[index]['session'])
        pending=[asyncio.create_task(self.post(route,body)) for route,body in zip(routes,bodies)]
        for _ in range(100):
            if len(self.rpc.responses)==12:break
            await asyncio.sleep(.001)
        self.assertEqual(len(self.rpc.responses),12)
        pending[0].cancel()
        self.assertIsInstance((await asyncio.gather(pending[0],return_exceptions=True))[0],asyncio.CancelledError)
        cancelled=next(s for s in self.bridge.sessions.values() if s.session_id=='cancel-lane0')
        self.assertTrue(cancelled.active)
        self.assertFalse(self.bridge.stopped)
        for state in self.bridge.sessions.values():self.rpc.finish(state.thread_id)
        await asyncio.wait_for(asyncio.gather(*pending[1:]),5)
        retried=await self.post(routes[0],bodies[0])
        self.assertIn(cancelled.thread_id,retried['choices'][0]['message']['content'])
        self.assertEqual(len(self.rpc.responses),12)
        self.assertFalse(any(method=='turn/interrupt' for method,_ in self.rpc.calls))

    async def test_global_stop_interrupts_all_six_exact_turns(self):
        self.rpc.hold_completion=True
        routes=[{'session':f'stop-lane{i}','role':'student','phase':'solve'} for i in range(6)]
        bodies=[request(f'Stop task {i}') for i in range(6)]
        first=await asyncio.gather(*[self.bridge.chat(body,route=route) for route,body in zip(routes,bodies)])
        for index,(body,response) in enumerate(zip(bodies,first)):add_results(body,response,routes[index]['session'])
        waiting=[asyncio.create_task(self.bridge.chat(body,route=route)) for route,body in zip(routes,bodies)]
        await asyncio.sleep(.01)
        exact={(s.thread_id,s.turn_id) for s in self.bridge.sessions.values()}
        self.bridge.stop('Offline account quota stop')
        results=await asyncio.wait_for(asyncio.gather(*waiting,return_exceptions=True),5)
        await asyncio.sleep(0)
        self.assertTrue(all(isinstance(value,CodexBridgeError) for value in results))
        self.assertEqual({(p['threadId'],p['turnId']) for method,p in self.rpc.calls if method=='turn/interrupt'},exact)
        self.assertEqual(len(exact),6)


class ConcurrentProgressTests(unittest.IsolatedAsyncioTestCase):
    async def test_six_checks_keep_gt_hint_history_and_waits_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            barrier=threading.Barrier(6)
            observed=[]
            lock=threading.Lock()
            def candidate(problem,gt,trajectory,hint,**kwargs):
                lane=int(problem.rsplit('-',1)[1])
                assert gt==f'PRIVATE_GT_{lane}' and trajectory==f'Observed_{lane}' and hint==f'Initial_{lane}'
                barrier.wait(timeout=3)
                time.sleep(.003*(lane+1))
                with lock:observed.append((lane,kwargs['api_base'],list(kwargs['previous_hints'])))
                return {'needs_hint':True,'corrective_hint':f'Check lane {lane}.'}
            def screen(hint,trajectory,**kwargs):
                lane=int(trajectory.split('_')[-1])
                assert hint==f'Check lane {lane}.'
                assert kwargs['previous_hints'][0]==f'Initial_{lane}'
                assert f'lane{lane}-I-r1_progress_' in kwargs['api_base']
                return {'deliver':True,'hint':hint}
            service=TeacherProgress(directory,candidate=candidate,screen=screen,status_reader=lambda:{'stopped':False},stopper=lambda reason:None)
            for lane in range(6):
                service.register({'session':f'lane{lane}-I-r1','task':f'task-{lane}','problem_statement':f'Problem-{lane}',
                    'golden_diff':f'PRIVATE_GT_{lane}','current_hint':f'Initial_{lane}','api_base':'http://offline/v1'})
            for check in (1,2):
                results=await asyncio.wait_for(asyncio.gather(*[service.progress({'session':f'lane{lane}-I-r1','task':f'task-{lane}','trajectory':f'Observed_{lane}','tool_count':20*check}) for lane in range(6)]),5)
                self.assertEqual([row['hint'] for row in results],[f'Check lane {lane}.' for lane in range(6)])
                self.assertTrue(all(row['checks']==check and row['teacher_wait_seconds']>0 for row in results))
            self.assertEqual(len({url for _,url,_ in observed}),12)
            for lane in range(6):
                own=[row for row in observed if row[0]==lane]
                self.assertEqual([row[2] for row in own],[[],[f'Check lane {lane}.']])
            rows=[json.loads(line) for line in (Path(directory)/'progress.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows),12)
            for lane in range(6):
                own=[row for row in rows if row['session']==f'lane{lane}-I-r1']
                self.assertEqual([row['check'] for row in own],[1,2])
                self.assertAlmostEqual(own[-1]['teacher_wait_seconds'],sum(row['duration_seconds'] for row in own))


if __name__=='__main__':
    unittest.main(verbosity=2)
