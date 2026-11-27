import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
PYTHON='/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
def run(p):
    name=p.stem.removesuffix('_prompt')
    return subprocess.run([PYTHON,'-u','-B','work/model_job.py','capability-'+name,str(p),str(OUT/'audit'/f'{name}.md')],check=False).returncode
with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,sorted((OUT/'config').glob('audit_S*_prompt.txt'))))
raise SystemExit(int(any(results)))
