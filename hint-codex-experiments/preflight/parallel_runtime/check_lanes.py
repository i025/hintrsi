#!/usr/bin/env python3
"""Check lane software, fixed resources, assigned images, and gateway routing."""

import argparse
import json
import shlex
import time
from pathlib import Path

import docker
import pyarrow.parquet as pq

from prepare_lane import OLD, OUT, PYTHON, ROOT, ssh

TASKS = {
    0:['claude-code-by-agents-recursive-delegation','termenv-preserve-ansi-resets'],
    1:['igel-persist-feature-schema','textual-kitty-key-phases'],
    2:['ink-grid-box-layout','valibot-recursive-schema-composition'],
    3:['kea-atomic-signal-selectors'],
    4:['obsidian-linter-auto-table-of-contents'],
    5:['sqlfmt-create-table-ddl-formatting'],
}
ROWS = {row['instance_id']:row for row in pq.read_table(OLD/'data/deep_swe_tasks.parquet').to_pylist()
        if row['instance_id'] in {task for tasks in TASKS.values() for task in tasks}}


def client_for(lane):
    return docker.DockerClient(base_url='unix://' + str(ROOT/f'vm-lane{lane}/docker.sock'),timeout=720)


def pull_image(lane, task):
    client = client_for(lane)
    original = ROWS[task]['image_name']
    path = OUT/f'lane{lane}_{task}_image.json'
    record = {'lane':lane,'task':task,'original_alias':original,'started_at_unix':time.time(),'model_calls':0}
    try:
        try:
            image = client.images.get(original)
            record['source'] = 'immutable_base_cache'
        except docker.errors.ImageNotFound:
            tag = original.rsplit(':',1)[1]
            repository = 'public.ecr.aws/d3j8x8q7/swe-bench-202605'
            record.update(source='official_public_registry',public_tag_ref=repository+':'+tag)
            with (OUT/f'lane{lane}_{task}_pull.jsonl').open('a') as log:
                for event in client.api.pull(repository,tag=tag,stream=True,decode=True):
                    log.write(json.dumps(event)+'\n')
                    if event.get('error'):
                        raise RuntimeError(event['error'])
            image = client.images.get(repository+':'+tag)
            repository, tag = original.rsplit(':',1)
            image.tag(repository,tag)
        record.update(ready=True,image_id=image.id,image_bytes=image.attrs['Size'])
    except Exception as error:
        record.update(ready=False,error=str(error))
    finally:
        client.close()
        record['finished_at_unix'] = time.time()
        path.write_text(json.dumps(record,indent=2)+'\n')
        print(json.dumps(record),flush=True)
    return record


def check(lane):
    client = client_for(lane)
    directory = ROOT/f'vm-lane{lane}'
    assigned = []
    for task in TASKS[lane]:
        try:
            image = client.images.get(ROWS[task]['image_name'])
            assigned.append({'task':task,'original_alias':ROWS[task]['image_name'],'ready':True,'image_id':image.id})
        except docker.errors.ImageNotFound:
            assigned.append({'task':task,'original_alias':ROWS[task]['image_name'],'ready':False})
    image = next(image for image in client.images.list() if any(tag.startswith('is.jd.com/') for tag in image.tags))
    env = {item.split('=',1)[0]:'offline-fixture' for item in image.attrs['Config'].get('Env',[])
           if any(word in item.split('=',1)[0].upper() for word in
                  ('KEY','TOKEN','SECRET','PASSWORD','ANTHROPIC','OPENAI','OFOX','HUBROUTER'))}
    env.update(PYTHONDONTWRITEBYTECODE='1',BUN_JSC_useJIT='0')
    container = client.containers.run(image.id,name=f'parallel-runtime-version-lane{lane}',
        entrypoint='',command=['tail','-f','/dev/null'],detach=True,
        mem_limit='128g',nano_cpus=8_000_000_000,network_mode='none',environment=env,
        volumes={'/opt/hint-codex-runtime/python':{'bind':'/opt/python3.12-tmp','mode':'ro'}})
    record = {'lane':lane,'assigned_images':assigned,'model_calls':0,'started_at_unix':time.time()}
    try:
        program = ("import json,platform,subprocess;from pathlib import Path;from importlib.metadata import version;"
            "import claude_agent_sdk;"
            "cli=Path(claude_agent_sdk.__file__).parent/'_bundled/claude';"
            "result=subprocess.run([str(cli),'--version'],capture_output=True,text=True,timeout=90,check=True);"
            "print(json.dumps({'python':platform.python_version(),'sdk':version('claude-agent-sdk'),"
            "'litellm':version('litellm'),'cli_version':result.stdout.strip(),'kernel':platform.release(),"
            "'cpu_max':Path('/sys/fs/cgroup/cpu.max').read_text().strip(),"
            "'memory_max':Path('/sys/fs/cgroup/memory.max').read_text().strip()}))")
        code, output = container.exec_run(['timeout','150',PYTHON,'-c',program])
        assert code == 0, output.decode()
        record['runtime'] = json.loads(output)
        assert record['runtime']['python'] == '3.12.16'
        assert record['runtime']['sdk'] == '0.2.186'
        assert record['runtime']['litellm'] == '1.81.8'
        assert record['runtime']['cli_version'].startswith('2.1.329 ')
        assert record['runtime']['cpu_max'] == '800000 100000'
        assert record['runtime']['memory_max'] == '137438953472'
        program = "import json;from urllib.request import urlopen;print(json.dumps({str(port):json.load(urlopen('http://172.17.0.1:'+str(port)+path,timeout=15)).get('stopped') for port,path in [(8765,'/status'),(8766,'/experiment/status?session=preflight-parallel-lane')]}))"
        output = ssh(lane,'python3 -c '+shlex.quote(program),capture_output=True,text=True).stdout
        record.update(gateway_reachable=True,gateway_status=json.loads(output),
                      ready=all(row['ready'] for row in assigned))
    finally:
        container.remove(force=True)
        client.close()
        record['version_container_removed'] = True
        record['finished_at_unix'] = time.time()
        (OUT/f'lane{lane}_ready.json').write_text(json.dumps(record,indent=2)+'\n')
        print(json.dumps(record),flush=True)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['check','pull'])
    parser.add_argument('--lane',type=int,required=True)
    parser.add_argument('--task')
    args = parser.parse_args()
    result = pull_image(args.lane,args.task) if args.action=='pull' else check(args.lane)
    raise SystemExit(0 if result['ready'] else 1)
