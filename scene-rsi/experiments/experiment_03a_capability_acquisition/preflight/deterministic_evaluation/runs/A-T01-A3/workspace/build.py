import bpy
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
