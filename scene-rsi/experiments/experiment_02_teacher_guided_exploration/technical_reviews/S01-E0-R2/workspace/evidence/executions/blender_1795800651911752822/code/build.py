import bpy, math, random
from mathutils import Vector
random.seed(12)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)

def mat(n,c,rough=.7,metal=0):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal; return m
white=mat('warm white walls',(.78,.78,.76)); trim=mat('white trim',(.91,.91,.88)); oak=mat('pale natural wood',(.68,.46,.33)); oaklight=mat('blind slats',(.78,.58,.46)); dark=mat('charcoal door',(.22,.22,.21)); inset=mat('door inset',(.255,.25,.24)); black=mat('black metal',(.025,.025,.025),.45); gray=mat('chair grey',(.42,.43,.43)); tabletop=mat('desktop charcoal',(.25,.26,.27)); floor=mat('wood floor',(.40,.35,.30)); teal=mat('turquoise planter',(.045,.25,.25),.35); soil=mat('dark potting soil',(.055,.05,.04)); leafm=[mat('grass %d'%i,c) for i,c in enumerate([(.17,.20,.045),(.23,.25,.07),(.30,.29,.08),(.11,.16,.035)])]
def cube(n,loc,scale,ma,bevel=0):
 bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bevel:
  mod=o.modifiers.new('soft edges','BEVEL'); mod.width=bevel; mod.segments=3; o.modifiers.new('weighted normals','WEIGHTED_NORMAL')
 return o
def cyl(n,loc,r,depth,ma,vertices=32):
 bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=depth,location=loc); o=bpy.context.object; o.name=n; o.data.materials.append(ma); return o
def bar(n,a,b,r,ma):
 a,b=Vector(a),Vector(b); d=b-a; o=cyl(n,(a+b)/2,r,d.length,ma,16); o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); return o
# room
cube('floor slab',(0,0,-.09),(8,8,.18),floor)
# floor plank geometry with varied tones
woods=[mat('floor board %d'%i,(.35+i*.014,.31+i*.012,.27+i*.01)) for i in range(8)]
for i in range(23):
 x=-3.8+i*.34
 for j in range(6):
  y=-3.5+j*1.36+(i%2)*.68
  cube('individual oak floor plank',(x,y,.006),(.335,1.35,.018),random.choice(woods))
cube('back wall',(-1.7,3.12,1.7),(4.4,.18,3.4),white); cube('right wall',(.5,-.8,1.7),(.18,8,3.4),white)
cube('back baseboard',(-1.7,2.99,.11),(4.4,.08,.20),trim,.01); cube('right baseboard',(.39,-.8,.11),(.08,8,.2),trim,.01)
# window and wood frame on rear wall
cube('blind backing',(-1.95,2.995,2.23),(2.65,.04,1.38),oaklight)
for x in [-3.33,-.57]: cube('window vertical casing',(x,2.93,2.23),(.12,.13,1.65),oak,.01)
for z in [1.45,3.01]: cube('window horizontal casing',(-1.95,2.93,z),(2.88,.13,.12),oak,.01)
for i in range(31): cube('horizontal venetian slat',(-1.95,2.91,1.56+i*.045),(2.65,.06,.025),oaklight,.006)
# door on perpendicular right-hand wall
cube('door casing',(.39,1.45,1.29),(.12,1.23,2.58),trim,.015)
cube('dark door leaf',(.29,1.45,1.28),(.12,1.12,2.49),dark,.012)
for y in [1.16,1.74]:
 for z,h in [(.39,.55),(1.05,.46),(1.59,.46),(2.13,.47)]:
  cube('recessed door panel',(.215,y,z),(.025,.43,h),inset,.008)
# bookcase below window, 4 bays 2 rows
cube('bookcase top',(-1.95,2.48,1.03),(2.8,.48,.12),oak,.012); cube('bookcase bottom',(-1.95,2.48,.08),(2.8,.48,.11),oak,.01)
for x in [-3.31,-2.63,-1.95,-1.27,-.59]: cube('bookcase upright',(x,2.48,.55),(.075,.47,.9),oak,.008)
cube('middle shelf',(-1.95,2.48,.53),(2.72,.46,.07),oak,.006)
# white tall narrow cabinet
cube('white cabinet',(-.23,2.64,.56),(.48,.55,1.12),trim,.018)
cube('cabinet front panel',(-.23,2.345,.58),(.40,.015,.94),white,.005)
# lamp at left
cyl('lamp foot',(-3.42,1.72,.035),.16,.05,black); bar('lamp stem',(-3.42,1.72,.06),(-3.42,1.72,1.62),.018,black)
bpy.ops.mesh.primitive_cone_add(vertices=48,radius1=.27,radius2=.18,depth=.49,location=(-3.42,1.72,1.83)); bpy.context.object.name='cream lampshade'; bpy.context.object.data.materials.append(trim)
# table foreground
cube('desk top',(-1.35,-1.25,.77),(2.6,1.5,.11),tabletop,.025)
for x in [-2.48,-.22]:
 for y in [-1.85,-.65]: cube('desk leg',(x,y,.37),(.07,.07,.74),black)
# chair shell made as smooth curved strips spanning seat and back
def chair(cx,cy,angle):
 # local coordinates x width, y front-to-back; back at positive y
 def tr(p):
  x,y,z=p; return (cx+x*math.cos(angle)-y*math.sin(angle),cy+x*math.sin(angle)+y*math.cos(angle),z)
 verts=[]; rows=[(-.46,.68),(-.32,.65),(.0,.66),(.26,.72),(.36,.90),(.41,1.15),(.43,1.40),(.40,1.53)]
 for y,z in rows:
  for x in [-.43,-.32,0,.32,.43]:
   # curved edges and rounded top
   zz=z+(.07 if abs(x)>.4 else 0); yy=y-(.05 if abs(x)>.4 else 0)
   verts.append(tr((x,yy,zz)))
 faces=[]
 for j in range(len(rows)-1):
  for k in range(4):
   a=j*5+k; faces.append((a,a+1,a+6,a+5))
 mesh=bpy.data.meshes.new('molded chair mesh'); mesh.from_pydata(verts,[],faces); mesh.update(); o=bpy.data.objects.new('curved grey office chair shell',mesh); bpy.context.collection.objects.link(o); o.data.materials.append(gray)
 for p in mesh.polygons:p.use_smooth=True
 sub=o.modifiers.new('smooth shell','SUBSURF'); sub.levels=2; sol=o.modifiers.new('shell thickness','SOLIDIFY'); sol.thickness=.045
 cyl('chair central post',(cx,cy,.38),.045,.57,black)
 for i in range(5):
  a=2*math.pi*i/5; end=(cx+.48*math.cos(a),cy+.48*math.sin(a),.12); bar('five star chair base',(cx,cy,.18),end,.035,black); cyl('caster wheel',(end[0],end[1],.075),.075,.09,black,20)
chair(-1.55,.70,-.3); chair(-.35,-.68,-.4)
# planter foreground right
bpy.ops.mesh.primitive_cone_add(vertices=64,radius1=.48,radius2=.63,depth=.52,location=(.0,-3.8,.27)); bpy.context.object.name='teal round planter'; bpy.context.object.data.materials.append(teal)
cyl('soil in pot',(.0,-3.8,.54),.60,.035,soil,64)
# blades are tapered triangular grass leaves
for i in range(380):
 a=random.random()*math.tau; r=random.random()**.6*.40; x=0+r*math.cos(a); y=-3.8+r*math.sin(a); h=random.uniform(.5,1.35); lean=random.uniform(.12,.65); a2=a+random.uniform(-.5,.5); tip=(x+lean*math.cos(a2),y+lean*math.sin(a2),.54+h); w=random.uniform(.012,.032); side=Vector((-math.sin(a2)*w,math.cos(a2)*w,0)); base=Vector((x,y,.55)); mid=base.lerp(Vector(tip),.55)+Vector((0,0,.12)); verts=[base-side,base+side,mid+side*.6,Vector(tip),mid-side*.6]; mesh=bpy.data.meshes.new('blade'); mesh.from_pydata(verts,[],[(0,1,2,3,4)]); mesh.materials.append(random.choice(leafm)); ob=bpy.data.objects.new('ornamental grass blade',mesh); bpy.context.collection.objects.link(ob)
# camera and lights
world=bpy.context.scene.world or bpy.data.worlds.new('World'); bpy.context.scene.world=world; world.use_nodes=True; world.node_tree.nodes['Background'].inputs[0].default_value=(.8,.8,.8,1); world.node_tree.nodes['Background'].inputs[1].default_value=.8
def area(loc,power,size,target):
 bpy.ops.object.light_add(type='AREA',location=loc); o=bpy.context.object; o.data.energy=power; o.data.shape='DISK'; o.data.size=size; o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
area((0,-1,5.8),700,5,(0,1,0)); area((-4,-2,4),400,4,(0,1,1))
bpy.ops.object.camera_add(location=(-5.0,-6.1,4.0)); cam=bpy.context.object; cam.rotation_euler=(Vector((-1.0,1.0,1.15))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.type='PERSP'; cam.data.lens=32; bpy.context.scene.camera=cam
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True; scene.render.resolution_x=640; scene.render.resolution_y=360; scene.render.resolution_percentage=100; scene.render.image_settings.file_format='PNG'; scene.render.filepath='/app/final.png'; scene.world.color=(.8,.8,.8); scene.view_settings.view_transform='AgX'; bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
