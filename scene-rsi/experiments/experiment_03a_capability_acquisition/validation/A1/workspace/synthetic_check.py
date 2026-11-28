import sys
sys.path.insert(0, '/app/library')
import bpy
import reconstruct as r
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
def box(z):
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0,0,z))
    return bpy.context.object
base=box(0)
child=box(2.5)
assert r.support_diagnostic(child,base,0.01)['classification']=='positive gap'
child.location.z=2
bpy.context.view_layer.update()
assert r.support_diagnostic(child,base,0.01)['classification']=='near-zero'
child.location.z=1.5
bpy.context.view_layer.update()
assert r.support_diagnostic(child,base,0.01)['classification']=='possible penetration'
child.location.x=10
bpy.context.view_layer.update()
assert r.support_diagnostic(child,base,0.01)['classification']=='unknown support'
child.parent=base
assert r.assembly_links([child,base]) == [(child.name,base.name,'parent')]
mat=r.make_directional_material('synthetic',(0.1,0.1,0.1,1),(0.3,0.3,0.3,1),(1,4,4))
assert mat.use_nodes and len(mat.node_tree.links)==5
bpy.ops.object.camera_add(location=(0,0,10))
cam=bpy.context.object
scene=bpy.context.scene
scene.camera=cam
p=r.projected_landmarks(scene,cam,{'center':(0,0,0)})['center']
assert p['in_frame'] and abs(p['xy'][0]-.5)<1e-5 and abs(p['xy'][1]-.5)<1e-5
assert r.landmark_loss(scene,cam,{'center':(0,0,0)},{'center':(.5,.5,1)})<1e-10
print('SYNTHETIC_CHECK_PASS')
