import bpy, math, random
from mathutils import Vector
random.seed(7)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
def mat(n,c,rough=.65,metal=0):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal; return m
wall=mat('pale lavender walls',(.70,.68,.75)); floor=mat('warm ivory floor',(.78,.75,.75)); white=mat('soft white painted wood',(.9,.9,.89)); blue=mat('pale ice blue upholstery',(.55,.78,.82)); rug=mat('blush pink rug',(.78,.70,.73)); oak=mat('light natural oak',(.69,.45,.32)); dark=mat('blackened bronze',(.09,.06,.055),.35,.55); bronze=mat('mirror bronze frame',(.31,.22,.16),.32,.65); mirror=mat('mirror glass',(.62,.68,.67),.12,.65); navy=mat('painting deep indigo',(.09,.08,.29)); coral=mat('painting coral',(.78,.30,.37)); peach=mat('painting peach',(.97,.62,.43)); tabletop=mat('coffee table brown glass',(.28,.17,.13),.18,.3); streak=mat('table pale streaks',(.65,.47,.38),.23,.2)
def cube(n,loc,scale,ma,bev=0):
 bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bev:
  mod=o.modifiers.new('soft rounded edges','BEVEL'); mod.width=bev; mod.segments=4
  o.modifiers.new('weighted normals','WEIGHTED_NORMAL')
 return o
def cyl(n,loc,r,depth,ma,vertices=32):
 bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=depth,location=loc); o=bpy.context.object; o.name=n; o.data.materials.append(ma); return o
def bar(n,a,b,r,ma):
 d=Vector(b)-Vector(a); mid=(Vector(a)+Vector(b))/2; o=cyl(n,mid,r,d.length,ma,12); o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); return o
# room: back at y=3.0
cube('floor',(0,0,-.08),(6.6,8,.16),floor)
cube('back wall',(0,3.04,1.8),(6.6,.12,3.6),wall)
cube('left wall',(-3.04,0,1.8),(.12,6.2,3.6),wall)
cube('right wall',(3.04,0,1.8),(.12,6.2,3.6),wall)
cube('back baseboard',(0,2.96,.12),(6,.055,.24),white,.015)
cube('left baseboard',(-2.96,0,.12),(.055,6,.24),white,.015)
# circular rug
cyl('round blush rug',(0,-.35,.012),2.12,.025,rug,96)
# sofa against back wall
cube('sofa lower upholstered base',(-.23,2.22,.31),(3.12,.98,.33),blue,.12)
for x in [-1.63,1.17]:
 for y in [1.88,2.56]: bar('sofa small dark foot',(x,y,.05),(x,y,.25),.025,dark)
for x in [-1.68,1.23]: cube('sofa padded arm',(x,2.20,.72),(.25,1.02,.85),blue,.10)
for x in [-1.15,-.23,.69]:
 cube('separate plump seat cushion',(x,2.04,.57),(.91,.78,.28),blue,.15)
 cube('separate plump back cushion',(x,2.57,.97),(.90,.31,.72),blue,.15)
# chaise extension at right
cube('chaise upholstered extension',(.70,1.38,.42),(.95,.92,.25),blue,.12)
for x in [.32,1.08]: bar('chaise foot',(x,1.15,.04),(x,1.15,.31),.018,dark)
# mirror on back wall
cube('mirror outer frame',(-.08,2.955,2.45),(1.10,.08,1.25),bronze,.025)
cube('mirror reflective inset',(-.08,2.904,2.45),(.96,.018,1.11),mirror,.005)
# lamp beside sofa
bar('lamp thin stand',(1.58,2.68,.1),(1.58,2.68,1.58),.025,dark)
cyl('lamp base',(1.58,2.68,.06),.23,.05,dark)
bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=.21, radius2=.16, depth=.42, location=(1.58,2.68,1.65)); bpy.context.object.name='cream tapered lamp shade'; bpy.context.object.data.materials.append(white)
# tall cabinet right side near wall, facing camera
cube('tall cupboard body',(2.25,2.25,1.04),(.72,.65,2.08),white,.025)
for x in [2.07,2.43]:
 cube('cabinet paneled door',(x,1.91,1.04),(.345,.045,1.96),white,.01)
 for z in [.55,1.51]:
  # raised narrow panel
  cube('cabinet inset panel',(x,1.882,z),(.27,.012,.82),floor,.006)
  cube('cabinet inner face',(x,1.873,z),(.24,.01,.78),white,.005)
for x in [2.18,2.32]: cube('cupboard handle',(x,1.85,1.03),(.022,.04,.16),white,.009)
# open shelving unit at right, facing left/front
# shelves arranged along y, with front towards camera
cube('bookcase rear',(2.91,-.15,1.65),(.12,3.15,3.3),oak)
for y in [-1.70,-.67,.36,1.39]: cube('bookcase upright',(2.60,y,1.65),(.65,.07,3.3),oak,.01)
for z in [.08,.72,1.36,2.00,2.64,3.28]: cube('bookcase shelf',(2.60,-.15,z),(.68,3.15,.07),oak,.01)
# low media console along left
cube('low white console top',(-2.52,-.65,.72),(.73,2.55,.10),white,.015)
cube('low white console bottom',(-2.52,-.65,.13),(.73,2.55,.09),white,.015)
for y in [-1.90,-.65,.60]: cube('console divider',(-2.52,y,.42),(.72,.08,.59),white,.01)
# coffee table top centered foreground
cube('coffee table dark rim',(0,-.55,.49),(1.68,1.22,.09),dark,.012)
cube('coffee table striped glass top',(0,-.55,.542),(1.60,1.14,.025),tabletop,.006)
# streaks on surface diagonally oriented across tabletop
for i in range(25):
 x=-.76+i*.065
 # line direction in XY, clipped to rectangular surface
 y0=-1.105; y1=.005; shift=.35
 xa=x; xb=x+shift
 if xb>.79: y1=y0+(y1-y0)*(.79-xa)/shift; xb=.79
 if xa<=.79 and y1>y0: bar('diagonal marble vein',(xa,y0,.558),(xb,y1,.558),random.choice([.003,.005,.009]),streak)
for x in [-.72,.72]:
 for y in [-1.05,-.05]: bar('table slender leg',(x,y,.03),(x,y,.48),.018,dark)
# framed abstract painting on left wall
cube('art dark frame',(-2.96,1.35,2.15),(.07,2.15,1.70),dark,.012)
cube('art indigo canvas',(-2.915,1.35,2.15),(.018,2.06,1.61),navy)
# abstract shapes polygon on vertical yz plane
def poly(n,coords,ma):
 mesh=bpy.data.meshes.new(n); mesh.from_pydata([(-2.90,y,z) for y,z in coords],[],[list(range(len(coords)))]); mesh.materials.append(ma); ob=bpy.data.objects.new(n,mesh); bpy.context.collection.objects.link(ob)
poly('abstract pink landform',[(.31,2.94),(.31,1.72),(.50,1.80),(.65,1.86),(.81,1.98),(1.04,2.00),(1.23,2.16),(1.40,2.20),(1.50,2.35),(1.40,2.56),(1.55,2.72),(1.45,2.94)],coral)
poly('abstract peach accent',[(.31,1.72),(.50,1.80),(.65,1.86),(.81,1.98),(1.04,2.00),(1.23,2.16),(1.4,2.20),(1.50,2.35),(1.42,2.40),(1.33,2.29),(1.19,2.27),(1.05,2.12),(.84,2.10),(.66,1.99),(.48,1.94),(.31,1.87)],peach)
# illumination
world=bpy.context.scene.world or bpy.data.worlds.new('World'); bpy.context.scene.world=world; world.use_nodes=True; world.node_tree.nodes['Background'].inputs[0].default_value=(.8,.82,.9,1); world.node_tree.nodes['Background'].inputs[1].default_value=.7
def area(loc,power,size,target):
 bpy.ops.object.light_add(type='AREA', location=loc); o=bpy.context.object; o.data.energy=power; o.data.shape='DISK'; o.data.size=size; o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
area((0,-2,5.5),650,5,(0,1,0)); area((-2,-1,3.5),250,3,(0,1,1))
# camera
bpy.ops.object.camera_add(location=(0,-6.5,4.15)); cam=bpy.context.object; cam.name='Reference camera'; cam.rotation_euler=(Vector((0,1.05,.85))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.lens=29; bpy.context.scene.camera=cam
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True; scene.render.threads_mode='FIXED'; scene.render.threads=8
scene.render.resolution_x=640; scene.render.resolution_y=360; scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'; scene.render.image_settings.file_format='PNG'; scene.render.filepath='/app/final.png'
bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
