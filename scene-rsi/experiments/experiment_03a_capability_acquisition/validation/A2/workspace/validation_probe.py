import sys, math, json
sys.path.insert(0,'/app/library')
import bpy
from mathutils import Vector
import reconstruct as r
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
def cube(name,loc,dims):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=name; o.dimensions=dims; bpy.context.view_layer.update(); return o
floor=cube('floor',(0,0,-.1),(10,10,.2)); obj=cube('sample',(0,0,.6),(1,1,1))
for z in [.6,.5,.4]:
 obj.location.z=z; bpy.context.view_layer.update(); print('SUPPORT',z,r.support_probe(obj,[floor],.001,8,1)['status'])
print('UNKNOWN',r.support_probe(obj,[],.001,8,1)['status']); print('AABB',r.aabb_relation(obj,floor))
bpy.ops.object.camera_add(); cam=bpy.context.object; bpy.context.scene.camera=cam
r.point_camera(cam,(0,-7,5),(0,0,0),40); print('PROJECTION',r.project_points(bpy.context.scene,cam,[(0,0,0)])); print('LANDMARK',r.landmark_errors(bpy.context.scene,cam,[('center',(0,0,0),(.5,.5),2)]))
# Editable selection-inspired table, chairs and hinged opening, not a reconstruction.
table=cube('table_top',(0,0,1),(2,1,.1)); leg=cube('table_leg',(-.8,-.35,.475),(.1,.1,.95)); chair=cube('chair_seat',(0,-1,.55),(.5,.5,.1))
bpy.ops.object.empty_add(); hinge=bpy.context.object; hinge.name='hinge'
leaf=cube('door_leaf',(0.5,0,1),(1,.08,2)); r.hinge_pose(hinge,leaf,(2,0,0),(1,0,0),math.pi/4)
print('HINGE',r.hinge_report(hinge.matrix_world.translation,leaf.matrix_world @ Vector((-.5,0,-.5)),(2,0,0),.001)); print('LEG_SUPPORT',r.support_probe(leg,[floor],.001,8,1)['status']); print('TABLE_LEG_AABB',r.aabb_relation(table,leg))
mat=r.mapped_stone('probe',coord_object=table); table.data.materials.append(mat)
print('MATERIAL_BINDING',table.material_slots[0].material.name)
print('MATERIAL_LINKS',[(l.from_node.bl_idname,l.from_socket.name,l.to_node.bl_idname,l.to_socket.name) for l in mat.node_tree.links]); print('COORD_OBJECT',next(n for n in mat.node_tree.nodes if n.bl_idname=='ShaderNodeTexCoord').object.name); print('IMAGES',[(n.name,n.image.name if n.image else None) for n in mat.node_tree.nodes if n.bl_idname=='ShaderNodeTexImage'])
bpy.ops.wm.save_as_mainfile(filepath='/app/selection_probe.blend')
print('PROBE COMPLETE')
