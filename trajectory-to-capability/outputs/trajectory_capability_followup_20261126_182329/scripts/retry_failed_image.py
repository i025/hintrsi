"""Bounded recovery for a real registry rate limit; preserve every preparation failure."""
import argparse
import json
import time
from pathlib import Path
import docker

OUT = Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
parser = argparse.ArgumentParser()
parser.add_argument('task')
args = parser.parse_args()
path = OUT / 'config' / f'image_{args.task}.json'
row = json.loads(path.read_text())
if row['ready']:
    raise RuntimeError('Image is already ready; no download required')
history = OUT / 'evidence/image_preparation'
history.mkdir(exist_ok=True)
prior = history / (args.task + '_attempt01.json')
if prior.exists():
    raise FileExistsError(prior)
prior.write_text(json.dumps(row, indent=2) + '\n')
client = docker.DockerClient(base_url=row['docker_host'], timeout=900)
try:
    for attempt in (2, 3):
        current = {k: v for k, v in row.items() if k not in ('error', 'finished_at', 'ready')}
        current.update(attempt=attempt, started_at=time.time())
        repository = 'public.ecr.aws/d3j8x8q7/swe-bench-202605'
        tag = row['original'].rsplit(':', 1)[1]
        try:
            try:
                image = client.images.get(row['original'])
                current['source'] = 'existing_cache_after_failed_preparation'
            except docker.errors.ImageNotFound:
                with (OUT / 'logs' / f'image_pull_{args.task}_attempt{attempt:02d}.jsonl').open('x') as stream:
                    for event in client.api.pull(repository, tag=tag, stream=True, decode=True):
                        stream.write(json.dumps({'at': time.time(), **event}) + '\n')
                        stream.flush()
                        if event.get('error'):
                            raise RuntimeError(event['error'])
                image = client.images.get(repository + ':' + tag)
                original_repository, original_tag = row['original'].rsplit(':', 1)
                image.tag(original_repository, original_tag)
            current.update(ready=True, image_bytes=image.attrs['Size'])
        except Exception as error:
            current.update(ready=False, error=str(error))
        current['finished_at'] = time.time()
        (history / f'{args.task}_attempt{attempt:02d}.json').write_text(json.dumps(current, indent=2) + '\n')
        path.write_text(json.dumps(current, indent=2) + '\n')
        print(json.dumps(current), flush=True)
        if current['ready']:
            break
        if attempt == 2:
            time.sleep(60)
finally:
    client.close()
