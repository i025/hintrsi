import bpy, math, random
from mathutils import Vector
random.seed(4)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)

def mat(n,c,rough=.75,metal=0):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal; return m
white=mat('warm white',(.87,.88,.84)); wall=mat('pale mint walls',(.68,.78,.69)); trim=mat('white trim',(.93,.93,.88)); pink=mat('dusty mauve bed frame',(.49,.30,.43)); mattress=mat('white quilted mattress',(.92,.90,.92)); wood=mat('wood table',(.39,.24,.17)); dark=mat('dark legs',(.16,.13,.13)); brass=mat('lamp stem',(.27,.22,.18),.4,.3); shade=mat('lamp shade',(.77,.77,.73)); rug=mat('beige pink rug',(.68,.60,.58)); chair=mat('charcoal chair',(.20,.23,.22)); black=mat('black wardrobe',(.016,.018,.018)); blue=mat('art blue',(.42,.56,.57)); frame=mat('art frame wood',(.73,.58,.46)); cream=mat('art cream',(.87,.83,.72))
def cube(n,loc,scale,ma,bevel=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bevel: mod=o.modifiers.new('soft edges','BEVEL'); mod.width=bevel; mod.segments=3; o.modifiers.new('weighted normals','WEIGHTED_NORMAL')
 return o
def cyl(n,loc,r,depth,ma,verts=32):
 bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=depth,location=loc); o=bpy.context.object; o.name=n; o.data.materials.append(ma); return o
def bar(n,a,b,r,ma):
 d=Vector(b)-Vector(a); o=cyl(n,(Vector(a)+Vector(b))/2,r,d.length,ma,16); o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); return o
# room
cube('floor',(0,0,-.08),(7,8,.16),white)
cube('back wall',(0,3.15,1.8),(7,.15,3.6),wall)
cube('left wall',(-3.45,0,1.8),(.15,6.3,3.6),wall)
cube('back skirting',(0,3.03,.09),(6.8,.09,.18),trim)
cube('left skirting',(-3.33,0,.09),(.09,6,.18),trim)
# floor tile grid
seam=mat('fine tile grout',(.73,.78,.76))
for x in [i*.52-3.1 for i in range(13)]: cube('tile line',(x,0,.002),(.008,6,.004),seam)
for y in [i*.52-3 for i in range(13)]: cube('tile line',(0,y,.003),(6.8,.008,.004),seam)
cube('large soft rug',(.35,-.35,.015),(4.9,3.3,.025),rug,.02)
# shelf, white open cubby grid on the back wall
sx=.60; sy=2.78; sw=3.35; sh=2.52; bottom=.16; top=bottom+sh
for x in [sx-sw/2,sx+sw/2]: cube('bookcase side',(x,sy,bottom+sh/2),(.09,.42,sh),white)
for i in range(1,5): cube('bookcase vertical divider',(sx-sw/2+i*sw/5,sy,bottom+sh/2),(.065,.42,sh),white)
for i in range(5): cube('bookcase shelf',(sx,sy,bottom+i*sh/4),(sw,.44,.075),white)
# bed aligned into room, head at back
bx=-1.67; by=-.28
cube('bed platform',(bx,by,.34),(1.65,3.05,.22),pink,.035)
for x in [bx-.65,bx+.65]:
 for y in [by-1.28,by+1.28]: cyl('bed foot',(x,y,.17),.105,.32,dark)
cube('thick white mattress',(bx,by,.61),(1.57,2.91,.40),mattress,.11)
# headboard rails at back
for x in [bx-.73,bx+.73]: bar('headboard post',(x,1.25,.25),(x,1.25,1.20),.035,dark)
for z in [.82,1.12]: cube('mauve headboard rail',(bx,1.25,z),(1.7,.09,.13),pink,.01)
# bedside table left of headboard
cube('bedside table top',(-2.78,1.57,.73),(.77,.72,.10),wood,.012)
for x in [-3.07,-2.49]:
 for y in [1.31,1.83]: cube('table leg',(x,y,.36),(.055,.055,.72),dark)
# abstract framed wall art
cube('picture backing',(-2.2,3.035,2.12),(.84,.05,1.24),frame)
cube('art print',(-2.2,3.0,2.12),(.72,.018,1.10),blue)
for x in [-2.6,-1.8]: cube('frame vertical',(x,2.98,2.12),(.06,.06,1.25),frame)
for z in [1.52,2.72]: cube('frame horizontal',(-2.2,2.98,z),(.85,.06,.06),frame)
# abstract marks on print
for i in range(25):
 x=random.uniform(-2.48,-2.12); z=random.uniform(2.40,2.56); cube('art dark fleck',(x,2.983,z),(random.uniform(.025,.07),.01,random.uniform(.02,.05)),dark)
for x,z,r in [(-2.14,2.02,.08),(-2.28,1.88,.055)]:
 o=cyl('art circle',(x,2.98,z),r,.012,dark,24); o.rotation_euler[0]=math.pi/2
cube('art pale patch',(-2.48,2.979,2.20),(.15,.01,.13),cream)
# floor lamps
for x,y in [(-3.05,2.10),(2.65,1.8)]:
 cyl('lamp base',(x,y,.035),.22,.07,brass)
 cyl('lamp pole',(x,y,1.00),.022,1.9,brass,16)
 bpy.ops.mesh.primitive_cone_add(vertices=48,radius1=.31,radius2=.22,depth=.55,location=(x,y,1.91)); bpy.context.object.name='tapered lampshade'; bpy.context.object.data.materials.append(shade)
 # soft bulbs and light pools
 bpy.ops.object.light_add(type='POINT',location=(x,y,1.75)); l=bpy.context.object; l.name='lamp light'; l.data.energy=75; l.data.color=(1,.88,.68); l.data.shadow_soft_size=.32
# chair in foreground, molded seat and curved back
# seat ellipsoid
bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,location=(2,-1.65,.58)); o=bpy.context.object; o.name='chair seat'; o.scale=(.68,.56,.15); o.data.materials.append(chair); bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); bpy.ops.object.shade_smooth()
# back as curved broad mesh
verts=[]; faces=[]
for z,y,w in [(.55,-1.28,.48),(.85,-1.22,.48),(1.22,-1.18,.52),(1.48,-1.12,.48),(1.60,-1.10,.35)]:
 for x in [-w,w]: verts.append((2+x,y,z))
for i in range(4): faces.append((2*i,2*i+1,2*i+3,2*i+2))
mesh=bpy.data.meshes.new('chair back mesh'); mesh.from_pydata(verts,[],faces); mesh.update(); o=bpy.data.objects.new('curved chair back',mesh); bpy.context.collection.objects.link(o); o.data.materials.append(chair); mod=o.modifiers.new('smooth back','SUBSURF'); mod.levels=2; mod=o.modifiers.new('thickness','SOLIDIFY'); mod.thickness=.06
for x in [1.65,2.35]:
 for y in [-1.95,-1.35]: bar('chair leg',(x,y,.52),(x+(x-2)*.2,y,.02),.035,dark)
# cropped foreground desk and dark wardrobe
cube('foreground white desk',(-3.0,-2.5,.73),(1.25,1.15,.08),white,.01)
for x in [-3.35,-2.65]: cube('desk leg',(x,-2.15,.36),(.06,.06,.72),dark)
cube('dark wardrobe edge',(3.32,-.4,1.45),(.25,2.25,2.9),black)
# lighting
world=bpy.context.scene.world; world.color=(.65,.65,.65); world.use_nodes=True; world.node_tree.nodes['Background'].inputs[0].default_value=(.68,.73,.70,1); world.node_tree.nodes['Background'].inputs[1].default_value=.45
bpy.ops.object.light_add(type='AREA',location=(0,-1,4.8)); bpy.context.object.data.energy=500; bpy.context.object.data.shape='DISK'; bpy.context.object.data.size=5
# camera
bpy.ops.object.camera_add(location=(5.4,-7.5,4.9)); cam=bpy.context.object; cam.rotation_euler=(Vector((-.15,.55,1.0))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.lens=32; bpy.context.scene.camera=cam
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True; scene.render.threads_mode='FIXED'; scene.render.threads=8
scene.render.resolution_x=640; scene.render.resolution_y=360; scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'; scene.render.image_settings.file_format='PNG'; scene.render.filepath='/app/final.png'
bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
