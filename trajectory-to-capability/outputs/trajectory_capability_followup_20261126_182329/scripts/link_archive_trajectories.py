"""Identify archive trajectory copies by direct content comparison, without hashes."""
import csv
import json
import re
import tarfile
import time
from pathlib import Path

OUT = Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
links = { (r['archive'],r['member']):r for r in json.loads((OUT / 'audit/scene_bundle_expanded_links.json').read_text())
    if Path(r['member']).name=='trajectory.jsonl'}
archives = list(dict.fromkeys(r['archive'] for r in links.values()))
record = {'started_at':time.time(), 'purpose':'Avoid counting or model-reviewing archive copies as independent trajectories. Full archived trajectory payload is read in place and compared directly to its mapped original text; no hash, checksum or signature system.', 'records':[]}
directory = OUT / 'evidence/archive_trajectory_differences'
for archive_path in archives:
    with tarfile.open(archive_path,'r|gz') as archive:
        for member in archive:
            link=links.get((archive_path,member.name))
            if link is None:
                continue
            payload=archive.extractfile(member).read()
            same=payload==Path(link['expanded_file']).read_bytes()
            row={**link,'archive_payload_bytes':len(payload),'same_full_content_direct_comparison':same}
            if not same:
                directory.mkdir(exist_ok=True)
                target=directory/f"{link['bundle_id']}_{len(record['records'])+1:03d}.jsonl"
                target.write_bytes(payload)
                row['different_archived_payload']=str(target)
            record['records'].append(row)
    (OUT / 'config/scene_archive_trajectory_links.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'archive':Path(archive_path).name,'read_trajectory_members':len(record['records']),
        'different_payloads':sum(not r['same_full_content_direct_comparison'] for r in record['records'])}),flush=True)
record.update(finished_at=time.time(),status='complete',trajectory_members=len(record['records']),
    identical_copies=sum(r['same_full_content_direct_comparison'] for r in record['records']))
# The original archive exporter replaces paths/accounts with documented literals.
# Reapply only those existing export rules to identify relocated copies faithfully.
counts={}
remaining=[]
for row in record['records']:
    suffix=str(Path(*Path(row['member']).parts[2:]))
    source=Path(str(Path(row['expanded_file']))[:-len(suffix)].rstrip('/'))
    home=source.parents[5]
    value=Path(row['expanded_file']).read_text()
    replacements=[(str(source),'__EXPERIMENT_ROOT__'),
        (str(source.parents[2]/'files-pasted-by-the-user-sceneevolve'),'__SCENEEVOLVE_REPRO__'),
        (str(home/'projects/BlenderWorld'),'__BLENDERWORLD_ROOT__'),
        (str(home/'projects/e-harness/datasets/web_scenes'),'__COMMONS_DATA_ROOT__'),
        (str(home),'__SERVER_USER_ROOT__'),('/home/'+home.name,'__SERVER_USER_ROOT__')]
    for old,new in replacements:
        value=value.replace(old,new)
    value=re.sub(r'\b'+re.escape(home.name)+r'\b','SERVER_USER',value)
    same=row['same_full_content_direct_comparison'] or value==Path(row['different_archived_payload']).read_text()
    row['same_after_existing_archive_public_path_rules']=same
    counts[same]=counts.get(same,0)+1
    if not same:
        remaining.append({'member':row['member'],'payload':row['different_archived_payload']})
record['original_export_path_rule_comparison']={
    'source_script':'/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/work/scene_archive/prepare_archive.py:55',
    'rules':'Exact six existing literal path substitutions and original server account word replacement. No state, behavior, output, event order or code normalization. No unused-reserve identifier rule applied.',
    'counts':counts,'unexplained_differences':remaining}
(OUT / 'config/scene_archive_trajectory_links.json').write_text(json.dumps(record,indent=2)+'\n')
