import bpy, math, random
from mathutils import Vector
random.seed(8)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)

def mat(n,c,rough=.5,metal=0):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal; return m
pink=mat('dusty rose plaster',(.66,.39,.42)); white=mat('warm white trim',(.83,.80,.76)); dark=mat('black chair hardware',(.025,.028,.028),.35, .25); chairmat=mat('pale blush upholstery',(.68,.59,.56),.75); wood=mat('window frame walnut',(.30,.16,.10),.38); teal=mat('dark teal door',(.025,.09,.09),.32); glass=mat('frosted bright window',(.71,.72,.68),.28); plantmat=mat('plant leaves',(.055,.18,.065),.65)

def cube(n,loc,scale,ma,bev=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bev:
  mod=o.modifiers.new('soft edges','BEVEL'); mod.width=bev; mod.segments=3; o.modifiers.new('weighted normals','WEIGHTED_NORMAL')
 return o

def beam(n,a,b,r,ma):
 d=Vector(b)-Vector(a); mid=(Vector(a)+Vector(b))/2; bpy.ops.mesh.primitive_cylinder_add(vertices=12,radius=r,depth=d.length,location=mid); o=bpy.context.object; o.name=n; o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); o.data.materials.append(ma); return o
# glossy checker floor procedural
floor=bpy.data.materials.new('glossy small checker parquet'); floor.diffuse_color=(.2,.12,.12,1); floor.use_nodes=True
nd=floor.node_tree.nodes; lk=floor.node_tree.links; p=nd.get('Principled BSDF'); p.inputs['Roughness'].default_value=.22
tex=nd.new('ShaderNodeTexChecker'); tex.inputs['Color1'].default_value=(.075,.065,.065,1); tex.inputs['Color2'].default_value=(.35,.20,.19,1); tex.inputs['Scale'].default_value=1
coord=nd.new('ShaderNodeTexCoord'); mapping=nd.new('ShaderNodeVectorMath'); mapping.operation='SCALE'; mapping.inputs[3].default_value=4.2; lk.new(coord.outputs['Object'],mapping.inputs[0]); lk.new(mapping.outputs[0],tex.inputs['Vector']); lk.new(tex.outputs['Color'],p.inputs['Base Color'])
cube('floor',(0,0,-.09),(10,12,.18),floor)
cube('left pink wall',(-5,0,2.05),(.16,12,4.1),pink); cube('far pink wall',(0,5.95,2.05),(10,.16,4.1),pink)
cube('left baseboard',(-4.89,0,.12),(.08,12,.24),white,.02); cube('back baseboard',(0,5.84,.12),(10,.08,.24),white,.02)
# window glazing overlay and wooden frame, left wall
cube('left frosted window',(-4.895,1.0,2.25),(.025,7.4,1.65),glass)
for y in [-2.7,-.23,1.55,2.9,3.76,4.7]: cube('left window mullion',(-4.86,y,2.25),(.07,.065,1.75),wood,.01)
for z in [1.39,3.11]: cube('left window frame',(-4.86,1, z),(.07,7.45,.07),wood,.01)
# far wall window
cube('back frosted window',(1.35,5.84,2.45),(2.65,.025,1.42),glass)
for x in [.01,2.69]: cube('back window vertical',(x,5.8,2.45),(.055,.07,1.5),dark)
for z in [1.72,3.18]: cube('back window horizontal',(1.35,5.8,z),(2.73,.07,.055),dark)
# large conference table polished pink wood
surface=mat('polished rosewood table',(.36,.20,.19),.19)
nt=surface.node_tree.nodes; links=surface.node_tree.links; bs=nt.get('Principled BSDF'); noise=nt.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value=3; noise.inputs['Detail'].default_value=3; texco=nt.new('ShaderNodeTexCoord'); mp=nt.new('ShaderNodeVectorMath'); mp.operation='MULTIPLY'; mp.inputs[1].default_value=(.6,12,3); links.new(texco.outputs['Generated'],mp.inputs[0]); links.new(mp.outputs[0],noise.inputs['Vector']); ramp=nt.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color=(.16,.085,.075,1); ramp.color_ramp.elements[1].color=(.52,.31,.29,1); links.new(noise.outputs['Fac'],ramp.inputs[0]); links.new(ramp.outputs['Color'],bs.inputs['Base Color'])
cube('long conference tabletop',(0,2.05,1.28),(6.9,2.45,.12),surface,.045)
for x in [-2.9,2.9]:
 for y in [1.1,3.0]: beam('splayed black table leg',(x,y,1.24),(x+(.20 if x>0 else -.20),y+(.22 if y>2 else -.22),.04),.035,dark)
# office chairs: seat and softly rounded upright backs
# y-facing chairs
for y,sgn in [(.28,-1),(3.78,1)]:
 for x in [-2.55,-1.3,0,1.3,2.6]:
  # face table; back farther from table
  cube('chair padded seat',(x,y,.67),(.79,.69,.15),chairmat,.12)
  back=cube('chair curved upholstered back',(x,y+sgn*.31,1.09),(.76,.16,.80),chairmat,.16); back.rotation_euler[0]=sgn*.10
  beam('chair center stem',(x,y,.22),(x,y,.66),.047,dark)
  for i in range(5):
   a=2*math.pi*i/5; end=(x+.42*math.cos(a),y+.42*math.sin(a),.12); beam('five star chair base',(x,y,.23),end,.035,dark)
   bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,radius=.075,location=(end[0],end[1],.095)); bpy.context.object.name='caster wheel'; bpy.context.object.scale=(1,.6,.7); bpy.context.object.data.materials.append(dark)
# plant near back corner
pot=mat('planter',(.22,.18,.16)); bpy.ops.mesh.primitive_cone_add(vertices=24,radius1=.18,radius2=.25,depth=.42,location=(-2.55,5.45,.22)); bpy.context.object.data.materials.append(pot)
for i in range(9):
 a=i*2.4; base=Vector((-2.55,5.45,.4)); tip=base+Vector((.35*math.cos(a),.35*math.sin(a),random.uniform(.55,1.05))); side=Vector((-.11*math.sin(a),.11*math.cos(a),.02)); mid=base.lerp(tip,.5); mesh=bpy.data.meshes.new('leaf'); mesh.from_pydata([base,mid+side,tip,mid-side],[],[(0,1,2,3)]); mesh.materials.append(plantmat); o=bpy.data.objects.new('pointed green leaf',mesh); bpy.context.collection.objects.link(o)
# foreground right door, open panel
D=cube('open dark teal door',(4.6,-3.2,2.1),(.16,1.9,4.2),teal,.025); D.rotation_euler[2]=-.25
# panel inset detailing on visible door face
for z in [.65,1.7,2.8,3.65]:
 o=cube('door inset panel',(4.49,-3.2,z),(.025,1.48,.72),teal,.025); o.rotation_euler[2]=-.25
# light
world=bpy.context.scene.world; world.color=(.32,.32,.32)
def area(loc,power,size,target):
 bpy.ops.object.light_add(type='AREA',location=loc); o=bpy.context.object; o.data.energy=power; o.data.shape='DISK'; o.data.size=size; o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
area((0,-1,6),1300,7,(0,2,0)); area((-4,-1,4),700,5,(0,2,1)); area((2,4,5),500,4,(0,2,0))
bpy.ops.object.camera_add(location=(8,-11,5.0)); cam=bpy.context.object; cam.rotation_euler=(Vector((-.35,2.0,1.65))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.type='PERSP'; cam.data.lens=25; bpy.context.scene.camera=cam
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.samples=32; sc.cycles.use_denoising=True; sc.render.threads_mode='FIXED'; sc.render.threads=8; sc.render.resolution_x=640; sc.render.resolution_y=360; sc.render.resolution_percentage=100
sc.view_settings.view_transform='AgX'; sc.render.image_settings.file_format='PNG'; sc.render.filepath='/app/final.png'; bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
