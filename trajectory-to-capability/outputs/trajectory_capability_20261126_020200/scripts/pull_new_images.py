import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import docker
import pyarrow.parquet as pq

HOME=Path('/srv/lab-disks/disk2/users/xymo')
OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
table={x['instance_id']:x for x in pq.read_table(HOME/'hint-baseline-run/data/deep_swe_tasks.parquet',columns=['instance_id','image_name']).to_pylist()}
tasks=[('superjson-error-stack-serialization',1),('tomlkit-toml-table-converters',2),('httpx-deterministic-cookie-store',3)]
def pull(item):
    task,lane=item
    directory=HOME/f'hint-codex-experiments/vm-lane{lane}'
    client=docker.DockerClient(base_url='unix://'+str(directory/'docker.sock'),timeout=900)
    original=table[task]['image_name']
    record={'task':task,'lane':lane,'started_at':time.time(),'original':original}
    try:
        if client.containers.list():raise RuntimeError('Lane occupied; preparation aborted')
        try:
            image=client.images.get(original);record['source']='existing_cache'
        except docker.errors.ImageNotFound:
            repo='public.ecr.aws/d3j8x8q7/swe-bench-202605';tag=original.rsplit(':',1)[1]
            record['source']=repo+':'+tag
            with (OUT/'logs'/f'image_pull_{lane}.jsonl').open('x') as f:
                for event in client.api.pull(repo,tag=tag,stream=True,decode=True):
                    f.write(json.dumps({'at':time.time(),**event})+'\n');f.flush()
                    if event.get('error'):raise RuntimeError(event['error'])
            image=client.images.get(repo+':'+tag)
            repo,tag=original.rsplit(':',1);image.tag(repo,tag)
        record.update(ready=True,image_bytes=image.attrs['Size'])
    except Exception as e:record.update(ready=False,error=str(e))
    finally:
        client.close();record['finished_at']=time.time()
        (OUT/'config'/f'image_{task}.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record),flush=True)
    return record
with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(pull,tasks))
