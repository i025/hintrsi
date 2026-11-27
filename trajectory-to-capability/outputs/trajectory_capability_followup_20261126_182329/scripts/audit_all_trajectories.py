"""Review complete historical text in explicit chunks using the existing CLI bridge."""
import argparse
import csv
import gzip
import json
import subprocess
import time
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

OUT = Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
OLD = OUT.parent / 'trajectory_capability_20261126_020200'
PYTHON = '/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
LIMIT = 420000
parser = argparse.ArgumentParser()
parser.add_argument('--project', choices=['hintrsi', 'scene', 'scene_additional'], required=True)
parser.add_argument('--retry_failed', action='store_true')
args = parser.parse_args()
destination = OUT / 'audit' / args.project
destination.mkdir(exist_ok=True)
packets = OUT / 'evidence' / (args.project + '_full_chunks')
packets.mkdir(exist_ok=True)
manifest_path = OUT / 'config' / (args.project + '_full_audit_manifest.json')

def text(path):
    return gzip.open(path, 'rt').read() if path.suffix == '.gz' else path.read_text()

def units_for(path):
    raw = text(path)
    try:
        data = json.loads(raw)
    except ValueError:
        # Preserve every JSONL line and its original one-based line number.
        return [('line:' + str(i), line) for i, line in enumerate(raw.splitlines(keepends=True), 1)]
    if isinstance(data, dict) and isinstance(data.get('trajectories'), dict):
        units = [('top_level_metadata', json.dumps({k: v for k, v in data.items()
            if k != 'trajectories'}, ensure_ascii=False))]
        for agent, trace in data['trajectories'].items():
            events = trace.splitlines() if isinstance(trace, str) else trace
            if not isinstance(events, list):
                events = [events]
            for number, event in enumerate(events, 1):
                units.append((f'{agent}:event:{number}', event if isinstance(event, str)
                    else json.dumps(event, ensure_ascii=False)))
        return units
    return [('complete_document', raw)]

if not manifest_path.exists():
    if args.project == 'hintrsi':
        rows = [r for r in csv.DictReader((OLD / 'trajectory_inventory.csv').open())
            if r['project'] == 'hintrsi']
    elif args.project=='scene':
        rows = [r for r in csv.DictReader((OLD / 'audit/scene_artifact_inventory.csv').open())
            if r['kind'] == 'student_trajectory']
    else:
        rows=json.loads((OUT/'config/scene_additional_trace_inventory.json').read_text())
    records = []
    for number, row in enumerate(rows, 1):
        path = Path(row['path'])
        source_id = {'hintrsi':'H','scene':'S','scene_additional':'A'}[args.project] + f'{number:04d}'
        units = units_for(path)
        chunks = []
        current = ''
        current_labels = []
        for label, value in units:
            # Large individual observations retain every character, with offsets.
            for start in range(0, max(1, len(value)), LIMIT - 1000):
                part = value[start:start + LIMIT - 1000]
                tag = f'{label}, characters [{start},{start + len(part)}) of {len(value)}'
                addition = '\n--- ' + tag + ' ---\n' + part + '\n'
                if current and len(current) + len(addition) > LIMIT:
                    chunks.append((current_labels, current))
                    current = ''
                    current_labels = []
                current += addition
                current_labels.append(tag)
        if current:
            chunks.append((current_labels, current))
        chunk_records = []
        for index, (labels, content) in enumerate(chunks, 1):
            name = f'{source_id}_chunk{index:03d}'
            packet = packets / (name + '.txt')
            header = {'source_id': source_id, 'original_file': str(path), 'kind': row['kind'],
                'task': row.get('task'), 'group': row.get('group'), 'round': row.get('round'),
                'file_inventory_metadata': row, 'chunk': index, 'chunks': len(chunks),
                'coverage': 'All decoded values are included without field/prefix truncation across chunks. A chunk may start/end inside an individual tool observation; offsets identify it. Other chunks are not visible to this call.'}
            instructions = '''Historical audit only. Do not generate benchmark answers or new knowledge libraries. Your analysis will not enter any student or extraction request. Output English, at most 600 words. Cite source ID, original file, exact agent/event or JSONL line, and character offsets for split observations. Treat inferred semantic goals separately from observed operations/results. Describe task or scene goal, actual changes, visible validation, actual teacher input and evidence of adoption (availability alone is not receipt), autonomous exploration, formal success/partial correctness/algorithm failure/empty patch/technical interruption/unknown outcome, transferable vs task-specific lessons and unresolved hypotheses. Do not infer unseen chunks or images. A score/name/teacher claim is not independent visual or geometric verification. For Scene explicitly check evidence of multiple objects, materials/textures, part connection, pose, camera/light/render issues; teacher detection, diagnosis, proposed updates and actual execution are distinct. If this is a teacher-only trace, identify its role and constraints without inventing student receipt. Return a concise evidence table and concrete uncertainty.\n'''
            packet.write_text(instructions + json.dumps(header, ensure_ascii=False) + '\nFULL OBSERVATIONS:\n' + content)
            assert packet.stat().st_size < 1000000, packet
            chunk_records.append({'name': name, 'packet': str(packet), 'labels': labels,
                'characters': len(content), 'report': str(destination / (name + '.md')), 'status': 'pending'})
        records.append({'source_id': source_id, 'original_file': str(path), 'kind': row['kind'],
            'original_bytes': path.stat().st_size, 'units': len(units), 'chunks': chunk_records})
    manifest = {'project': args.project, 'created_at': time.time(), 'policy': 'Full decoded content; no clipping, no hidden omissions, no hash system. Original files remain authoritative. Full file review requires every chunk job complete.', 'files': records}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
else:
    manifest = json.loads(manifest_path.read_text())

if args.retry_failed:
    shutil.copy2(manifest_path, manifest_path.with_name(manifest_path.stem+f'_before_retry_{int(time.time())}.json'))
    for row in manifest['files']:
        for chunk in row['chunks']:
            if chunk['status']!='failed':continue
            attempt=len(chunk.setdefault('previous_failed_attempts',[]))+1
            record={k:chunk.get(k) for k in ('status','exit_code','completed_at','job_summary')}
            job=Path(chunk['report']+'.job.json')
            if job.exists():
                saved=job.with_name(job.name+f'.failed_attempt{attempt:02d}')
                shutil.copy2(job,saved);record['preserved_job']=str(saved)
            chunk['previous_failed_attempts'].append(record)
            chunk.update(status='pending',invocation_suffix=f'-recovery{attempt:02d}')
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
jobs = [c for r in manifest['files'] for c in r['chunks'] if c['status'] == 'pending']
print(json.dumps({'project': args.project, 'files': len(manifest['files']), 'pending_calls': len(jobs)}), flush=True)

stop_after_error=threading.Event()
def run(chunk):
    if stop_after_error.is_set():return chunk,None,'Deferred after another audit request failed; no model call.'
    completed = subprocess.run([PYTHON, '-u', '-B', str(Path(__file__).with_name('model_job.py')),
        'followup-audit-' + chunk['name']+chunk.get('invocation_suffix',''), chunk['packet'], chunk['report']], check=False,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if completed.returncode:stop_after_error.set()
    return chunk, completed.returncode, completed.stdout[-1000:]

with ThreadPoolExecutor(max_workers=2) as pool:
    for chunk, code, output in pool.map(run, jobs):
        if code is None:continue
        chunk.update(status='complete' if code == 0 else 'failed', exit_code=code,
            completed_at=time.time(), job_summary=output)
        manifest['completed_chunks'] = sum(c['status'] == 'complete' for r in manifest['files'] for c in r['chunks'])
        manifest['complete_files'] = sum(all(c['status'] == 'complete' for c in r['chunks']) for r in manifest['files'])
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'project': args.project, 'job': chunk['name'], 'exit_code': code,
            'complete_files': manifest['complete_files'], 'completed_chunks': manifest['completed_chunks']}), flush=True)
manifest['finished_at'] = time.time()
manifest['status'] = 'complete' if all(c['status'] == 'complete' for r in manifest['files'] for c in r['chunks']) else 'some_chunks_failed'
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
