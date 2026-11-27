"""Bound the already-started first optional verifier without touching its patch."""
import datetime
import json
import time
from pathlib import Path

import docker

OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
name='capability_hint_development_claude-code-by-agents-recursive-delegation_NoHint'
client=docker.DockerClient(base_url='unix:///srv/lab-disks/disk2/users/xymo/hint-codex-experiments/vm/docker.sock',timeout=20)
matches=[c for c in client.containers.list() if c.labels.get('hint.experiment_name')==name
    and c.attrs['Config']['Image'].startswith('deepswe-verifier-')]
if len(matches)!=1:raise RuntimeError('Expected exactly the existing NoHint verifier')
container=matches[0];created=datetime.datetime.fromisoformat(container.attrs['Created'].replace('Z','+00:00')).timestamp()
record=dict(experiment=name,container_id=container.id,container_name=container.name,
    created_unix=created,evaluation_limit_seconds=600,anchor='Existing container creation; test exec followed setup, exact exec-start timestamp unavailable.',
    detected_at_unix=time.time(),process_observation=container.top(),status='waiting_for_bound',
    reason='CPU-bound Vitest worker; root cause not established; no test or student code inspected/changed.')
path=OUT/'logs/optional_evaluation_timeout_NoHint.json'
path.write_text(json.dumps(record,indent=2)+'\n')
while time.time()<created+600:
    time.sleep(min(30,max(0,created+600-time.time())))
    container.reload()
    if container.status!='running':
        record.update(status='completed_before_external_stop',finished_at_unix=time.time());break
else:
    record.update(stop_requested_at_unix=time.time(),elapsed_since_container_created=time.time()-created,
        process_observation_at_bound=container.top())
    container.stop(timeout=10)
    record.update(status='evaluation_timeout_stopped',stopped_at_unix=time.time())
path.write_text(json.dumps(record,indent=2)+'\n');client.close()
print(json.dumps({'record':str(path),'status':record['status']}),flush=True)
