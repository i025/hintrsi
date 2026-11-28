"""Run the unchanged SDK entrypoint/tunnel against a local synthetic Unix API."""
from pathlib import Path
import http.server
import json
import socketserver
import subprocess
import sys
import tempfile
import threading

ROOT=Path('/srv/lab-disks/disk2/users/xymo/scene-rsi')
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'harness'))
from isolation import prepare,command

ACTIONS=[('Read',{'file_path':'/harness/'+name}) for name in ['run_teacher_alignment.py','run_capability_acquisition.py','run_exploration.py','sdk_student.py','socket_tunnel.py']]
ACTIONS += [('Read',{'file_path':'/capabilities/README.md'}),('Write',{'file_path':'/capabilities/entrypoint_write_probe.txt','content':'must fail'}),('Bash',{'command':'blender --background --factory-startup --python-exit-code 1 --python-expr "import bpy; print(\'SDK_ENTRYPOINT_BLENDER_OK\')"','timeout':30000})]
DIRECTORY=OUT/'shared_v2_entrypoint'
SESSION={'role':'student','condition':'OFFLINE_ONLY_RUNTIME_V2','initial_images':[],
         'readonly_mounts':[{'source':str(OUT/'capability_fixture'),'target':'/capabilities'}],
         'tools':['Read','Write','Bash'],'persistent_capability_enabled':True,'hint_enabled':False}
prepare(DIRECTORY,OUT/'fixture.png','Offline deterministic SDK transport check; no model used.',session=SESSION)

class Handler(http.server.BaseHTTPRequestHandler):
    calls=0
    def log_message(self,*args): pass
    def do_POST(self):
        request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        with (DIRECTORY/'synthetic_requests.jsonl').open('a') as output:
            output.write(json.dumps({'path':self.path,'request':request})+'\n')
        if 'count_tokens' in self.path:
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"input_tokens":100}');return
        index=Handler.calls;Handler.calls+=1
        active=index<len(ACTIONS)
        content=({'type':'tool_use','id':'offline_entry_'+str(index),'name':ACTIONS[index][0],'input':ACTIONS[index][1]} if active else {'type':'text','text':'Offline SDK entrypoint check complete.'})
        stop='tool_use' if active else 'end_turn'
        message={'id':'msg_offline_entry_'+str(index),'type':'message','role':'assistant','model':'default_model','content':[content],'stop_reason':stop,'stop_sequence':None,'usage':{'input_tokens':100,'output_tokens':20}}
        self.send_response(200);self.send_header('Content-Type','text/event-stream' if request.get('stream') else 'application/json');self.end_headers()
        if not request.get('stream'):
            self.wfile.write(json.dumps(message).encode());return
        events=[('message_start',{'type':'message_start','message':dict(message,content=[],stop_reason=None)}),
                ('content_block_start',{'type':'content_block_start','index':0,'content_block':dict(content,input={}) if active else {'type':'text','text':''}}),
                ('content_block_delta',{'type':'content_block_delta','index':0,'delta':{'type':'input_json_delta','partial_json':json.dumps(content['input'])} if active else {'type':'text_delta','text':content['text']}}),
                ('content_block_stop',{'type':'content_block_stop','index':0}),
                ('message_delta',{'type':'message_delta','delta':{'stop_reason':stop,'stop_sequence':None},'usage':{'output_tokens':20}}),
                ('message_stop',{'type':'message_stop'})]
        for event,data in events:
            self.wfile.write(('event: '+event+'\ndata: '+json.dumps(data)+'\n\n').encode())
        self.wfile.flush()

class UnixServer(socketserver.ThreadingMixIn,socketserver.UnixStreamServer):
    daemon_threads=True

with tempfile.TemporaryDirectory(prefix='scene-rsi-offline-v2-') as temporary:
    proxy_socket=Path(temporary)/'proxy.sock'
    with UnixServer(str(proxy_socket),Handler) as server:
        threading.Thread(target=server.serve_forever,daemon=True).start()
        argv=['taskset','-c','32-39']+command(DIRECTORY,proxy_socket,15)
        (DIRECTORY/'sdk_command.json').write_text(json.dumps(argv,indent=2))
        result=subprocess.run(argv,capture_output=True,text=True,timeout=120)
        (DIRECTORY/'stdout.log').write_text(result.stdout+result.stderr)
        server.shutdown()

traj=json.loads((DIRECTORY/'capture/trajs.json').read_text())
users=[json.loads(line)['message'] for line in traj['trajectories']['main_agent'].splitlines() if json.loads(line)['type']=='user']
checks={'entrypoint_exit_zero':result.returncode==0,'sdk_completed':traj['metadata']['status']=='completed',
        'controller_reads_missing':all(item['content'][0].get('is_error') and 'File does not exist' in item['content'][0]['content'] for item in users[:3]),
        'runtime_reads_ok':all(not item['content'][0].get('is_error') for item in users[3:6]),
        'readonly_write_denied':users[6]['content'][0].get('is_error') and 'EROFS' in users[6]['content'][0]['content'],
        'blender_sdk_execution_ok':not users[7]['content'][0].get('is_error') and 'SDK_ENTRYPOINT_BLENDER_OK' in users[7]['content'][0]['content']}
report={'checks':checks,'all_passed':all(checks.values()),'real_model_calls':0,'api_kind':'Local synthetic Unix HTTP fixture','sdk_request_count':Handler.calls,'uses_actual_entrypoint_and_socket_tunnel':True,'cpu_affinity':list(range(32,40)),'tool_results':users}
(DIRECTORY/'entrypoint_check.json').write_text(json.dumps(report,indent=2))
print(json.dumps({key:value for key,value in report.items() if key!='tool_results'},indent=2))
assert report['all_passed']
