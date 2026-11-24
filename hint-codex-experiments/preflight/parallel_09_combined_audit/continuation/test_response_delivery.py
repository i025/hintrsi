"""Regression checks for last-response replay and partial tool delivery."""
import asyncio
import ast
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT))
from test_concurrency import InterleavedRPC,request,add_results
import codex_cli_bridge as candidate



class DeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.rpc=InterleavedRPC()
        self.bridge=candidate.CodexBridge(self.tmp.name,rpc=self.rpc)
        self.route={'session':'same-sdk','role':'student','phase':'solve'}
        self.body=request('Use two external tools')

    async def asyncTearDown(self):
        await self.bridge.close()
        self.tmp.cleanup()

    async def chat(self,body=None,route=None):
        return await asyncio.wait_for(self.bridge.chat(body or self.body,route=route or self.route),2)

    def ledger(self):
        path=Path(self.tmp.name)/'token_usage.jsonl'
        return path.read_text() if path.exists() else ''

    async def finish(self,response):
        add_results(self.body,response,'Actual SDK result')
        return await self.chat()

    async def test_lost_tool_response_replays_exact_response_without_native_calls(self):
        first=await self.chat()
        call_count=len(self.rpc.calls)
        replay=await self.chat()
        self.assertEqual(replay,first)
        self.assertEqual(len(self.rpc.calls),call_count)
        self.assertEqual(self.rpc.responses,[])
        final=await self.finish(replay)
        self.assertEqual(final['choices'][0]['finish_reason'],'stop')
        self.assertEqual(len(self.rpc.responses),2)
        self.assertEqual(len({rpc_id for rpc_id,_ in self.rpc.responses}),2)
        self.assertEqual(sum(m=='turn/start' for m,_ in self.rpc.calls),1)

    async def test_completed_final_replay_preserves_body_usage_and_ledger(self):
        first=await self.chat()
        final=await self.finish(first)
        ledger=self.ledger();calls=len(self.rpc.calls);replies=len(self.rpc.responses)
        replay=await self.chat()
        self.assertEqual(replay,final)
        self.assertTrue(replay['choices'][0]['message']['content'])
        self.assertGreater(replay['usage']['total_tokens'],0)
        self.assertEqual(self.ledger(),ledger)
        self.assertEqual(len(self.rpc.calls),calls)
        self.assertEqual(len(self.rpc.responses),replies)
        responses=[json.loads(line) for line in (Path(self.tmp.name)/'model_responses.jsonl').read_text().splitlines()]
        self.assertTrue(responses[-1]['replayed_response'])
        self.assertEqual(responses[-1]['response']['id'],responses[-2]['response']['id'])

    async def test_plain_text_compressor_replay_preserves_exact_usage(self):
        async def emit_text(thread,turn):
            await asyncio.sleep(.001)
            self.rpc.finish(thread)
        self.rpc.issue_tools=emit_text
        body=request('Compress guidance');body.pop('tools')
        route={'session':'compress-r1','role':'compressor','phase':'compress_r1'}
        first=await self.chat(body,route)
        ledger=self.ledger();calls=len(self.rpc.calls)
        second=await self.chat(body,route)
        self.assertEqual(second,first)
        self.assertEqual(second['choices'][0]['finish_reason'],'stop')
        self.assertGreater(second['usage']['total_tokens'],0)
        self.assertEqual(self.ledger(),ledger)
        self.assertEqual(len(self.rpc.calls),calls)

    async def test_partial_seen_calls_replay_only_unseen_pending(self):
        first=await self.chat()
        tools=first['choices'][0]['message']['tool_calls']
        self.body['messages'].append({'role':'assistant','content':'Partial stream',
                                      'tool_calls':[copy.deepcopy(tools[0])]})
        second=await self.chat()
        self.assertEqual(second['choices'][0]['message']['tool_calls'],[tools[1]])
        self.body['messages'].append(second['choices'][0]['message'])
        for tool in tools:self.body['messages'].append({'role':'tool','tool_call_id':tool['id'],'content':'Actual '+tool['id']})
        final=await self.chat()
        self.assertEqual(final['choices'][0]['finish_reason'],'stop')
        self.assertEqual(len(self.rpc.responses),2)
        self.assertEqual(sum(m=='turn/start' for m,_ in self.rpc.calls),1)

    async def test_seen_call_without_result_is_not_replayed(self):
        first=await self.chat()
        self.body['messages'].append(first['choices'][0]['message'])
        waiting=asyncio.create_task(self.bridge.chat(self.body,route=self.route))
        await asyncio.sleep(.02)
        self.assertFalse(waiting.done())
        state=next(iter(self.bridge.sessions.values()))
        self.assertFalse(state.ready)
        call='newly-arrived-third';rpc_id='rpc-third'
        self.rpc.tools[rpc_id]=(state.thread_id,state.turn_id,call)
        self.rpc.emit('item/tool/call',{'threadId':state.thread_id,'turnId':state.turn_id,
            'callId':call,'tool':'Read','arguments':{'path':'/app/third'}},rpc_id)
        response=await asyncio.wait_for(waiting,2)
        self.assertEqual([t['id'] for t in response['choices'][0]['message']['tool_calls']],[call])
        self.assertEqual(self.rpc.responses,[])

    async def test_mutated_return_and_request_do_not_change_saved_snapshot(self):
        first=await self.chat();expected=copy.deepcopy(first)
        first['choices'][0]['message']['tool_calls'][0]['function']['arguments']='MUTATED OUTSIDE'
        replay=await self.chat()
        self.assertEqual(replay,expected)
        final=await self.finish(replay)
        original_final=copy.deepcopy(final)
        final['usage']['total_tokens']=-1
        self.assertEqual(await self.chat(),original_final)
        state=next(iter(self.bridge.sessions.values()))
        saved=copy.deepcopy(state.last_request)
        self.body['messages'].append({'role':'user','content':'New normal continuation'})
        self.assertEqual(state.last_request,saved)
        next_tools=await self.chat()
        self.assertEqual(next_tools['choices'][0]['finish_reason'],'tool_calls')
        self.assertEqual(sum(m=='turn/start' for m,_ in self.rpc.calls),2)
        self.assertNotEqual(next_tools['id'],original_final['id'])

    async def test_completed_calls_not_reexecuted_after_normal_next_context(self):
        first=await self.chat();final=await self.finish(first)
        self.body['messages'].extend([final['choices'][0]['message'],{'role':'user','content':'Check next condition'}])
        next_tools=await self.chat();next_final=await self.finish(next_tools)
        self.assertEqual(len(self.rpc.responses),4)
        self.assertEqual(len({rpc_id for rpc_id,_ in self.rpc.responses}),4)
        ledger=self.ledger();self.assertEqual(await self.chat(),next_final);self.assertEqual(self.ledger(),ledger)
        self.assertEqual(sum(m=='turn/start' for m,_ in self.rpc.calls),2)

    async def test_tool_schema_change_and_global_stop_are_not_hidden_by_replay(self):
        first=await self.chat()
        changed=copy.deepcopy(self.body);changed['tools'][0]['function']['description']='Different contract'
        with self.assertRaises(candidate.CodexBridgeError):await self.chat(changed)
        self.assertTrue(self.bridge.stopped)
        with self.assertRaises(candidate.CodexBridgeError):await self.chat()
        self.assertEqual(sum(m=='turn/start' for m,_ in self.rpc.calls),1)

    async def test_multiple_partial_calls_keep_order_before_new_arrivals(self):
        original_issue = self.rpc.issue_tools
        async def four_tools(thread, turn):
            await original_issue(thread, turn)
            for index in (2, 3):
                call = turn + '-tool-' + str(index)
                rpc_id = 'rpc-' + call
                self.rpc.tools[rpc_id] = (thread, turn, call)
                self.rpc.emit('item/tool/call', {'threadId': thread, 'turnId': turn,
                    'callId': call, 'tool': 'Read', 'arguments': {'path': '/app/' + call}}, rpc_id)
        self.rpc.issue_tools = four_tools
        first = await self.chat()
        tools = first['choices'][0]['message']['tool_calls']
        self.assertEqual(len(tools), 4)
        self.body['messages'].append({'role': 'assistant', 'content': 'Partial',
                                     'tool_calls': [tools[0], tools[2]]})
        state = next(iter(self.bridge.sessions.values()))
        self.rpc.tools['rpc-new'] = (state.thread_id, state.turn_id, 'new-arrival')
        self.rpc.emit('item/tool/call', {'threadId': state.thread_id, 'turnId': state.turn_id,
            'callId': 'new-arrival', 'tool': 'Read', 'arguments': {'path': '/app/new'}}, 'rpc-new')
        response = await self.chat()
        self.assertEqual([t['id'] for t in response['choices'][0]['message']['tool_calls']],
                         [tools[1]['id'], tools[3]['id'], 'new-arrival'])
        self.assertEqual(self.rpc.responses, [])

    async def test_replay_snapshots_stay_in_memory_and_teacher_checkpoint_format_matches(self):
        self.route.update(role='teacher', phase='generate')
        first = await self.chat()
        await self.finish(first)
        state = next(iter(self.bridge.sessions.values()))
        self.assertIsNotNone(state.last_request)
        self.assertIsNotNone(state.last_response)
        recovery = json.loads((Path(self.tmp.name)/'bridge_recovery.json').read_text())
        baseline = ast.parse(Path(candidate.__file__).read_text())
        session = next(node for node in baseline.body if isinstance(node, ast.ClassDef) and node.name == 'Session')
        fields = {node.target.id for node in session.body if isinstance(node, ast.AnnAssign)}
        self.assertEqual(set(recovery[0]['state']), fields - {'lock', 'changed', 'last_request', 'last_response'})
        self.assertIn('recovered_tool_results', recovery[0]['state'])
        self.assertNotIn('last_request', recovery[0]['state'])
        self.assertNotIn('last_response', recovery[0]['state'])

    async def test_teacher_new_phase_does_not_replay_old_response(self):
        self.route.update(role='teacher',phase='generate')
        first=await self.chat();final=await self.finish(first)
        self.body['messages'].extend([final['choices'][0]['message'],{'role':'user','content':'Review the failed student'}])
        self.route['phase']='review_r1'
        review_tools=await self.chat()
        self.assertNotEqual(review_tools['id'],final['id'])
        self.assertEqual(len(self.bridge.sessions),1)
        self.assertEqual(sum(m=='thread/start' for m,_ in self.rpc.calls),1)
        self.assertEqual(sum(m=='turn/start' for m,_ in self.rpc.calls),2)


if __name__=='__main__':unittest.main(verbosity=2)
