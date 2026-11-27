"""Index all existing bundle members and audit selected full control records in place."""
import csv
import json
import subprocess
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

OUT = Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
OLD = OUT.parent / 'trajectory_capability_20261126_020200'
PYTHON = '/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
directory = OUT / 'evidence/scene_bundle_controls'
directory.mkdir(exist_ok=True)
reports = OUT / 'audit/scene_bundles'
reports.mkdir(exist_ok=True)
manifest_path = OUT / 'config/scene_bundle_audit_manifest.json'
if manifest_path.exists():
    raise FileExistsError(manifest_path)
bundles = list(csv.DictReader((OLD / 'audit/scene_bundles.csv').open()))
names = {'meta.py', 'policy.py', 'proposal_result.json', 'diagnostic_observations.json',
    'meta_execution.json', 'evidence_projection.json', 'acceptance.json', 'selection.json',
    'candidate_acceptance.json', 'regression_report.json', 'state.json', 'summary.json',
    'final_summary.json', 'stage_events.jsonl', 'candidate.json', 'proposal.json',
    'h.json', 'm.json', 'H.json', 'M.json', 'scores.csv'}
manifest = {'started_at': time.time(), 'policy': 'Every tar member indexed. Only explicitly named control/code/acceptance records are read and model-audited in full; image/blend/large geometry contents remain separately indexed. No repeated archive extraction or new render.', 'bundles': []}
jobs = []
with (OUT / 'audit/scene_bundle_member_inventory.csv').open('w') as stream:
    writer = csv.DictWriter(stream, fieldnames=['bundle_id', 'archive', 'member', 'bytes', 'type', 'control_selected'])
    writer.writeheader()
    for number, bundle in enumerate(bundles, 1):
        identifier = f'B{number:02d}'
        row = {'bundle_id': identifier, 'archive': bundle['path'], 'members': 0,
            'selected_controls': [], 'chunks': [], 'status': 'indexing'}
        current = ''
        labels = []
        chunks = []
        with tarfile.open(bundle['path'], 'r|gz') as archive:
            for member in archive:
                selected = member.isfile() and Path(member.name).name in names
                writer.writerow({'bundle_id': identifier, 'archive': bundle['path'],
                    'member': member.name, 'bytes': member.size, 'type': member.type.decode(errors='replace'),
                    'control_selected': selected})
                row['members'] += 1
                if not selected:
                    continue
                raw = archive.extractfile(member).read().decode('utf-8', errors='replace')
                row['selected_controls'].append({'member': member.name, 'bytes': member.size,
                    'characters': len(raw), 'complete': True})
                for start in range(0, max(1, len(raw)), 410000):
                    part = raw[start:start + 410000]
                    label = f'{identifier} {member.name} characters [{start},{start+len(part)}) of {len(raw)}'
                    addition = '\nSOURCE ' + label + '\n' + part + '\n'
                    if current and len(current) + len(addition) > 420000:
                        chunks.append((labels, current))
                        current = ''
                        labels = []
                    current += addition
                    labels.append(label)
        if current:
            chunks.append((labels, current))
        for index, (labels, content) in enumerate(chunks, 1):
            name = identifier + f'_chunk{index:03d}'
            packet = directory / (name + '.txt')
            packet.write_text('''Read-only historical Scene RSI archive audit. Output English at most 750 words. You receive complete selected control/program/teacher/candidate-acceptance records, not the entire archive. Cite original archive and member paths plus exact keys/line numbers/character ranges. Distinguish teacher problem detection, diagnostic hypothesis, proposed H/M/code update, actual student mechanism execution and candidate acceptance. Examine evidence about multi-object coverage, material/texture, part connections, pose, camera/light/render. Identify technical versus quality failures, acceptance rules and whether records actually substantiate them. Do not infer image appearance, physical contact or unseen execution from code or agent claims. Separate observations and hypotheses. No new experiments, solver answers or skill updates.\n''' + json.dumps({'archive': bundle['path'], 'bundle_id': identifier,
                'chunk': index, 'chunks': len(chunks), 'member_inventory': str(OUT / 'audit/scene_bundle_member_inventory.csv')}) + '\n' + content)
            job = {'name': name, 'packet': str(packet), 'report': str(reports / (name + '.md')),
                'labels': labels, 'status': 'pending'}
            row['chunks'].append(job)
            jobs.append(job)
        row['status'] = 'indexed_controls_pending'
        manifest['bundles'].append(row)
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
        stream.flush()
        print(json.dumps({'bundle': identifier, 'members': row['members'],
            'controls': len(row['selected_controls']), 'model_chunks': len(row['chunks'])}), flush=True)

def run(job):
    result = subprocess.run([PYTHON, '-u', '-B', str(Path(__file__).with_name('model_job.py')),
        'followup-bundle-' + job['name'], job['packet'], job['report']],
        capture_output=True, text=True, check=False)
    return job, result.returncode, result.stdout[-1000:]

with ThreadPoolExecutor(max_workers=2) as pool:
    for job, code, output in pool.map(run, jobs):
        job.update(status='complete' if code == 0 else 'failed', exit_code=code,
            job_summary=output, completed_at=time.time())
        manifest['completed_chunks'] = sum(c['status'] == 'complete' for r in manifest['bundles'] for c in r['chunks'])
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
        print(json.dumps({'chunk': job['name'], 'exit_code': code}), flush=True)
manifest.update(finished_at=time.time(), status='complete' if all(c['status'] == 'complete' for r in manifest['bundles'] for c in r['chunks']) else 'some_chunks_failed')
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
