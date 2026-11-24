import subprocess,json,time
from pathlib import Path
D=Path("/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/preflight/parallel_runtime")
rows=[]
for lane in (1,2,4,5):
 print("checking lane",lane,flush=True)
 r=subprocess.run(["/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python","-u","-B",str(D/"check_lanes.py"),"check","--lane",str(lane)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 (D/f"lane{lane}_check.log").write_text(r.stdout)
 rows.append({"lane":lane,"exit_code":r.returncode})
 print(json.dumps(rows[-1]),flush=True)
 if r.returncode:break
(D/"lane_checks_batch.json").write_text(json.dumps({"results":rows,"finished_at_unix":time.time()},indent=2)+"\n")
