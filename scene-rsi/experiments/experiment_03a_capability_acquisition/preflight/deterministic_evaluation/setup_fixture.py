"""Artificial engineering fixtures, excluded from scientific student results."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[4]
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'analysis'))
from harness.isolation import command
from evaluate_capability_acquisition import environment, blender, invoke

(BASE / 'configs').mkdir(exist_ok=True)
(BASE / 'capability_fixture').mkdir(exist_ok=True)
(BASE / 'capability_fixture/helper.py').write_text('COLOR = (0.6, 0.12, 0.03, 1)\n')
(BASE / 'unused_model_socket').touch()
source = '''import bpy
from mathutils import Vector
from pathlib import Path
import json
assert not Path('/srv/lab-disks/disk2/users/xymo/scene-rsi/data').exists()
assert not Path('/gt').exists()
COLOR = (0.6, 0.12, 0.03, 1)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.5))
obj=bpy.context.object; obj.name='fixture_cube'
m=bpy.data.materials.new('fixture_material');m.use_nodes=True
m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=COLOR
obj.data.materials.append(m)
bpy.ops.mesh.primitive_plane_add(size=6)
bpy.context.object.name='fixture_floor'
bpy.ops.object.camera_add(location=(3,-4,3))
cam=bpy.context.object
cam.rotation_euler=(Vector((0,0,0.5))-cam.location).to_track_quat('-Z','Y').to_euler()
bpy.context.scene.camera=cam
bpy.ops.object.light_add(type='AREA',location=(1,-2,5))
bpy.context.object.data.energy=500
s=bpy.context.scene
s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=4
s.render.resolution_x=640;s.render.resolution_y=360;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.render.filepath='/app/final.png'
bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend')
bpy.ops.render.render(write_still=True)
Path('/app/isolation_assertion.json').write_text(json.dumps({'gt_accessible':False,'capability_library_accessible':Path('/capabilities').exists()}))
'''
for group in ('A0', 'A1', 'A2'):
    run = BASE / 'runs' / ('A-T01-' + group)
    for name in ('workspace', 'home', 'capture', 'tmp', 'inputs'):
        (run / name).mkdir(parents=True, exist_ok=True)
    session = {'readonly_mounts': [{'source': str(BASE / 'capability_fixture'), 'target': '/capabilities'}]}
    (run / 'inputs/session.json').write_text(json.dumps(session))
    (run / 'status.json').write_text(json.dumps({'status': 'completed', 'synthetic_fixture': True}))
    build = source
    if group == 'A1':
        build = source.replace('COLOR = (0.6, 0.12, 0.03, 1)',
                               'import sys\nsys.path.insert(0,"/capabilities")\nfrom helper import COLOR')
    (run / 'workspace/build.py').write_text(build)
    (run / 'sdk_command.json').write_text(json.dumps(command(run, BASE / 'unused_model_socket')))
    output = run / 'fixture_generation'
    argv = environment(run, output, run / 'workspace', True)
    result = invoke(blender(argv, '/app/build.py'), output, 'generate', '72-79', 120)
    assert result['exit_code'] == 0, result
    if group == 'A2':
        (run / 'workspace/build.py').write_text("raise RuntimeError('synthetic student error retained')\n")
reference = BASE / 'runs/A-T01-A0/workspace/final.png'
(BASE / 'configs/data_split.json').write_text(json.dumps({'test': [{'id': 'A-T01', 'reference': str(reference)}]}))
print('Three synthetic originals generated; no SDK or model calls')
