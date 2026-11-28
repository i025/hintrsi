import bpy, sys, math, json
from mathutils import Vector
sys.path.insert(0,'/app/library')
import reconstruction as r
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
s=bpy.context.scene
bpy.ops.object.camera_add(); cam=bpy.context.object; s.camera=cam
r.aim_camera(cam,(5,-8,6),(0,0,1),35)
print('PROJECTION',r.project_points(s,cam,[(0,0,1)]),r.landmark_error(s,cam,[((0,0,1),(.5,.5),1)]))
def cube(name,loc,scale):
 bpy.ops.mesh.primitive_cube_add(); o=bpy.context.object; o.name=name; o.location=loc; o.scale=scale; bpy.context.view_layer.update(); return o
floor=cube('floor',(0,0,-.1),(4,4,.1)); table=cube('table',(0,0,1),(.9,1.5,.08)); leg=cube('leg',(.7,1.2,.46),(.08,.08,.46)); leg.parent=table; bpy.context.view_layer.update()
print('SUPPORT',r.support_bounds(leg,floor),r.support_bounds(table,leg),r.assembly_components([floor,table,leg]))
wall=cube('wall_left',(-2,2,1.5),(.8,.1,1.5)); jamb=cube('jamb',(-1.2,2,1.5),(.05,.15,1.5)); door=cube('door',(-.6,2,1.5),(.6,.05,1.5)); handle=cube('handle',(-.15,1.92,1.5),(.04,.04,.1)); handle.parent=door; bpy.context.view_layer.update()
pivot=door.matrix_world @ Vector((-1,0,0)); before=handle.matrix_world.translation.copy(); r.hinge_pose(door,pivot,math.pi/3,(-1,0,0)); bpy.context.view_layer.update(); print('HINGE',list(door.matrix_world @ Vector((-1,0,0))),list(pivot),'handle_before_after',list(before),list(handle.matrix_world.translation))
mat=r.make_directional_material('grain',(.08,.03,.01,1),(.6,.3,.1,1)); table.data.materials.append(mat)
print('MATERIAL_BINDING',table.name,[m.name for m in table.data.materials]); print('MATERIAL_LINKS',[(l.from_node.bl_idname,l.from_socket.name,l.to_node.bl_idname,l.to_socket.name) for l in mat.node_tree.links]); print('IMAGES',[(im.name,im.source,im.filepath, bool(im.packed_file)) for im in bpy.data.images]); print('MAPPING',[(n.bl_idname,tuple(n.inputs['Scale'].default_value) if n.bl_idname=='ShaderNodeMapping' else None) for n in mat.node_tree.nodes if n.bl_idname in ('ShaderNodeMapping','ShaderNodeTexCoord')])
# An AABB overlap candidate that is not a mesh intersection: separate diagonal slender bars.
a=cube('bar_a',(0,-2,1),(1,.05,.05)); b=cube('bar_b',(0,-2,1.3),(1,.05,.05)); a.rotation_euler.z=math.pi/4; b.rotation_euler.z=-math.pi/4; bpy.context.view_layer.update(); print('CANDIDATE_ONLY',r.support_bounds(a,b))
s.render.engine='CYCLES'; s.cycles.samples=4; s.render.resolution_x=320; s.render.resolution_y=180; s.render.resolution_percentage=100
bpy.ops.object.light_add(type='AREA', location=(1,-3,6)); bpy.context.object.data.energy=1000; bpy.context.object.data.shape='DISK'; bpy.context.object.data.size=5
s.world.color=(.3,.3,.3); s.render.filepath='/app/selection_probe.png'; bpy.ops.wm.save_as_mainfile(filepath='/app/selection_probe.blend'); bpy.ops.render.render(write_still=True)
print('PROBE_DONE')
