import bpy, math, random
from mathutils import Vector
random.seed(4)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)

def mat(n,c,rough=0.7,metal=0):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal; return m
white=mat('Warm white',(0.88,.89,.85)); wall=mat('Pale mint walls',(.72,.82,.75)); floor=mat('Ivory tile',(.82,.84,.80)); grout=mat('Tile grout',(.63,.72,.70)); mauve=mat('Dusty mauve bed',(.48,.29,.42)); mattress=mat('White mattress',(.94,.94,.92)); silver=mat('Brushed metal',(.48,.49,.47),.3,.65); dark=mat('Dark bronze',(.17,.14,.13),.5,.4); rug=mat('Blush rug',(.72,.63,.61)); chairmat=mat('Charcoal chair',(.18,.21,.20)); wood=mat('Table wood',(.45,.28,.18)); frame=mat('Pale wood frame',(.67,.50,.39)); art=mat('Blue grey artwork',(.47,.61,.62)); black=mat('Artwork dark markings',(.06,.08,.06)); gold=mat('Artwork ochre',(.55,.49,.30))
def cube(n,loc,scale,ma,bev=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bev: mod=o.modifiers.new('Soft edges','BEVEL'); mod.width=bev; mod.segments=3; o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
 return o
def cyl(n,a,b,r,ma,vertices=20):
 d=Vector(b)-Vector(a); mid=(Vector(a)+Vector(b))/2; bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=r, depth=d.length, location=mid); o=bpy.context.object; o.name=n; o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); o.data.materials.append(ma); return o
# room
cube('Floor',(0,0,-.06),(7,7,.12),floor)
cube('Back wall',(0,3.1,1.65),(7,.12,3.3),wall)
cube('Left wall',(-3.5,0,1.65),(.12,6.2,3.3),wall)
cube('Right wall',(3.5,1.25,1.65),(.12,3.7,3.3),wall)
cube('Back baseboard',(0,3.01,.10),(7,.08,.20),white,.015); cube('Right baseboard',(3.43,1.25,.1),(.08,3.6,.2),white,.01)
for x in [i*.55-3.3 for i in range(13)]: cube('Floor tile seam',(x,0,.003),(.008,6.2,.004),grout)
for y in [i*.55-2.75 for i in range(11)]: cube('Floor tile seam',(0,y,.004),(7,.008,.004),grout)
cube('Large pale rose rug',(0,-.7,.012),(4.5,3.3,.018),rug)
# shelf open grid on back wall
sx=.75; sy=2.86; width=3.35; height=2.42; base=.12; depth=.38
for x in [sx-width/2+i*width/6 for i in range(7)]: cube('Shelf vertical',(x,sy,base+height/2),(.065,depth,height),white)
for z in [base+i*height/4 for i in range(5)]: cube('Shelf horizontal',(sx,sy,z),(width+.065,depth,.07),white)
# bed length along x
cube('Bed platform',(-1.0,-.50,.34),(3.15,1.68,.22),mauve,.04)
for x in [-2.32,.35]:
 for y in [-1.13,.13]: cyl('Bed short leg',(x,y,.03),(x,y,.31),.095,silver)
cube('Mattress',(-1.0,-.50,.59),(3.02,1.58,.38),mattress,.105)
# subtle seams
for y in [-1.28,.28]: cyl('Mattress piping',(-2.43,y,.73),(.43,y,.73),.012,white,12)
# headboard left
for y in [-1.25,.25]: cyl('Headboard post',(-2.58,y,.34),(-2.58,y,1.15),.045,silver)
for z in [.77,1.03]: cube('Headboard slat',(-2.59,-.5,z),(.085,1.7,.16),mauve,.015)
# bedside table toward wall
cube('Bedside table top',(-2.03,1.13,.77),(1.03,.72,.09),wood,.025)
for x in [-2.45,-1.61]:
 for y in [.86,1.4]: cube('Bedside table leg',(x,y,.39),(.055,.055,.76),dark)
# wood streaks top
for i in range(22):
 x=-2.52+random.random()*.96; y=.80+random.random()*.64
 ob=cube('Fine wood grain',(x,y,.818),(.008,random.uniform(.12,.62),.002),frame); ob.rotation_euler[2]=-.7
# artwork on rear wall
cube('Artwork frame',(-2.2,3.015,2.14),(1.0,.07,1.34),frame,.025); cube('Artwork print',(-2.2,2.968,2.14),(.88,.012,1.21),art)
for i in range(55):
 x=-2.58+random.random()*.42; z=2.48+random.random()*.15
 cube('Painted fleck',(x,2.956,z),(random.uniform(.015,.05),.008,random.uniform(.015,.04)),black)
for x,z,r in [(-2.15,2.05,.09),(-2.24,1.9,.06),(-2.05,1.7,.08),(-1.88,1.72,.1)]:
 bpy.ops.mesh.primitive_torus_add(major_radius=r,minor_radius=.009,major_segments=24,minor_segments=6,location=(x,2.951,z),rotation=(math.pi/2,0,0)); bpy.context.object.data.materials.append(gold if z<1.8 else black)
# two floor lamps
def lamp(x,y):
 cyl('Lamp base',(x,y,.02),(x,y,.055),.22,dark); cyl('Slender lamp pole',(x,y,.05),(x,y,1.92),.024,dark)
 bpy.ops.mesh.primitive_cone_add(vertices=48,radius1=.32,radius2=.22,depth=.48,location=(x,y,1.94)); bpy.context.object.name='Tapered lampshade'; bpy.context.object.data.materials.append(white)
 bpy.ops.object.light_add(type='POINT', location=(x,y,1.85)); bpy.context.object.data.energy=90; bpy.context.object.data.color=(1,.84,.65); bpy.context.object.data.shadow_soft_size=.32
lamp(-3.03,1.85); lamp(2.77,1.55)
# chair foreground sculpted seat/back using curved mesh
verts=[]; faces=[]
profile=[(-.63,.55),(-.42,.53),(-.15,.54),(.10,.59),(.26,.69),(.31,.88),(.34,1.10),(.40,1.31),(.51,1.40)]
for y,z in profile:
 for x in [-.42,.42]: verts.append((x+1.9,y-1.8,z))
for i in range(len(profile)-1): faces.append((2*i,2*i+1,2*i+3,2*i+2))
mesh=bpy.data.meshes.new('Chair shell mesh'); mesh.from_pydata(verts,[],faces); mesh.update(); ob=bpy.data.objects.new('Curved chair shell',mesh); bpy.context.collection.objects.link(ob); ob.data.materials.append(chairmat); mod=ob.modifiers.new('Smooth shell','SUBSURF'); mod.levels=2; mod=ob.modifiers.new('Shell thickness','SOLIDIFY'); mod.thickness=.04
for x in [1.61,2.19]:
 for y in [-2.2,-1.5]: cyl('Chair leg',(x,y,.04),(x,y,.55),.025,dark)
# foreground desk corner
cube('Foreground desk',(-3.05,-2.57,.72),(1.2,1.1,.08),white,.015)
# lighting
world=bpy.context.scene.world; world.color=(.7,.7,.7); world.use_nodes=True; world.node_tree.nodes['Background'].inputs[0].default_value=(.75,.8,.77,1); world.node_tree.nodes['Background'].inputs[1].default_value=.45
bpy.ops.object.light_add(type='AREA', location=(0,-2,4.8)); bpy.context.object.data.energy=650; bpy.context.object.data.shape='DISK'; bpy.context.object.data.size=5
# camera
bpy.ops.object.camera_add(location=(4.2,-6.7,4.15)); cam=bpy.context.object; cam.rotation_euler=(Vector((-.1,.7,.9))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.type='PERSP'; cam.data.lens=28; bpy.context.scene.camera=cam
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True; scene.render.threads_mode='FIXED'; scene.render.threads=8; scene.render.resolution_x=640; scene.render.resolution_y=360; scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'; scene.render.image_settings.file_format='PNG'; scene.render.filepath='/app/final.png'; bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
