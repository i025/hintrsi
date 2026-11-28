import bpy, math, random
from mathutils import Vector
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
random.seed(4)
def mat(n,c,metal=0,rough=.65):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Metallic'].default_value=metal; p.inputs['Roughness'].default_value=rough; return m
wall=mat('pale lavender walls',(.72,.70,.78)); white=mat('warm white',(.91,.90,.89)); floor=mat('floor',(.77,.74,.76)); blue=mat('powder blue upholstery',(.59,.81,.85)); wood=mat('light oak',(.72,.49,.34)); dark=mat('dark bronze',(.12,.09,.08),.55); mirror=mat('mirror',(.55,.61,.62),.8,.16); pink=mat('pale blush rug',(.81,.72,.76)); black=mat('lamp black',(.045,.04,.04)); glass=mat('coffee table smoked glass',(.35,.22,.19),.4,.2); navy=mat('art deep indigo',(.12,.10,.36)); coral=mat('art coral',(.88,.40,.47)); cream=mat('art gold',(.97,.66,.41))
def box(n,loc,scale,ma,bev=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bev:
  mod=o.modifiers.new('soft edges','BEVEL'); mod.width=bev; mod.segments=4; o.modifiers.new('weighted normals','WEIGHTED_NORMAL')
 return o
def cyl(n,loc,r,depth,ma,verts=32):
 bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=depth,location=loc); o=bpy.context.object; o.name=n; o.data.materials.append(ma); return o
def beam(n,a,b,r,ma):
 d=Vector(b)-Vector(a); o=cyl(n,(Vector(a)+Vector(b))/2,r,d.length,ma); o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); return o
# room back y=2.4, left x=-2.5
box('floor',(0,0,-.07),(5.4,6,.14),floor)
box('back wall',(0,2.45,1.65),(5.3,.12,3.3),wall)
box('left wall',(-2.55,0,1.65),(.12,5,3.3),wall)
box('back skirting',(0,2.35,.1),(5.05,.06,.2),white,.015)
box('left skirting',(-2.46,0,.1),(.06,4.8,.2),white,.015)
# sofa, back wall
box('sofa base',(-.16,1.54,.28),(3.18,.98,.31),blue,.13)
box('sofa back',(-.16,1.99,.83),(3.12,.25,1.12),blue,.13)
for x in [-1.67,1.35]: box('sofa arm',(x,1.51,.65),(.24,1.04,.87),blue,.09)
for x in [-1.14,-.16,.82]:
 box('seat cushion',(x,1.36,.52),(.94,.89,.23),blue,.12)
 box('back cushion',(x,1.84,.99),(.94,.30,.68),blue,.14)
for x in [-1.42,1.14]:
 for y in [1.2,1.9]: cyl('sofa foot',(x,y,.09),.035,.18,dark)
box('chaise extension',(.82,.69,.44),(.96,.68,.20),blue,.11)
for x in [.48,1.16]: cyl('chaise foot',(x,.43,.13),.025,.2,dark)
# mirror centered on rear wall
box('mirror frame',(-.10,2.365,2.31),(1.04,.055,1.15),wood,.018)
box('mirror inset',(-.10,2.325,2.31),(.94,.02,1.05),mirror,.003)
# floor lamp
cyl('lamp base',(1.65,1.93,.035),.18,.05,black)
beam('lamp stem',(1.65,1.93,.06),(1.65,1.93,1.72),.018,black)
bpy.ops.mesh.primitive_cone_add(vertices=48,radius1=.22,radius2=.15,depth=.38,location=(1.65,1.93,1.68)); bpy.context.object.name='white tapered lampshade'; bpy.context.object.data.materials.append(white)
# cabinet right rear, facing camera
box('cabinet carcass',(2.03,1.7,1.03),(.68,.58,2.06),white,.025)
for x in [1.86,2.20]:
 box('cabinet door',(x,1.394,1.04),(.31,.03,1.96),white,.012)
 for z in [.57,1.53]: box('door inset panel',(x,1.372,z),(.24,.012,.83),wall,.009)
 for z in [.57,1.53]: box('door inner face',(x,1.361,z),(.21,.012,.79),white,.006)
# rug
cyl('round blush rug',(0,-.65,.015),1.9,.025,pink,96)
# low left console
box('console top',(-1.98,-.75,.53),(.76,2.0,.09),white,.015)
box('console bottom',(-1.98,-.75,.08),(.76,2.0,.08),white,.01)
for y in [-1.7,-.75,.2]: box('console divider',(-1.98,y,.30),(.74,.06,.45),white,.01)
# large right shelving unit side on right wall, along y
for x in [2.27,2.93]: box('shelf side',(x,-.66,1.45),(.08,2.85,2.9),wood,.012)
for y in [-2.04,-1.1,-.16,.72]: box('shelf vertical partition',(2.6,y,1.45),(.66,.07,2.9),wood,.01)
for z in [.07,.68,1.29,1.90,2.51,2.88]: box('shelf horizontal board',(2.6,-.66,z),(.72,2.82,.075),wood,.009)
# coffee table
box('table top',(.05,-1.04,.49),(1.45,1.10,.08),dark,.015)
box('smoked reflective tabletop',(.05,-1.04,.54),(1.37,1.02,.025),glass,.008)
for x in [-.60,.70]:
 for y in [-1.5,-.58]: beam('table leg',(x,y,.48),(x,y,.04),.018,dark)
# thin tabletop decorative diagonal streaks
for i in range(8):
 x=-.57+i*.17
 beam('table reflection stripe',(x,-1.50,.558),(min(x+.45,.70),-.59,.558),.005,white)
# art on left wall, facing inward
box('art frame',(-2.47,.45,2.0),(.05,1.75,1.4),dark,.01)
box('art canvas',(-2.435,.45,2.0),(.02,1.68,1.33),navy)
# abstract irregular patches in plane x constant
for j,(cy,cz,ry,rz,ma) in enumerate([(.25,2.18,.55,.56,coral),(.05,2.34,.42,.38,cream),(.18,2.28,.39,.37,coral)]):
 verts=[(-2.42,cy,cz)]; N=28
 for i in range(N):
  a=2*math.pi*i/N; f=random.uniform(.82,1.15); verts.append((-2.42,cy+ry*math.cos(a)*f,cz+rz*math.sin(a)*f))
 faces=[(0,i+1,(i+1)%N+1) for i in range(N)]; me=bpy.data.meshes.new('abstract patch'); me.from_pydata(verts,[],faces); ob=bpy.data.objects.new('painted abstract shape',me); bpy.context.collection.objects.link(ob); ob.data.materials.append(ma)
# lighting
world=bpy.context.scene.world; world.color=(.65,.65,.65); world.use_nodes=True; world.node_tree.nodes['Background'].inputs[0].default_value=(.78,.77,.83,1); world.node_tree.nodes['Background'].inputs[1].default_value=.8
def area(loc,power,size,target):
 bpy.ops.object.light_add(type='AREA',location=loc); o=bpy.context.object; o.data.energy=power; o.data.shape='DISK'; o.data.size=size; o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
area((-.5,-1,4.7),650,5,(0,1,0)); area((0,-3,3),300,4,(0,1,1))
# camera
bpy.ops.object.camera_add(location=(0,-4.8,3.35)); cam=bpy.context.object; cam.rotation_euler=(Vector((0,1.0,.75))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.lens=27; bpy.context.scene.camera=cam
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True; scene.render.threads_mode='FIXED'; scene.render.threads=8
scene.render.resolution_x=640; scene.render.resolution_y=360; scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'; scene.render.image_settings.file_format='PNG'; scene.render.filepath='/app/final.png'
bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
