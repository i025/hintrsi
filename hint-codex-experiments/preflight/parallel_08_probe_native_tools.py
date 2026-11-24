"""Probe tool discovery routing using a loopback fake Responses provider only."""
import asyncio,json,os,sys,threading,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'preflight/parallel_08_native_tool_probe'
OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'source_parallel_07'))
from codex_cli_bridge import CodexRPCClient,default_command
records=[]
mode=''
count=0
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):
        self.send_response(404);self.end_headers()
    def do_POST(self):
        global count
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        count+=1
        records.append({'case':mode,'n':count,'path':self.path,'body':body})
        if mode=='injected_during_search' and count==1:
            item={'type':'function_call','id':'fc-search','call_id':'call-search','name':'ToolSearch','arguments':'{"query":"select:Monitor"}','status':'completed'}
        elif count==(2 if mode=='injected_during_search' else 1):
            item={'type':'function_call','id':'fc-monitor','call_id':'call-monitor','name':'Monitor','arguments':'{"description":"offline"}','status':'completed'}
        else:
            item={'type':'message','id':'msg-done','role':'assistant','status':'completed','content':[{'type':'output_text','text':'OFFLINE_DONE','annotations':[]}]}
        response={'id':'resp-'+str(count),'object':'response','created_at':int(time.time()),'status':'completed','output':[item], 'usage':{'input_tokens':20,'output_tokens':5,'total_tokens':25,'input_tokens_details':{'cached_tokens':0},'output_tokens_details':{'reasoning_tokens':0}}}
        events=[{'type':'response.created','response':{**response,'status':'in_progress','output':[]}}, {'type':'response.output_item.added','output_index':0,'item':{**item,'status':'in_progress'}}, {'type':'response.output_item.done','output_index':0,'item':item},{'type':'response.completed','response':response}]
        raw=''.join('event: '+e['type']+'\ndata: '+json.dumps(e)+'\n\n' for e in events).encode()
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
os.environ['HINT_LOCAL_PROBE_KEY']='offline-local-fake-key'
monitor={'type':'function','name':'Monitor','description':'Offline monitor routing fixture.','inputSchema':{'type':'object','properties':{'description':{'type':'string'}},'required':['description'],'additionalProperties':False}}
search={'type':'function','name':'ToolSearch','description':'Offline search routing fixture.','inputSchema':{'type':'object','properties':{'query':{'type':'string'}},'required':['query'],'additionalProperties':False}}
response_tool={'type':'function','name':'Monitor','description':monitor['description'],'parameters':monitor['inputSchema']}
async def main():
    global mode,count
    queue=asyncio.Queue()
    events=[]
    def record(e):
        events.append(e)
        if 'method'in e:queue.put_nowait(e)
    command=default_command()+['-c','model_provider="hint_local_probe"','-c','model_providers.hint_local_probe.name="Offline loopback probe"','-c','model_providers.hint_local_probe.base_url="http://127.0.0.1:'+str(server.server_address[1])+'/v1"','-c','model_providers.hint_local_probe.wire_api="responses"','-c','model_providers.hint_local_probe.env_key="HINT_LOCAL_PROBE_KEY"','-c','model_providers.hint_local_probe.requires_openai_auth=false','-c','model_providers.hint_local_probe.request_max_retries=0','-c','model_providers.hint_local_probe.stream_max_retries=0']
    rpc=CodexRPCClient(command=command,event_callback=record,stderr_path=OUT/'stderr.log',cwd=str(OUT))
    result={'real_model_calls':0,'synthetic_usage_excluded':True,'provider_base_url':'http://127.0.0.1:'+str(server.server_address[1])+'/v1','cases':[]}
    try:
        await asyncio.wait_for(rpc.start(),30)
        for mode in ['registered_control','injected_before_turn','injected_during_search']:
            count=0
            while not queue.empty():queue.get_nowait()
            tools=[search,monitor] if mode=='registered_control' else [search]
            thread=await rpc.request('thread/start',{'model':'gpt-6.1-terra','modelProvider':'hint_local_probe','allowProviderModelFallback':False,'baseInstructions':'Offline synthetic tool routing test.','developerInstructions':'Use only external dynamic tools.','config':{'model_reasoning_effort':'low'},'approvalPolicy':'never','environments':[],'ephemeral':True,'cwd':str(OUT),'dynamicTools':tools})
            tid=thread['thread']['id']
            case={'mode':mode,'thread_id':tid,'external_calls':[],'errors':[]}
            if mode=='injected_before_turn':
                case['inject_result']=await rpc.request('thread/inject_items',{'threadId':tid,'items':[{'type':'additional_tools','role':'system','tools':[response_tool]}]})
            await rpc.request('turn/start',{'threadId':tid,'model':'gpt-6.1-terra','effort':'low','input':[{'type':'text','text':'Run the synthetic local tool routing case.'}],'environments':[]})
            while True:
                event=await asyncio.wait_for(queue.get(),60)
                method=event.get('method');p=event.get('params',{})
                if p.get('threadId') not in (None,tid):continue
                if method=='item/tool/call':
                    case['external_calls'].append(p['tool'])
                    if p['tool']=='ToolSearch':
                        case['inject_result']=await rpc.request('thread/inject_items',{'threadId':tid,'items':[{'type':'additional_tools','role':'system','tools':[response_tool]}]})
                    await rpc.respond(event['id'],{'success':True,'contentItems':[{'type':'inputText','text':'OFFLINE_TOOL_OK'}]})
                elif method=='error':case['errors'].append(p)
                elif method=='turn/completed':
                    case['turn']=p['turn'];case['http_requests']=count;break
            result['cases'].append(case)
    except Exception as exc:
        result['error']=repr(exc)
    finally:
        await rpc.close();server.shutdown();server.server_close()
        (OUT/'requests.json').write_text(json.dumps(records,indent=2))
        (OUT/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
        (OUT/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)
asyncio.run(main())
