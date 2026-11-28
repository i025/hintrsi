import bpy, math, random
from mathutils import Vector
random.seed(4)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)

def mat(n,c,rough=0.8,metal=0):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal; return m
white=mat('Warm white painted wood',(0.87,.88,.84)); wall=mat('Pale mint walls',(.72,.82,.72)); floor=mat('Pale ceramic tiles',(.76,.81,.79)); grout=mat('Tile seams',(.62,.69,.67)); purple=mat('Dusty mauve bed frame',(.48,.30,.43)); mattress=mat('Soft white mattress',(.92,.91,.92)); dark=mat('Dark metal',(.17,.16,.16),.4,.4); shade=mat('Cream lampshade',(.83,.82,.78)); rug=mat('Blush beige rug',(.70,.60,.59)); chairmat=mat('Charcoal grey chair',(.30,.32,.30)); wood=mat('Table walnut',(.37,.24,.19)); gold=mat('Picture frame pale wood',(.76,.61,.49)); blue=mat('Artwork blue grey',(.53,.64,.66)); black=mat('Art ink',(.06,.075,.06)); yellow=mat('Art ochre',(.59,.54,.35));
def cube(n,loc,scale,ma,bevel=0):
 bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bevel: mod=o.modifiers.new('Soft edges','BEVEL'); mod.width=bevel; mod.segments=3; o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
 return o
def cyl(n,loc,r,depth,ma,verts=32):
 bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc); o=bpy.context.object; o.name=n; o.data.materials.append(ma); return o
def rod(n,a,b,r,ma):
 d=Vector(b)-Vector(a); o=cyl(n,(Vector(a)+Vector(b))/2,r,d.length,ma,16); o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); return o
def point(n,loc,energy,color=(1,.91,.76),size=.2):
 bpy.ops.object.light_add(type='POINT',location=loc); o=bpy.context.object; o.name=n; o.data.energy=energy; o.data.color=color; o.data.shadow_soft_size=size
# room
cube('Floor',(0,0,-.08),(6.5,6,.16),floor)
cube('Back wall',(0,2.55,1.8),(6.5,.12,3.6),wall)
cube('Left wall',(-3.2,-.2,1.8),(.12,5.5,3.6),wall)
cube('Right wall',(3.2,.3,1.8),(.12,4.5,3.6),wall)
for x in [i*.45 for i in range(-7,8)]: cube('floor grout',(x,0,.003),(.007,5.1,.003),grout)
for y in [i*.45 for i in range(-6,6)]: cube('floor grout',(0,y,.004),(6.3,.007,.003),grout)
cube('Back skirting',(0,2.45,.08),(6.35,.08,.16),white)
cube('Right skirting',(3.12,.2,.08),(.08,4.5,.16),white)
# rug
cube('Large muted pink rug',(0,-.88,.015),(3.9,2.35,.025),rug)
# shelving on back wall, open cubbies
sx=.55; sy=2.17; bottom=.15; height=2.5; width=3.05; depth=.36
for x in [sx-width/2,sx+width/2]: cube('Bookcase side',(x,sy,bottom+height/2),(.085,depth,height),white)
for z in [bottom+i*height/4 for i in range(5)]: cube('Bookcase horizontal shelf',(sx,sy,z),(width,depth,.075),white)
for x in [sx-width/2+i*width/5 for i in range(1,5)]: cube('Bookcase upright',(x,sy,bottom+height/2),(.075,depth,height),white)
# bed across the foreground
bx=-1.0; by=-.65
cube('Bed platform',(bx,by,.30),(2.95,1.58,.20),purple,.025)
for x in [-2.28,.26]:
 for y in [-1.24,-.06]: cyl('Bed foot',(x,y,.16),.09,.32,dark)
cube('White mattress',(bx,by,.55),(2.78,1.48,.38),mattress,.09)
# mattress lower seam
cube('Mattress piping',(bx,by,.405),(2.79,1.49,.018),white,.008)
# headboard on left end
for y in [-1.36,.06]: rod('Headboard metal post',(-2.48,y,.32),(-2.48,y,1.10),.035,dark)
for z in [.76,1.00]: cube('Mauve headboard slat',(-2.48,-.65,z),(.09,1.57,.14),purple,.018)
# side table near bed at back left
cube('Bedside table top',(-2.0,1.06,.65),(.86,.67,.08),wood,.02)
for x in [-2.36,-1.64]:
 for y in [.80,1.32]: cube('Table leg',(x,y,.33),(.055,.055,.64),dark)
# light streaks in wood tabletop
for i in range(12):
 x=-2.39+i*.067
 ob=cube('Wood grain',(x,1.06,.695),(.012,.60,.003),gold); ob.rotation_euler[2]=.25
# floor lamps with tapered shade
def lamp(x,y,h):
 cyl('Lamp base',(x,y,.025),.21,.05,dark); cyl('Lamp stem',(x,y,h/2),.018,h,dark)
 bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=.27, radius2=.19, depth=.48, location=(x,y,h)); o=bpy.context.object; o.name='Tapered linen lampshade'; o.data.materials.append(shade)
 cyl('Lamp glowing top',(x,y,h+.235),.183,.01,white,48); point('Warm lamp light',(x,y,h-.16),75,(1,.85,.65),.3)
lamp(-2.85,1.35,1.72); lamp(2.62,1.20,1.78)
# framed abstract art on back wall
cube('Artwork backing',(-2.03,2.46,2.12),(.94,.07,1.29),gold,.01)
cube('Blue artwork',(-2.03,2.411,2.12),(.83,.02,1.17),blue)
# artwork ink spots on vertical face
for i in range(55):
 x=-2.36+random.random()*.36; z=2.46+random.random()*.13
 cube('Ink fleck',(x,2.397,z),(.035,.009,.03),black,.005)
for i in range(16):
 x=-2.12+random.uniform(-.06,.06); z=2.02+random.uniform(-.06,.06)
 cube('Artwork mark',(x,2.394,z),(.025,.01,.028),black,.006)
# small ochre circles on art via torus facing camera
for x,z in [(-2.2,1.78),(-1.77,1.79),(-2.11,2.02)]:
 bpy.ops.mesh.primitive_torus_add(major_radius=.07,minor_radius=.009,major_segments=24,minor_segments=8,location=(x,2.39,z),rotation=(math.pi/2,0,0)); bpy.context.object.name='Artwork circle'; bpy.context.object.data.materials.append(yellow)
# sculpted chair foreground: mesh seat and back as continuous curved shell
verts=[]; faces=[]
profile=[(-.48,.48),(-.3,.44),(0,.43),(.25,.46),(.36,.54),(.38,.74),(.39,.95),(.43,1.12),(.48,1.20)]
for y,z in profile:
 for x in [-.39,.39]: verts.append((x+1.75,y-1.65,z))
for i in range(len(profile)-1): faces.append((2*i,2*i+1,2*i+3,2*i+2))
me=bpy.data.meshes.new('Chair shell mesh'); me.from_pydata(verts,[],faces); me.update(); ob=bpy.data.objects.new('Curved grey chair shell',me); bpy.context.collection.objects.link(ob); ob.data.materials.append(chairmat)
sol=ob.modifiers.new('Shell thickness','SOLIDIFY'); sol.thickness=.04
sub=ob.modifiers.new('Smooth rounded chair','SUBSURF'); sub.levels=2
for p in me.polygons: p.use_smooth=True
for x in [1.48,2.02]:
 for y in [-1.95,-1.37]: rod('Chair leg',(x,y,.46),(x+(-.10 if x<1.75 else .10),y-.05,.02),.025,dark)
# cropped desk at bottom left
cube('White desk corner',(-2.65,-2.35,.74),(1.15,.90,.065),white,.01)
for x in [-3.05,-2.25]: rod('Desk leg',(x,-2.15,.72),(x,-2.15,.02),.035,dark)
# dark edge of foreground doorway
cube('Dark door edge',(3.1,-1.85,1.4),(.17,.25,2.8),dark)
# lighting and camera
world=bpy.context.scene.world or bpy.data.worlds.new('World'); bpy.context.scene.world=world; world.use_nodes=True; world.node_tree.nodes['Background'].inputs[0].default_value=(.75,.79,.75,1); world.node_tree.nodes['Background'].inputs[1].default_value=.45
bpy.ops.object.light_add(type='AREA', location=(0,-2,4.7)); bpy.context.object.name='Large ceiling softbox'; bpy.context.object.data.energy=450; bpy.context.object.data.shape='DISK'; bpy.context.object.data.size=5
bpy.ops.object.camera_add(location=(3.25,-6.8,3.55)); cam=bpy.context.object; cam.name='Camera'; target=Vector((0,.35,1.05)); cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.type='PERSP'; cam.data.lens=38; bpy.context.scene.camera=cam
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.samples=32; sc.cycles.use_denoising=True; sc.render.threads_mode='FIXED'; sc.render.threads=8; sc.render.resolution_x=640; sc.render.resolution_y=360; sc.render.resolution_percentage=100
sc.view_settings.view_transform='AgX'; sc.render.image_settings.file_format='PNG'; sc.render.filepath='/app/final.png'; bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
