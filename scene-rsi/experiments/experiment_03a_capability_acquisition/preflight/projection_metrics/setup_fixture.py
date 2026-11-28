"""Known synthetic correspondences validate engineering, never research labels."""
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[4]
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'analysis'))
from harness.isolation import command
from evaluate_capability_acquisition import environment, blender, invoke, write

BASE.mkdir(parents=True, exist_ok=True)
(BASE / 'unused_model_socket').touch()
source = '''import bpy
from mathutils import Vector
LEFT_X = -.8
OCCLUDER_SCALE = 1
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
def cube(name, location, dimensions, color):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj=bpy.context.object;obj.name=name;obj.dimensions=dimensions
    mat=bpy.data.materials.new(name+'_material');mat.use_nodes=True
    mat.node_tree.nodes.clear()
    emission=mat.node_tree.nodes.new('ShaderNodeEmission');emission.inputs['Color'].default_value=(*color,1)
    out=mat.node_tree.nodes.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(emission.outputs[0],out.inputs['Surface'])
    obj.data.materials.append(mat)
    return obj
assembly=bpy.data.objects.new('assembly',None);bpy.context.scene.collection.objects.link(assembly)
left=cube('left',(LEFT_X,0,0),(.8,.6,1.2),(.8,.2,.1));left.parent=assembly
right=cube('right',(.8,0,0),(.8,.6,1.2),(.1,.3,.8));right.parent=assembly
cube('occluder',(-.8,-1,.25),(.4*OCCLUDER_SCALE,.2,.6*OCCLUDER_SCALE),(.2,.2,.2))
bpy.ops.object.camera_add(location=(0,-8,0))
cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,0))-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.type='ORTHO';cam.data.ortho_scale=4
s=bpy.context.scene;s.camera=cam;s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=4
s.render.resolution_x=640;s.render.resolution_y=360;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.render.filepath='/app/final.png'
bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend')
bpy.ops.render.render(write_still=True)
'''


def mapping(ids, names, confidence='high', ambiguity=None):
    return {'gt_instance_ids': ids, 'gt_semantic_label': 'synthetic_known_object_union',
            'student_object_names': names, 'confidence': confidence, 'basis': ['Known fixture construction, not a model or human scientific annotation.'],
            'ambiguity': ambiguity or [], 'orientation_identifiability': 'synthetic axis-aligned test; no angle error is computed'}


scenes = []
for index in range(1, 8):
    scene_id = 'A-T' + str(index).zfill(2)
    run = BASE / 'runs' / (scene_id + '-A0')
    for name in ('workspace', 'home', 'capture', 'tmp', 'inputs'):
        (run / name).mkdir(parents=True, exist_ok=True)
    (run / 'inputs/session.json').write_text('{}')
    (run / 'status.json').write_text(json.dumps({'status': 'completed', 'synthetic_fixture': True}))
    code = source.replace('LEFT_X = -.8', 'LEFT_X = -.5') if index == 2 else source
    if index == 3:
        code = code.replace('OCCLUDER_SCALE = 1', 'OCCLUDER_SCALE = 1.5')
    if index == 7:
        code = code.replace('LEFT_X = -.8', 'LEFT_X = 20')
    (run / 'workspace/build.py').write_text(code)
    write(run / 'sdk_command.json', command(run, BASE / 'unused_model_socket'))
    output = run / 'fixture_generation'
    argv = environment(run, output, run / 'workspace')
    result = invoke(blender(argv, '/app/build.py'), output, 'generate', '72-79', 120)
    assert result['exit_code'] == 0, result
    if index == 1:
        gt = BASE / 'private_fixture_gt'
        gt.mkdir(exist_ok=True)
        shutil.copy2(run / 'workspace/final.png', gt / 'color.png')
        specs = [dict(mapping([i], [name]), mapping_index=i) for i, name in ((1, 'left'), (2, 'right'), (3, 'occluder'))]
        write(output / 'inputs/gt_mapping.json', specs)
        result = invoke(blender(argv, '/analysis/acquisition_projection_masks.py',
                                ['--input', '/app/scene.blend', '--mappings', '/inputs/gt_mapping.json',
                                 '--output', '/capture/synthetic_gt_masks', '--samples', '4']),
                        output, 'synthetic_gt_masks', '72-79', 120)
        assert result['exit_code'] == 0, result
        import numpy as np
        from PIL import Image
        segmentation = np.zeros((360, 640), dtype=np.uint16)
        for i in (1, 2, 3):
            mask = np.asarray(Image.open(output / 'capture/synthetic_gt_masks' / ('mapping_' + str(i).zfill(3) + '.png')).convert('L')) >= 128
            segmentation[mask] = i
        Image.fromarray(segmentation).save(gt / 'instance_segmentation.png')
    if index == 1:
        correspondence = [mapping([1], ['left']), mapping([2], ['right']), mapping([3], ['occluder']), mapping([999], ['left_missing'], 'unknown')]
    elif index == 4:
        correspondence = [mapping([1, 2], ['assembly'])]
    elif index == 5:
        correspondence = [mapping([1], ['name_does_not_exist'])]
    elif index == 6:
        correspondence = [mapping([1], ['left'], 'unknown', ['Repeated instance assignment intentionally unresolved.'])]
    else:
        correspondence = [mapping([1], ['left'])]
    annotation = BASE / 'acquisition_reviews/technical' / run.name / 'workspace/technical_annotation.json'
    write(annotation, {'run_id': run.name, 'scene_id': scene_id, 'synthetic_fixture': True,
                       'semantic_correspondence': correspondence})
    scenes.append({'id': scene_id, 'directory': str(BASE / 'private_fixture_gt'),
                   'reference': str(BASE / 'private_fixture_gt/color.png')})
write(BASE / 'configs/data_split.json', {'test': scenes})
print('Seven non-model engineering fixtures ready', flush=True)
