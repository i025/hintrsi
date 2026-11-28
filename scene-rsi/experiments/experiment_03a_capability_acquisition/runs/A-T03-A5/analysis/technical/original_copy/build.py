import bpy, math, random
from mathutils import Vector
random.seed(9)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)

def mat(n,c,metal=0,rough=.4):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Metallic'].default_value=metal; p.inputs['Roughness'].default_value=rough; return m
white=mat('painted white cabinetry',(.82,.83,.82),0,.32); edge=mat('white edge',(.95,.95,.93)); black=mat('black enamel',(.022,.024,.024),.35,.22); glass=mat('smoked reflective oven glass',(.045,.048,.043),.45,.14); steel=mat('brushed stainless steel',(.46,.43,.4),.7,.27); dark=mat('burner ceramic',(.075,.083,.075),.15,.4); brown=mat('dark door wood',(.13,.075,.045),0,.38); grout=mat('dark grout',(.14,.105,.035)); floor=mat('brown wood floor',(.24,.15,.11),0,.48); cream=mat('light beyond door',(.8,.75,.63)); mirror=mat('mirror',(.52,.56,.53),1,.07)
# wood grain procedural
p=floor.node_tree.nodes.get('Principled BSDF'); tex=floor.node_tree.nodes.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value=5; tex.inputs['Detail'].default_value=3; mapping=floor.node_tree.nodes.new('ShaderNodeVectorMath'); mapping.operation='MULTIPLY'; mapping.inputs[1].default_value=(2,35,3); coord=floor.node_tree.nodes.new('ShaderNodeTexCoord'); floor.node_tree.links.new(coord.outputs['Generated'],mapping.inputs[0]); floor.node_tree.links.new(mapping.outputs[0],tex.inputs['Vector']); ramp=floor.node_tree.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color=(.07,.035,.02,1); ramp.color_ramp.elements[1].color=(.38,.24,.16,1); floor.node_tree.links.new(tex.outputs['Fac'],ramp.inputs[0]); floor.node_tree.links.new(ramp.outputs[0],p.inputs['Base Color'])
def cube(n,loc,dim,ma,bev=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=n; o.dimensions=dim; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bev: mod=o.modifiers.new('soft edges','BEVEL'); mod.width=bev; mod.segments=2; o.modifiers.new('weighted normals','WEIGHTED_NORMAL')
 return o
def cyl(n,loc,r,depth,ma,rot=(0,0,0)):
 bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r,depth=depth,location=loc,rotation=rot); o=bpy.context.object;o.name=n;o.data.materials.append(ma); return o
# floor and tiled wall
cube('floor',(0,0,-.06),(5.5,5.8,.12),floor)
cube('back wall',(-.3,2.0,1.65),(4.4,.12,3.3),grout)
# individually varied small gold tiles
tiles=[]
for i in range(22):
 for j in range(17):
  v=random.uniform(.65,1.18); m=mat('tile %02d %02d'%(i,j),(.32*v,.235*v,.065*v),.18,.28); tiles.append(m)
  cube('gold square tile',(-2.48+i*.2,1.925,.10+j*.2),(.197,.025,.197),m)
cube('baseboard',(-.3,1.88,.09),(4.4,.07,.17),white)
# doorway to right of tiled wall
cube('illuminated opening',(2.05,2.08,1.65),(1.0,.06,3.3),cream)
cube('dark lower opening',(2.05,2.0,.30),(1,.04,.6),black)
cube('door slab',(2.43,1.64,1.55),(.65,.12,3.1),brown,.015)
for z in [.62,1.65,2.65]:
 cube('door panel',(2.42,1.57,z),(.48,.025,.75),brown,.015)
# appliance range, front facing camera (negative y)
x=.2; y=1.13
cube('range black body',(x,y,.52),(1.05,.85,1.04),black,.02)
cube('range oven outer door',(x,.685,.52),(1.00,.045,.78),steel,.015)
cube('range oven glass',(x,.655,.51),(.9,.025,.64),glass,.012)
cube('range lower black border',(x,.635,.19),(.93,.026,.07),black)
cube('range handle',(x,.59,.89),(.86,.065,.055),steel,.02)
cube('range cooktop',(x,1.12,1.06),(1.06,.88,.075),steel,.01)
for dx,dy,r in [(-.27,-.21,.15),(.27,-.21,.16),(-.27,.20,.14),(.27,.20,.14)]: cyl('round electric hob',(x+dx,1.12+dy,1.103),r,.008,dark)
cube('raised stove controls',(x,1.49,1.27),(1.05,.13,.29),steel,.025)
for dx in [-.32,.32]: cyl('control dial',(x+dx,1.414,1.28),.09,.035,steel,(math.pi/2,0,0))
# left wine fridge
x=-1.18; y=1.05
cube('wine refrigerator body',(x,y,.49),(1.15,.86,.98),black,.018)
cube('wine fridge glass door',(x,.60,.47),(1.07,.04,.82),glass,.01)
for z in [.25,.36,.47,.58,.69]:
 cube('wine shelf',(x,.568,z),(.94,.02,.012),steel)
 for xx in [x-.32,x-.16,x,x+.16,x+.32]: cube('rack upright',(xx,.56,z+.03),(.009,.01,.065),steel)
cube('fridge handle',(x,.53,.84),(.93,.06,.045),steel,.016)
# white open cubby behind range to right
x=1.02; y=1.70
cube('shelf back',(x,1.87,.70),(.69,.045,1.4),white)
for dx in [-.35,.35]: cube('shelf side',(x+dx,y,.70),(.055,.40,1.4),white)
for z in [.03,.70,1.37]: cube('shelf horizontal',(x,y,z),(.73,.40,.055),white)
cube('shelf divider',(x,y,1.03),(.045,.39,.64),white)
# framed wall mirror, reflects suggestion of upper cabinet
cube('mirror glass',(-1.05,1.89,2.35),(1.70,.03,1.15),mirror)
for xx in [-1.92,-.18]: cube('mirror frame',(xx,1.85,2.35),(.035,.05,1.20),black)
for zz in [1.75,2.95]: cube('mirror frame',(-1.05,1.85,zz),(1.77,.05,.035),black)
# reflected cabinet stylized white shapes on mirror
cube('reflected cabinet',(-1.13,1.82,2.58),(1.15,.025,.70),white)
for xx in [-1.62,-1.15,-.66]: cube('reflected cabinet seam',(xx,1.795,2.58),(.012,.012,.67),steel)
cube('reflected counter',(-1.10,1.80,1.91),(1.28,.06,.06),white)
# right foreground cabinetry
cube('right base cabinet',(2.12,-.65,.48),(1.25,2.05,.96),white,.015)
cube('right marble countertop',(2.12,-.65,.99),(1.32,2.1,.12),edge,.012)
# marble procedural
m=edge;p=m.node_tree.nodes.get('Principled BSDF'); tex=m.node_tree.nodes.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=9;tex.inputs['Detail'].default_value=2; ramp=m.node_tree.nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.42;ramp.color_ramp.elements[0].color=(.63,.64,.64,1);ramp.color_ramp.elements[1].position=.53;ramp.color_ramp.elements[1].color=(.94,.94,.92,1);m.node_tree.links.new(tex.outputs['Fac'],ramp.inputs[0]);m.node_tree.links.new(ramp.outputs[0],p.inputs['Base Color'])
cube('upper right cabinet',(2.55,.35,2.62),(.45,1.40,1.08),white)
# foreground dark surface
cube('foreground dark counter',(.0,-2.0,.84),(2.2,1.0,.10),black,.01)
# lighting
world=bpy.context.scene.world or bpy.data.worlds.new('World'); bpy.context.scene.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.65,.65,.65,1);world.node_tree.nodes['Background'].inputs[1].default_value=.6
bpy.ops.object.light_add(type='AREA', location=(0,-2,4.5)); bpy.context.object.data.energy=500; bpy.context.object.data.shape='DISK';bpy.context.object.data.size=4
bpy.ops.object.light_add(type='AREA', location=(2,1.5,3));bpy.context.object.data.energy=250;bpy.context.object.data.size=2
# camera
bpy.ops.object.camera_add(location=(3.5,-5.2,3.35)); cam=bpy.context.object; target=Vector((0,1.0,1.05));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=25; bpy.context.scene.camera=cam
sc=bpy.context.scene;sc.render.engine='CYCLES';sc.cycles.samples=32;sc.cycles.use_denoising=True;sc.render.threads_mode='FIXED';sc.render.threads=8;sc.render.resolution_x=640;sc.render.resolution_y=360;sc.render.resolution_percentage=100
sc.view_settings.view_transform='AgX';sc.render.image_settings.file_format='PNG';sc.render.filepath='/app/final.png';bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend');bpy.ops.render.render(write_still=True)
