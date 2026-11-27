import bpy, math, random
from mathutils import Vector
random.seed(12)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)

def mat(n,c,rough=.75,metal=0):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal; return m
white=mat('warm white walls',(.77,.77,.75)); trim=mat('white painted trim',(.91,.91,.89)); wood=mat('pale maple',(.72,.48,.34)); wood2=mat('blind slats',(.78,.58,.47)); dark=mat('door charcoal',(.18,.18,.18)); groove=mat('door panel grooves',(.095,.095,.09)); grey=mat('chair grey',(.43,.44,.44)); black=mat('black metal',(.025,.027,.027)); desk=mat('desk graphite',(.22,.23,.23)); pot=mat('teal ceramic',(.025,.19,.18),.3); soil=mat('soil',(.085,.075,.057)); leafm=[mat('grass '+str(i),c) for i,c in enumerate([(.19,.22,.055),(.27,.29,.085),(.35,.35,.12),(.12,.15,.035)])]

def cube(n,loc,scale,ma,bev=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bev: mod=o.modifiers.new('soft edges','BEVEL'); mod.width=bev; mod.segments=2; o.modifiers.new('weighted normals','WEIGHTED_NORMAL')
 return o

def cyl(n,loc,r,depth,ma,verts=24):
 bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=depth,location=loc); o=bpy.context.object;o.name=n;o.data.materials.append(ma); return o

def rod(n,a,b,r,ma):
 d=Vector(b)-Vector(a); o=cyl(n,(Vector(a)+Vector(b))/2,r,d.length,ma,12); o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); return o
# room floor with individual staggered boards
floorbase=mat('floor grout',(.27,.25,.23)); cube('floor base',(0,0,-.07),(6,6,.14),floorbase)
floors=[mat('oak floor '+str(i),(.35+i*.012,.31+i*.011,.27+i*.009)) for i in range(10)]
for ix in range(24):
 x=-2.88+ix*.25
 for iy in range(8):
  y=-2.8+iy*.8+(ix%2)*.4
  cube('individual oak plank',(x,y,.008),(.245,.795,.025),random.choice(floors))
# back wall y=2 and right wall x=3
cube('back wall',(0,2.02,1.65),(6,.12,3.3),white); cube('right wall',(3.02,0,1.65),(.12,4,3.3),white)
cube('back baseboard',(0,1.92,.09),(6,.08,.18),trim); cube('right baseboard',(2.92,0,.09),(.08,4,.18),trim)
# window frame on back wall
cube('window recess',(-1.25,1.93,2.20),(2.25,.06,1.35),wood2)
for x in [-2.43,-.07]: cube('window vertical frame',(x,1.87,2.2),(.11,.12,1.52),wood,.012)
for z in [1.48,2.92]: cube('window horizontal frame',(-1.25,1.87,z),(2.47,.12,.10),wood,.01)
for i in range(29): cube('horizontal blind slat',(-1.25,1.83,1.54+i*.047),(2.25,.045,.027),wood2,.005)
# low cubby shelf
sx=-1.25; sy=1.55
for z in [.13,.69,1.24]: cube('shelf horizontal',(sx,sy,z),(2.55,.42,.085),wood,.01)
for x in [-2.48,-1.85,-1.22,-.59,-.02]: cube('shelf divider',(x,sy,.69),(.075,.42,1.12),wood,.008)
cube('tall white cabinet',(.32,1.7,.58),(.43,.40,1.16),trim,.015)
# door on right wall, dark recessed face and panel outlines
cube('door white casing',(2.91,.76,1.28),(.10,1.22,2.56),trim,.015)
cube('dark door',(2.84,.76,1.25),(.10,1.08,2.47),dark,.01)
for yy in [.48,1.02]:
 for zz in [.38,.92,1.46,2.00]:
  for y in [yy-.21,yy+.21]: cube('panel inset vertical',(2.779,y,zz),(.012,.012,.40),groove)
  for z in [zz-.20,zz+.20]: cube('panel inset horizontal',(2.779,yy,z),(.012,.43,.012),groove)
# lamp at left
cyl('lamp foot',(-2.72,1.38,.035),.14,.05,black); rod('lamp stem',(-2.72,1.38,.06),(-2.72,1.38,1.48),.012,black)
bpy.ops.mesh.primitive_cone_add(vertices=32,radius1=.22,radius2=.15,depth=.48,location=(-2.72,1.38,1.53)); bpy.context.object.name='cream lampshade'; bpy.context.object.data.materials.append(trim)
# desk foreground
cube('dark desk top',(-1.25,-1.28,.74),(2.25,1.35,.10),desk,.025)
for x in [-2.2,-.3]:
 for y in [-1.8,-.8]: cube('desk leg',(x,y,.37),(.055,.055,.72),black)
# chairs mesh shell profile, local facing toward -y
def chair(name,cx,cy,angle):
 def trans(x,y,z):
  a=angle;return (cx+x*math.cos(a)-y*math.sin(a),cy+x*math.sin(a)+y*math.cos(a),z)
 # continuous curved shell across width, seat toward -y, back toward +y
 profile=[(-.42,.75),(-.32,.70),(-.05,.69),(.20,.72),(.30,.80),(.34,1.05),(.38,1.30),(.43,1.46)]
 verts=[]
 for y,z in profile:
  for x in [-.43,-.34,0,.34,.43]: verts.append(trans(x,y,z + (.045 if abs(x)>.4 else 0)))
 faces=[]
 for j in range(len(profile)-1):
  for i in range(4): a=j*5+i;faces.append((a,a+1,a+6,a+5))
 mesh=bpy.data.meshes.new(name+' shell mesh');mesh.from_pydata(verts,[],faces);mesh.update();o=bpy.data.objects.new(name+' molded shell',mesh);bpy.context.collection.objects.link(o);o.data.materials.append(grey)
 for p in mesh.polygons:p.use_smooth=True
 mod=o.modifiers.new('rounded shell','SUBSURF');mod.levels=2;mod.render_levels=2
 mod=o.modifiers.new('shell thickness','SOLIDIFY');mod.thickness=.035
 cyl(name+' central post',(cx,cy,.40),.045,.55,black)
 for i in range(5):
  a=2*math.pi*i/5; end=(cx+.43*math.cos(a),cy+.43*math.sin(a),.11);rod(name+' caster arm',(cx,cy,.18),end,.035,black);cyl(name+' wheel',(end[0],end[1],.075),.075,.055,black,16)
chair('left office chair',-.5,.35,-.15);chair('foreground office chair',.75,-.85,-.4)
# plant pot at front right
bpy.ops.mesh.primitive_cone_add(vertices=48,radius1=.34,radius2=.48,depth=.47,location=(2.36,-1.50,.25)); bpy.context.object.name='teal planter';bpy.context.object.data.materials.append(pot)
cyl('exposed soil',(2.36,-1.50,.49),.455,.025,soil,48)
# long tapered leaves, curved triangular strips
for i in range(180):
 a=random.uniform(0,math.tau); radius=random.uniform(.02,.23); length=random.uniform(.55,1.25); lean=random.uniform(.15,.75); x=2.36+radius*math.cos(a);y=-1.5+radius*math.sin(a); z=.5
 side=Vector((-math.sin(a),math.cos(a),0))*random.uniform(.008,.022); start=Vector((x,y,z)); mid=Vector((x+lean*.38*math.cos(a),y+lean*.38*math.sin(a),z+length*.68)); tip=Vector((x+lean*math.cos(a),y+lean*math.sin(a),z+length));
 verts=[start-side,start+side,mid+side*.6,tip,mid-side*.6]; mesh=bpy.data.meshes.new('blade');mesh.from_pydata(verts,[],[(0,1,2,3,4)]);mesh.update(); ob=bpy.data.objects.new('grass blade',mesh);bpy.context.collection.objects.link(ob);ob.data.materials.append(random.choice(leafm))
# lighting and camera
world=bpy.context.scene.world or bpy.data.worlds.new('World');bpy.context.scene.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.8,.8,.8,1);world.node_tree.nodes['Background'].inputs[1].default_value=.8
bpy.ops.object.light_add(type='AREA',location=(-2,-3,5));bpy.context.object.data.energy=650;bpy.context.object.data.shape='DISK';bpy.context.object.data.size=5
bpy.ops.object.camera_add(location=(-3.4,-4.5,3.0));cam=bpy.context.object;cam.rotation_euler=(Vector((0,.35,1.35))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='PERSP';cam.data.lens=24;bpy.context.scene.camera=cam
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True;scene.render.resolution_x=640;scene.render.resolution_y=360;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.filepath='/app/final.png';scene.view_settings.view_transform='AgX';scene.render.threads_mode='FIXED';scene.render.threads=8
bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend');bpy.ops.render.render(write_still=True)
