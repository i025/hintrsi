import sys, math
sys.path.insert(0, '/app/library')
import bpy
from mathutils import Vector
import spatial, support, appearance
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add(size=2, location=(0,0,-1)); floor=bpy.context.object
bpy.ops.mesh.primitive_cube_add(size=2, location=(0,0,2)); obj=bpy.context.object
bpy.context.view_layer.update()
assert support.sample_support(obj,[floor])['category']=='positive gap'
obj.location.z=1; bpy.context.view_layer.update()
assert support.sample_support(obj,[floor])['category']=='near-zero sample'
obj.location.z=.9; bpy.context.view_layer.update()
assert support.sample_support(obj,[floor])['category']=='possible penetration'
obj.location.x=10; bpy.context.view_layer.update()
assert support.sample_support(obj,[floor])['category']=='unknown support'
assert support.world_bounds(obj) is not None
assert abs(spatial.hinge_positions((0,0,0),1,[math.pi/2])[0][1]-1)<1e-6
bpy.ops.object.camera_add(location=(0,0,10)); camera=bpy.context.object
bpy.context.view_layer.update()
assert spatial.project_points(bpy.context.scene,camera,[(0,0,0)])[0]['depth']>0
mat=appearance.directional_stone('synthetic'); assert mat.use_nodes and mat.node_tree.nodes.get('Principled BSDF')
print('LIBRARY_SYNTHETIC_CHECK_PASS')
