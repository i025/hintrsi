import sys, math, json
sys.path.insert(0,'/app/library')
import bpy
from mathutils import Vector
import spatial, support, appearance
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
def box(name, loc, scale):
 bpy.ops.mesh.primitive_cube_add(size=2, location=loc); o=bpy.context.object; o.name=name; o.scale=scale; return o
floor=box('floor',(0,0,-.1),(4,4,.1)); leg=box('leg',(0,0,1),(.1,.1,1)); bpy.context.view_layer.update()
for z in (1.2,1,.9):
 leg.location.z=z; bpy.context.view_layer.update(); print('SUPPORT',z,support.sample_support(leg,[floor]))
leg.location.x=8; bpy.context.view_layer.update(); print('MISS',support.sample_support(leg,[floor])); print('BOUNDS',support.world_bounds(leg))
print('HINGE',spatial.hinge_positions((1,2,0),2,[0,math.pi/2]));
try: spatial.hinge_positions((0,0,0),0,[0])
except ValueError as e: print('EXPECTED_EXCEPTION',str(e))
bpy.ops.object.camera_add(location=(0,0,10)); cam=bpy.context.object; bpy.context.view_layer.update(); print('PROJECTION',spatial.project_points(bpy.context.scene,cam,[(0,0,0),(0,0,11)]))
mat=appearance.directional_stone('probe'); leg.data.materials.append(mat)
print('MATERIAL_BINDING',leg.material_slots[0].material.name,'LINKS',[(l.from_node.bl_idname,l.from_socket.name,l.to_node.bl_idname,l.to_socket.name) for l in mat.node_tree.links]); print('IMAGE_RESOURCES',[(n.name,n.image.name if n.image else None) for n in mat.node_tree.nodes if n.bl_idname=='ShaderNodeTexImage'])
# Limited selection-inspired editable table and articulated door; not a reconstruction.
leg.location=(0,0,1); top=box('tabletop',(0,0,2.05),(1.3,.7,.05)); pivot=bpy.data.objects.new('hinge',None); bpy.context.collection.objects.link(pivot); pivot.location=(3,0,0)
leaf=box('door_leaf',(0,0,0),(0.5,.04,1)); leaf.parent=pivot; leaf.location=(.5,0,1); detail=box('door_detail',(0,0,0),(.1,.01,.2)); detail.parent=leaf; detail.location=(0,1.1,0)
for a in (0,math.pi/4):
 pivot.rotation_euler.z=a; bpy.context.view_layer.update(); print('ASSEMBLY',a,'hinge',tuple(pivot.matrix_world.translation),'leaf',tuple(leaf.matrix_world.translation),'detail',tuple(detail.matrix_world.translation),'edge_prediction',spatial.hinge_positions(tuple(pivot.location),1,[a]))
print('TABLE_SUPPORT',support.sample_support(leg,[floor])); print('AABB_ONLY',support.world_bounds(top),support.world_bounds(leaf))
bpy.ops.wm.save_as_mainfile(filepath='/app/selection_probe.blend')
print('PROBE_COMPLETE')
