import bpy, math, random
from mathutils import Vector
random.seed(14)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)

def mat(n,c,rough=0.6,metal=0):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal; return m
white=mat('warm white plaster',(0.75,0.75,0.73)); trim=mat('white baseboards',(0.91,0.91,0.89)); wood=mat('light maple',(0.66,0.43,0.29)); edge=mat('pale maple trim',(0.77,0.55,0.40)); slat=mat('venetian blind slats',(0.83,0.65,0.53)); dark=mat('charcoal door',(0.19,0.19,0.18)); groove=mat('door inset shadow',(0.09,0.09,0.085)); chair=mat('chair warm grey',(0.42,0.43,0.42)); black=mat('black chair hardware',(0.035,0.038,0.037),0.4); desk=mat('dark grey desk',(0.24,0.25,0.25)); pot=mat('glazed teal planter',(0.035,0.20,0.19),0.24); soil=mat('soil',(0.055,0.047,0.038)); leafm=[mat('grass olive %02d'%i,(0.12+i*.012,0.15+i*.012,0.045+i*.005)) for i in range(7)]

def cube(n,loc,scale,ma,bevel=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bevel:
  mod=o.modifiers.new('soft edges','BEVEL'); mod.width=bevel; mod.segments=2; o.modifiers.new('weighted normals','WEIGHTED_NORMAL')
 return o

def cyl(n,loc,r,depth,ma,vertices=24):
 bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=depth,location=loc); o=bpy.context.object; o.name=n; o.data.materials.append(ma); return o

def rod(n,a,b,r,ma):
 mid=(Vector(a)+Vector(b))/2; d=Vector(b)-Vector(a); o=cyl(n,mid,r,d.length,ma,12); o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); return o
# room
cube('floor substrate',(0,0,-.09),(10,9,.18),white)
# individual wood floorboards with randomized tones
floor_mats=[mat('floorboard %02d'%i,(.32+i*.013,.29+i*.011,.25+i*.009)) for i in range(12)]
for ix in range(34):
 x=-4.9+ix*.30
 for iy in range(8):
  y=-4.3+iy*1.17+(ix%2)*.58
  cube('individual timber floor plank',(x,y,.008),(.294,1.16,.025),random.choice(floor_mats))
cube('back wall',(0,3.0,1.7),(10,.12,3.4),white)
cube('right wall',(4.35,-.3,1.7),(.12,6.65,3.4),white)
cube('back skirting',(0,2.91,.105),(8.65,.09,.21),trim,.012)
cube('right skirting',(4.26,-.2,.105),(.09,6.2,.21),trim,.012)
# window left side back wall
cube('window recess',(-1.72,2.90,2.30),(2.65,.055,1.48),slat)
for x in [-3.10,-.34]: cube('window side casing',(x,2.82,2.30),(.14,.13,1.68),edge,.012)
for z in [1.49,3.11]: cube('window horizontal casing',(-1.72,2.82,z),(2.89,.13,.14),edge,.012)
for i in range(29):
 z=1.56+i*.053
 cube('horizontal blind slat %02d'%i,(-1.72,2.79,z),(2.58,.07,.025),slat,.006)
# shelving under window
cube('shelf top',(-1.68,2.46,1.17),(2.65,.55,.13),edge,.01)
cube('shelf base',(-1.68,2.46,.15),(2.65,.55,.13),wood,.01)
for x in [-2.96,-2.33,-1.70,-1.07,-.40]: cube('shelf vertical divider',(x,2.46,.66),(.10,.55,1.00),wood,.008)
cube('middle shelf',(-1.68,2.46,.64),(2.59,.55,.09),wood,.008)
# tall white cabinet beside shelf
cube('white narrow cabinet',(.17,2.67,.67),(.48,.48,1.32),trim,.015)
cube('cabinet front inset',(.17,2.414,.69),(.36,.025,1.12),white,.005)
# paneled door on right wall
cube('door frame',(4.25,1.60,1.42),(.16,1.30,2.83),trim,.012)
cube('door dark slab',(4.14,1.60,1.40),(.10,1.18,2.73),dark,.012)
# inset panel strips on visible surface of right wall
for y in [1.29,1.91]:
 for z in [.43,1.02,1.60,2.18]:
  w=.43; h=.48 if z<1 else .42
  cube('recessed door panel',(4.078,y,z),(.012,w,h),groove,.006)
  cube('raised center of door panel',(4.067,y,z),(.012,w-.035,h-.035),dark,.004)
# desk foreground
cube('desk top',(-.55,-1.95,.78),(2.65,1.32,.09),desk,.015)
for x in [-1.70,.60]:
 for y in [-2.45,-1.48]: cube('desk leg',(x,y,.39),(.07,.07,.76),black)
cube('second foreground tabletop',(1.25,-3.0,.76),(1.7,.85,.08),desk,.01)
# chairs, shell modeled as smooth surface with seating and rising back; local facing toward negative y
def makechair(x,y,angle):
 # local shell width x; front negative y, back positive y
 verts=[]; faces=[]
 rows=[(-.48,.76,.31),(-.31,.72,.46),(0,.73,.48),(.22,.82,.45),(.32,1.01,.41),(.38,1.32,.38),(.40,1.63,.31)]
 for yy,z,w in rows:
  for j in range(9):
   u=(j-4)/4; verts.append((u*w,yy,z+0.07*u*u))
 for i in range(len(rows)-1):
  for j in range(8):
   a=i*9+j; faces.append((a,a+1,a+10,a+9))
 me=bpy.data.meshes.new('molded shell mesh'); me.from_pydata(verts,[],faces); me.update(); ob=bpy.data.objects.new('grey molded chair shell',me); bpy.context.collection.objects.link(ob); ob.location=(x,y,0); ob.rotation_euler[2]=angle; ob.data.materials.append(chair)
 for p in me.polygons:p.use_smooth=True
 mod=ob.modifiers.new('shell smoothing','SUBSURF'); mod.levels=2; mod.render_levels=2
 mod=ob.modifiers.new('shell thickness','SOLIDIFY'); mod.thickness=.035
 cyl('chair center column',(x,y,.42),.045,.55,black)
 cyl('chair hub',(x,y,.16),.11,.10,black)
 for i in range(5):
  a=i*math.tau/5; end=(x+.45*math.cos(a),y+.45*math.sin(a),.12); rod('chair five star spoke',(x,y,.18),end,.035,black); cyl('caster wheel',(end[0],end[1],.075),.075,.09,black,16)
makechair(-.54,1.02,-.20); makechair(1.55,-.45,.45)
# floor lamp near shelf
cyl('lamp foot',(-3.55,1.93,.04),.16,.07,black); rod('lamp stem',(-3.55,1.93,.07),(-3.55,1.93,1.70),.018,black)
bpy.ops.mesh.primitive_cone_add(vertices=48,radius1=.24,radius2=.16,depth=.43,location=(-3.55,1.93,1.86)); bpy.context.object.name='ivory tapered lampshade'; bpy.context.object.data.materials.append(trim)
# planter with tapered ceramic bowl
bpy.ops.mesh.primitive_cone_add(vertices=64,radius1=.43,radius2=.61,depth=.48,location=(3.36,-2.50,.25)); bpy.context.object.name='large teal plant pot'; bpy.context.object.data.materials.append(pot)
cyl('dark soil',(3.36,-2.50,.50),.56,.025,soil,64)
# dense long pointed grass blades radiating from the pot
for i in range(340):
 a=random.random()*math.tau; rad=random.random()*.34; bx=3.36+rad*math.cos(a); by=-2.50+rad*math.sin(a); h=random.uniform(.45,1.25); lean=random.uniform(.12,.60); a2=a+random.uniform(-.6,.6); dx=math.cos(a2)*lean; dy=math.sin(a2)*lean; w=random.uniform(.008,.023); perp=Vector((-math.sin(a2)*w,math.cos(a2)*w,0)); base=Vector((bx,by,.50)); middle=base+Vector((dx*.45,dy*.45,h*.62)); tip=base+Vector((dx,dy,h)); vs=[base-perp,base+perp,middle+perp*.65,tip,middle-perp*.65]; me=bpy.data.meshes.new('grass blade'); me.from_pydata(vs,[],[(0,1,2,3,4)]); ob=bpy.data.objects.new('pointed grass blade',me); bpy.context.collection.objects.link(ob); ob.data.materials.append(random.choice(leafm))
# illumination
world=bpy.context.scene.world or bpy.data.worlds.new('World'); bpy.context.scene.world=world; world.use_nodes=True; world.node_tree.nodes['Background'].inputs[0].default_value=(.75,.77,.78,1); world.node_tree.nodes['Background'].inputs[1].default_value=.7
bpy.ops.object.light_add(type='AREA',location=(0,-2,5.5)); bpy.context.object.data.energy=700; bpy.context.object.data.shape='DISK'; bpy.context.object.data.size=5
bpy.ops.object.light_add(type='AREA',location=(-3,-1,3.6)); bpy.context.object.data.energy=300; bpy.context.object.data.size=4
# camera
bpy.ops.object.camera_add(location=(4.0,-7.5,4.5)); cam=bpy.context.object; target=Vector((0,1.0,1.05)); cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.type='PERSP'; cam.data.lens=26; bpy.context.scene.camera=cam
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.samples=32; sc.cycles.use_denoising=True; sc.render.resolution_x=640; sc.render.resolution_y=360; sc.render.resolution_percentage=100; sc.render.image_settings.file_format='PNG'; sc.render.filepath='/app/final.png'; sc.view_settings.view_transform='AgX'; sc.render.film_transparent=False
bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
