"""Focused explicit-eligibility fixtures; known labels are not research reviews."""
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[4]
BASE = Path(__file__).resolve().parent
V1 = BASE.parent / 'projection_metrics'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'analysis'))
from harness.isolation import command
from evaluate_capability_acquisition import write

(BASE / 'unused_model_socket').touch()
scenes, reviews = [], []
for index in range(1, 7):
    scene_id = 'A-T' + str(index).zfill(2)
    run = BASE / 'runs' / (scene_id + '-A0')
    source = V1 / 'runs' / ('A-T02-A0' if index == 2 else 'A-T01-A0')
    shutil.copytree(source / 'workspace', run / 'workspace')
    for name in ('home', 'capture', 'tmp', 'inputs'):
        (run / name).mkdir(parents=True, exist_ok=True)
    write(run / 'inputs/session.json', {})
    write(run / 'status.json', {'status': 'completed', 'synthetic_fixture': True})
    write(run / 'sdk_command.json', command(run, BASE / 'unused_model_socket'))
    caveat = 'Texture and shape differ; no mask validation has occurred.' if index == 2 else 'Extent and occlusion differ; hidden feet are unknown.'
    proposal = {'gt_instance_ids': [1], 'gt_semantic_label': 'known_synthetic_left_cube',
                'student_object_names': ['left'], 'confidence': 'low' if index == 4 else 'high',
                'basis': ['Known synthetic object construction; not a model or human research annotation.'],
                'ambiguity': [caveat], 'orientation_identifiability': 'No 3D angle alignment is asserted.'}
    write(BASE / 'acquisition_reviews/technical' / run.name / 'workspace/technical_annotation.json',
          {'run_id': run.name, 'scene_id': scene_id, 'synthetic_fixture': True,
           'semantic_correspondence': [proposal]})
    eligibility = {'mapping_index': 0, 'measurement_eligible': False if index == 3 else None if index == 6 else True,
                   'identity_ambiguity': ['The entity assignment is unresolved.'] if index == 3 else [],
                   'non_identity_limits': [caveat], 'basis': ['Synthetic known identity fixture, not an actual SDK comparison.'],
                   'reason': 'An identity decision is separate from appearance and visibility limitations.'}
    reviews.append({'run_id': run.name, 'mappings': [] if index == 5 else [eligibility]})
    gt = V1 / 'private_fixture_gt'
    scenes.append({'id': scene_id, 'directory': str(gt), 'reference': str(gt / 'color.png')})
write(BASE / 'configs/data_split.json', {'test': scenes})
write(BASE / 'acquisition_reviews/knowledge-comparison/COMPARISON/workspace/knowledge_comparison.json',
      {'synthetic_fixture': True, 'projection_correspondence_review': reviews})
print('Six focused eligibility fixtures reuse unchanged v1 scenes; no model calls')
