"""Observe fresh exec context limits and error mapping using a local Responses provider."""
import asyncio
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT.parents[1]))
from codex_exec_bridge import CodexExecBridge, default_command
RECORDS = []

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass
    def do_GET(self):
        self.send_response(404); self.end_headers()
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        case = self.path.split('/')[1]
        compact = any(item.get('type') == 'compaction_trigger' for item in body.get('input',[]))
        number = sum(r['case']==case for r in RECORDS)+1
        record = {'at':time.time(),'case':case,'request_number':number,'compact':compact,'body':body}
        RECORDS.append(record)
        if case == 'context_error' and not compact:
            payload = {'error': {'type':'invalid_request_error','code':'context_length_exceeded',
                'message':'Your input exceeds the context window of this model. Please adjust your input and try again.','param':'input'}}
            raw=json.dumps(payload).encode()
            record['status']=400
            self.send_response(400);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            return
        if compact:
            item={'type':'compaction','id':'cmp-'+case,'encrypted_content':'OFFLINE_COMPACTED_CONTEXT'}
        else:
            item={'type':'message','id':'msg-'+case,'role':'assistant','status':'completed',
                'content':[{'type':'output_text','text':json.dumps({'content':'OFFLINE_CONTEXT_DONE','tool_calls':[]}), 'annotations':[]}]}
        response={'id':'resp-'+case+str(number),'object':'response','created_at':int(time.time()),
            'status':'completed','output':[item],'usage':{'input_tokens':100,'output_tokens':20,
            'total_tokens':120,'input_tokens_details':{'cached_tokens':0},'output_tokens_details':{'reasoning_tokens':0}}}
        events=[{'type':'response.created','response':{**response,'status':'in_progress','output':[]}},
            {'type':'response.output_item.added','output_index':0,'item':item},
            {'type':'response.output_item.done','output_index':0,'item':item},
            {'type':'response.completed','response':response}]
        raw=''.join('event: '+e['type']+'\ndata: '+json.dumps(e)+'\n\n' for e in events).encode()
        record['status']=200
        self.send_response(200);self.send_header('Content-Type','text/event-stream')
        self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)

async def run(case,address):
    command=default_command()+['-c','model_provider="hint_context_probe"',
        '-c','model_providers.hint_context_probe.name="Offline context probe"',
        '-c','model_providers.hint_context_probe.base_url='+json.dumps(address+'/'+case+'/v1'),
        '-c','model_providers.hint_context_probe.wire_api="responses"',
        '-c','model_providers.hint_context_probe.env_key="HINT_CONTEXT_PROBE_KEY"',
        '-c','model_providers.hint_context_probe.requires_openai_auth=false',
        '-c','model_providers.hint_context_probe.request_max_retries=0',
        '-c','model_providers.hint_context_probe.stream_max_retries=0',
        '-c','model_providers.hint_context_probe.capabilities.remote_compaction="v2"',
        '-c','features.code_mode=true','-c','features.code_mode_only=true',
        '-c','model_auto_compact_token_limit=1000']
    path=OUT/case;path.mkdir(exist_ok=True)
    (path/'command.json').write_text(json.dumps(command,indent=2))
    bridge=CodexExecBridge(path/'runtime',command)
    body={'model':'fixture','messages':[{'role':'system','content':'Return the next action.'},
        {'role':'user','content':('FULL_HISTORY_MARKER alpha beta gamma delta\n'*4000 if case=='large_first_input' else 'Short fixture request.')}], 'tools':[]}
    result={'case':case,'started_at':time.time(),'input_characters':len(json.dumps(body))}
    try:
        result['response']=await asyncio.wait_for(bridge.chat(body,route={'session':case}),35)
    except Exception as exc:
        result['error']={'class':type(exc).__name__,'message':str(exc),'code':getattr(exc,'code',None),'status':getattr(exc,'status',None)}
    finally:
        result['remaining_processes']=len(bridge.processes)
        await bridge.close()
    captured=[r for r in RECORDS if r['case']==case]
    result['provider_requests']=[{'number':r['request_number'],'compact':r['compact'],'status':r['status'],
        'input_types':[item.get('type') for item in r['body'].get('input',[])]} for r in captured]
    result['elapsed_seconds']=time.time()-result['started_at']
    return result

async def main():
    os.environ['HINT_CONTEXT_PROBE_KEY']='offline-local-fixture'
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    address='http://127.0.0.1:'+str(server.server_address[1])
    try:
        cases=await asyncio.gather(run('large_first_input',address),run('context_error',address))
    finally:
        server.shutdown();server.server_close()
        (OUT/'requests.json').write_text(json.dumps(RECORDS))
    result={'real_model_calls':0,'formal_configuration_changed':False,'test_only_auto_compact_token_limit':1000,'cases':cases}
    (OUT/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
if __name__=='__main__':asyncio.run(main())
