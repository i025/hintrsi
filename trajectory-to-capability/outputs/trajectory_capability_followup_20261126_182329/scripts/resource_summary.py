"""Summarize existing30-second observations; these are sampled, not exact peaks."""
import csv
import datetime
import json
from pathlib import Path

OUT=Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
samples=[];containers={}
for line in (OUT/'logs/monitor.jsonl').open():
    d=json.loads(line);samples.append(d)
    for c in d.get('containers',[]):
        key=(c['lane'],c['name'])
        row=containers.setdefault(key,{'lane':c['lane'],'container':c['name'],'experiment':c['experiment'],
            'first_observed_unix':d['timestamp'],'last_observed_unix':d['timestamp'],
            'peak_observed_memory_bytes':0,'last_observed_cumulative_cpu_seconds':0})
        row['last_observed_unix']=d['timestamp']
        row['peak_observed_memory_bytes']=max(row['peak_observed_memory_bytes'],c.get('memory_bytes') or 0)
        row['last_observed_cumulative_cpu_seconds']=max(row['last_observed_cumulative_cpu_seconds'],(c.get('cpu_total_ns') or 0)/1e9)
times=sorted({d['timestamp'] for d in samples})
closure='Three previously stopped original VM overlays were resumed for this follow-up and will be stopped at closure.'
if (OUT/'logs/followup_cleanup.json').exists():
    cleanup=json.loads((OUT/'logs/followup_cleanup.json').read_text())
    if not cleanup['remaining_owned_processes']:
        closure='The three resumed VM processes and saved owned services were stopped; see logs/followup_cleanup.json.'
summary={'samples':len(samples),'first_observation_utc':datetime.datetime.fromtimestamp(min(times),datetime.timezone.utc).isoformat(),
    'last_observation_utc':datetime.datetime.fromtimestamp(max(times),datetime.timezone.utc).isoformat(),
    'maximum_gap_seconds':max(b-a for a,b in zip(times,times[1:])),
    'peak_observed_simultaneous_own_containers':max(len(d.get('containers',[])) for d in samples),
    'peak_observed_sum_container_memory_bytes':max(sum(c.get('memory_bytes') or 0 for c in d.get('containers',[])) for d in samples),
    'unique_observed_own_containers':len(containers),
    'host_loadavg_1min_range':[min(d['loadavg'][0] for d in samples),max(d['loadavg'][0] for d in samples)],
    'scope':'Only containers with exact saved follow-up experiment labels.30-second sampling can miss brief peaks/tails; the recorded operator-interruption gap is retained. Host load includes other users and is not attributed to this experiment. '+closure+' Overlays/images are preserved. No GPU used.'}
with (OUT/'results/resource_observations.csv').open('w',newline='') as f:
    rows=list(containers.values());writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
(OUT/'results/resource_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary))
