import json
import os
import subprocess
import time
from pathlib import Path

root = Path('/srv/lab-disks/disk2/users/xymo/hint-codex-experiments')
python = root.parent / 'hint-baseline-run/env/bin/python'
services = []
for name, script, port in [('bridge', 'codex_cli_bridge.py', '8765'), ('progress', 'teacher_progress.py', '8766')]:
    run_dir = root / 'logs' / name
    run_dir.mkdir(parents=True, exist_ok=True)
    command = [str(python), '-B', str(root / 'source' / script), '--run_dir', str(run_dir), '--port', port]
    with (root / 'logs' / (name + '.log')).open('ab') as stream:
        process = subprocess.Popen(command, cwd=root / 'source', stdout=stream, stderr=subprocess.STDOUT,
                                   start_new_session=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    services.append({'name': name, 'pid': process.pid, 'command': command})
(root / 'logs/services.json').write_text(json.dumps({'started_at': time.time(), 'services': services}, indent=2) + '\n')
print(json.dumps(services))
