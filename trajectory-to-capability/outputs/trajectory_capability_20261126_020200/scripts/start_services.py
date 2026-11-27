import json
import os
import socket
import subprocess
import time
from pathlib import Path

OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
PYTHON='/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
env=dict(os.environ, CODEX_HOME=str(Path.cwd()/'work/cli_home'), PYTHONDONTWRITEBYTECODE='1')
for n in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):env.pop(n,None)
rows=[]
for name,script,port in [('bridge','codex_cli_bridge.py',8765),('progress','teacher_progress.py',8766)]:
    with socket.socket() as s:
        s.settimeout(1)
        if s.connect_ex(('127.0.0.1',port))==0:raise RuntimeError(f'Port {port} is occupied; preserving existing service')
    cmd=[PYTHON,'-u','-B',str(OUT/'source'/script),'--run_dir',str(OUT/'logs'/name),'--port',str(port)]
    with (OUT/'logs'/f'{name}.log').open('xb') as f:
        p=subprocess.Popen(cmd,cwd=OUT/'source',env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
    rows.append({'name':name,'pid':p.pid,'command':cmd,'started_at':time.time()})
(OUT/'config/services.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows))
