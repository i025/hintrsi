import bpy, sys, math
from mathutils import Vector
sys.path.insert(0, '/app/library')
import reconstruction as r
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.ops.object.camera_add(); cam=bpy.context.object; bpy.context.scene.camera=cam
r.aim_camera(cam,(0,-6,3),(0,0,0),35)
p=r.project_points(bpy.context.scene,cam,[(0,0,0)])[0]
assert abs(p[0]-.5)<1e-5 and abs(p[1]-.5)<1e-5 and p[2]>0, p
assert r.landmark_error(bpy.context.scene,cam,[((0,0,0),(.5,.5),1)])<1e-5
bpy.ops.mesh.primitive_cube_add(location=(0,0,0)); lower=bpy.context.object
bpy.ops.mesh.primitive_cube_add(location=(0,0,3)); upper=bpy.context.object
bpy.context.view_layer.update()
assert r.support_bounds(upper,lower)['status']=='positive gap'
upper.location.z=2; bpy.context.view_layer.update(); assert r.support_bounds(upper,lower)['status']=='near-zero'
upper.location.z=1.5; bpy.context.view_layer.update(); assert r.support_bounds(upper,lower)['status']=='possible penetration'
upper.location.x=10; bpy.context.view_layer.update(); assert r.support_bounds(upper,lower)['status']=='unknown support'
upper.parent=lower; assert len(r.assembly_components([upper,lower]))==1
upper.parent=None; upper.location=(0,0,0); bpy.context.view_layer.update(); hinge=upper.matrix_world @ Vector((-1,0,0)); r.hinge_pose(upper,hinge,math.pi/2,(-1,0,0)); assert (upper.matrix_world @ Vector((-1,0,0))-hinge).length<1e-5
mat=r.make_directional_material('test',(0.2,0.2,0.2,1),(0.8,0.8,0.8,1)); assert len(mat.node_tree.links)==5
print('LIBRARY_CHECKS_PASS: projection landmark support statuses parenting hinge material node links')
