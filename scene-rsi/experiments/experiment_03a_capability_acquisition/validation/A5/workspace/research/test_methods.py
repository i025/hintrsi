import bpy, sys, math, json
sys.path.insert(0, "/app/library")
import methods as m
bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete(use_global=False)
def cube(name, loc, scale):
 bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o=bpy.context.object; o.name=name; o.scale=scale; bpy.context.view_layer.update(); return o
floor=cube("floor",(0,0,-.5),(10,10,1))
box=cube("box",(0,0,1),(1,1,1))
results={}
for z in (1,.5,.499, -2):
 box.location.z=z; bpy.context.view_layer.update(); results[str(z)]=m.support_samples(box,floor,tolerance=.002)
assert results['1']['state']=='positive gap'
assert results['0.5']['state']=='near-zero'
assert results['-2']['state']=='unknown support'
box.location.z=1; bpy.context.view_layer.update(); results['separation']=m.bounds_separation(box,floor)
assert results['separation'] > 0
bpy.ops.object.camera_add(location=(0,-5,2)); camera=bpy.context.object; camera.rotation_euler=(math.radians(90),0,0); bpy.context.scene.camera=camera; bpy.context.view_layer.update()
results['projection']=m.landmarks(bpy.context.scene,camera,{'p':(0,0,2)})
assert results['projection']['p']['depth']>0
assert m.landmark_error(results['projection'],{'p':(.5,.5,1)})<1e-8
bpy.ops.object.empty_add(); pivot=bpy.context.object
m.hinge_pose(pivot,(1,2,0),.5); assert m.hinge_error(pivot,(1,2,0))<1e-6
mat=m.directional_material('test'); assert mat.node_tree and len(mat.node_tree.links)>=4
results['hinge_material']='passed'
open('/app/research/test_results.json','w').write(json.dumps(results,indent=2))
print('TEST RESULTS',json.dumps(results))
