import bpy, math, random
from mathutils import Vector
random.seed(4)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)

def mat(n,c,rough=.7,metal=0):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal; return m
wall=mat('warm ivory wallpaper',(0.79,.77,.75)); grout=mat('fine hexagon lines',(.60,.59,.58)); floor=mat('pale stone floor',(.77,.76,.74)); dark=mat('black metal',(.025,.024,.024),.4); desk=mat('charcoal brown tabletops',(.25,.235,.23)); white=mat('white molded plastic',(.9,.9,.89),.35); frame=mat('dark window frame',(.085,.073,.068)); glass=mat('frosted pale blue glass',(.68,.77,.81),.35); shade=mat('taupe lampshade',(.46,.40,.37)); brass=mat('lamp bronze stem',(.34,.24,.21),.35,.5)

def cube(n,loc,scale,ma,bevel=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bevel:
  mod=o.modifiers.new('subtle softened edges','BEVEL'); mod.width=bevel; mod.segments=3; o.modifiers.new('weighted normals','WEIGHTED_NORMAL')
 return o

def rod(n,a,b,r,ma,verts=12):
 d=Vector(b)-Vector(a); mid=(Vector(a)+Vector(b))/2; bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=d.length,location=mid); o=bpy.context.object; o.name=n; o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); o.data.materials.append(ma); return o

def sphere(n,loc,scale,ma):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=20,ring_count=12,location=loc); o=bpy.context.object; o.name=n; o.scale=scale; o.data.materials.append(ma); bpy.ops.object.shade_smooth(); return o
# room
cube('floor',(0,0,-.08),(15,18,.16),floor)
cube('back wall',(0,4.2,2.4),(14,.12,4.8),wall)
cube('right wall',(6.0,-1,2.4),(.12,10.5,4.8),wall)
cube('back baseboard',(0,4.11,.10),(12,.045,.20),white)
cube('right baseboard',(5.91,-1,.10),(.045,10.4,.20),white)
# fine regular hexagonal wall outlines, actual editable curves
# pointy top hexagons in wall plane
curve=bpy.data.curves.new('hexagon wallpaper linework','CURVE'); curve.dimensions='3D'; curve.bevel_depth=.0025; curve.bevel_resolution=0
r=.19
for row in range(19):
 z=.12+row*1.5*r
 for col in range(43):
  x=-7.0+col*math.sqrt(3)*r+(row%2)*math.sqrt(3)*r/2
  s=curve.splines.new('POLY'); s.points.add(5)
  for k,p in enumerate(s.points):
   a=math.radians(30+60*k); p.co=(x+r*math.cos(a),4.127,z+r*math.sin(a),1)
  s.use_cyclic_u=True
obj=bpy.data.objects.new('hexagonal wallpaper back',curve); bpy.context.collection.objects.link(obj); obj.data.materials.append(grout)
# right wall wallpaper
curve=bpy.data.curves.new('right hexagonal linework','CURVE'); curve.dimensions='3D'; curve.bevel_depth=.0025; curve.bevel_resolution=0
for row in range(19):
 z=.12+row*1.5*r
 for col in range(34):
  y=-6+col*math.sqrt(3)*r+(row%2)*math.sqrt(3)*r/2
  s=curve.splines.new('POLY'); s.points.add(5)
  for k,p in enumerate(s.points):
   a=math.radians(30+60*k); p.co=(5.927,y+r*math.cos(a),z+r*math.sin(a),1)
  s.use_cyclic_u=True
obj=bpy.data.objects.new('hexagonal wallpaper right',curve); bpy.context.collection.objects.link(obj); obj.data.materials.append(grout)
# window on back wall, wide dark frame with two panes
cube('window recess',(0,4.04,2.65),(2.45,.12,1.75),frame)
cube('left window pane',(-.61,3.965,2.65),(1.09,.025,1.53),glass)
cube('right window pane',(.61,3.965,2.65),(1.09,.025,1.53),glass)
for x in [-1.23,0,1.23]: cube('window vertical frame',(x,3.94,2.65),(.09,.07,1.78),frame)
for z in [1.78,3.52]: cube('window horizontal frame',(0,3.94,z),(2.52,.07,.09),frame)
# desk rows, long narrow individual desks
for y in [2.65,.65]:
 for x in [-4.3,-1.45,1.4,4.25]:
  cube('rectangular dark desk top',(x,y,.76),(2.75,.72,.065),desk,.012)
  for dx in [-1.25,1.25]:
   for dy in [-.29,.29]: rod('slender black desk leg',(x+dx,y+dy,.04),(x+dx,y+dy,.74),.017,dark,8)
# chairs: sculpted backs, seat, swivel post and five caster legs
# facing back wall; back is on camera side
def chair(x,y,ang=0):
 def tr(v):
  a=ang; X,Y,Z=v; return (x+X*math.cos(a)-Y*math.sin(a),y+X*math.sin(a)+Y*math.cos(a),Z)
 # seat shallow ellipsoid
 sphere('chair white seat',tr((0,0,.49)),(.49,.43,.065),white)
 # concave shaped back, rounded top silhouette using variable width at levels
 levels=[(.49,.41),(.55,.48),(.67,.47),(.82,.42),(.99,.32),(1.07,.20),(1.09,0)]
 verts=[]; faces=[]; N=12
 for z,w in levels:
  for i in range(N+1):
   u=-1+2*i/N; yy=-.30+ .13*(u*u) + .12*(z-.49); verts.append(tr((u*w,yy,z)))
 for j in range(len(levels)-1):
  for i in range(N):
   a=j*(N+1)+i; faces.append((a,a+1,a+N+2,a+N+1))
 mesh=bpy.data.meshes.new('molded shell mesh'); mesh.from_pydata(verts,[],faces); mesh.update(); o=bpy.data.objects.new('curved white chair back',mesh); bpy.context.collection.objects.link(o); o.data.materials.append(white)
 for p in mesh.polygons:p.use_smooth=True
 so=o.modifiers.new('plastic shell thickness','SOLIDIFY'); so.thickness=.025
 su=o.modifiers.new('soft shell','SUBSURF'); su.levels=2
 rod('chair central post',tr((0,0,.14)),tr((0,0,.48)),.027,dark)
 for k in range(5):
  a=2*math.pi*k/5; ex=.40*math.cos(a); ey=.40*math.sin(a)
  rod('chair five star spoke',tr((0,0,.15)),tr((ex,ey,.10)),.035,dark)
  sphere('black caster wheel',tr((ex,ey,.075)),(.078,.055,.075),dark)
for x,y in [(-4.6,1.85),(-1.8,1.85),(1.1,1.85),(3.8,1.85),(-4,-.45),(-.6,-.48),(2.55,-.48),(5,-.35)]: chair(x,y,random.uniform(-.15,.15))
# two floor lamps with tapered cloth shades and light pools
for x,y in [(4.0,3.62),(5.65,2.4)]:
 rod('lamp slender stem',(x,y,.04),(x,y,1.72),.018,brass)
 bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.17,depth=.025,location=(x,y,.025)); bpy.context.object.name='lamp round base'; bpy.context.object.data.materials.append(brass)
 bpy.ops.mesh.primitive_cone_add(vertices=48,radius1=.23,radius2=.17,depth=.34,location=(x,y,1.77)); bpy.context.object.name='taupe drum lamp shade'; bpy.context.object.data.materials.append(shade)
 for z,energy in [(1.58,85),(1.97,85)]:
  bpy.ops.object.light_add(type='POINT',location=(x,y,z)); l=bpy.context.object; l.name='warm lamp glow'; l.data.energy=energy; l.data.color=(1,.73,.52); l.data.shadow_soft_size=.18
# lighting
world=bpy.context.scene.world or bpy.data.worlds.new('World'); bpy.context.scene.world=world; world.use_nodes=True; world.node_tree.nodes['Background'].inputs[0].default_value=(.72,.75,.8,1); world.node_tree.nodes['Background'].inputs[1].default_value=.65
bpy.ops.object.light_add(type='AREA',location=(0,-2,5)); bpy.context.object.name='large overhead softbox'; bpy.context.object.data.energy=650; bpy.context.object.data.shape='DISK'; bpy.context.object.data.size=7
# camera
bpy.ops.object.camera_add(location=(0,-9.8,2.5)); cam=bpy.context.object; cam.name='Camera'; cam.rotation_euler=(Vector((0,2,1.55))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.lens=31; bpy.context.scene.camera=cam
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.samples=32; sc.cycles.use_denoising=True; sc.render.threads_mode='FIXED'; sc.render.threads=8
sc.render.resolution_x=640; sc.render.resolution_y=360; sc.render.resolution_percentage=100
sc.view_settings.view_transform='AgX'; sc.render.image_settings.file_format='PNG'; sc.render.filepath='/app/final.png'
bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
