#!/usr/bin/env python3
"""Run real SDK hooks against a local deterministic fake Anthropic endpoint."""

import asyncio
import json
import sys
import threading
import time
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0,"/tmp")
from sdk_script import OnlineTeacher, create_agent_options
from claude_agent_sdk import ClaudeSDKClient, ResultMessage, SystemMessage

OUT=Path('/tmp/subagent_probe_out')
OUT.mkdir(exist_ok=True)
MARKER='TEACHER_HINT_MARKER_7B93'
FILE_TEXT='ORIGINAL_FIXTURE_FILE_CONTENT_2C41'
requests=[]
main_requests=[]
issued=False
MODE=sys.argv[1] if len(sys.argv)>1 else 'fork'


def sse_body(content,stop_reason):
    message={'id':'msg_fixture','type':'message','role':'assistant','model':'gpt-6.1-terra',
             'content':[],'stop_reason':None,'stop_sequence':None,
             'usage':{'input_tokens':100,'output_tokens':0}}
    events=[('message_start',{'type':'message_start','message':message})]
    for index,block in enumerate(content):
        start=dict(block)
        if block['type']=='tool_use':
            start['input']={}
            delta={'type':'input_json_delta','partial_json':json.dumps(block['input'])}
        else:
            start['text']=''
            delta={'type':'text_delta','text':block['text']}
        events += [('content_block_start',{'type':'content_block_start','index':index,'content_block':start}),
                   ('content_block_delta',{'type':'content_block_delta','index':index,'delta':delta}),
                   ('content_block_stop',{'type':'content_block_stop','index':index})]
    events += [('message_delta',{'type':'message_delta','delta':{'stop_reason':stop_reason,'stop_sequence':None},
                                'usage':{'output_tokens':20}}),('message_stop',{'type':'message_stop'})]
    return ''.join('event: '+event+'\ndata: '+json.dumps(data)+'\n\n' for event,data in events).encode()


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def do_POST(self):
        global issued
        data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        requests.append({'path':self.path,'body':data,'timestamp':time.time()})
        (OUT/'captured_requests.json').write_text(json.dumps(requests,indent=2))
        if 'count_tokens' in self.path:
            payload=json.dumps({'input_tokens':100}).encode()
            content_type='application/json'
        else:
            tools={tool.get('name') for tool in data.get('tools',[])}
            main='Read' in tools
            if main:
                main_requests.append(data)
            index=len(main_requests)
            if main and index==1:
                content=[{'type':'tool_use','id':'fixture-parent-read','name':'Read',
                          'input':{'file_path':'/app/fixture_parent.txt'}}]
                stop_reason='tool_use'
            elif main and index==2:
                names={tool.get('name') for tool in data.get('tools',[])}
                agent_name='Agent' if 'Agent' in names else 'Task'
                content=[{'type':'tool_use','id':'fixture-parent-agent','name':agent_name,
                          'input':{'description':'Inspect fixture child file',
                                   'prompt':'SUBAGENT_FIXTURE_CHILD_MARKER: Read /app/fixture_child.txt and return its exact content.',
                                   'subagent_type':MODE,'run_in_background':False}}]
                stop_reason='tool_use'
            elif main and index==3:
                content=[{'type':'tool_use','id':'fixture-child-read','name':'Read',
                          'input':{'file_path':'/app/fixture_child.txt'}}]
                stop_reason='tool_use'
            elif main and index==4:
                content=[{'type':'text','text':'CHILD_SUMMARY_MARKER: child fixture inspected.'}]
                stop_reason='end_turn'
            else:
                content=[{'type':'text','text':'PARENT_FINAL_MARKER: child summary received.'}]
                stop_reason='end_turn'
            if data.get('stream'):
                payload=sse_body(content,stop_reason)
                content_type='text/event-stream'
            else:
                payload=json.dumps({'id':'msg_fixture','type':'message','role':'assistant',
                    'model':'gpt-6.1-terra','content':content,'stop_reason':stop_reason,
                    'stop_sequence':None,'usage':{'input_tokens':100,'output_tokens':20}}).encode()
                content_type='application/json'
        self.send_response(200)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        payload=b'{}'
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def marker_locations(value,path='$'):
    found=[]
    if isinstance(value,str) and MARKER in value:
        found.append({'path':path,'count':value.count(MARKER)})
    elif isinstance(value,list):
        for index,item in enumerate(value):
            found+=marker_locations(item,f'{path}[{index}]')
    elif isinstance(value,dict):
        for key,item in value.items():
            found+=marker_locations(item,path+'.'+key)
    return found


async def run_probe():
    teacher=OnlineTeacher('http://127.0.0.1:8766/experiment/progress',
                          'preflight-sdk-subagent-fixture','fixture-task',OUT)
    def unexpected_hint(payload):
        raise AssertionError('A three-tool fixture must not reach a teacher check')
    teacher.request_hint=unexpected_hint
    options=create_agent_options('/app',online_teacher=teacher)
    records=[]
    async with ClaudeSDKClient(options=options) as client:
        await client.query('SUBAGENT_FIXTURE_PARENT_MARKER: Read the parent fixture and delegate the child fixture inspection using the available Agent tool. Wait for its summary and then report completion.')
        async for message in client.receive_response():
            records.append({'type':type(message).__name__,'message':asdict(message)})
    (OUT/'sdk_messages.json').write_text(json.dumps(records,indent=2))
    (OUT/'captured_requests.json').write_text(json.dumps(requests,indent=2))
    (OUT/'hook_events.json').write_text(json.dumps(teacher.events,indent=2))
    summaries=[]
    for index,data in enumerate(main_requests):
        results=[block.get('tool_use_id') for message in data.get('messages',[])
                 if isinstance(message.get('content'),list) for block in message['content']
                 if block.get('type')=='tool_result']
        uses=[block.get('id') for message in data.get('messages',[])
              if isinstance(message.get('content'),list) for block in message['content']
              if block.get('type')=='tool_use']
        summaries.append({'index':index+1,'model':data.get('model'),'metadata':data.get('metadata'),
                          'roles':[message['role'] for message in data['messages']],
                          'history_tool_uses':uses,'history_tool_results':results})
    sdk_child=[item for item in records if item['message'].get('parent_tool_use_id')]
    result={'kind':'offline_sdk_subagent_fixture','mode':MODE,'real_model_calls':0,
            'synthetic_model_usage':True,'main_model_requests':len(main_requests),
            'all_fake_http_requests':len(requests),'requests':summaries,
            'sdk_child_parent_tool_use_ids':sorted({item['message']['parent_tool_use_id'] for item in sdk_child}),
            'hook_main_tool_count':teacher.tool_count,'teacher_checks':teacher.checks,
            'sdk_hook_events':teacher.events,
            'child_summary_received':any('CHILD_SUMMARY_MARKER' in json.dumps(message.get('content'))
                 for data in main_requests[-1:] for message in data['messages']),
            'parent_final_received':any('PARENT_FINAL_MARKER' in json.dumps(item) for item in records)}
    result['passed']=(len(main_requests)==5 and bool(sdk_child) and result['child_summary_received']
                      and result['parent_final_received'] and teacher.checks==0)
    (OUT/'result.json').write_text(json.dumps(result,indent=2))
    return result


def main():
    server=ThreadingHTTPServer(('127.0.0.1',8767),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        result=asyncio.run(run_probe())
        print(json.dumps(result))
        return 0 if result['passed'] else 1
    except BaseException as exc:
        (OUT/'captured_requests.json').write_text(json.dumps(requests,indent=2))
        (OUT/'result.json').write_text(json.dumps({'kind':'offline_sdk_subagent_fixture','passed':False,
            'error':str(exc),'real_model_calls':0,'synthetic_model_usage':True},indent=2))
        raise
    finally:
        server.shutdown()
        server.server_close()


if __name__=='__main__':
    raise SystemExit(main())
