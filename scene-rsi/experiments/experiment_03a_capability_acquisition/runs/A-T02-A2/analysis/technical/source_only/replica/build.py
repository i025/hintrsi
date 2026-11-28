import bpy, math, random
from mathutils import Vector
random.seed(4)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)

def mat(n,c,rough=.75,metal=0):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal; return m
white=mat('Warm white painted wood',(.89,.90,.86)); wall=mat('Pale mint walls',(.73,.83,.74)); floor=mat('Pale porcelain',(.79,.84,.82)); grout=mat('Tile joints',(.69,.76,.75)); mauve=mat('Dusty mauve bed frame',(.48,.30,.41)); mattress=mat('White mattress fabric',(.94,.93,.93)); rug=mat('Blush beige rug',(.70,.63,.62)); wood=mat('Wood tabletop',(.47,.31,.23)); dark=mat('Dark bronze',(.17,.15,.14),.5,.4); shade=mat('Ivory lampshades',(.85,.84,.80)); grey=mat('Charcoal grey chair',(.24,.27,.26)); black=mat('Dark doorway',(.015,.017,.017)); artbg=mat('Artwork blue grey',(.40,.53,.54)); frame=mat('Artwork pale wood frame',(.73,.61,.50))
def cube(n,loc,scale,ma,bev=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bev: mod=o.modifiers.new('Soft edges','BEVEL'); mod.width=bev; mod.segments=3; o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
 return o
def cyl(n,a,b,r,ma,vertices=24):
 d=Vector(b)-Vector(a); mid=(Vector(a)+Vector(b))/2; bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=d.length,location=mid); o=bpy.context.object; o.name=n; o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); o.data.materials.append(ma); return o
def area(n,loc,power,size,target):
 bpy.ops.object.light_add(type='AREA', location=loc); o=bpy.context.object; o.name=n; o.data.energy=power; o.data.shape='DISK'; o.data.size=size; o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
# room
cube('Floor',(0,0,-.06),(7,7,.12),floor)
for i in range(-7,8):
 cube('Floor grout X',(i*.5,0,.004),(.008,7,.003),grout); cube('Floor grout Y',(0,i*.5,.005),(7,.008,.003),grout)
cube('Back wall',(0,3.05,1.65),(7,.1,3.3),wall); cube('Left wall',(-3.55,0,1.65),(.1,6.1,3.3),wall); cube('Right wall',(3.55,0,1.65),(.1,6.1,3.3),wall)
cube('Back skirting',(0,2.96,.09),(7,.07,.18),white); cube('Right skirting',(3.47,0,.09),(.07,6,.18),white)
# cubby shelving, open back, white grid
sx=.65; sy=2.72; width=3.25; height=2.65; bottom=.12; dep=.36
for x in [sx-width/2,sx+width/2]: cube('Shelf outer side',(x,sy,bottom+height/2),(.085,dep,height),white)
for z in [bottom,bottom+height]: cube('Shelf outer horizontal',(sx,sy,z),(width+.08,dep,.085),white)
for i in range(1,5): cube('Shelf divider',(sx-width/2+i*width/5,sy,bottom+height/2),(.065,dep,height),white)
for i in range(1,4): cube('Shelf shelf',(sx,sy,bottom+i*height/4),(width,dep,.065),white)
# rug and bed
cube('Large rectangular blush rug',(.15,-.75,.025),(3.4,3.15,.035),rug)
# bed long axis x
cube('Mauve bed base',(-1.0,-.65,.34),(2.9,1.65,.24),mauve,.045)
for x in [-2.25,.22]:
 for y in [-1.30,.0]: cyl('Bed round foot',(x,y,.03),(x,y,.32),.095,dark)
cube('Mattress',(-1.02,-.65,.58),(2.75,1.53,.34),mattress,.09)
# mattress edge quilting subtle seams
for x in [-2.25+i*.16 for i in range(17)]:
 for z in [.48,.56]:
  cyl('Mattress quilt stitch',(x,-1.421,z),(x+.075,-1.424,z+.035),.006,white,8)
# headboard at left x end
for y in [-1.35,.05]: cyl('Headboard post',(-2.49,y,.36),(-2.49,y,1.14),.045,dark)
for z in [.80,1.06]: cube('Headboard mauve slat',(-2.5,-.65,z),(.09,1.62,.14),mauve,.012)
# side table rear left
cube('Side table wooden top',(-2.05,1.03,.76),(.78,.70,.07),wood,.018)
for x in [-2.36,-1.74]:
 for y in [.76,1.29]: cyl('Table leg',(x,y,.05),(x,y,.73),.035,dark)
# tabletop pale wood grain streaks
for i in range(12):
 y=.73+i*.049; cyl('Table grain',(-2.4,y,.801),(-1.73,y+random.uniform(-.12,.12),.801),.006,frame,8)
# floor lamps conical shades
def lamp(n,x,y):
 cyl(n+' stem',(x,y,.05),(x,y,1.93),.025,dark); cyl(n+' foot',(x,y,.035),(x,y,.06),.19,dark)
 bpy.ops.mesh.primitive_cone_add(vertices=48,radius1=.32,radius2=.21,depth=.49,location=(x,y,1.94)); o=bpy.context.object; o.name=n+' tapered shade'; o.data.materials.append(shade)
 area(n+' warm pool',(x,y,1.86),90,.28,(x,y,0)); area(n+' wall glow',(x,y,2.18),75,.3,(x,3,2.3))
lamp('Left floor lamp',-2.95,1.6); lamp('Right floor lamp',2.65,1.5)
# framed artwork on back wall left
cube('Artwork backing',(-2.05,2.96,2.03),(.87,.055,1.35),frame)
cube('Artwork print',(-2.05,2.925,2.03),(.73,.015,1.20),artbg)
ink=mat('Print black ink',(.055,.065,.055)); cream=mat('Print cream',(.90,.87,.78)); gold=mat('Print gold',(.62,.57,.35))
# simple abstract marks on print
for i in range(35):
 x=-2.36+random.random()*.37; z=2.43+random.random()*.14; cube('Art ink fleck',(x,2.91,z),(.035,.009,.035),ink,.006)
for cx,cz,r,ma in [(-2.12,1.91,.075,ink),(-2.22,1.79,.05,ink),(-2.34,2.10,.10,cream),(-1.83,1.59,.08,gold)]:
 for j in range(12):
  t=j*math.tau/12; x=cx+r*math.cos(t); z=cz+r*math.sin(t); cube('Abstract print mark',(x,2.908,z),(.025,.009,.025),ma,.006)
# modern chair in foreground seat and curved back via mesh
cube('Chair seat',(2.12,-1.72,.52),(.85,.80,.12),grey,.14)
verts=[]; faces=[]
for z,y,w in [(.53,-1.38,.39),(.76,-1.32,.38),(1.08,-1.27,.34),(1.30,-1.23,.28)]:
 for x in [-w,w]: verts.append((2.12+x,y,z))
for i in range(3): faces.append((2*i,2*i+1,2*i+3,2*i+2))
me=bpy.data.meshes.new('Chair back mesh'); me.from_pydata(verts,[],faces); me.update(); ob=bpy.data.objects.new('Curved chair back',me); bpy.context.collection.objects.link(ob); ob.data.materials.append(grey); sol=ob.modifiers.new('Shell thickness','SOLIDIFY'); sol.thickness=.10; sub=ob.modifiers.new('Rounded shell','SUBSURF'); sub.levels=2
for x in [1.83,2.41]:
 for y in [-1.99,-1.45]: cyl('Chair leg',(x,y,.03),(x,y,.51),.025,dark)
# foreground partial desk and dark door edge
cube('Foreground white desk',(-2.4,-2.6,.76),(1.7,.75,.07),white,.012)
cube('Dark door at right',(3.48,-1.8,1.45),(.08,1.4,2.9),black)
# lighting and camera
world=bpy.context.scene.world or bpy.data.worlds.new('World'); bpy.context.scene.world=world; world.use_nodes=True; world.node_tree.nodes['Background'].inputs[0].default_value=(.78,.84,.80,1); world.node_tree.nodes['Background'].inputs[1].default_value=.7
area('Large ceiling softbox',(0,-.2,4.8),550,5,(0,.5,0))
bpy.ops.object.camera_add(location=(4.8,-7.5,5.1)); cam=bpy.context.object; cam.name='Camera'; cam.rotation_euler=(Vector((0,.5,1.05))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.type='PERSP'; cam.data.lens=35; bpy.context.scene.camera=cam
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True; scene.render.threads_mode='FIXED'; scene.render.threads=8; scene.render.resolution_x=640; scene.render.resolution_y=360; scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'; scene.render.image_settings.file_format='PNG'; scene.render.filepath='/app/final.png'; bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
