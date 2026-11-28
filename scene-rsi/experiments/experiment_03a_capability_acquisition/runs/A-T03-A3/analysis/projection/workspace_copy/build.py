import bpy, math, random
from mathutils import Vector
random.seed(8)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)

def mat(n,c,metal=0,rough=.45):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Metallic'].default_value=metal; p.inputs['Roughness'].default_value=rough; return m
white=mat('warm white cabinetry',(.83,.83,.81),0,.36); edge=mat('white trim',(.94,.94,.92)); black=mat('black enamel',(.018,.02,.022),.25,.22); glass=mat('smoked oven glass',(.045,.046,.04),.45,.18); steel=mat('brushed stainless steel',(.4,.39,.37),.75,.28); burner=mat('dark ceramic burners',(.075,.085,.075),.18,.33); brown=mat('dark wood door',(.16,.085,.045),0,.4); grout=mat('tile grout',(.19,.14,.045)); mirror=mat('mirror',(.5,.53,.51),.95,.08)
def box(n,loc,dim,ma,bev=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=n; o.dimensions=dim; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bev:
  mod=o.modifiers.new('subtle rounded edges','BEVEL'); mod.width=bev; mod.segments=2; o.modifiers.new('weighted normals','WEIGHTED_NORMAL')
 return o
def cyl(n,loc,r,depth,ma,rot=(0,0,0)):
 bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r,depth=depth,location=loc,rotation=rot); o=bpy.context.object; o.name=n; o.data.materials.append(ma); o.modifiers.new('edge normals','WEIGHTED_NORMAL'); return o
# floor with elongated wood grain
wood=mat('walnut plank floor',(.25,.15,.1),0,.55); nt=wood.node_tree; p=nt.nodes.get('Principled BSDF'); tex=nt.nodes.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value=3.5; tex.inputs['Detail'].default_value=3; tex.inputs['Roughness'].default_value=.7; mapping=nt.nodes.new('ShaderNodeVectorMath'); mapping.operation='MULTIPLY'; mapping.inputs[1].default_value=(2,30,3); coord=nt.nodes.new('ShaderNodeTexCoord'); nt.links.new(coord.outputs['Generated'],mapping.inputs[0]); nt.links.new(mapping.outputs[0],tex.inputs[0]); ramp=nt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color=(.075,.036,.021,1); ramp.color_ramp.elements[1].color=(.38,.24,.16,1); nt.links.new(tex.outputs['Fac'],ramp.inputs[0]); nt.links.new(ramp.outputs[0],p.inputs['Base Color'])
box('wood floor',(0,0,-.08),(6,6,.16),wood)
# tiled back wall individual square tiles
box('back wall',(0,2.1,1.65),(6,.12,3.3),grout)
tiles=[]
for i in range(18):
 c=random.uniform(.7,1.22); tiles.append(mat('ochre tile %02d'%i,(min(.44*c,1),min(.32*c,1),min(.095*c,1)),.12,.33))
for ix in range(30):
 for iz in range(17):
  box('square gold backsplash tile',(-2.9+ix*.2,2.025,.1+iz*.2),(.196,.025,.196),random.choice(tiles))
box('back skirting',(0,1.96,.09),(6,.11,.18),edge)
# stove main
box('range body',(-.25,1.05,.47),(1.06,.91,.94),black,.015)
box('range stainless cooktop',(-.25,1.05,.95),(1.09,.94,.055),steel,.015)
for x in [-.55,.06]:
 for y in [.79,1.29]: cyl('round electric burner',(x,y,.983),.15,.008,burner)
box('stove raised control panel',(-.25,1.53,1.13),(1.09,.13,.32),steel,.015)
for x in [-.62,.12]:
 cyl('range control knob',(x,1.452,1.14),.075,.035,steel,(math.pi/2,0,0))
box('oven door rim',(-.25,.575,.45),(.98,.045,.79),steel,.012)
box('oven door dark glass',(-.25,.544,.43),(.88,.025,.63),glass,.006)
box('oven door upper band',(-.25,.523,.76),(.96,.065,.09),black,.01)
box('oven horizontal handle',(-.25,.47,.735),(.77,.055,.045),steel,.014)
for z in [.28,.42,.56]: box('oven interior rack',(-.25,.525,z),(.72,.008,.008),steel)
# separate compact black appliance left of stove
box('black standalone oven',(-1.55,.9,.48),(1.03,.9,.96),black,.02)
box('standalone oven front frame',(-1.55,.43,.46),(.95,.05,.84),black,.01)
box('standalone oven window',(-1.55,.397,.43),(.87,.016,.68),glass)
box('standalone oven top handle',(-1.55,.345,.78),(.84,.055,.045),steel,.012)
for z in [.22,.35,.48,.61]: box('standalone rack',(-1.55,.382,z),(.76,.01,.009),steel)
# small white cube shelf to right of range
box('shelf back',( .65,1.9,.56),(.64,.05,1.12),white)
for x in [.32,.98]: box('shelf side',(x,1.71,.56),(.04,.43,1.12),white)
for z in [.02,.56,1.1]: box('shelf horizontal',(.65,1.71,z),(.7,.43,.04),white)
box('shelf divider',(.65,1.7,.83),(.035,.42,.52),white)
# back wall mirror and reflected cabinet represented as framed wall inset
box('mirror dark frame',(-1.38,1.96,2.02),(1.45,.07,1.23),black)
box('mirror surface',(-1.38,1.915,2.02),(1.38,.015,1.16),mirror)
# stylized reflection white upper cabinet, recessed cubbies
box('reflected cabinet back',(-1.38,1.90,2.19),(1.02,.018,.72),white)
for x in [-1.87,-1.63,-1.15,-.89]: box('reflected cupboard stile',(x,1.88,2.19),(.035,.03,.75),edge)
for z in [1.84,2.19,2.54]: box('reflected cupboard shelf',(-1.38,1.88,z),(1.03,.03,.035),edge)
box('reflected cabinet central door',(-1.39,1.85,2.22),(.43,.035,.62),edge)
# doorway at right, dark open cavity and angled wooden leaf
box('dark doorway',(1.55,2.0,1.2),(.73,.05,2.4),black)
box('door jamb',(1.91,1.95,1.2),(.09,.17,2.4),brown)
door=box('partly opened brown door',(1.83,1.72,1.19),(.09,.75,2.37),brown,.012); door.rotation_euler[2]=-.22
# right cabinetry and marble counter foreground
box('right base cabinet',(2.15,.25,.46),(1.05,2.0,.92),white)
marble=mat('white marble countertop',(.8,.81,.8),0,.27); nt=marble.node_tree; p=nt.nodes.get('Principled BSDF'); noise=nt.nodes.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value=7; noise.inputs['Detail'].default_value=4; noise.inputs['Roughness'].default_value=.75; ramp=nt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color=(.49,.51,.51,1); ramp.color_ramp.elements[1].color=(.94,.94,.93,1); nt.links.new(noise.outputs['Fac'],ramp.inputs[0]); nt.links.new(ramp.outputs[0],p.inputs['Base Color'])
box('marble counter',(2.15,.25,.94),(1.13,2.1,.1),marble,.01)
box('upper white cabinet',(2.55,1.1,2.25),(.7,1.1,.9),white)
# foreground island dark top
box('foreground island',(0,-1.75,.64),(2.1,1.05,.76),white)
box('foreground black worktop',(0,-1.75,1.04),(2.2,1.16,.08),black,.012)
# camera and lighting
world=bpy.context.scene.world; world.color=(.3,.3,.3)
def area(loc,power,size,target):
 bpy.ops.object.light_add(type='AREA',location=loc); o=bpy.context.object; o.data.energy=power; o.data.shape='DISK'; o.data.size=size; o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
area((0,-1,4.5),650,4,(0,1,0)); area((3,-1,3.5),450,3,(0,1,1))
bpy.ops.object.camera_add(location=(-3.7,-5.8,3.45)); cam=bpy.context.object; cam.rotation_euler=(Vector((0,1.0,.85))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.lens=35; bpy.context.scene.camera=cam
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True; scene.render.threads_mode='FIXED'; scene.render.threads=8; scene.render.resolution_x=640; scene.render.resolution_y=360; scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'; scene.render.image_settings.file_format='PNG'; scene.render.filepath='/app/final.png'; bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
