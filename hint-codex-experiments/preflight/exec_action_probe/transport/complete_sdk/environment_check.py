"""Verify network namespace rules and teacher read-only mounts without a model."""
import errno
import json
import time
from pathlib import Path

import docker
import pyarrow.parquet as pq
from driver import ROOT, HERE, PYTHON, create_container, restrict_network

out = HERE / 'environment_check'
out.mkdir()
client = docker.DockerClient(base_url='unix://' + str(ROOT / 'vm-lane5/docker.sock'), timeout=120)
row = next(row for row in pq.read_table(ROOT.parent / 'hint-baseline-run/data/deep_swe_tasks.parquet').to_pylist() if row['instance_id'] == 'sqlfmt-create-table-ddl-formatting')
image = client.images.get(row['image_name'])
container = create_container(client, image, 'codex-exec-environment-check', 'preflight_exec_environment_check')
result = {'passed': False, 'real_model_calls': 0, 'started_at_unix': time.time(), 'container': container.id, 'same_image_as_B': image.id}
try:
    result['network'] = restrict_network(container, ports=(8765, 8766))
    command = 'set -e; rm -rf /app; mkdir -p /app; touch /app/fixture.txt /tmp/golden_diff.diff; mount --bind /app /app; mount -o remount,bind,ro /app; mount --bind /tmp/golden_diff.diff /tmp/golden_diff.diff; mount -o remount,bind,ro /tmp/golden_diff.diff'
    code, output = container.exec_run(['bash', '-c', command])
    (out / 'mount.log').write_bytes(output)
    assert code == 0, output
    program = """import errno,json,os,urllib.request
checks={}
for path in ['/app/fixture.txt','/tmp/golden_diff.diff']:
 try:
  fd=os.open(path,os.O_WRONLY);os.close(fd);checks[path]='writable'
 except OSError as exc:
  assert exc.errno==errno.EROFS,(path,exc.errno)
  checks[path]='EROFS'
with urllib.request.urlopen('http://172.17.0.1:8765/health',timeout=10) as response:
 health=json.load(response)
print(json.dumps({'readonly_checks':checks,'gateway_health':health}))
"""
    code, output = container.exec_run([PYTHON, '-c', program])
    (out / 'checks.log').write_bytes(output)
    assert code == 0, output
    result.update(json.loads(output))
    result['passed'] = True
finally:
    container.remove(force=True)
    client.close()
    result.update(container_removed=True, finished_at_unix=time.time())
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result), flush=True)
