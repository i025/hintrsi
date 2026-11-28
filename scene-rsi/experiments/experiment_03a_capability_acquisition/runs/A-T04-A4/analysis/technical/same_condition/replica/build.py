import bpy, math, random
from mathutils import Vector
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
random.seed(5)
def mat(n,c,rough=.7,metal=0):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal; return m
def box(n,loc,dim,ma,bevel=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=n; o.dimensions=dim; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bevel:
  mod=o.modifiers.new('Soft rounded edges','BEVEL'); mod.width=bevel; mod.segments=4; o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
 return o
def cyl(n,loc,r,depth,ma,vertices=48):
 bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=depth,location=loc); o=bpy.context.object; o.name=n; o.data.materials.append(ma); return o
def area(n,loc,power,size,target):
 bpy.ops.object.light_add(type='AREA',location=loc); o=bpy.context.object; o.name=n; o.data.energy=power; o.data.shape='DISK'; o.data.size=size; o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
wall=mat('Pale lavender plaster',(.69,.67,.75)); floor=mat('Warm ivory floor',(.83,.80,.80)); white=mat('Cabinet white',(.91,.90,.91)); blue=mat('Powder blue upholstery',(.57,.80,.84)); rug=mat('Pale blush rug',(.78,.70,.75)); wood=mat('Light maple',(.67,.40,.27)); dark=mat('Dark bronze',(.12,.09,.08),.4,.5); glass=mat('Smoked reflective glass',(.30,.23,.22),.12,.45); mirror=mat('Mirror silver',(.56,.62,.61),.12,.7); black=mat('Black lamp stem',(.06,.055,.065),.4,.3); shade=mat('Lamp linen',(.89,.86,.84)); navy=mat('Artwork blue',(.075,.055,.28)); pink=mat('Artwork coral',(.78,.31,.39)); peach=mat('Artwork peach',(.95,.61,.43))
# room
box('Floor',(0,0,-.06),(5.7,7,.12),floor)
box('Back wall',(0,2.18,1.85),(5.7,.12,3.7),wall)
box('Left wall',(-2.48,-.5,1.85),(.12,5.5,3.7),wall)
box('Back baseboard',(0,2.08,.10),(4.9,.05,.20),white,.012)
box('Left baseboard',(-2.40,-.4,.10),(.05,4.9,.20),white,.012)
# circular rug
cyl('Round blush rug',(0,-.93,.009),1.70,.018,rug,128)
# couch body and upholstered cushions
box('Sofa lower base',(-.20,1.37,.34),(2.72,.88,.25),blue,.12)
box('Sofa back',(-.20,1.82,.83),(2.70,.20,1.08),blue,.10)
for x in [-1.03,-.20,.63]:
 box('Separate back cushion',(x,1.67,.92),(.81,.25,.64),blue,.13)
 box('Separate seat cushion',(x,1.28,.57),(.80,.82,.24),blue,.105)
for x in [-1.59,1.19]: box('Sofa arm',(x,1.39,.71),(.20,1.02,.80),blue,.07)
for x in [-1.35,.98]:
 for y in [1.08,1.72]: box('Sofa foot',(x,y,.12),(.055,.055,.24),dark,.01)
# chaise ottoman in front of right seat
box('Chaise extension',(.63,.60,.48),(.86,.75,.22),blue,.10)
for x in [.32,.96]: box('Chaise leg',(x,.37,.16),(.035,.035,.30),dark,.01)
# mirror behind sofa
box('Mirror frame',(-.08,2.085,2.42),(.94,.055,1.27),wood,.015)
box('Mirror glass',(-.08,2.048,2.42),(.83,.012,1.16),mirror,.005)
# cabinet against back right wall, front towards camera
box('Tall cabinet',(1.70,1.70,1.03),(.62,.60,2.05),white,.025)
for x in [1.545,1.855]:
 box('Cabinet door',(x,1.385,1.04),(.29,.026,1.96),white,.012)
 for z in [.54,1.53]:
  box('Inset door panel',(x,1.366,z),(.235,.012,.83),white,.012)
for x in [1.66,1.74]: box('Small cabinet handle',(x,1.345,1.0),(.018,.035,.11),white,.006)
# standing lamp
cyl('Lamp foot',(1.16,1.84,.035),.20,.04,black); cyl('Lamp stem',(1.16,1.84,.85),.018,1.62,black)
bpy.ops.mesh.primitive_cone_add(vertices=64,radius1=.20,radius2=.14,depth=.37,location=(1.16,1.84,1.70)); bpy.context.object.name='Cream tapered lampshade'; bpy.context.object.data.materials.append(shade)
cyl('Shade top rim',(1.16,1.84,1.89),.14,.015,black)
# large open maple bookcase on right, facing left/front
for x in [2.00,2.61]: box('Bookcase side',(x,-.32,1.60),(.075,2.8,3.2),wood,.008)
for z in [.06,.70,1.34,1.98,2.62,3.18]: box('Bookcase horizontal shelf',(2.30,-.32,z),(.65,2.8,.07),wood,.006)
for y in [-1.70,-.76,.18,1.10]: box('Bookcase vertical divider',(2.30,y,1.61),(.65,.065,3.15),wood,.006)
# low white console left foreground
box('Console top',(-2.04,-1.15,.57),(.68,2.16,.08),white,.015)
box('Console bottom',(-2.04,-1.15,.05),(.68,2.16,.08),white,.01)
for y in [-2.18,-1.15,-.12]: box('Console dividers',(-2.04,y,.31),(.68,.07,.52),white,.01)
# low rectangular coffee table, glass inset and frame
box('Coffee table glass',(0,-1.45,.37),(1.30,1.55,.045),glass,.015)
for x in [-.67,.67]: box('Table long border',(x,-1.45,.38),(.035,1.59,.045),dark,.006)
for y in [-2.23,-.67]: box('Table short border',(0,y,.38),(1.37,.035,.045),dark,.006)
for x in [-.59,.59]:
 for y in [-2.14,-.76]: box('Table leg',(x,y,.19),(.035,.035,.36),dark,.006)
# abstract picture on left wall
box('Picture frame',(-2.402,.53,1.95),(.045,1.70,1.54),dark,.008)
box('Blue abstract canvas',(-2.371,.53,1.95),(.01,1.64,1.48),navy)
# irregular abstract shapes on vertical wall
def patch(name,coords,ma):
 mesh=bpy.data.meshes.new(name); mesh.from_pydata([(-2.36,y,z) for y,z in coords],[],[list(range(len(coords)))]); mesh.materials.append(ma); o=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(o)
patch('Coral abstract shape',[(.05,2.68),(.86,2.68),(1.18,2.38),(1.02,2.13),(.82,2.07),(.65,1.85),(.43,1.89),(.27,2.09),(-.05,2.17),(-.20,2.45)],pink)
patch('Peach abstract accent',[(.60,1.88),(.76,1.94),(.87,2.08),(1.02,2.10),(1.12,2.28),(1.20,2.38),(1.14,2.15),(.99,2.00),(.84,1.95),(.73,1.82)],peach)
# lights and camera
area('Large soft ceiling light',(-1,-1,4.5),500,5,(0,1,0)); area('Front fill',(1,-4,3.6),280,4,(0,1,1))
world=bpy.context.scene.world; world.color=(.75,.75,.75)
bpy.ops.object.camera_add(location=(0,-5.0,3.0)); cam=bpy.context.object; cam.name='Camera'; cam.rotation_euler=(Vector((0,1.0,.85))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.lens=27; bpy.context.scene.camera=cam
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.samples=32; sc.cycles.use_denoising=True; sc.render.threads_mode='FIXED'; sc.render.threads=8; sc.render.resolution_x=640; sc.render.resolution_y=360; sc.render.resolution_percentage=100
sc.view_settings.view_transform='AgX'; sc.render.image_settings.file_format='PNG'; sc.render.filepath='/app/final.png'; bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
