import anyio
import errno
import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
sys.path.insert(0, '/harness')
import sdk_student
session=json.loads(Path('/inputs/session.json').read_text())
mount=session['readonly_mounts'][0]['target']
read_path=mount+('/GT.json' if session['role']=='teacher' else '/README.md')
probe={'role':session['role'],'visible_read':Path(read_path).exists(),
       'host_project_visible':Path('/srv/lab-disks/disk2/users/xymo/scene-rsi').exists(),
       'old_scene_visible':Path('/srv/lab-disks/disk2/users/xymo/scene').exists(),
       'test_gt_visible':Path('/test_gt').exists(),
       'opposite_mount_visible':Path('/capabilities' if session['role']=='teacher' else '/dev_gt').exists(),
       'cpu_affinity':sorted(os.sched_getaffinity(0))}
try:
 Path(mount+'/namespace_write_probe.txt').write_text('must fail')
 probe['readonly_write_denied']=False
except OSError as error:
 probe['readonly_write_denied']=error.errno==errno.EROFS
 probe['readonly_write_errno']=error.errno
Path('/capture/namespace_probe.json').write_text(json.dumps(probe,indent=2))
actions=[('Read',{'file_path':read_path}),
         ('Read',{'file_path':'/test_gt/scene.blend'}),
         ('Read',{'file_path':'/srv/lab-disks/disk2/users/xymo/scene-rsi/data/evaluation_gt/office/office_s1210607561/GT.json'}),
         ('Write',{'file_path':mount+'/sdk_write_probe.txt','content':'must fail'})]
class Handler(http.server.BaseHTTPRequestHandler):
 calls=0
 def log_message(self,*args):pass
 def do_POST(self):
  request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  with Path('/capture/synthetic_requests.jsonl').open('a') as stream:
   stream.write(json.dumps({'path':self.path,'request':request})+'\n')
  if 'count_tokens' in self.path:
   payload=json.dumps({'input_tokens':100}).encode()
   self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(payload);return
  index=Handler.calls;Handler.calls+=1
  active=index<len(actions)
  content=({'type':'tool_use','id':'offline_'+str(index),'name':actions[index][0],'input':actions[index][1]} if active else {'type':'text','text':'Offline SDK transport check complete.'})
  message={'id':'msg_offline_'+str(index),'type':'message','role':'assistant','model':'default_model','content':[content],'stop_reason':'tool_use' if active else 'end_turn','stop_sequence':None,'usage':{'input_tokens':100,'output_tokens':20}}
  self.send_response(200)
  self.send_header('Content-Type','text/event-stream' if request.get('stream') else 'application/json')
  self.end_headers()
  if not request.get('stream'):
   self.wfile.write(json.dumps(message).encode());return
  events=[('message_start',{'type':'message_start','message':dict(message,content=[],stop_reason=None)}),
          ('content_block_start',{'type':'content_block_start','index':0,'content_block':dict(content,input={}) if active else {'type':'text','text':''}}),
          ('content_block_delta',{'type':'content_block_delta','index':0,'delta':{'type':'input_json_delta','partial_json':json.dumps(content['input'])} if active else {'type':'text_delta','text':content['text']}}),
          ('content_block_stop',{'type':'content_block_stop','index':0}),
          ('message_delta',{'type':'message_delta','delta':{'stop_reason':message['stop_reason'],'stop_sequence':None},'usage':{'output_tokens':20}}),
          ('message_stop',{'type':'message_stop'})]
  for event,data in events:
   self.wfile.write(('event: '+event+'\ndata: '+json.dumps(data)+'\n\n').encode())
  self.wfile.flush()
server=http.server.ThreadingHTTPServer(('127.0.0.1',18767),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
for args in [['init','-q','/app'],['-C','/app','config','user.name','Offline isolation check'],['-C','/app','config','user.email','offline@local.invalid'],['-C','/app','add','-A'],['-C','/app','commit','-qm','Offline namespace fixture']]:
 subprocess.run(['git']+args,check=True)
try:
 anyio.run(sdk_student.main)
finally:
 server.shutdown()
