import bpy, sys, json, math
from mathutils import Vector
sys.path.insert(0, '/app/library')
import methods as m
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
results={}
def cube(name,loc,scale):
 bpy.ops.mesh.primitive_cube_add(size=2,location=loc); o=bpy.context.object; o.name=name; o.scale=scale; bpy.context.view_layer.update(); return o
floor=cube('floor',(0,0,-.1),(5,5,.1))
obj=cube('support_piece',(0,0,1.5),(.5,.5,.5))
results['gap']=m.support_samples(obj,floor)
obj.location.z=.5; bpy.context.view_layer.update(); results['near']=m.support_samples(obj,floor)
obj.location.z=.498; bpy.context.view_layer.update(); results['penetration']=m.support_samples(obj,floor)
obj.location=(20,0,.5); bpy.context.view_layer.update(); results['unknown']=m.support_samples(obj,floor)
results['bounds_separated']=m.bounds_separation(obj,floor)
obj.location=(0,0,.5); bpy.context.view_layer.update(); results['bounds_overlap_candidate']=m.bounds_separation(obj,floor)
bpy.ops.object.camera_add(location=(0,0,5)); cam=bpy.context.object; cam.rotation_euler=(0,0,0); bpy.context.scene.camera=cam; bpy.context.view_layer.update()
results['projection']=m.landmarks(bpy.context.scene,cam,{'center':(0,0,0),'behind':(0,0,10)})
results['error']=m.landmark_error(results['projection'],{'center':(.5,.5,1)})
bpy.ops.object.empty_add(); pivot=bpy.context.object
leaf=cube('leaf',(1,0,1),(1,.05,1)); leaf.parent=pivot
bpy.context.view_layer.update(); m.hinge_pose(pivot,(0,0,0),math.pi/2); results['hinge_error']=m.hinge_error(pivot,(0,0,0)); results['leaf_center']=list(leaf.matrix_world.translation)
mat=m.directional_material('test'); obj.data.materials.append(mat)
results['material']={'binding':obj.material_slots[0].material.name,'links':[(x.from_node.bl_idname,x.from_socket.name,x.to_node.bl_idname,x.to_socket.name) for x in mat.node_tree.links], 'images':[(n.name,n.image.name if n.image else None) for n in mat.node_tree.nodes if n.bl_idname=='ShaderNodeTexImage'], 'coordinates':[x.from_socket.name for x in mat.node_tree.links if x.from_node.bl_idname=='ShaderNodeTexCoord']}
# Selection-inspired editable probe: table with supported legs, hinged door pivot and opening posts.
top=cube('selection_table',(0,2,1.5),(1.5,.7,.08))
legs=[cube('selection_leg_'+str(i),(x,y,.71),(.06,.06,.71)) for i,(x,y) in enumerate([(-1.35,1.4),(1.35,1.4),(-1.35,2.6),(1.35,2.6)])]
results['selection_leg_support']=[m.support_samples(x,floor) for x in legs]
results['selection_leaf_anchor']=m.hinge_error(pivot,(0,0,0))
results['selection_table_landmarks']=m.landmarks(bpy.context.scene,cam,{'center':top.matrix_world.translation})
results['selection_material_bound']=top.data.materials.append(mat) is None
bpy.ops.wm.save_as_mainfile(filepath='/app/research/selection_probe.blend')
with open('/app/research/validation_probe_results.json','w') as f: json.dump(results,f,indent=2)
print('VALIDATION_RESULTS',json.dumps(results))
