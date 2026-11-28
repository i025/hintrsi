import bpy, math, random
from mathutils import Vector
random.seed(8)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)

def mat(n,c,rough=.7,metal=0):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal; return m
wall=mat('pale lavender plaster',(0.72,.69,.76)); floor=mat('warm ivory floor',(.78,.75,.75)); white=mat('warm white painted furniture',(.9,.88,.87)); blue=mat('pale ice blue upholstery',(.59,.80,.84)); blue2=mat('sofa cushion blue',(.66,.85,.88)); wood=mat('light peach oak',(.72,.48,.34)); dark=mat('dark bronze',(.12,.10,.10),.34,.5); mirror=mat('muted mirror',(.55,.60,.59),.15,.55); rug=mat('pale blush rug',(.78,.68,.71)); shade=mat('lampshade ivory',(.87,.85,.83)); table=mat('brown polished tabletop',(.30,.19,.16),.24); stripe=mat('cream streaks',(.83,.67,.57),.4); navy=mat('art deep indigo',(.12,.12,.34)); coral=mat('art rose',(.8,.36,.45)); pink=mat('art salmon',(.93,.53,.48)); gold=mat('art peach',(.97,.72,.48))
def cube(n,loc,scale,ma,bev=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 if ma:o.data.materials.append(ma)
 if bev:
  mod=o.modifiers.new('soft rounded edges','BEVEL'); mod.width=bev; mod.segments=4
  mod=o.modifiers.new('weighted normals','WEIGHTED_NORMAL'); mod.keep_sharp=True
 return o
def cyl(n,loc,r,depth,ma,vertices=32):
 bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=depth,location=loc); o=bpy.context.object; o.name=n; o.data.materials.append(ma); return o
def rod(n,a,b,r,ma):
 v=Vector(b)-Vector(a); o=cyl(n,(Vector(a)+Vector(b))/2,r,v.length,ma,16); o.rotation_euler=v.to_track_quat('Z','Y').to_euler(); return o
def poly(n,pts,ma):
 mesh=bpy.data.meshes.new(n); mesh.from_pydata(pts,[],[list(range(len(pts)))]); mesh.materials.append(ma); ob=bpy.data.objects.new(n,mesh); bpy.context.collection.objects.link(ob); return ob
# room shell
cube('floor',(0,0,-.055),(5.4,7.2,.11),floor)
cube('back wall',(0,3.05,1.65),(5.4,.12,3.3),wall)
cube('left wall',(-2.65,0,1.65),(.12,6.1,3.3),wall)
cube('right wall',(2.65,0,1.65),(.12,6.1,3.3),wall)
cube('back skirting',(0,2.96,.09),(5.2,.07,.18),white,.01)
cube('left skirting',(-2.56,0,.09),(.07,5.9,.18),white,.01)
# sofa against back
cube('sofa lower base',(-.26,2.24,.31),(2.65,.89,.25),blue,.12)
for x in [-1.44,.92]:
 for y in [1.92,2.55]: rod('sofa short tapered leg',(x,y,.05),(x,y,.22),.027,dark)
for x in [-1.60,1.08]: cube('sofa padded arm',(x,2.25,.67),(.22,.94,.87),blue,.09)
for x in [-1.13,-.26,.61]:
 cube('separate back cushion',(x,2.57,.94),(.85,.27,.69),blue2,.14)
 cube('separate seat cushion',(x,2.08,.52),(.85,.81,.22),blue2,.10)
# chaise extension
cube('chaise extension cushion',(.61,1.42,.48),(.88,.68,.20),blue2,.10)
for x in [.30,.93]: rod('chaise leg',(x,1.25,.05),(x,1.25,.40),.023,dark)
# back wall mirror
cube('mirror dark outer frame',(-.18,2.965,2.29),(.91,.065,1.16),dark,.012)
cube('mirror wood inner frame',(-.18,2.923,2.29),(.84,.025,1.09),wood,.008)
cube('mirror glass',(-.18,2.905,2.29),(.75,.012,1.0),mirror,.005)
# lamp
rod('floor lamp stem',(1.37,2.70,.04),(1.37,2.70,1.55),.018,dark)
cyl('lamp foot',(1.37,2.70,.035),.18,.04,dark)
bpy.ops.mesh.primitive_cone_add(vertices=48,radius1=.18,radius2=.135,depth=.38,location=(1.37,2.70,1.54)); bpy.context.object.name='white conical lampshade'; bpy.context.object.data.materials.append(shade)
# tall white cabinet right of sofa
cube('white storage cabinet',(1.93,2.43,.99),(.65,.51,1.98),white,.025)
for z in [.51,1.50]:
 for x in [1.77,2.09]:
  cube('cabinet inset door',(x,2.158,z),(.29,.026,.89),white,.009)
  cube('door inset panel',(x,2.139,z),(.23,.015,.80),floor,.005)
# pink round rug
cyl('round blush rug',(0,.12,.014),1.75,.025,rug,96)
# coffee table foreground
cube('coffee table dark perimeter',(-.08,-.35,.44),(1.45,1.87,.09),dark,.015)
cube('coffee table brown surface',(-.08,-.35,.49),(1.40,1.82,.025),table,.008)
for x in [-.72,.56]:
 for y in [-1.18,.48]: rod('table leg',(x,y,.03),(x,y,.42),.025,dark)
# narrow irregular diagonal streaks, clipped to top rectangle
xmin,xmax=-.77,.61; ymin,ymax=-1.25,.55
for i in range(55):
 # stripes x = slope*y+intercept
 slope=.37; b=random.uniform(xmin-.3,xmax+.5); w=random.uniform(.003,.025)
 pts=[]
 for y in [ymin,ymax]:
  x=b+slope*y; pts.append((max(xmin,min(xmax,x)),y))
 (x1,y1),(x2,y2)=pts
 if (x1 in (xmin,xmax)) and (x2 in (xmin,xmax)) and x1==x2: continue
 poly('fine tabletop diagonal streak',[(x1,y1,.507),(min(xmax,x1+w),y1,.507),(min(xmax,x2+w),y2,.507),(x2,y2,.507)],stripe)
# left low open console
cube('console top',(-2.30,-.55,.65),(.57,2.25,.08),white,.008)
cube('console bottom',(-2.30,-.55,.08),(.57,2.25,.08),white,.008)
for y in [-1.63,-.55,.53]: cube('console divider',(-2.30,y,.36),(.57,.07,.55),white,.008)
# tall oak bookshelf right foreground facing camera/front left
# back and outer vertical panels, shelves
cube('oak bookshelf back',(2.54,-.10,1.42),(.10,2.35,2.84),wood)
for y in [-1.26,-.10,1.06]: cube('oak bookcase vertical divider',(2.22,y,1.42),(.66,.09,2.84),wood,.008)
for z in [.08,.78,1.48,2.18,2.80]: cube('oak bookcase horizontal shelf',(2.22,-.10,z),(.66,2.36,.09),wood,.008)
# abstract picture on left wall
cube('art frame',(-2.575,1.0,2.06),(.07,1.77,1.56),dark,.01)
cube('art indigo field',(-2.53,1.0,2.06),(.025,1.68,1.47),navy)
# textured coral continent-like polygon in plane x const
poly('abstract coral shape',[(-2.51,.20,2.70),(-2.51,.90,2.75),(-2.51,1.08,2.55),(-2.51,1.02,2.39),(-2.51,1.31,2.25),(-2.51,1.10,2.08),(-2.51,.87,2.04),(-2.51,.72,1.87),(-2.51,.43,1.92),(-2.51,.22,2.08)],coral)
for j in range(28):
 y=random.uniform(.2,1.0); z=random.uniform(2.0,2.7); s=random.uniform(.025,.08)
 poly('abstract gold fleck',[(-2.50,y,z),(-2.50,y+s,z+.02),(-2.50,y+s*.5,z+s),(-2.50,y-.02,z+s*.5)],gold if j%2 else pink)
# illumination
world=bpy.context.scene.world or bpy.data.worlds.new('World'); bpy.context.scene.world=world; world.use_nodes=True; world.node_tree.nodes['Background'].inputs[0].default_value=(.78,.76,.83,1); world.node_tree.nodes['Background'].inputs[1].default_value=.8
def area(n,loc,power,size,target):
 bpy.ops.object.light_add(type='AREA',location=loc); o=bpy.context.object; o.name=n; o.data.energy=power; o.data.shape='DISK'; o.data.size=size; o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
area('large ceiling softbox',(-.6,-.6,3.9),520,4.5,(0,1,0)); area('front fill',(0,-4,2.8),250,3,(0,1,1))
# camera
bpy.ops.object.camera_add(location=(-.15,-4.85,2.95)); cam=bpy.context.object; cam.name='Camera'; cam.rotation_euler=(Vector((0,1.50,.80))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.lens=23; bpy.context.scene.camera=cam
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.samples=32; sc.cycles.use_denoising=True; sc.render.resolution_x=640; sc.render.resolution_y=360; sc.render.resolution_percentage=100; sc.render.image_settings.file_format='PNG'; sc.render.filepath='/app/final.png'; sc.view_settings.view_transform='AgX'; sc.render.film_transparent=False
bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
