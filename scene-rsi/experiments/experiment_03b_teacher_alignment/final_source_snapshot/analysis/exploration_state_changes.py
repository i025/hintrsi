"""Describe changes within a common checkpoint coordinate frame, not GT error."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'experiments/experiment_02_teacher_guided_exploration'
OLD=ROOT/'experiments/experiment_01_natural_trajectories'


def changes(before,after,fields):
    return {key:{'before':before.get(key),'after':after.get(key)}
            for key in fields if before.get(key)!=after.get(key)}


def main():
    cases={r['scene']:r for r in json.loads((EXP/'configs/cases.json').read_text())}
    results=[]
    for run in sorted((EXP/'runs').iterdir()):
        path=run/'analysis/technical/capture/final_state.json'
        if not path.exists():continue
        baseline=json.loads((OLD/'runs'/cases[run.name[:3]]['source_run']/'analysis/technical/capture/final_state.json').read_text())
        final=json.loads(path.read_text())
        initial_objects={o['name']:o for o in baseline['objects']};final_objects={o['name']:o for o in final['objects']}
        matched=[]
        for name in initial_objects.keys()&final_objects.keys():
            before,after=initial_objects[name],final_objects[name]
            delta=changes(before,after,['type','parent','location','world_location','rotation_euler','scale','dimensions','materials','modifiers','camera','light','hide_render'])
            if delta:matched.append({'name':name,'type':after['type'],'changes':delta})
        materials=[]
        for m in final['materials']:
            materials.append({'name':m['name'],'node_types':[n['type'] for n in m['nodes']],
                              'image_nodes':[n for n in m['nodes'] if n['type']=='ShaderNodeTexImage'],
                              'mapping_nodes':[n for n in m['nodes'] if n['type']=='ShaderNodeMapping'],
                              'color_ramps':[n for n in m['nodes'] if n['type']=='ShaderNodeValToRGB'],
                              'links':m['links']})
        def comparable(material):
            return {'diffuse_color':material['diffuse_color'],'roughness':material['roughness'],
                    'metallic':material['metallic'],'links':material['links'],
                    'nodes':[{k:node.get(k) for k in ('name','type','inputs','image','node_group')}
                             for node in material['nodes']]}
        before_materials={m['name']:m for m in baseline['materials']}
        after_materials={m['name']:m for m in final['materials']}
        changed_materials=[name for name in before_materials.keys()&after_materials.keys()
                           if comparable(before_materials[name])!=comparable(after_materials[name])]
        row={'run':run.name,'matched_name_changes':sorted(matched,key=lambda x:x['name']),
             'names_only_in_final':sorted(final_objects.keys()-initial_objects.keys()),
             'names_only_in_initial':sorted(initial_objects.keys()-final_objects.keys()),
             'camera_or_light_changed':any(x['type'] in ('CAMERA','LIGHT') for x in matched),
             'world_changed':baseline['world']!=final['world'],
             'render_changed':changes(baseline['render'],final['render'],list(baseline['render'])),
             'actual_final_materials':materials,'images':final['images'],
             'named_materials_changed_in_comparable_fields':sorted(changed_materials),
             'material_comparison_limit':'Original state extraction lacks the new ColorRamp/operation properties; absent old properties are unknown, not changes. Actual source and new state retain their evidence.',
             'scope':'Within copied checkpoint frame, exact named correspondences only. Renamed objects are unmatched, not automatically semantic additions/deletions. Not a GT-aligned 3D distance.'}
        (run/'analysis/state_changes.json').write_text(json.dumps(row,indent=2))
        results.append(row)
    (EXP/'analysis/state_changes.json').write_text(json.dumps(results,indent=2))
    print('Recorded named-object, material, camera and light changes for',len(results),'branches.')


if __name__=='__main__':main()
