"""Exercise long prompt files with the real SDK and a network-isolated fake API."""

import io
import json
import tarfile
import time
from pathlib import Path

import docker
import pyarrow.parquet as pq

ROOT = Path('/srv/lab-disks/disk2/users/xymo/hint-codex-experiments')
OUT = ROOT / 'preflight/parallel_06_prompt_file_gate'
PYTHON = '/opt/python3.12-tmp/bin/python3'

GUEST = r'''
import json, os, subprocess, threading, time
from pathlib import Path
from http.server import ThreadingHTTPServer
from hook_fixture import Handler as OriginalHandler, sse_body

OUT=Path('/tmp/transport_out')
OUT.mkdir()
requests=[]
plans=[]

class Handler(OriginalHandler):
    def do_POST(self):
        data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        requests.append(data)
        if 'count_tokens' in self.path:
            payload=json.dumps({'input_tokens':100}).encode()
            content_type='application/json'
        else:
            main='Read' in {t.get('name') for t in data.get('tools',[])}
            content=plans.pop(0) if main and plans else [{'type':'text','text':'OFFLINE_TRANSPORT_COMPLETE'}]
            stop='tool_use' if any(b['type']=='tool_use' for b in content) else 'end_turn'
            payload=sse_body(content,stop)
            content_type='text/event-stream'
        self.send_response(200)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

def tool(name, values, callid):
    return {'type':'tool_use','id':callid,'name':name,'input':values}

def text_contents(body):
    for message in body.get('messages',[]):
        if message['role'] != 'user':
            continue
        content=message.get('content',[])
        if isinstance(content,str):
            yield content
        else:
            for block in content:
                if block.get('type')=='text':
                    yield block['text']

subprocess.run(['git','init','-q','/app'],check=True)
subprocess.run(['git','-C','/app','config','user.email','offline@example.invalid'],check=True)
subprocess.run(['git','-C','/app','config','user.name','Offline fixture'],check=True)
Path('/app/counter.py').write_text('def add(a, b):\n    return a - b\n')
subprocess.run(['git','-C','/app','add','counter.py'],check=True)
subprocess.run(['git','-C','/app','commit','-qm','Offline fixture'],check=True)
base=subprocess.check_output(['git','-C','/app','rev-parse','HEAD'],text=True).strip()
server=ThreadingHTTPServer(('127.0.0.1',8767),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
result={'passed':False,'real_model_calls':0,'synthetic_usage_excluded':True,'phases':[]}
try:
    session=None
    for phase in ('initial','resume'):
        prefix='LONG_FILE_TRANSPORT_'+phase.upper()+'\r\n'
        payload=prefix+('Preserve this literal transport fixture text. ' * 5100)+"\r\nLiteral 'quotes', \"quotes\", $(touch /tmp/should_not_exist), `touch /tmp/also_should_not_exist`.\r\nEND_"+phase+'\n\n'
        prompt=Path('/tmp/'+phase+'_prompt.txt')
        prompt.write_bytes(payload.encode())
        expected=payload.rstrip('\n')
        old=subprocess.run(['/bin/bash','-c',"/opt/python3.12-tmp/bin/python3 -c 'pass' --problem_statement \"$(cat "+str(prompt)+")\""],capture_output=True)
        assert old.returncode==126 and b'Argument list too long' in old.stderr,old.stderr
        old_value='return a - b' if phase=='initial' else 'return a + b'
        new_value='return a + b' if phase=='initial' else 'return a + b\n\ndef multiply(a, b):\n    return a * b'
        plans[:]=[
            [tool('Read',{'file_path':'/app/counter.py'},phase+'-read')],
            [tool('Edit',{'file_path':'/app/counter.py','old_string':old_value,'new_string':new_value},phase+'-edit')],
            [tool('Bash',{'command':"/opt/python3.12-tmp/bin/python3 -c \"import counter; assert counter.add(3,2)==5; print('LOCAL_TEST_PASSED')\"",'description':'Check the offline fixture'},phase+'-test')],
            [{'type':'text','text':'OFFLINE_TRANSPORT_COMPLETE'}],
        ]
        output=OUT/phase
        command=['/opt/python3.12-tmp/bin/python3','/tmp/sdk_script.py','--cwd','/app','--base_commit',base,'--output_dir',str(output),'--log_path',str(OUT/(phase+'.log'))]
        if session:
            command+=['--resume_session_id',session,'--extra_message_file',str(prompt)]
        else:
            command+=['--problem_statement_file',str(prompt)]
        started=time.monotonic()
        response=subprocess.run(command,capture_output=True,timeout=200)
        (OUT/(phase+'_stdout.log')).write_bytes(response.stdout+response.stderr)
        assert response.returncode==0,response.stderr[-2000:]
        trajs=json.loads((output/'trajs.json').read_text())
        meta=trajs['metadata']
        current=meta['ResultMessage']['session_id']
        assert meta['status']=='completed' and not meta['ResultMessage']['is_error'],meta
        if session:
            assert session==current
        session=current
        assert not plans,'The SDK did not execute the expected local tools'
        assert any(expected in text for body in requests for text in text_contents(body)), 'The complete effective prompt was not delivered'
        expected_tools={phase+'-read',phase+'-edit',phase+'-test'}
        seen={b.get('tool_use_id'):b for body in requests for m in body.get('messages',[]) if m.get('role')=='user' and isinstance(m.get('content'),list) for b in m['content'] if b.get('tool_use_id') in expected_tools}
        assert set(seen)==expected_tools and all(not b.get('is_error') for b in seen.values()),seen
        assert 'LOCAL_TEST_PASSED' in str(seen[phase+'-test'])
        assert not Path('/tmp/should_not_exist').exists() and not Path('/tmp/also_should_not_exist').exists()
        result['phases'].append({'phase':phase,'prompt_file_bytes':len(payload.encode()),'effective_prompt_bytes':len(expected.encode()),'legacy_exit':old.returncode,'new_exit':response.returncode,'full_prompt_delivered':True,'successful_tools':sorted(seen),'sdk_session_id':session,'wall_seconds':time.monotonic()-started})
    assert 'def multiply' in Path('/app/counter.py').read_text()
    result['passed']=True
finally:
    server.shutdown()
    server.server_close()
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
'''


def put(container, path, data):
    data = data.encode() if isinstance(data, str) else data
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        item = tarfile.TarInfo(Path(path).name)
        item.size = len(data)
        archive.addfile(item, io.BytesIO(data))
    container.put_archive(str(Path(path).parent), stream.getvalue())


def main():
    OUT.mkdir()
    client = docker.DockerClient(base_url='unix://' + str(ROOT / 'vm/docker.sock'), timeout=600)
    row = next(r for r in pq.read_table(ROOT.parent / 'hint-baseline-run/data/deep_swe_tasks.parquet').to_pylist() if r['instance_id']=='obsidian-linter-auto-table-of-contents')
    image = client.images.get(row['image_name'])
    env = {v.split('=',1)[0]:'offline-fixture' for v in image.attrs['Config'].get('Env',[]) if any(k in v.split('=',1)[0].upper() for k in ('KEY','TOKEN','SECRET','PASSWORD','ANTHROPIC','OPENAI','OFOX','HUBROUTER'))}
    env.update(ANTHROPIC_BASE_URL='http://127.0.0.1:8767', ANTHROPIC_AUTH_TOKEN='offline-fixture', ANTHROPIC_MODEL='gpt-6.1-terra', ANTHROPIC_SMALL_FAST_MODEL='gpt-6.1-terra', CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1', IS_SANDBOX='1', API_TIMEOUT_MS='60000', PYTHONDONTWRITEBYTECODE='1', SYSTEM_PROMPT_FILE='', HTTP_PROXY='', HTTPS_PROXY='', ALL_PROXY='', http_proxy='', https_proxy='', all_proxy='', NO_PROXY='*', BUN_JSC_useJIT='0')
    container = client.containers.run(image.id,name='codex-parallel06-prompt-file-offline',entrypoint='',command=['tail','-f','/dev/null'],detach=True,mem_limit='128g',nano_cpus=8_000_000_000,privileged=True,network_mode='none',environment=env,labels={'hint.experiment_name':'preflight_parallel_06_prompt_file'},volumes={'/opt/hint-codex-runtime/python':{'bind':'/opt/python3.12-tmp','mode':'ro'}})
    record = {'started_at_unix':time.time(),'real_model_calls':0,'network':'none','container':container.id}
    try:
        code, output = container.exec_run(['bash','-c','rm -rf /app /root/.claude; mkdir -p /app'])
        assert code==0,output
        for path,target in [(ROOT/'source_parallel_06/run_cc_sdk.py','/tmp/sdk_script.py'),(ROOT/'source_parallel_06/logging_utils.py','/tmp/logging_utils.py'),(ROOT/'preflight/sdk_hook_fixture/probe.py','/tmp/hook_fixture.py')]:
            put(container,target,path.read_bytes())
        put(container,'/tmp/probe_transport.py',GUEST)
        started=time.monotonic()
        code,output=container.exec_run(['timeout','--signal=INT','--kill-after=20','440',PYTHON,'/tmp/probe_transport.py'],workdir='/app')
        (OUT/'stdout.log').write_bytes(output)
        chunks,_=container.get_archive('/tmp/transport_out')
        with tarfile.open(fileobj=io.BytesIO(b''.join(chunks))) as archive:
            for item in archive.getmembers():
                if item.isfile():
                    target=OUT/Path(item.name).relative_to('transport_out')
                    target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(archive.extractfile(item).read())
        result=json.loads((OUT/'result.json').read_text())
        record.update(exit_code=code,passed=code==0 and result['passed'],host_exec_seconds=time.monotonic()-started)
    finally:
        container.remove(force=True)
        client.close()
        record.update(container_removed=True,finished_at_unix=time.time())
        (OUT/'host_result.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record),flush=True)
    return 0 if record.get('passed') else 1


if __name__=='__main__':
    raise SystemExit(main())
