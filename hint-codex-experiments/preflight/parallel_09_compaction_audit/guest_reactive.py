"""Observe the real SDK auto-compaction request shape with synthetic token usage."""
import asyncio, json, os, threading, time
from dataclasses import asdict
from pathlib import Path
from http.server import ThreadingHTTPServer
from hook_fixture import Handler as OriginalHandler, sse_body
from sdk_script import create_agent_options
from claude_agent_sdk import ClaudeSDKClient

OUT=Path('/tmp/transport_audit_out');OUT.mkdir()
requests=[];issued=False;context_error_sent=False
class Handler(OriginalHandler):
 def do_POST(self):
  global issued,context_error_sent
  data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  requests.append({'path':self.path,'body':data,'timestamp':time.time()})
  (OUT/'requests.json').write_text(json.dumps(requests,indent=2))
  if 'count_tokens' in self.path:
   payload=json.dumps({'input_tokens':100}).encode();ctype='application/json'
  else:
   main='Read' in {t.get('name') for t in data.get('tools',[])}
   if main and issued and not context_error_sent:
    context_error_sent=True
    payload=json.dumps({'type':'error','error':{'type':'invalid_request_error','message':'prompt is too long: 1000100 tokens > 1000000 maximum'}}).encode()
    self.send_response(400);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload);return
   first=main and not issued
   if first:
    issued=True
    content=[{'type':'tool_use','id':'before-compaction-read','name':'Read','input':{'file_path':'/app/fixture.txt'}}];stop='tool_use';tokens=980000
   else:
    content=[{'type':'text','text':'<summary>Offline task: read /app/fixture.txt. The Read succeeded. Report OFFLINE_COMPACTION_COMPLETE.</summary>\nOFFLINE_COMPACTION_COMPLETE'}];stop='end_turn';tokens=100
   if data.get('stream'):
    payload=sse_body(content,stop).replace(b'"input_tokens": 100',b'"input_tokens": '+str(tokens).encode());ctype='text/event-stream'
   else:
    payload=json.dumps({'id':'msg-offline','type':'message','role':'assistant','model':'gpt-6.1-terra','content':content,'stop_reason':stop,'stop_sequence':None,'usage':{'input_tokens':tokens,'output_tokens':20}}).encode();ctype='application/json'
  self.send_response(200);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)

async def main():
 Path('/app/fixture.txt').write_text('COMPACTION_FIXTURE_READ_SUCCESS\n')
 server=ThreadingHTTPServer(('127.0.0.1',8767),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
 options=create_agent_options('/app');options.extra_args={'debug-file':str(OUT/'sdk_debug.log')}
 records=[];result={'passed':False,'real_model_calls':0,'synthetic_usage_excluded':True,'network':'none','compact_window_env':os.environ.get('CLAUDE_CODE_AUTO_COMPACT_WINDOW'),'disable_auto_compact_env':os.environ.get('DISABLE_AUTO_COMPACT'),'model':os.environ.get('ANTHROPIC_MODEL'),'trigger':'single synthetic 400 prompt-too-long error, no SDK configuration change'}
 try:
  async with ClaudeSDKClient(options=options) as client:
   await client.query('Read the fixture and report completion. This is a controlled offline transport check.')
   async for message in client.receive_response():
    records.append({'type':type(message).__name__,'message':asdict(message)})
  result['request_count']=len(requests);result['system_messages']=[r for r in records if r['type']=='SystemMessage'];result['final_messages']=[r for r in records if r['type']=='ResultMessage'];result['passed']=True
 finally:
  server.shutdown();server.server_close()
  (OUT/'sdk_messages.json').write_text(json.dumps(records,indent=2))
  (OUT/'requests.json').write_text(json.dumps(requests,indent=2))
  (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
  print(json.dumps(result),flush=True)
asyncio.run(main())
