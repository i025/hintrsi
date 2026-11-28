import sys, math
sys.path.insert(0, '/app/library')
import bpy
import reconstruct as r
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
def cube(name, loc, scale):
 bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o=bpy.context.object; o.name=name; o.dimensions=scale; bpy.context.view_layer.update(); return o
floor=cube('floor',(0,0,-.1),(5,5,.2)); obj=cube('sample',(0,0,.6),(1,1,1))
for z,want in [(.6,'positive gap'),(.5,'near-zero'),(.4,'possible penetration')]:
 obj.location.z=z; bpy.context.view_layer.update(); res=r.support_probe(obj,[floor],.001,8,1); print('SUPPORT',z,res['status']); assert res['status']==want
assert r.support_probe(obj,[],.001,8,1)['status']=='unknown support'
assert r.aabb_relation(obj,floor)['aabb_overlap']
bpy.ops.object.camera_add(location=(0,-5,3)); camera=bpy.context.object; bpy.context.scene.camera=camera
r.point_camera(camera,(0,-5,3),(0,0,0),40); p=r.project_points(bpy.context.scene,camera,[(0,0,0)])[0]; print('PROJECT',p); assert abs(p[0]-.5)<1e-5 and abs(p[1]-.5)<1e-5
assert len(r.landmark_errors(bpy.context.scene,camera,[('center',(0,0,0),(.5,.5),1)]))==1
bpy.ops.object.empty_add(); hinge=bpy.context.object
r.hinge_pose(hinge,obj,(0,0,0),(1,0,0),math.pi/4); assert obj.parent==hinge
assert r.hinge_report((0,0,0),(0,0,0),(0,0,0),.001)['within_tolerance']
m=r.mapped_stone('test'); assert m.node_tree.nodes.get('Noise Texture') is not None
print('ALL TESTS PASSED')
