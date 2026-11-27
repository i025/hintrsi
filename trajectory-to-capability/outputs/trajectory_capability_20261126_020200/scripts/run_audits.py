import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
PYTHON='/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
def audit(p):
    name=p.stem.removesuffix('_prompt')
    command=[PYTHON,'-u','-B','work/model_job.py','capability-'+name,str(p),str(OUT/'audit'/f'{name}.md')]
    return subprocess.run(command,check=False).returncode
with ThreadPoolExecutor(max_workers=2) as pool:
    results=list(pool.map(audit,sorted((OUT/'config').glob('audit_D*_prompt.txt'))))
raise SystemExit(int(any(results)))
