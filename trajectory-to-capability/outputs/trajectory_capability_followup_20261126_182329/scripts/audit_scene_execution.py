"""Link archived attempts to existing files and review actual Blender execution records."""
import csv
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

OUT = Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
BASE = Path('/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender')
PYTHON = '/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
selected_names = {'record.json', 'status.json', 'task.json', 'build.py', 'result.json', 'selected.json'}
rows = list(csv.DictReader((OUT / 'audit/scene_bundle_member_inventory.csv').open()))
trajectory_ids = {r['original_file']: r['source_id'] for r in
    json.loads((OUT / 'config/scene_full_audit_manifest.json').read_text())['files']}
sources = {}
links = []
for row in rows:
    relative = Path(row['member'])
    if relative.name not in selected_names | {'trajectory.jsonl'}:
        continue
    parts = relative.parts
    candidates = [BASE / relative, BASE / 'outputs' / Path(*parts[1:]), BASE / 'archive/scene' / relative]
    path = next((p for p in candidates if p.is_file()), None)
    link = {'bundle_id': row['bundle_id'], 'archive': row['archive'], 'member': row['member'],
        'expanded_file': str(path) if path else None, 'trajectory_source_id': trajectory_ids.get(str(path))}
    links.append(link)
    if path and path.name in selected_names:
        sources.setdefault(str(path), []).append({'archive': row['archive'], 'member': row['member']})
(OUT / 'audit/scene_bundle_expanded_links.json').write_text(json.dumps(links, indent=2) + '\n')
directory = OUT / 'evidence/scene_execution_chunks'
directory.mkdir(exist_ok=True)
reports = OUT / 'audit/scene_execution'
reports.mkdir(exist_ok=True)
manifest_path = OUT / 'config/scene_execution_audit_manifest.json'
if manifest_path.exists():
    raise FileExistsError(manifest_path)
chunks = []
content = ''
labels = []
for index, (path, aliases) in enumerate(sorted(sources.items()), 1):
    raw = Path(path).read_text()
    label = {'source_id': f'X{index:04d}', 'file': path, 'archive_members': aliases,
        'complete': True, 'characters': len(raw), 'lines': len(raw.splitlines())}
    numbered = '\n'.join(f'{i:05d}: {line}' for i, line in enumerate(raw.splitlines(), 1))
    for start in range(0, max(1, len(numbered)), 410000):
        part = numbered[start:start+410000]
        addition = '\nSOURCE ' + json.dumps(label) + f'\nNUMBERED TEXT characters [{start},{start+len(part)}) of {len(numbered)}\n' + part + '\n'
        if content and len(content) + len(addition) > 420000:
            chunks.append((labels, content))
            content = ''
            labels = []
        content += addition
        labels.append(label)
if content:
    chunks.append((labels, content))
manifest = {'created_at': time.time(), 'unique_files': len(sources), 'archive_links': len(links),
    'trajectory_links': sum(r['trajectory_source_id'] is not None for r in links),
    'unmapped_members': [r for r in links if r['expanded_file'] is None],
    'policy': 'Path-provenance mapping to original expanded files, no hashes and no duplicate resource extraction. Archive trajectory members are linked to the complete 360-file audit rather than model-read twice. Full selected Blender programs and execution/acceptance records supplied with line numbers. Images and binary geometry are separate evidence.', 'chunks': []}
for index, (labels, content) in enumerate(chunks, 1):
    name = f'EX{index:03d}'
    packet = directory / (name + '.txt')
    packet.write_text('''Historical Scene actual execution audit only. Output English at most 800 words. Source text is complete across numbered chunks; no image attachments. Cite original expanded file, archive/member provenance, source ID and exact line numbers. Analyze actual generated Blender code, object/part representation, materials and texture operations, pose/camera/light/render settings, execution errors, validation, recorded selection and acceptance. Separate code intent, measured geometry/render metadata, actual successful execution and visual quality. For multi-object/part connections, code coordinates or AABBs do not prove physical contact or image fidelity. Do not treat an available teacher policy as received, or numeric acceptance as independently validated quality. Distinguish technical rendering failures from completed but potentially poor reconstruction. No new code or skill updates.\n''' + content)
    manifest['chunks'].append({'name': name, 'packet': str(packet), 'report': str(reports / (name + '.md')),
        'sources': labels, 'status': 'pending'})
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({'files': len(sources), 'chunks': len(chunks), 'trajectory_links': manifest['trajectory_links'],
    'unmapped': len(manifest['unmapped_members'])}), flush=True)

def run(job):
    code = subprocess.run([PYTHON, '-u', '-B', str(Path(__file__).with_name('model_job.py')),
        'followup-scene-execution-' + job['name'], job['packet'], job['report']],
        stdout=subprocess.DEVNULL, check=False).returncode
    return job, code
with ThreadPoolExecutor(max_workers=2) as pool:
    for job, code in pool.map(run, manifest['chunks']):
        job.update(status='complete' if code == 0 else 'failed', exit_code=code, completed_at=time.time())
        manifest['completed_chunks'] = sum(r['status'] == 'complete' for r in manifest['chunks'])
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
        print(json.dumps({'chunk': job['name'], 'exit_code': code}), flush=True)
manifest.update(finished_at=time.time(), status='complete' if all(r['status']=='complete' for r in manifest['chunks']) else 'some_chunks_failed')
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
