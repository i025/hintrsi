"""Record actual resident memory of the saved VM and service processes."""
import datetime
import json
import os
from pathlib import Path

OUT=Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
runtime=json.loads((OUT/'config/runtime_resume.json').read_text())
processes=[{'name':'VM_lane'+str(l['lane']),'pid':l['vm_pid']} for l in runtime['lanes']]
processes+=json.loads((OUT/'config/services.json').read_text())
record={'at_beijing':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
    'host_logical_CPUs':os.cpu_count(),'processes':[],
    'scope':'Point observations of exact saved processes, not historical peaks. VM resident memory includes guest containers; do not add it to guest container usage.'}
for item in processes:
    pid=item['pid'];path=Path(f'/proc/{pid}')
    if not path.exists():raise RuntimeError('Saved process is not visible; use host execution or inspect '+str(pid))
    if str(OUT).encode() not in (path/'cmdline').read_bytes():raise RuntimeError('Saved process identity changed')
    values={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in (path/'status').read_text().splitlines() if line.startswith(('State:','VmRSS:','VmSize:','Threads:'))}
    raw=(path/'stat').read_text();fields=raw[raw.rfind(')')+2:].split()
    values.update(cumulative_CPU_seconds=(int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK'),
        nice=os.getpriority(os.PRIO_PROCESS,pid))
    record['processes'].append({'name':item['name'],'pid':pid,**values})
with (OUT/'logs/host_resource_snapshots.jsonl').open('a') as stream:stream.write(json.dumps(record)+'\n')
print(json.dumps(record))
