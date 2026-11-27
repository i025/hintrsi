"""Synthesize only fully reviewed historical groups, preserving chunk provenance."""
import argparse
import csv
import json
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

OUT = Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
OLD = OUT.parent / 'trajectory_capability_20261126_020200'
PYTHON = '/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
parser = argparse.ArgumentParser()
parser.add_argument('--project', choices=['hintrsi','scene'], required=True)
args = parser.parse_args()
manifest = json.loads((OUT / 'config' / (args.project + '_full_audit_manifest.json')).read_text())
index = {r['path']: r for r in csv.DictReader((OLD / 'trajectory_inventory.csv').open()) if r['project']=='hintrsi'}
groups = defaultdict(list)
for row in manifest['files']:
    path = Path(row['original_file'])
    if args.project == 'hintrsi':
        group = index[row['original_file']]['task'] or 'unassigned_preflight_or_teacher'
    else:
        version = next((p for p in path.parts if p.startswith('scene_rsi_')), 'other_scene')
        tail = path.parts[path.parts.index(version)+1:] if version in path.parts else path.parts
        cohort = 'other'
        if 'results' in tail:
            pos = tail.index('results')
            cohort = tail[pos+1] if pos+1<len(tail) else 'results'
        elif tail:
            cohort = tail[0]
        group = version + '__' + cohort
    groups[group].append(row)
directory = OUT / 'audit' / (args.project + '_groups')
directory.mkdir(exist_ok=True)
jobs = []
for group, rows in sorted(groups.items()):
    if not all(c['status']=='complete' for r in rows for c in r['chunks']):
        continue
    pieces = []
    for row in rows:
        metadata = {'source_id':row['source_id'], 'original_file':row['original_file'],
            'kind':row['kind'], 'original_bytes':row['original_bytes'], 'units':row['units'],
            'inventory':index.get(row['original_file'])}
        text = json.dumps(metadata,ensure_ascii=False) + '\n'
        for chunk in row['chunks']:
            text += '\nFULL-OBSERVATION AUDIT REPORT '+chunk['report']+'\n'+Path(chunk['report']).read_text()+'\n'
        pieces.append(text)
    batches = []
    current = ''
    for piece in pieces:
        if current and len(current)+len(piece)>580000:
            batches.append(current)
            current = ''
        current += piece
    if current:
        batches.append(current)
    for number, content in enumerate(batches,1):
        name = group.replace('/', '_') + f'_part{number:02d}'
        output = directory / (name+'.md')
        if output.exists():
            continue
        prompt = OUT / 'config' / ('aggregate_'+args.project+'_'+name+'_prompt.txt')
        prompt.write_text('''Historical evidence synthesis, English at most 1800 words. All source files in this group were supplied completely across explicit model-reviewed chunks; this input contains their audit reports and inventory, not raw source again. Cite original source IDs, paths and exact event/line IDs already supported in the reports; do not fabricate a missing detail. Compare actual successful, failed, partial and interrupted attempts; distinguish empty patches, permission/branch/CLI stops and algorithmic behavior. For teacher roles and Scene, distinguish advice availability, actual receipt, diagnosis, executed update, validation/acceptance and independently observed quality. Identify transferable constraints, task-specific facts and unverified hypotheses, with evidence for adoption or absence, and counterexamples to overgeneralization. File counts include copies, not independent trials. Missing formal scores are unknown; old model cost cannot be recovered from absence. Do not generate new solutions, skills, Test feedback or causal superiority claims. This report remains audit-only and never enters capability generation. Include an evidence matrix and coverage statement for this group/batch.\n''' + json.dumps({'project':args.project,'group':group,'batch':number,'batches':len(batches),'group_files':len(rows)},ensure_ascii=False)+'\n'+content)
        assert len(prompt.read_text())<=700000
        jobs.append((name,prompt,output))
print(json.dumps({'project':args.project,'complete_groups':sum(all(c['status']=='complete' for r in rows for c in r['chunks']) for rows in groups.values()),'total_groups':len(groups),'new_jobs':len(jobs)}),flush=True)

def run(job):
    name,prompt,output=job
    return subprocess.run([PYTHON,'-u','-B',str(Path(__file__).with_name('model_job.py')),
        'followup-group-'+args.project+'-'+name,str(prompt),str(output)],check=False).returncode
with ThreadPoolExecutor(max_workers=2) as pool:
    codes=list(pool.map(run,jobs))
print(json.dumps({'project':args.project,'failed':sum(bool(c) for c in codes)}),flush=True)
