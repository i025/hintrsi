import sys, json, math
sys.path.insert(0,'/app/library')
import bpy
from mathutils import Vector
import reconstruct as r
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
results={}
def cube(name,loc,scale):
 bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o=bpy.context.object; o.name=name; o.scale=scale; bpy.context.view_layer.update(); return o
floor=cube('support',(0,0,-.1),(4,4,.2)); box=cube('child',(0,0,.5),(1,1,1))
results['contact_candidate']=r.support_diagnostic(box,floor)
box.location.z=1; bpy.context.view_layer.update(); results['gap']=r.support_diagnostic(box,floor)
box.location.z=.4; bpy.context.view_layer.update(); results['penetration_candidate']=r.support_diagnostic(box,floor)
box.location.x=10; bpy.context.view_layer.update(); results['unknown']=r.support_diagnostic(box,floor)
try: r.support_diagnostic(box,floor,-1)
except Exception as e: results['negative_tolerance']=type(e).__name__
empty=bpy.data.objects.new('pivot',None); bpy.context.collection.objects.link(empty)
results['nonmesh']=r.support_diagnostic(empty,floor)
leaf=cube('leaf',(1,0,1),(2,.08,2)); leaf.parent=empty; bpy.context.view_layer.update(); before=empty.matrix_world @ Vector((0,0,0)); empty.rotation_euler.z=.7; bpy.context.view_layer.update(); after=empty.matrix_world @ Vector((0,0,0)); results['hinge_pivot_displacement']=(after-before).length; results['links']=r.assembly_links([empty,leaf]); results['leaf_bounds']=r.world_bounds(leaf)
camdata=bpy.data.cameras.new('cam'); cam=bpy.data.objects.new('cam',camdata); bpy.context.collection.objects.link(cam); cam.location=(0,0,10); bpy.context.view_layer.update(); scene=bpy.context.scene; scene.camera=cam
p=r.projected_landmarks(scene,cam,{'center':(0,0,0),'behind':(0,0,11)}); results['projection']=p; results['loss']=r.landmark_loss(scene,cam,{'center':(0,0,0)},{'center':(.5,.5,1)})
try: r.landmark_loss(scene,cam,{'behind':(0,0,11)},{'behind':(.5,.5,1)})
except Exception as e: results['behind_error']=str(e)
mat=r.make_directional_material('test',(.1,.2,.3,1),(.8,.7,.6,1),(.2,3,4),.5); leaf.data.materials.append(mat)
results['material']={'assigned':leaf.active_material==mat,'links':[(l.from_node.bl_idname,l.from_socket.name,l.to_node.bl_idname,l.to_socket.name) for l in mat.node_tree.links], 'images':[n.image.name if n.image else None for n in mat.node_tree.nodes if n.bl_idname=='ShaderNodeTexImage'], 'mapping':list(next(n for n in mat.node_tree.nodes if n.bl_idname=='ShaderNodeVectorMath').inputs[1].default_value)}
# Limited editable selection-inspired probe: table, chairs and hinged door, not a fitted reconstruction.
table=cube('tabletop',(0,0,1.2),(3,1.5,.12)); chair=cube('chair_seat',(0,-1.3,.65),(.6,.6,.12)); results['selection_probe_support']=r.support_diagnostic(chair,floor); results['selection_probe_table_bounds']=r.world_bounds(table)
bpy.ops.wm.save_as_mainfile(filepath='/app/selection_probe.blend')
with open('/app/validation_probe_results.json','w') as f: json.dump(results,f,indent=2)
print('VALIDATION_RESULTS',json.dumps(results))
