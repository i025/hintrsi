import bpy, math, random
from mathutils import Vector
random.seed(4)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)

def mat(n,c,rough=0.7,metal=0):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal; return m
white=mat('warm white shelving',(0.89,.90,.86)); wall=mat('pale mint plaster',(.68,.79,.69)); trim=mat('white trim',(.91,.92,.88)); floor=mat('ivory tile',(.78,.83,.80)); purple=mat('dusty mauve bed',(.43,.25,.37)); mattress=mat('white quilt',(.93,.92,.91)); grey=mat('chair grey',(.32,.35,.34)); wood=mat('wood tabletop',(.43,.27,.17)); metal=mat('dark bronze',(.24,.22,.19),.35,.55); shade=mat('ivory lamp shade',(.84,.84,.79)); rug=mat('warm beige rug',(.69,.60,.58)); art=mat('blue gray art',(.47,.59,.60)); frame=mat('natural pale wood',(.73,.57,.44)); black=mat('dark markings',(.09,.10,.07)); gold=mat('ochre',(.62,.55,.36))
def box(n,loc,scale,ma,bev=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bev: mod=o.modifiers.new('soft edges','BEVEL'); mod.width=bev; mod.segments=3; o.modifiers.new('weighted normals','WEIGHTED_NORMAL')
 return o
def cyl(n,loc,r,depth,ma,vertices=32):
 bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=depth,location=loc); o=bpy.context.object; o.name=n; o.data.materials.append(ma); return o
def rod(n,a,b,r,ma):
 d=Vector(b)-Vector(a); o=cyl(n,(Vector(a)+Vector(b))/2,r,d.length,ma); o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); return o
def aim(o,p): o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
# room
box('floor',(0,0,-.055),(7,7,.1),floor)
box('back wall',(0,3.15,1.65),(7,.12,3.3),wall)
box('left wall',(-3.45,0,1.65),(.12,6.3,3.3),wall)
box('back baseboard',(0,3.04,.09),(7,.07,.18),trim,.015)
box('left baseboard',(-3.34,0,.09),(.07,6.1,.18),trim,.015)
# floor subtle tile lines
seam=mat('tile grout',(.70,.76,.73))
for x in [i*.52-3.12 for i in range(13)]: box('floor tile joint',(x,0,.002),(.008,6.2,.003),seam)
for y in [i*.52-3.12 for i in range(13)]: box('floor tile joint',(0,y,.003),(6.8,.008,.003),seam)
box('large taupe rug',(-.15,-.70,.012),(4.5,3,.018),rug)
# shelving open cubbies, back wall visible
sx=.72; sy=2.90; bottom=.17; top=2.82; width=3.35; depth=.34
for z in [bottom, .83,1.49,2.15,top]: box('shelf horizontal',(sx,sy,z),(width,depth,.075),white,.009)
for i in range(7):
 x=sx-width/2+i*width/6
 box('shelf upright',(x,sy,(top+bottom)/2),(.065,depth,top-bottom),white,.008)
# bed running left to right
box('mauve platform',(-1.05,-.35,.34),(3.25,1.60,.23),purple,.04)
for x in [-2.42,.30]:
 for y in [-.98,.28]: cyl('bed round foot',(x,y,.16),.105,.30,metal)
box('thick mattress',(-1.08,-.35,.59),(3.06,1.48,.34),mattress,.10)
# quilted stitch effect along exposed side
stitch=mat('mattress stitching',(.80,.80,.80))
for i in range(29):
 x=-2.53+i*.105
 for j in range(2):
  z=.49+j*.10
  rod('quilted mattress seam',(x,-1.097,z),(x+.052,-1.099,z+.045),.004,stitch)
  rod('quilted mattress seam',(x+.052,-1.099,z+.045),(x+.105,-1.097,z),.004,stitch)
# headboard at left
for y in [-1.01,.31]: rod('headboard posts',(-2.72,y,.26),(-2.72,y,1.16),.045,metal)
for z in [.85,1.10]: box('headboard mauve slat',(-2.72,-.35,z),(.09,1.48,.14),purple,.015)
# small wooden bedside table behind bed
box('bedside table top',(-2.22,1.05,.78),(.80,.70,.09),wood,.025)
for x in [-2.54,-1.90]:
 for y in [.79,1.30]: box('bedside table leg',(x,y,.40),(.065,.065,.76),wood,.01)
for i in range(15):
 x=-2.58+i*.05
 box('wood grain stripe',(x,1.05,.828),(.008,.65,.003),frame)
# framed picture on back wall, offset left
box('picture frame backing',(-2.00,3.035,2.05),(.88,.075,1.26),frame,.015)
box('picture blue gray inset',(-2.00,2.989,2.05),(.76,.012,1.13),art)
for x in [-2.41,-1.59]: box('picture vertical frame',(x,2.97,2.05),(.045,.045,1.23),frame,.005)
for z in [1.46,2.64]: box('picture horizontal frame',(-2.0,2.97,z),(.86,.045,.045),frame,.005)
# abstract black blotches on picture
for k in range(65):
 x=random.uniform(-2.31,-1.95); z=random.uniform(2.36,2.51)
 box('abstract dark paint',(x,2.975,z),(random.uniform(.018,.07),.007,random.uniform(.018,.045)),black)
for k in range(18):
 x=-2.04+random.uniform(-.09,.09); z=1.91+random.uniform(-.09,.09)
 o=cyl('abstract spot',(x,2.975,z),random.uniform(.012,.035),.009,black,12); o.rotation_euler[0]=math.pi/2
# floor lamps
def lamp(x,y,h):
 cyl('lamp foot',(x,y,.025),.19,.05,metal); rod('lamp slender stem',(x,y,.04),(x,y,h-.34),.022,metal)
 bpy.ops.mesh.primitive_cone_add(vertices=48,radius1=.27,radius2=.19,depth=.50,location=(x,y,h-.20)); o=bpy.context.object; o.name='tapered fabric lampshade'; o.data.materials.append(shade)
 bpy.ops.object.light_add(type='POINT',location=(x,y,h-.2)); l=bpy.context.object; l.name='lamp glow'; l.data.energy=95; l.data.color=(1,.85,.65); l.data.shadow_soft_size=.35
lamp(-3.02,1.90,2.10); lamp(2.83,1.50,2.18)
# chair foreground, shaped curved shell as mesh
verts=[]; faces=[]
# chair profile: seat slopes up into curved back, transverse strips
profile=[(-.45,.46),(-.18,.46),(.10,.47),(.27,.53),(.32,.68),(.29,.90),(.30,1.08),(.38,1.25),(.48,1.32)]
for y,z in profile:
 for x in [-.37,.37]: verts.append((x,y,z))
for i in range(len(profile)-1): faces.append((2*i,2*i+1,2*i+3,2*i+2))
mesh=bpy.data.meshes.new('chair curved shell mesh'); mesh.from_pydata(verts,[],faces); mesh.update(); chair=bpy.data.objects.new('single curved gray chair',mesh); bpy.context.collection.objects.link(chair); chair.location=(1.86,-1.60,0); chair.data.materials.append(grey)
sol=chair.modifiers.new('shell thickness','SOLIDIFY'); sol.thickness=.07
sub=chair.modifiers.new('rounded shell','SUBSURF'); sub.levels=2
for p in mesh.polygons: p.use_smooth=True
for x in [1.62,2.10]:
 for y in [-1.87,-1.35]: rod('chair leg',(x,y,.46),(x+(.08 if x>1.8 else -.08),y-.06,.03),.022,metal)
# partial desk in immediate foreground
box('white desk corner',(-3.13,-2.42,.74),(1.4,.90,.065),white,.02)
rod('desk leg',(-2.62,-2.20,.73),(-2.55,-2.20,.02),.035,metal)
# lighting and camera
world=bpy.context.scene.world; world.color=(.75,.75,.75)
bpy.ops.object.light_add(type='AREA',location=(0,-2,5)); bpy.context.object.data.energy=500; bpy.context.object.data.shape='DISK'; bpy.context.object.data.size=5
bpy.ops.object.camera_add(location=(4.3,-7.6,5.1)); cam=bpy.context.object; aim(cam,(-.05,.65,1.05)); cam.data.type='PERSP'; cam.data.lens=31; bpy.context.scene.camera=cam
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True
scene.render.resolution_x=640; scene.render.resolution_y=360; scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'; scene.render.image_settings.file_format='PNG'; scene.render.filepath='/app/final.png'
bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
