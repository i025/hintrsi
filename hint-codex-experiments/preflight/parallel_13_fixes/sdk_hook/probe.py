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

OUT=Path('/tmp/hook_probe_out')
OUT.mkdir(exist_ok=True)
MARKER='TEACHER_HINT_MARKER_7B93'
FILE_TEXT='ORIGINAL_FIXTURE_FILE_CONTENT_2C41'
requests=[]
main_requests=[]
issued=False


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
        if 'count_tokens' in self.path:
            payload=json.dumps({'input_tokens':100}).encode()
            content_type='application/json'
        else:
            tools={tool.get('name') for tool in data.get('tools',[])}
            main='Read' in tools
            if main:
                main_requests.append(data)
            if main and not issued:
                issued=True
                content=[{'type':'tool_use','id':f'fixture-read-{number}','name':'Read',
                          'input':{'file_path':f'/app/fixture_{number}.txt'}} for number in range(1,21)]
                stop_reason='tool_use'
            else:
                content=[{'type':'text','text':'HOOK_FIXTURE_DONE'}]
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
                          'preflight-sdk-hook-fixture','fixture-task',OUT)
    teacher_requests=[]
    def fake_hint(payload):
        teacher_requests.append(payload)
        return {'hint':MARKER,'stopped':False,'stop_reason':None}
    teacher.request_hint=fake_hint
    options=create_agent_options('/app',online_teacher=teacher)
    records=[]
    async with ClaudeSDKClient(options=options) as client:
        await client.query('Complete this local transport fixture using the provided file-reading tools. '
                           'Read the fixture files requested by the response and report completion. '
                           'Do not modify any file.')
        async for message in client.receive_response():
            records.append({'type':type(message).__name__,'message':asdict(message)})
    (OUT/'sdk_messages.json').write_text(json.dumps(records,indent=2))
    (OUT/'teacher_requests.json').write_text(json.dumps(teacher_requests,indent=2))
    (OUT/'captured_requests.json').write_text(json.dumps(requests,indent=2))
    (OUT/'hook_events.json').write_text(json.dumps(teacher.events,indent=2))
    second=main_requests[1] if len(main_requests)>1 else {}
    tool_results=[block for message in second.get('messages',[]) if message['role']=='user'
                  for block in (message.get('content') if isinstance(message.get('content'),list) else [])
                  if block.get('type')=='tool_result']
    locations=marker_locations(second)
    session_ids={item['message'].get('data',{}).get('session_id')
                 for item in records if item['type']=='SystemMessage'}
    session_ids.update(item['message'].get('session_id') for item in records if item['type']=='ResultMessage')
    session_ids.discard(None)
    raw_metadata=[message.get('metadata',{}).get('user_id') for message in main_requests]
    result={'kind':'offline_sdk_hook_fixture','real_model_calls':0,'synthetic_model_usage':True,
            'main_model_requests':len(main_requests),'all_fake_http_requests':len(requests),
            'tool_count':teacher.tool_count,'teacher_checks':teacher.checks,
            'teacher_request_count':len(teacher_requests),'marker_locations':locations,
            'marker_count_in_next_request':sum(item['count'] for item in locations),
            'initial_request_has_no_marker':not marker_locations(main_requests[0]) if main_requests else False,
            'next_request_tool_results':len(tool_results),
            'tool_result_ids':[block.get('tool_use_id') for block in tool_results],
            'all_original_results_present':all(FILE_TEXT in json.dumps(block.get('content')) for block in tool_results),
            'session_ids':sorted(session_ids),'request_user_identity_count':len(set(raw_metadata)),
            'teacher_wait_seconds':teacher.wait_seconds}
    result['passed']=(len(main_requests)==2 and teacher.tool_count==20 and teacher.checks==1
                      and len(teacher_requests)==1 and result['marker_count_in_next_request']==1
                      and result['initial_request_has_no_marker'] and len(tool_results)==20
                      and result['all_original_results_present'] and len(session_ids)==1
                      and result['request_user_identity_count']==1)
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
        (OUT/'result.json').write_text(json.dumps({'kind':'offline_sdk_hook_fixture','passed':False,
            'error':str(exc),'real_model_calls':0,'synthetic_model_usage':True},indent=2))
        raise
    finally:
        server.shutdown()
        server.server_close()


if __name__=='__main__':
    raise SystemExit(main())
