#!/usr/bin/env python3
"""Launch the isolated SDK hook probe in the existing experiment VM."""

import io
import json
import tarfile
import time
from pathlib import Path
import docker

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
NAME='codex-sdk-hook-preflight'


def put_file(container,path,content):
    content=content.encode() if isinstance(content,str) else content
    archive=io.BytesIO()
    with tarfile.open(fileobj=archive,mode='w') as output:
        item=tarfile.TarInfo(Path(path).name)
        item.size=len(content)
        output.addfile(item,io.BytesIO(content))
    container.put_archive(str(Path(path).parent),archive.getvalue())


def main():
    client=docker.DockerClient(base_url='unix://'+str(ROOT/'vm/docker.sock'),timeout=300)
    original=json.loads((ROOT/'preflight/sdk_fixture_container.json').read_text())
    image=client.images.get(original['image'])
    env={item.split('=',1)[0]:'offline-fixture' for item in image.attrs['Config'].get('Env',[])
         if any(word in item.split('=',1)[0].upper() for word in
                ('KEY','TOKEN','SECRET','PASSWORD','ANTHROPIC','OPENAI','OFOX','HUBROUTER'))}
    env.update({'ANTHROPIC_BASE_URL':'http://127.0.0.1:8767','ANTHROPIC_AUTH_TOKEN':'offline-fixture',
                'ANTHROPIC_MODEL':'gpt-6.1-terra','ANTHROPIC_SMALL_FAST_MODEL':'gpt-6.1-terra',
                'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC':'1','IS_SANDBOX':'1','API_TIMEOUT_MS':'60000',
                'PYTHONDONTWRITEBYTECODE':'1','HTTP_PROXY':'','HTTPS_PROXY':'','ALL_PROXY':'',
                'http_proxy':'','https_proxy':'','all_proxy':'','NO_PROXY':'*'})
    container=client.containers.run(image.id,name=NAME,entrypoint='',command=['tail','-f','/dev/null'],
        detach=True,mem_limit='128g',nano_cpus=8_000_000_000,privileged=True,network_mode='none',
        environment=env,volumes={'/opt/hint-codex-runtime/python':{'bind':'/opt/python3.12-tmp','mode':'ro'}})
    run={'container':container.id,'name':NAME,'image':image.id,'network_mode':'none',
         'runtime_mount_mode':'ro','real_model_calls':0,'started_at':time.time()}
    try:
        code,output=container.exec_run(['/bin/bash','-c','rm -rf /app /root/.claude; mkdir -p /app /tmp/hook_probe_out'])
        if code:raise RuntimeError(output.decode())
        for number in range(1,21):
            put_file(container,f'/app/fixture_{number}.txt','ORIGINAL_FIXTURE_FILE_CONTENT_2C41\n')
        for path,target in [(ROOT/'source/run_cc_sdk.py','/tmp/sdk_script.py'),
                            (ROOT/'source/logging_utils.py','/tmp/logging_utils.py'),
                            (OUT/'probe.py','/tmp/hook_probe.py')]:
            put_file(container,target,path.read_bytes())
        code,output=container.exec_run(['timeout','180','/opt/python3.12-tmp/bin/python3','/tmp/hook_probe.py'],
                                       workdir='/app',environment=env)
        (OUT/'stdout.log').write_bytes(output)
        run['exit_code']=code
        archive,_=container.get_archive('/tmp/hook_probe_out')
        with tarfile.open(fileobj=io.BytesIO(b''.join(archive))) as source:
            for item in source.getmembers():
                if item.isfile():
                    (OUT/Path(item.name).name).write_bytes(source.extractfile(item).read())
        result=json.loads((OUT/'result.json').read_text())
        run['passed']=result.get('passed',False)
        print(json.dumps({'exit_code':code,'passed':run['passed'],'result':str(OUT/'result.json'),
                          'marker_locations':result.get('marker_locations'),'error':result.get('error')}))
    finally:
        run['finished_at']=time.time()
        (OUT/'container_run.json').write_text(json.dumps(run,indent=2))
        container.remove(force=True)
        client.close()
    return 0 if run.get('passed') and run.get('exit_code')==0 else 1


if __name__=='__main__':
    raise SystemExit(main())
