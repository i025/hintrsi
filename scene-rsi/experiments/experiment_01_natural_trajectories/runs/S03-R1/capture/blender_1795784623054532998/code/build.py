import bpy, math, random
from mathutils import Vector
random.seed(12)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)

def mat(n,c,metal=0,rough=.5):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Metallic'].default_value=metal; p.inputs['Roughness'].default_value=rough; return m
white=mat('warm white paint',(.82,.83,.81)); wall=mat('walls',(.88,.89,.87)); dark=mat('dark stove enamel',(.035,.065,.06),.35,.25); steel=mat('brushed steel',(.42,.47,.46),.75,.28); burner=mat('electric burners',(.15,.22,.21),.4,.34); purple=mat('control knobs',(.36,.18,.35),.7,.24); counter=mat('pale aqua counter',(.57,.75,.73),.1,.25); black=mat('drawer charcoal',(.12,.13,.13)); green=mat('sage green',(.39,.50,.37)); wood=mat('light wood',(.68,.52,.39)); floor=mat('pale oak flooring',(.69,.64,.58)); seam=mat('floor seams',(.54,.49,.44)); soil=mat('soil',(.30,.22,.20)); pot=mat('gray ceramic',(.38,.45,.48)); leaf=mat('olive leaves',(.24,.27,.08)); leaf2=mat('leaf highlights',(.38,.37,.11)); gold=mat('olive cabinet',(.27,.27,.08),.3); marble=mat('white marble',(.83,.84,.82),.05,.25)
# marble procedural
nt=marble.node_tree; p=nt.nodes.get('Principled BSDF'); tex=nt.nodes.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value=4; tex.inputs['Detail'].default_value=3; tex.inputs['Roughness'].default_value=.7; mapping=nt.nodes.new('ShaderNodeVectorMath'); mapping.operation='MULTIPLY'; mapping.inputs[1].default_value=(1,8,1); coord=nt.nodes.new('ShaderNodeTexCoord'); nt.links.new(coord.outputs['Generated'],mapping.inputs[0]); nt.links.new(mapping.outputs[0],tex.inputs['Vector']); ramp=nt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].position=.35; ramp.color_ramp.elements[0].color=(.65,.66,.65,1); ramp.color_ramp.elements[1].position=.6; ramp.color_ramp.elements[1].color=(.92,.92,.9,1); nt.links.new(tex.outputs['Fac'],ramp.inputs[0]); nt.links.new(ramp.outputs[0],p.inputs['Base Color'])
def cube(n,loc,scale,ma,bev=0):
 bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bev: mod=o.modifiers.new('soft edges','BEVEL'); mod.width=bev; mod.segments=2; o.modifiers.new('weighted normals','WEIGHTED_NORMAL')
 return o
def cyl(n,loc,r,depth,ma,rot=None,verts=48):
 bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=depth,location=loc,rotation=rot or (0,0,0)); o=bpy.context.object; o.name=n; o.data.materials.append(ma); o.modifiers.new('edge bevel','BEVEL').width=.008; o.modifiers.new('weighted normals','WEIGHTED_NORMAL'); return o
def rod(n,a,b,r,ma):
 d=Vector(b)-Vector(a); o=cyl(n,(Vector(a)+Vector(b))/2,r,d.length,ma); o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); return o
# room
cube('floor',(0,1,-.09),(4.6,8,.18),floor)
for y in [i*.34-3 for i in range(23)]: cube('floor plank joint',(0,y,.003),(4.6,.008,.005),seam)
for j,y in enumerate([i*.34-3 for i in range(23)]):
 for x in [-1.8+(j%2)*.6,-.6+(j%2)*.6,.6+(j%2)*.6,1.8+(j%2)*.6]: cube('staggered joint',(x,y+.17,.004),(.006,.34,.006),seam)
cube('back wall',(0,4,1.65),(4.7,.12,3.3),wall); cube('left wall',(-2.32,1,1.65),(.12,6,3.3),wall); cube('right wall',(2.32,1,1.65),(.12,6,3.3),wall)
# door at far end dark opening and pale open door
cube('door opening',(-.35,3.925,1.2),(1,.025,2.4),dark); cube('open door',(-.72,3.75,1.2),(.79,.055,2.38),white); cyl('door knob',(-.31,3.70,1.15),.035,.04,steel,(math.pi/2,0,0)); cube('door jamb',(.16,3.88,1.25),(.05,.07,2.5),black)
# stove foreground left
cube('range body',(-1.42,-.20,.45),(1.42,1.05,.9),dark,.025); cube('range cooktop',(-1.42,-.20,.92),(1.44,1.07,.075),steel,.015)
for x in [-1.88,-.99]:
 for y in [-.53,-.20,.13]: cyl('round electric hotplate',(x,y,.966),.17,.012,burner)
# raised rear console tilted
console=cube('range control backsplash',(-1.42,.38,1.19),(1.43,.16,.51),steel,.015); console.rotation_euler.x=-.20
for x in [-1.91,-.92]:
 cyl('purple stove dial',(x,.272,1.22),.115,.07,purple,(math.pi/2-.2,0,0)); rod('dial indicator',(x,.228,1.22),(x-.02,.225,1.28),.007,dark)
# range clock text
bpy.ops.object.text_add(location=(-1.49,.265,1.23),rotation=(math.pi/2-.2,0,0)); t=bpy.context.object; t.name='digital clock'; t.data.body='12:01'; t.data.size=.12; t.data.extrude=.002; t.data.materials.append(dark)
# cabinet behind range
cube('left cabinet',(-1.32,1.22,.47),(1.4,1.4,.94),gold,.015); cube('aqua countertop',(-1.32,1.22,.99),(1.48,1.47,.12),counter,.015)
# visible side handle
rod('side handle',(-.60,.66,.20),(-.60,.66,.77),.022,purple); rod('handle mount',(-.65,.66,.20),(-.57,.66,.20),.018,purple); rod('handle mount',(-.65,.66,.77),(-.57,.66,.77),.018,purple)
# right bank of cabinets runs along y
cube('right cabinet carcass',(1.76,.28,.47),(1.06,4.8,.94),white,.01); cube('marble countertop',(1.75,.28,.99),(1.17,4.9,.12),marble,.014)
# visible fronts on left-facing x plane
for i,y in enumerate([-1.65,-.85,-.05,.75,1.55,2.35]):
 for j,z in enumerate([.20,.50,.79]):
  ma= [black,white,wood,black,green,black,white][(i*3+j)%7]; cube('drawer front',(1.215,y,z),(.025,.74,.265),ma,.008); cyl('drawer pull',(1.19,y,z),.018,.035,steel,(0,math.pi/2,0),20)
# upper cabinets along right wall
cube('upper cabinet boxes',(2.04,1.35,2.36),(.56,3.6,.86),white,.01)
for y in [-.15,.75,1.65,2.55]:
 cube('upper framed door',(1.745,y,2.36),(.03,.85,.78),white,.012); cube('upper green inset',(1.723,y,2.36),(.012,.69,.60),green,.004); cyl('upper knob',(1.70,y-.22,2.36),.018,.03,black,(0,math.pi/2,0),16)
# potted plant at back
bpy.ops.mesh.primitive_cone_add(vertices=48,radius1=.17,radius2=.24,depth=.34,location=(.79,3.20,.17)); bpy.context.object.name='plant pot'; bpy.context.object.data.materials.append(pot); cyl('potting soil',(.79,3.20,.345),.215,.015,soil)
rod('plant stem',(.79,3.2,.35),(.87,3.2,1.55),.012,leaf)
def blade(n,base,tip,width,ma):
 b=Vector(base); t=Vector(tip); mid=b.lerp(t,.55); side=Vector((width,0,0)); verts=[b,mid+side,t,mid-side,mid+Vector((0,-.035,0))]; faces=[(0,1,4),(1,2,4),(2,3,4),(3,0,4)]; me=bpy.data.meshes.new(n); me.from_pydata(verts,[],faces); me.materials.append(ma); ob=bpy.data.objects.new(n,me); bpy.context.collection.objects.link(ob)
for i,(dx,dz) in enumerate([(-.23,.5),(.23,.67),(-.17,.86),(.18,1.02),(-.10,1.17),(.08,1.42)]): blade('long pointed plant leaf',(.8,3.2,.40+i*.09),(.8+dx,3.2,.40+dz),.055,leaf if i%2 else leaf2)
blade('plant bud',(.86,3.2,1.45),(.89,3.2,1.77),.06,leaf2)
# illumination
world=bpy.context.scene.world; world.color=(.7,.7,.7)
def area(loc,power,size,target):
 bpy.ops.object.light_add(type='AREA', location=loc); o=bpy.context.object; o.data.energy=power; o.data.shape='DISK'; o.data.size=size; o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
area((0,-2.4,3.6),500,5,(0,1,0)); area((0,3,3.1),300,3,(0,1,0))
# camera
bpy.ops.object.camera_add(location=(0,-4.6,2.0)); cam=bpy.context.object; cam.rotation_euler=(Vector((0,1.4,1.0))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.lens=24; bpy.context.scene.camera=cam
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True; scene.render.resolution_x=640; scene.render.resolution_y=360; scene.render.resolution_percentage=100; scene.view_settings.view_transform='AgX'; scene.render.image_settings.file_format='PNG'; scene.render.filepath='/app/final.png'; scene.render.threads_mode='FIXED'; scene.render.threads=8
bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
