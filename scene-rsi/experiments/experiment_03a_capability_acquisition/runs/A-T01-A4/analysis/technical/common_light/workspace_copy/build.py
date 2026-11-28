import bpy, math, random
from mathutils import Vector
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
random.seed(2)
def mat(n,c,rough=.7,metal=0):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal; return m
white=mat('warm white plaster',(0.76,.745,.73)); floor=mat('pale floor',(0.72,.71,.69)); dark=mat('dark charcoal steel',(.035,.031,.029)); top=mat('dark gray desk tops',(.18,.17,.16)); chairmat=mat('white molded plastic',(.88,.87,.85),.38); frame=mat('window frame',(.065,.052,.045)); glass=mat('pale sky',(.67,.75,.79)); grout=mat('fine hexagon outlines',(.55,.53,.52)); lampmat=mat('taupe lampshades',(.45,.40,.37)); brass=mat('lamp stems',(.38,.25,.20),.45,.35)
def cube(n,loc,scale,ma,bevel=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bevel: mod=o.modifiers.new('soft edges','BEVEL'); mod.width=bevel; mod.segments=3; o.modifiers.new('weighted normals','WEIGHTED_NORMAL')
 return o
def cyl(n,a,b,r,ma,vertices=12):
 d=Vector(b)-Vector(a); mid=(Vector(a)+Vector(b))/2; bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=d.length,location=mid); o=bpy.context.object; o.name=n; o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); o.data.materials.append(ma); return o
def line(n,pts,r,ma):
 cu=bpy.data.curves.new(n,'CURVE'); cu.dimensions='3D'; cu.bevel_depth=r; cu.bevel_resolution=1; sp=cu.splines.new('POLY'); sp.points.add(len(pts)-1)
 for p,co in zip(sp.points,pts): p.co=(*co,1)
 ob=bpy.data.objects.new(n,cu); bpy.context.collection.objects.link(ob); ob.data.materials.append(ma); return ob
# room
cube('floor',(0,1,-.08),(16,16,.15),floor)
cube('back wall',(0,4.02,2.5),(16,.12,5),white)
cube('right wall',(6.0,0,2.5),(.12,8,5),white)
cube('back skirting',(0,3.94,.09),(12,.07,.18),chairmat)
cube('right skirting',(5.93,0,.09),(.07,8,.18),chairmat)
# delicate hexagon grid on back and right walls, as individual splines in a single curve
cu=bpy.data.curves.new('hexagonal wallpaper lines','CURVE'); cu.dimensions='3D'; cu.bevel_depth=.0023; cu.bevel_resolution=0
r=.145
for row in range(-2,25):
 z=row*1.5*r
 for col in range(-30,31):
  x=(col+(row%2)*.5)*math.sqrt(3)*r
  pts=[(x+r*math.cos(math.radians(30+60*k)),3.951,z+r*math.sin(math.radians(30+60*k))) for k in range(7)]
  sp=cu.splines.new('POLY'); sp.points.add(6)
  for p,v in zip(sp.points,pts): p.co=(*v,1)
ob=bpy.data.objects.new('back wall honeycomb pattern',cu); bpy.context.collection.objects.link(ob); ob.data.materials.append(grout)
cu2=cu.copy(); ob=bpy.data.objects.new('right wall honeycomb pattern',cu2); bpy.context.collection.objects.link(ob); ob.data.materials.append(grout); ob.rotation_euler[2]=-math.pi/2; ob.location=(9.95,9.95,0)
# window panel on rear wall
cube('window recess',(0,3.91,2.65),(1.85,.10,1.48),frame)
cube('left window pane',(-.46,3.845,2.65),(.82,.025,1.32),glass)
cube('right window pane',(.46,3.845,2.65),(.82,.025,1.32),glass)
for x in [-.92,0,.92]: cube('window vertical frame',(x,3.80,2.65),(.075,.09,1.5),frame)
for z in [1.91,3.39]: cube('window horizontal frame',(0,3.8,z),(1.9,.09,.075),frame)
# desks slender legs and thin rectangular tops
def desk(x,y,w=2.0,depth=.72):
 cube('rectangular charcoal desktop',(x,y,.78),(w,depth,.055),top,.012)
 for dx in [-w/2+.07,w/2-.07]:
  for dy in [-depth/2+.06,depth/2-.06]: cube('slender desk leg',(x+dx,y+dy,.38),(.035,.035,.76),dark,.006)
for y in [1.45,3.0]:
 for x in [-4.05,-2.0,.05,2.1,4.15]: desk(x,y)
# chair shells: molded curved back, seat, central post and five spoke casters
def chair(x,y,ang=0):
 # local forward is +Y, back located at negative Y; viewer sees outer rear
 def tr(p):
  a,b,c=p; return (x+a*math.cos(ang)-b*math.sin(ang),y+a*math.sin(ang)+b*math.cos(ang),c)
 # seat flattened ellipsoid
 bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,location=tr((0,0,.49))); o=bpy.context.object; o.name='molded white chair seat'; o.scale=(.46,.40,.075); o.rotation_euler[2]=ang; o.data.materials.append(chairmat); bpy.ops.object.shade_smooth()
 # smooth back shell broad bottom tapered dome top, curved towards the seat
 verts=[]; faces=[]; rows=12; cols=24
 for j in range(rows+1):
  t=j/rows; z=.48+.68*t; width=.46*(1-.45*t*t)**.5
  for i in range(cols+1):
   u=2*i/cols-1; xx=width*u; yy=-.27-.09*t+.10*u*u; zz=z-.08*(abs(u)**3)*(t**5); verts.append(tr((xx,yy,zz)))
 for j in range(rows):
  for i in range(cols):
   a=j*(cols+1)+i; faces.append((a,a+1,a+cols+2,a+cols+1))
 me=bpy.data.meshes.new('chair back mesh'); me.from_pydata(verts,[],faces); me.update(); ob=bpy.data.objects.new('curved white chair back',me); bpy.context.collection.objects.link(ob); ob.data.materials.append(chairmat)
 for p in me.polygons:p.use_smooth=True
 so=ob.modifiers.new('shell thickness','SOLIDIFY'); so.thickness=.025; be=ob.modifiers.new('rounded shell rim','BEVEL'); be.width=.025; be.segments=3
 cyl('chair central support',tr((0,0,.13)),tr((0,0,.48)),.025,dark)
 for i in range(5):
  a=2*math.pi*i/5; xx=.39*math.cos(a); yy=.39*math.sin(a); cyl('five star chair spoke',tr((0,0,.16)),tr((xx,yy,.09)),.027,dark)
  bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,location=tr((xx,yy,.075))); wh=bpy.context.object; wh.name='black caster wheel'; wh.scale=(.075,.052,.075); wh.data.materials.append(dark)
for x,y,a in [(-3.4,-.4,0),(-.25,-.45,0),(2.4,-.35,-.12),(4.7,.0,-.45),(-4.7,1.55,0),(-2.45,1.65,0),(-.35,1.7,0),(1.65,1.72,0),(3.3,1.72,0)]: chair(x,y,a)
# standing lamps in front of right wall
def lamp(x,y):
 cyl('lamp round foot',(x,y,.025),(x,y,.055),.19,brass,32); cyl('thin lamp stem',(x,y,.05),(x,y,1.55),.015,brass)
 bpy.ops.mesh.primitive_cone_add(vertices=40,radius1=.23,radius2=.18,depth=.30,location=(x,y,1.58)); bpy.context.object.name='taupe fabric lampshade'; bpy.context.object.data.materials.append(lampmat)
 for dz,energy in [(.2,80),(-.2,45)]:
  bpy.ops.object.light_add(type='POINT',location=(x,y,1.58+dz)); l=bpy.context.object; l.name='warm lamp glow'; l.data.energy=energy; l.data.color=(1,.68,.45); l.data.shadow_soft_size=.22
lamp(3.65,3.54); lamp(5.35,3.2)
# illumination
world=bpy.context.scene.world or bpy.data.worlds.new('World'); bpy.context.scene.world=world; world.use_nodes=True; world.node_tree.nodes['Background'].inputs[0].default_value=(.78,.80,.83,1); world.node_tree.nodes['Background'].inputs[1].default_value=.6
bpy.ops.object.light_add(type='AREA',location=(0,-1,5)); bpy.context.object.data.energy=850; bpy.context.object.data.shape='DISK'; bpy.context.object.data.size=7
bpy.ops.object.camera_add(location=(0,-9.6,3.15)); cam=bpy.context.object; cam.rotation_euler=(Vector((0,2.0,1.65))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.lens=35; bpy.context.scene.camera=cam
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.samples=32; sc.cycles.use_denoising=True; sc.render.threads_mode='FIXED'; sc.render.threads=8; sc.render.resolution_x=640; sc.render.resolution_y=360; sc.render.resolution_percentage=100
sc.view_settings.view_transform='AgX'; sc.render.image_settings.file_format='PNG'; sc.render.filepath='/app/final.png'; bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
