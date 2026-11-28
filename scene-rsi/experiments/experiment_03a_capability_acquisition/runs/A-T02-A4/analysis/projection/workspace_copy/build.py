import bpy, math, random
from mathutils import Vector
random.seed(4)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)

def mat(n,c,rough=.75,metal=0):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal; return m
white=mat('Warm white',(0.87,.89,.85)); wall=mat('Pale mint walls',(.72,.82,.73)); trim=mat('White trim',(.92,.92,.86)); mauve=mat('Dusty mauve bed',(.48,.30,.42)); mattress=mat('Mattress ivory',(.94,.93,.92)); wood=mat('Table wood',(.42,.26,.16)); gold=mat('Lamp stems',(.32,.27,.21),.35,.5); shade=mat('Lampshade',(.75,.75,.73)); chairmat=mat('Chair grey',(.29,.32,.30)); rugmat=mat('Rug warm blush',(.70,.62,.59)); tile=mat('Tile',(.80,.85,.81)); dark=mat('Dark doorway',(.012,.014,.013)); frame=mat('Picture frame pale wood',(.72,.57,.44)); art=mat('Art blue',(.48,.60,.61)); black=mat('Art black',(.06,.07,.05)); cream=mat('Art cream',(.85,.83,.71))
def cube(n,loc,scale,ma,bevel=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bevel:
  mod=o.modifiers.new('Soft edges','BEVEL'); mod.width=bevel; mod.segments=3; o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
 return o
def cyl(n,loc,r,depth,ma,vertices=24):
 bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=depth,location=loc); o=bpy.context.object;o.name=n;o.data.materials.append(ma);return o
def beam(n,a,b,r,ma):
 d=Vector(b)-Vector(a); o=cyl(n,(Vector(a)+Vector(b))/2,r,d.length,ma);o.rotation_euler=d.to_track_quat('Z','Y').to_euler();return o
# room
cube('Floor',(0,0,-.06),(6.8,7,.12),tile)
cube('Back wall',(0,3.05,1.75),(6.8,.12,3.5),wall)
cube('Left wall',(-3.4,0,1.75),(.12,6.1,3.5),wall)
cube('Right wall',(3.4,0,1.75),(.12,6.1,3.5),wall)
cube('Back baseboard',(0,2.96,.10),(6.8,.06,.2),trim);cube('Right baseboard',(3.31,0,.10),(.06,6,.2),trim)
# tile grout lines
line=mat('Grout',(.69,.76,.72))
for x in [i*.5 for i in range(-6,7)]: cube('Floor grout',(x,0,.003),(.008,6,.005),line)
for y in [i*.5 for i in range(-6,7)]: cube('Floor grout',(0,y,.004),(6.8,.008,.005),line)
# back shelf, grid open
sx=.95; sy=2.73; W=3.05; H=2.65; z0=.12; D=.34
for x in [sx-W/2+i*W/6 for i in range(7)]: cube('Shelf vertical divider',(x,sy,z0+H/2),(.065,D,H),white)
for z in [z0+i*H/4 for i in range(5)]: cube('Shelf horizontal shelf',(sx,sy,z),(W+.06,D,.065),white)
# bed axis x
cube('Bed platform',(-1.0,-.45,.33),(3.05,1.75,.20),mauve,.035)
cube('Thick white mattress',(-1.0,-.45,.58),(2.94,1.63,.36),mattress,.10)
for x in [-2.25,.25]:
 for y in [-1.12,.20]: cyl('Bed round foot',(x,y,.17),.11,.32,gold)
# headboard at left
for y in [-1.14,.23]: cube('Headboard post',(-2.53,y,.83),(.08,.08,1.2),gold)
for z in [.89,1.18]: cube('Headboard slat',(-2.53,-.45,z),(.08,1.46,.16),mauve,.015)
# rug
cube('Large blush rug',(.10,-.8,.012),(3.5,2.9,.018),rugmat)
# side table at back left
cube('Bedside table top',(-2.1,1.15,.72),(.84,.65,.09),wood,.025)
for x in [-2.43,-1.77]:
 for y in [.91,1.39]: cube('Side table leg',(x,y,.36),(.06,.06,.72),wood)
# wood grain thin lines
for i in range(18):
 x=-2.5+i*.046; o=cube('Tabletop grain',(x,1.15,.769),(.008,.59,.003),frame)
# wall art
cube('Picture outer frame',(-2.15,2.95,2.10),(.90,.07,1.35),frame,.015)
cube('Picture artwork',(-2.15,2.90,2.10),(.78,.018,1.23),art)
for i in range(35):
 x=random.uniform(-2.48,-2.12); z=random.uniform(2.46,2.62); cube('Artwork dark mark',(x,2.886,z),(random.uniform(.02,.08),.008,random.uniform(.02,.06)),black)
for x,z,r in [(-2.17,1.95,.09),(-2.28,1.81,.06)]:
 o=cyl('Abstract art circle',(x,2.88,z),r,.01,black);o.rotation_euler[0]=math.pi/2
cube('Artwork white patch',(-2.42,2.88,2.20),(.19,.01,.15),cream)
# lamps
def lamp(x,y,h):
 cyl('Lamp base',(x,y,.035),.23,.05,gold);cyl('Lamp slender pole',(x,y,h/2),.025,h,gold)
 bpy.ops.mesh.primitive_cone_add(vertices=48,radius1=.30,radius2=.20,depth=.49,location=(x,y,h-.1));o=bpy.context.object;o.name='Tapered fabric lampshade';o.data.materials.append(shade)
 bpy.ops.object.light_add(type='POINT',location=(x,y,h-.12));bpy.context.object.data.energy=75; bpy.context.object.data.color=(1,.88,.68);bpy.context.object.data.shadow_soft_size=.35
lamp(-2.86,1.65,2.02);lamp(2.85,1.65,2.12)
# foreground chair sculpted shell via mesh curved profile
verts=[]; faces=[]
profile=[(-.55,.46),(-.28,.49),(.05,.48),(.25,.52),(.32,.70),(.35,1.05),(.42,1.26),(.55,1.34)]
for y,z in profile:
 for x in [-.42,.42]: verts.append((x+1.70,y-2.0,z))
for i in range(len(profile)-1): faces.append((2*i,2*i+1,2*i+3,2*i+2))
mesh=bpy.data.meshes.new('Curved chair shell mesh');mesh.from_pydata(verts,[],faces);mesh.update();o=bpy.data.objects.new('Molded grey chair',mesh);bpy.context.collection.objects.link(o);o.data.materials.append(chairmat);mod=o.modifiers.new('Smooth shell','SUBSURF');mod.levels=3;mod=o.modifiers.new('Shell thickness','SOLIDIFY');mod.thickness=.045
for x in [1.42,1.98]:
 for y in [-2.35,-1.75]: beam('Chair leg',(x,y,.05),(x,y,.49),.025,gold)
# dark doorway edge far right
cube('Dark door opening',(3.31,-.2,1.30),(.03,1.15,2.6),dark)
# foreground white desk corner
cube('Desk corner',(-3.0,-2.75,.72),(1.25,.9,.08),white,.015)
# lighting
world=bpy.context.scene.world;world.color=(.7,.7,.7);world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.75,.80,.76,1);world.node_tree.nodes['Background'].inputs[1].default_value=.8
bpy.ops.object.light_add(type='AREA',location=(0,-2,4.8));bpy.context.object.data.energy=550;bpy.context.object.data.shape='DISK';bpy.context.object.data.size=5
# camera
bpy.ops.object.camera_add(location=(0,-6.8,4.25));cam=bpy.context.object;cam.rotation_euler=(Vector((0,1.0,1.15))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=34;bpy.context.scene.camera=cam
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True;scene.render.threads_mode='FIXED';scene.render.threads=8
scene.render.resolution_x=640;scene.render.resolution_y=360;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'
scene.render.image_settings.file_format='PNG';scene.render.filepath='/app/final.png'
bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend');bpy.ops.render.render(write_still=True)
