"""Project saved-state observations for a bounded CLI audit; raw probes stay complete."""
import json
from pathlib import Path

OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
BASE=Path('/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/stagewise_teaching_student_selfcheck_pilot/tasks/D01/stages/04')
directory=OUT/'evidence/scene_geometry';states=[];source_files=[]
for label in ['technical_repair_build','visual_revision_build']:
    p=directory/(label+'.json');d=json.loads(p.read_text())
    chosen=[o for o in d['objects'] if o['type']=='MESH' and any(k in n.lower() for n in [o['name']]+o['ancestors'] for k in ['monitor','screen','display','stand'])]
    states.append({'derived_probe':str(p),'source_blend':d['filepath'],
        'blender_version':d['blender_version'],'frame':d['current_frame'],'unit_system':d['unit_system'],'unit_scale':d['unit_scale'],
        'total_objects_observed':len(d['objects']),'semantic_subset_meshes':len(chosen),
        'all_probe_object_exceptions':sum('exceptions' in o for o in d['objects']),
        'all_object_and_data_driver_count':sum(o.get('object_animation_drivers',0)+o.get('data_animation_drivers',0) for o in d['objects']),
        'active_camera':d['active_camera'],'render_resolution':d['render_resolution'],
        'selected_meshes':[{k:v for k,v in o.items() if k!='world_matrix'} for o in chosen],
        'all_selected_pair_lower_bounds':d['mesh_aabb_pairs'],'scope':d['scope']})
    source_files.append(d['filepath'])
texts={}
for relative in ['review.json','confirmation.json','technical_repair_build/patch.py','visual_revision_build/patch.py',
    'technical_repair_build/actual_render_settings.json','visual_revision_build/actual_render_settings.json']:
    p=BASE/relative
    if p.exists():texts[str(p)]=p.read_text();source_files.append(str(p))
data={'states':states,'original_text_evidence':texts,
    'earlier_text_audit':(OUT/'audit/audit_S01.md').read_text(),
    'execution_records':json.loads((directory/'execution_records.json').read_text()),
    'coverage':'Two existing binary checkpoints, each874objects numerically observed; only48named/ancestor-filtered meshes and all1128pair bounds per checkpoint are supplied for semantic interpretation. Not874independent objects across experiments, not a broad Scene quality evaluation. No render or new student generation.'}
prompt='''Read-only Scene geometry addendum in English, at most1600words. New numerical observations come from actual cached .blend files loaded with the original Blender4.2.10 binary, factory startup, disabled autoexec,1thread and noGPU. No original file was saved, and no render/new scene reconstruction/learning trial occurred. Frame and drivers are reported. The probe did not reapply render-backend overrides; use supplied actual-render-settings records and do not silently equate every saved property with the final rendered state.

Use original stage4 teacher review, student patch, confirmation and previous audit to identify the monitor/display subgoal and actual named component roles. Cite exact original/derived paths, object names and relevant JSON fields. Semantic labels inferred from names/ancestor paths/code must be marked as inference. Compare the two saved checkpoints's actual observed changes, teacher detection/diagnosis/update and student execution. Preserve source units: unit scale alone does not establish true physical scale.

Every supplied AABB pair is a bound, not an exact collision/contact test. A positive lower bound establishes separated bounds for that pair; zero does not establish touching. Separate pairs within an inferred same monitor assembly from unrelated monitors; different objects can validly be apart. A gap for one pair does not by itself prove the whole assembly is disconnected because another connector may exist. Do not choose only positive pairs or declare all components defective. If the evidence does not settle contact/quality, explicitly retain that uncertainty. Do not infer hidden geometry correctness, visual quality gains, causal teaching efficacy, or a whole-Scene conclusion. This post-freeze audit never updates code-experiment libraries or students. End with confirmed saved-state facts, still-unverified claims, and exact coverage.\nDATA:\n'''+json.dumps(data,ensure_ascii=False,separators=(',',':'))
if len(prompt)>700000:raise RuntimeError('Geometry addendum packet exceeds declared input cap')
(OUT/'config/audit_SG01_prompt.txt').write_text(prompt)
old=json.loads((OUT/'audit/scene_deep_audit_sources.json').read_text())
old_paths={s['path'] for case in old for s in case['sources']}
additional=[p for p in source_files if p not in old_paths]
(OUT/'audit/scene_geometry_audit_sources.json').write_text(json.dumps({'sources':source_files,
    'additional_original_text_sources':[p for p in additional if not p.endswith('.blend')],
    'additional_original_binary_sources':[p for p in additional if p.endswith('.blend')],
    'raw_probes':[s['derived_probe'] for s in states],'selected_meshes_per_checkpoint':[s['semantic_subset_meshes'] for s in states],
    'all_pair_bounds_per_checkpoint':[len(s['all_selected_pair_lower_bounds']) for s in states],
    'prompt_characters':len(prompt),'postfreeze_audit_only':True},indent=2)+'\n')
print(json.dumps({'prompt_characters':len(prompt),'meshes':[s['semantic_subset_meshes'] for s in states]}))
