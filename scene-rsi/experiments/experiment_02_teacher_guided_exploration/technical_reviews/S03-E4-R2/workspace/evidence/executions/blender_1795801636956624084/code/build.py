import bpy, math, random, os
from mathutils import Vector
random.seed(4)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
# materials
def mat(n,c,metal=0,rough=.5):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Metallic'].default_value=metal; p.inputs['Roughness'].default_value=rough; return m
white=mat('warm white',(0.87,.87,.84)); wall=mat('walls',(0.91,.91,.89)); dark=mat('deep teal enamel',(.025,.07,.065),.35); steel=mat('brushed silver',(.43,.46,.44),.7,.3); cook=mat('glass cooktop',(.52,.55,.52),.25,.3); burner=mat('burner circles',(.16,.23,.22),.25); purple=mat('violet chrome',(.32,.19,.31),.75,.25); sage=mat('sage green glass',(.39,.49,.37)); black=mat('charcoal drawer',(.12,.12,.12)); wood=mat('pale timber',(.66,.54,.43)); olive=mat('olive cabinet',(.24,.27,.12),.25); teal=mat('pale aqua worktop',(.51,.72,.70)); pot=mat('grey blue ceramic',(.30,.39,.43)); soil=mat('potting soil',(.31,.22,.20)); leaf=mat('olive leaves',(.28,.31,.10)); marble=mat('white stone',(.82,.83,.81),.05,.32)
def cube(n,loc,scale,ma, bevel=0):
 bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bevel:
  mod=o.modifiers.new('soft edges','BEVEL'); mod.width=bevel; mod.segments=2; o.modifiers.new('weighted normals','WEIGHTED_NORMAL')
 return o
def cyl(n,loc,r,depth,ma,rot=(0,0,0),verts=48):
 bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc, rotation=rot); o=bpy.context.object; o.name=n; o.data.materials.append(ma); o.modifiers.new('edge normals','WEIGHTED_NORMAL'); return o
def rod(n,a,b,r,ma):
 d=Vector(b)-Vector(a); o=cyl(n,(Vector(a)+Vector(b))/2,r,d.length,ma); o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); return o
# room floor and wall
cube('floor',(0,1.2,-.055),(4.5,7,.1),wood)
# individual pale plank floor with seams
planks=[mat('oak tone '+str(i),(0.66+i*.018,0.60+i*.017,0.53+i*.016)) for i in range(4)]
for i in range(14):
 x=-2.1+i*.32
 cube('floor plank',(x,1.4,.002),(.315,6.8,.012),planks[i%4])
 for j in range(4):
  y=-1.9+j*1.65+(i%2)*.82
  cube('plank joint',(x,y,.010),(.315,.006,.002),wood)
cube('back wall',(0,4.05,1.65),(4.5,.12,3.3),wall); cube('left wall',(-2.23,1.1,1.65),(.12,6,3.3),wall); cube('right wall',(2.23,1.1,1.65),(.12,6,3.3),wall)
cube('back skirting',(0,3.96,.09),(4.4,.035,.16),white)
# doorway dark opening and open white door
cube('doorway',(0,3.975,1.27),(1.05,.025,2.54),black)
door=cube('open door',(.29,3.64,1.27),(.88,.055,2.54),white); door.rotation_euler[2]=math.radians(-19)
rod('door handle',(-.1,3.51,1.25),(-.1,3.45,1.25),.018,steel)
# right cabinet run, countertop
cube('right base cabinet',(1.73,.95,.48),(.95,4.1,.96),white)
cube('right marble counter',(1.70,.95,1.01),(1.07,4.2,.12),marble,.012)
# Countertop variants use the same geometry, camera and illumination.
# Object coordinates are in metres, so the streaks do not stretch with object scale.
variant=os.environ.get('COUNTER_VARIANT','image')
n=marble.node_tree.nodes; l=marble.node_tree.links; bs=n.get('Principled BSDF')
tex=n.new('ShaderNodeTexCoord'); sep=n.new('ShaderNodeSeparateXYZ'); l.new(tex.outputs['Object'],sep.inputs[0])
if variant=='image':
 # Art-directed flowing, asymmetric veins generated in countertop-local coordinates.
 # Image is packed into the blend, and can be regenerated from this source.
 size=512; img=bpy.data.images.new('Art directed stone streaks',width=size,height=size)
 pixels=[]
 for j in range(size):
  y=j/(size-1)
  for i in range(size):
   x=i/(size-1)
   v=0.0
   for center,amp,width,phase in [(0.15,.075,.030,0.2),(.31,.11,.042,1.5),(.48,.065,.025,2.8),(.62,.10,.045,4.0),(.79,.08,.035,5.2),(.91,.05,.020,0.9)]:
    path=center+.040*math.sin(y*5.0+phase)+.014*math.sin(y*13+phase*2)
    d=abs(x-path); v+=amp*math.exp(-(d/width)**2)*(0.65+0.35*math.sin(y*4+phase)**2)
   c=max(.64,.86-v); pixels.extend((c,c*.997,c*.99,1))
 img.pixels.foreach_set(pixels); img.pack()
 # Map local x across the short dimension and local y along the counter length.
 comb=n.new('ShaderNodeCombineXYZ')
 for source,scale,offset,socket in [(sep.outputs['X'],.92,.5,'X'),(sep.outputs['Y'],.238,.5,'Y')]:
  mul=n.new('ShaderNodeMath'); mul.operation='MULTIPLY_ADD'; mul.inputs[1].default_value=scale; mul.inputs[2].default_value=offset; l.new(source,mul.inputs[0]); l.new(mul.outputs[0],comb.inputs[socket])
 it=n.new('ShaderNodeTexImage'); it.image=img; it.extension='EXTEND'; l.new(comb.outputs[0],it.inputs['Vector']); l.new(it.outputs['Color'],bs.inputs['Base Color'])
elif variant=='procedural':
 mapping=n.new('ShaderNodeVectorMath'); mapping.operation='MULTIPLY'; mapping.inputs[1].default_value=(5.0,.65,1.0); l.new(tex.outputs['Object'],mapping.inputs[0])
 noise=n.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value=1.3; noise.inputs['Detail'].default_value=3; noise.inputs['Roughness'].default_value=.6; l.new(mapping.outputs[0],noise.inputs[0])
 ramp=n.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].position=.25; ramp.color_ramp.elements[0].color=(.68,.69,.68,1); ramp.color_ramp.elements[1].position=.75; ramp.color_ramp.elements[1].color=(.88,.88,.86,1); l.new(noise.outputs['Fac'],ramp.inputs[0]); l.new(ramp.outputs[0],bs.inputs['Base Color'])
elif variant=='roughness':
 mapping=n.new('ShaderNodeVectorMath'); mapping.operation='MULTIPLY'; mapping.inputs[1].default_value=(5,.7,1); l.new(tex.outputs['Object'],mapping.inputs[0])
 noise=n.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value=1.5; noise.inputs['Detail'].default_value=3; l.new(mapping.outputs[0],noise.inputs[0])
 ramp=n.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color=(.12,.12,.12,1); ramp.color_ramp.elements[1].color=(.65,.65,.65,1); l.new(noise.outputs['Fac'],ramp.inputs[0]); l.new(ramp.outputs[0],bs.inputs['Roughness'])
# faces on inward x side
for j,y in enumerate([-.58,.22,1.02,1.82,2.62]):
 for k,z in enumerate([.17,.47,.77]):
  m= [black,wood,white,black,sage][(j*2+k)%5]
  cube('cabinet drawer front',(1.242,y,z),(.025,.75,.27),m,.006)
  cyl('drawer knob',(1.218,y,z),.022,.045,steel,(0,math.pi/2,0),20)
# wall cabinets on right
for y in [.25,1.3,2.35]:
 cube('upper cabinet',(1.97,y,2.50),(.49,.99,.90),white,.01)
 cube('upper green inset',(1.714,y,2.50),(.018,.83,.72),sage)
 cyl('upper cabinet pull',(1.69,y,2.48),.02,.035,steel,(0,math.pi/2,0),16)
# stove left foreground. inner side faces toward camera
cube('range body',(-1.40,.45,.49),(1.25,1.32,.98),dark,.015)
cube('range top rim',(-1.40,.45,1.01),(1.30,1.34,.10),steel,.01)
cube('range cook surface',(-1.40,.45,1.07),(1.20,1.23,.035),cook)
for x in [-1.73,-1.08]:
 for y in [.06,.48,.88]: cyl('round electric burner',(x,y,1.092),.16,.006,burner,verts=64)
# raised control panel at back
panel=cube('raised range control panel',(-1.40,1.16,1.38),(1.30,.16,.55),steel,.012); panel.rotation_euler[0]=math.radians(-12)
for x in [-1.83,-.98]:
 cyl('purple control dial',(x,1.055,1.42),.115,.07,purple,(math.pi/2,0,0))
 cube('dial index',(x,1.012,1.46),(.012,.008,.07),black)
# range oven face on visible right side
cube('oven door',(-.765,.43,.51),(.035,1.10,.68),dark,.01)
rod('oven handle',(-.71,-.02,.82),(-.71,.86,.82),.025,purple)
# left rear cabinet and aqua top
cube('rear island cabinet',(-1.47,2.40,.48),(1.34,1.60,.96),olive)
cube('rear aqua countertop',(-1.46,2.40,1.03),(1.42,1.68,.15),teal,.01)
rod('rear cabinet pull',(-.76,1.88,.22),(-.76,1.88,.81),.023,purple)
# plant by back wall
cyl('plant pot',(1.03,3.45,.18),.22,.34,pot,verts=48); cyl('pot soil',(1.03,3.45,.356),.20,.012,soil)
rod('plant stem',(1.03,3.45,.35),(1.06,3.45,1.64),.012,leaf)
def blade(n,a,b,width):
 a=Vector(a); b=Vector(b); mid=a.lerp(b,.55); side=Vector((width,0,0)); verts=[a,mid+side,b,mid-side]; mesh=bpy.data.meshes.new(n); mesh.from_pydata(verts,[],[(0,1,2,3)]); mesh.materials.append(leaf); obj=bpy.data.objects.new(n,mesh); bpy.context.collection.objects.link(obj); sol=obj.modifiers.new('leaf thickness','SOLIDIFY'); sol.thickness=.008
for i,(z,dx,dy,dz) in enumerate([(0.6,-.20,.02,.42),(.72,.22,.01,.35),(.9,-.16,0,.43),(1.02,.16,.04,.4),(1.2,-.1,0,.35)]): blade('pointed plant leaf',(1.05,3.45,z),(1.05+dx,3.45+dy,z+dz),.045)
blade('tall bud',(1.06,3.45,1.52),(1.09,3.45,1.85),.055)
# lighting
def area(n,loc,power,size,target):
 bpy.ops.object.light_add(type='AREA', location=loc); o=bpy.context.object; o.name=n; o.data.energy=power; o.data.shape='DISK'; o.data.size=size; o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
area('large overhead softbox',(0,-.4,3.8),350,4,(0,1,0)); area('rear daylight',(0,3,3.0),180,2,(0,1,0)); area('front fill',(0,-3,2.8),120,3,(0,1,1))
if os.environ.get('ALT_LIGHT'):
 bpy.data.objects['large overhead softbox'].location=(3,2,3.8)
 bpy.data.objects['large overhead softbox'].rotation_euler=(Vector((0,1,0))-bpy.data.objects['large overhead softbox'].location).to_track_quat('-Z','Y').to_euler()
world=bpy.context.scene.world; world.color=(.65,.65,.65)
# camera
bpy.ops.object.camera_add(location=(0,-1.6,2.05)); cam=bpy.context.object; cam.rotation_euler=(Vector((0,2.0,1.0))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.lens=22; bpy.context.scene.camera=cam
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True; scene.render.threads_mode='FIXED'; scene.render.threads=8
scene.render.resolution_x=640; scene.render.resolution_y=360; scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'; scene.render.image_settings.file_format='PNG'; scene.render.filepath='/app/final.png'
if os.environ.get('COMPARISON'):
 scene.render.filepath='/app/compare_'+variant+('_alternate' if os.environ.get('ALT_LIGHT') else '')+'.png'
else:
 bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend')
bpy.ops.render.render(write_still=True)
