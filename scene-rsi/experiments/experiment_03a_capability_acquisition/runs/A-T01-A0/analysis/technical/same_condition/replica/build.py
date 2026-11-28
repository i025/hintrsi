import bpy, math, random
from mathutils import Vector
random.seed(4)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)

def mat(n,c,rough=.7,metal=0):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal; return m
wall=mat('warm ivory wall',(0.76,.73,.70)); floor=mat('pale polished floor',(.73,.71,.69),.35); grout=mat('fine hexagonal seams',(.57,.55,.53)); black=mat('black metal',(.025,.025,.025),.45); desk=mat('dark grey table tops',(.23,.22,.22)); white=mat('white molded plastic',(.91,.90,.88),.34); frame=mat('dark bronze window frame',(.075,.061,.055),.35); glass=mat('pale sky glass',(.65,.75,.80),.28); shade=mat('lamp fabric',(.46,.41,.38)); brass=mat('lamp stems',(.36,.20,.16),.4)
def cube(n,loc,scale,ma,bevel=0):
 bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bevel: mod=o.modifiers.new('soft edges','BEVEL'); mod.width=bevel; mod.segments=3; o.modifiers.new('weighted normals','WEIGHTED_NORMAL')
 return o
def rod(n,a,b,r,ma,verts=12):
 d=Vector(b)-Vector(a); mid=(Vector(a)+Vector(b))/2; bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=d.length, location=mid); o=bpy.context.object; o.name=n; o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); o.data.materials.append(ma); return o
# room: camera facing back wall y=4
cube('floor',(0,0,-.06),(14,16,.12),floor)
cube('back wall',(0,4.05,2.2),(14,.12,4.4),wall)
cube('right wall',(6.05,0,2.2),(.12,8.2,4.4),wall)
cube('right baseboard',(5.96,.0,.09),(.06,8,.18),white)
# fine hex tiles, drawn as thin lines on walls, grouped curve
cu=bpy.data.curves.new('hex tile joints','CURVE'); cu.dimensions='3D'; cu.bevel_depth=.003; cu.bevel_resolution=0
r=.135
# pointy top hex, x spacing sqrt(3)r, z spacing 1.5r
for row in range(24):
 z=row*1.5*r
 for col in range(-32,33):
  x=col*math.sqrt(3)*r+(row%2)*math.sqrt(3)*r/2
  if abs(x)>6.9: continue
  sp=cu.splines.new('POLY'); sp.points.add(6)
  for j in range(7):
   a=math.pi/6+j*math.pi/3; sp.points[j].co=(x+r*math.cos(a),3.978,z+r*math.sin(a),1)
obj=bpy.data.objects.new('hexagon pattern back wall',cu); bpy.context.collection.objects.link(obj); obj.data.materials.append(grout)
cu2=cu.copy(); obj=bpy.data.objects.new('hexagon pattern right wall',cu2); bpy.context.collection.objects.link(obj); obj.rotation_euler[2]=math.pi/2; obj.location=(9.95,-2.0,0)
# window inset at back
cube('window dark outer frame',(0,3.91,2.45),(2.05,.13,1.65),frame,.018)
cube('window glass left',(-.49,3.83,2.45),(.91,.025,1.48),glass)
cube('window glass right',(.49,3.83,2.45),(.91,.025,1.48),glass)
cube('window center mullion',(0,3.79,2.45),(.09,.07,1.58),frame)
# tables in two rows, modular
for y in [1.45,3.0]:
 for x in [-4.5,-2.25,0,2.25,4.5]:
  cube('rectangular charcoal tabletop',(x,y,.78),(2.18,.75,.065),desk,.012)
  for dx in [-.98,.98]:
   for dy in [-.29,.29]: rod('slender table leg',(x+dx,y+dy,.04),(x+dx,y+dy,.76),.018,black,8)
# chairs viewed from back. molded curved shell formed mesh; front faces +y
def chair(x,y,ang=0):
 # seat oval
 bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=12,location=(x,y,.48)); o=bpy.context.object; o.name='white curved seat'; o.scale=(.49,.42,.075); o.data.materials.append(white); bpy.ops.object.shade_smooth()
 # curved back shell across width, rising behind seat (toward camera)
 verts=[]; faces=[]
 for iz in range(11):
  t=iz/10; z=.48+.68*t; width=.46*(1-.28*t*t)
  for ix in range(17):
   u=ix/8-1; xx=width*u; yy=-.29-.12*t+.12*u*u; zz=z-.07*(abs(u)**3)*t
   verts.append((x+xx,y+yy,zz))
 for iz in range(10):
  for ix in range(16):
   a=iz*17+ix; faces.append((a,a+1,a+18,a+17))
 mesh=bpy.data.meshes.new('molded chair back mesh'); mesh.from_pydata(verts,[],faces); mesh.update(); ob=bpy.data.objects.new('rounded white chair back',mesh); bpy.context.collection.objects.link(ob); ob.data.materials.append(white)
 for p in mesh.polygons:p.use_smooth=True
 sol=ob.modifiers.new('plastic thickness','SOLIDIFY'); sol.thickness=.025
 sub=ob.modifiers.new('rounded shell','SUBSURF'); sub.levels=2
 rod('central chair column',(x,y,.11),(x,y,.48),.035,black)
 for i in range(5):
  a=2*math.pi*i/5+.2; ex=x+.48*math.cos(a); ey=y+.48*math.sin(a)
  rod('five star chair base',(x,y,.13),(ex,ey,.09),.037,black,8)
  bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,location=(ex,ey,.075)); w=bpy.context.object; w.name='black caster'; w.scale=(.085,.055,.075); w.data.materials.append(black)
for x,y in [(-4.1,-.7),(-1.35,-.65),(1.5,-.6),(4.0,-.5),(-4.35,2.2),(-2.25,2.25),(0,2.25),(2.15,2.25),(4.05,2.25)]: chair(x,y)
# lamps along right wall
for y in [2.5,-.5]:
 x=5.55
 bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.20,depth=.035,location=(x,y,.03)); bpy.context.object.data.materials.append(brass)
 rod('slender floor lamp stem',(x,y,.04),(x,y,1.62),.017,brass)
 bpy.ops.mesh.primitive_cone_add(vertices=32,radius1=.24,radius2=.19,depth=.35,location=(x,y,1.61)); bpy.context.object.name='taupe lampshade'; bpy.context.object.data.materials.append(shade)
 for z,energy in [(1.82,100),(1.40,65)]:
  bpy.ops.object.light_add(type='POINT', location=(x-.1,y,z)); l=bpy.context.object; l.name='warm lamp glow'; l.data.energy=energy; l.data.color=(1,.66,.42); l.data.shadow_soft_size=.25
# lights
world=bpy.context.scene.world; world.color=(.7,.7,.7)
bpy.ops.object.light_add(type='AREA',location=(0,-2,5)); bpy.context.object.data.energy=900; bpy.context.object.data.shape='DISK'; bpy.context.object.data.size=8
bpy.ops.object.light_add(type='AREA',location=(-4,1,4)); bpy.context.object.data.energy=350; bpy.context.object.data.size=5
# camera
bpy.ops.object.camera_add(location=(0,-8.8,2.65)); cam=bpy.context.object; cam.rotation_euler=(Vector((0,2,1.45))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.type='PERSP'; cam.data.lens=32; bpy.context.scene.camera=cam
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True; scene.render.threads_mode='FIXED'; scene.render.threads=8
scene.render.resolution_x=640; scene.render.resolution_y=360; scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'; scene.render.image_settings.file_format='PNG'; scene.render.filepath='/app/final.png'
bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
