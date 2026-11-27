"""Reuse each idle lane's cache before preparing the pre-saved new task images."""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import docker

OUT = Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
split = json.loads((OUT / 'config/task_split.json').read_text())
tasks = {r['instance_id']: r for r in json.loads((OUT / 'config/new_task_public_metadata.json').read_text())}

def prepare(lane):
    for _ in range(240):
        lanes = json.loads((OUT / 'config/runtime_resume.json').read_text())['lanes']
        runtime = next((r for r in lanes if r['lane'] == lane and r['status'] == 'ready'), None)
        if runtime:
            break
        time.sleep(5)
    else:
        raise RuntimeError(f'Lane {lane} is not ready')
    client = docker.DockerClient(base_url=runtime['docker_host'], timeout=900)
    order = split['development'] + split['selection'] + split['test']
    try:
        for task in order:
            if split['lanes'][task] != lane:
                continue
            path = OUT / 'config' / f'image_{task}.json'
            if path.exists():
                continue
            if any(not c.labels.get('hint.experiment_name', '').startswith('capability_followup_')
                    for c in client.containers.list()):
                raise RuntimeError(f'Unrelated container on lane {lane}; preserve it')
            original = tasks[task]['image_name']
            row = {'task': task, 'lane': lane, 'docker_host': runtime['docker_host'],
                'original': original, 'started_at': time.time()}
            try:
                try:
                    image = client.images.get(original)
                    row['source'] = 'existing_cache'
                except docker.errors.ImageNotFound:
                    repository = 'public.ecr.aws/d3j8x8q7/swe-bench-202605'
                    tag = original.rsplit(':', 1)[1]
                    row['source'] = repository + ':' + tag
                    with (OUT / 'logs' / f'image_pull_{task}.jsonl').open('x') as stream:
                        for event in client.api.pull(repository, tag=tag, stream=True, decode=True):
                            stream.write(json.dumps({'at': time.time(), **event}) + '\n')
                            stream.flush()
                            if event.get('error'):
                                raise RuntimeError(event['error'])
                    image = client.images.get(repository + ':' + tag)
                    name, tag = original.rsplit(':', 1)
                    image.tag(name, tag)
                row.update(ready=True, image_bytes=image.attrs['Size'])
            except Exception as error:
                row.update(ready=False, error=str(error))
            row['finished_at'] = time.time()
            path.write_text(json.dumps(row, indent=2) + '\n')
            print(json.dumps(row), flush=True)
            if not row['ready']:
                break
    finally:
        client.close()

with ThreadPoolExecutor(max_workers=2) as pool:
    list(pool.map(prepare, [1, 2, 0]))
