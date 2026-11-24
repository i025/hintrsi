import asyncio, json, os, sys, threading, socket
from pathlib import Path
os.environ['LITELLM_LOCAL_MODEL_COST_MAP']='True'
os.environ['LITELLM_TELEMETRY']='False'
ROOT=Path('/srv/lab-disks/disk2/users/xymo/hint-codex-experiments')
sys.path.insert(0,str(ROOT/'source_parallel_09_checked'))
sys.path.insert(0,sys.argv[1])
import codex_cli_bridge as shared
import streaming_fix
import litellm,uvicorn
from litellm.llms.anthropic.experimental_pass_through.adapters.streaming_iterator import AnthropicStreamWrapper
streaming_fix.apply()
response={'id':'offline-usage','created':1,'model':'gpt-6.1-terra','object':'chat.completion','choices':[{'index':0,'message':{'role':'assistant','content':'OFFLINE_TEXT'},'finish_reason':'stop'}],'usage':{'prompt_tokens':123,'completion_tokens':17,'total_tokens':140}}
class Bridge:
 stopped=False
 async def chat(self,*args): return response
original=shared._sse
async def separate(resp):
 async for line in original(resp):
  if line.startswith('data: {'):
   value=json.loads(line[6:])
   if value.get('usage'):
    usage=value.pop('usage')
    yield 'data: '+json.dumps(value)+'\n\n'
    yield 'data: '+json.dumps({**{k:value[k] for k in ('id','created','model','object')},'choices':[],'usage':usage})+'\n\n'
    continue
  yield line
s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close()
server=uvicorn.Server(uvicorn.Config(shared.create_app(Bridge()),host='127.0.0.1',port=port,log_level='error'))
thread=threading.Thread(target=server.run);thread.start()
async def main():
 while not server.started: await asyncio.sleep(.02)
 result={}
 for fixture in ('text', 'tools'):
  if fixture=='tools':
   response['choices'][0].update(message={'role':'assistant','content':'Inspect the fixture.', 'tool_calls':[{'id':'call-read-1','type':'function','function':{'name':'Read','arguments':json.dumps({'file_path':'/app/fixture.txt'})}},{'id':'call-bash-2','type':'function','function':{'name':'Bash','arguments':json.dumps({'command':'printf OFFLINE_OK'})}}]},finish_reason='tool_calls')
  for variant in ('same_chunk','separate_usage'):
   shared._sse=original if variant=='same_chunk' else separate
   stream=await litellm.acompletion(model='openai/gpt-6.1-terra',api_base=f'http://127.0.0.1:{port}/v1',api_key='offline-fixture',messages=[{'role':'user','content':'offline only'}],stream=True,stream_options={'include_usage':True})
   chunks=[]
   async def record():
    async for c in stream:
     chunks.append(c.model_dump())
     yield c
   translated=[]
   try:
    async for e in AnthropicStreamWrapper(record(),'gpt-6.1-terra'): translated.append(e)
    result[fixture+'_'+variant]={'chunks':chunks,'anthropic_events':translated}
   except Exception as e: result[fixture+'_'+variant]={'chunks':chunks,'anthropic_events':translated,'error':repr(e)}
 Path(sys.argv[2]).write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(json.dumps({name:{'usage':[x.get('usage') for x in data['anthropic_events'] if x['type']=='message_delta'], 'error':data.get('error')} for name,data in result.items()}),flush=True)
try: asyncio.run(main())
finally:
 server.should_exit=True;thread.join(5)
