import bpy, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import sys
path=sys.argv[sys.argv.index('--')+1]
bpy.ops.wm.open_mainfile(filepath=path)
dg=bpy.context.evaluated_depsgraph_get()
floors=[o for o in bpy.context.scene.objects if o.name.startswith('individual oak floor plank') or o.name=='floor slab']
tris=[]; verts=[]
for o in floors:
 ev=o.evaluated_get(dg); m=ev.to_mesh(); off=len(verts); verts += [o.matrix_world @ v.co for v in m.vertices]; tris += [tuple(off+i for i in p.vertices) for p in m.polygons]; ev.to_mesh_clear()
bvh=BVHTree.FromPolygons(verts,tris,all_triangles=False)
for o in sorted([o for o in bpy.context.scene.objects if o.name.startswith('caster wheel')],key=lambda x:x.name):
 ev=o.evaluated_get(dg); m=ev.to_mesh(); vs=[o.matrix_world @ v.co for v in m.vertices]; low=min(v.z for v in vs); lows=[v for v in vs if v.z<low+0.0001]; gaps=[]
 for v in lows:
  hit,_,_,_=bvh.ray_cast(Vector((v.x,v.y,2)),Vector((0,0,-1)),4)
  if hit: gaps.append(v.z-hit.z)
 print(o.name,'low',round(low,5),'floor gaps', [round(min(gaps),5),round(max(gaps),5)] if gaps else 'NO FLOOR')
 ev.to_mesh_clear()
for o in bpy.context.scene.objects:
 if o.name.startswith('chair central post') or o.name.startswith('curved grey office chair shell'):
  ev=o.evaluated_get(dg); m=ev.to_mesh(); vs=[o.matrix_world@v.co for v in m.vertices]; print(o.name,'zrange',round(min(v.z for v in vs),4),round(max(v.z for v in vs),4)); ev.to_mesh_clear()
# Isolate chairs and floor and render side elevation.
for o in bpy.context.scene.objects:
 if o.type=='MESH' and not (o.name.startswith(('caster wheel','caster fork','five star chair base','chair central post','curved grey office chair shell','individual oak floor plank')) or o.name=='floor slab'): o.hide_render=True
scene=bpy.context.scene
cam=scene.camera; cam.location=(0,-10,1.1); cam.rotation_euler=(Vector((0,0,0.8))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.type='ORTHO'; cam.data.ortho_scale=4.8
scene.render.resolution_x=1000; scene.render.resolution_y=500; scene.cycles.samples=16; scene.render.filepath=path.replace('.blend','_side.png'); bpy.ops.render.render(write_still=True)
