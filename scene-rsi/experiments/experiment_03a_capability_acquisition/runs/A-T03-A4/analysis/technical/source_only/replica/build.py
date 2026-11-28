import bpy, math, random
from mathutils import Vector
random.seed(7)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)

def mat(n,c,metal=0,rough=.4):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Metallic'].default_value=metal; p.inputs['Roughness'].default_value=rough; return m
white=mat('painted ivory',(.82,.82,.8)); black=mat('black enamel',(.018,.02,.021),.25,.25); glass=mat('smoked glass',(.037,.045,.04),.35,.18); steel=mat('brushed stainless',(.4,.37,.35),.7,.26); burner=mat('ceramic burners',(.065,.073,.068),.18,.28); trim=mat('dark trim',(.015,.014,.012),.15); floor=mat('walnut floor',(.24,.15,.115),0,.6); door=mat('dark walnut door',(.12,.065,.038),0,.5); gold=[]
for i in range(24):
 v=random.uniform(.22,.48); gold.append(mat('tile %02d'%i,(v,v*.72,v*.28),.3,.34))
# textured procedural materials
p=floor.node_tree.nodes; l=floor.node_tree.links; bs=p.get('Principled BSDF'); tex=p.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value=4; tex.inputs['Detail'].default_value=3; mapping=p.new('ShaderNodeVectorMath'); mapping.operation='MULTIPLY'; mapping.inputs[1].default_value=(2,28,3); coord=p.new('ShaderNodeTexCoord'); l.new(coord.outputs['Generated'],mapping.inputs[0]); l.new(mapping.outputs[0],tex.inputs['Vector']); ramp=p.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color=(.075,.035,.024,1); ramp.color_ramp.elements[1].color=(.34,.21,.15,1); l.new(tex.outputs['Fac'],ramp.inputs[0]); l.new(ramp.outputs[0],bs.inputs['Base Color'])

def cube(n,loc,dim,ma,bev=0):
 bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o=bpy.context.object; o.name=n; o.dimensions=dim; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bev: mod=o.modifiers.new('soft edges','BEVEL'); mod.width=bev; mod.segments=2; o.modifiers.new('weighted normals','WEIGHTED_NORMAL')
 return o

def cyl(n,loc,r,depth,ma,rot=(0,0,0)):
 bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r,depth=depth,location=loc,rotation=rot); o=bpy.context.object; o.name=n; o.data.materials.append(ma); return o
# floor and wall
cube('floor',(0,0,-.07),(7,7,.14),floor)
cube('back wall',(-.7,1.62,1.65),(4.6,.12,3.3),gold[4]); cube('right wall',(2.6,.8,1.65),(.12,1.65,3.3),gold[4])
# tiled backsplash, individual squares
for ix in range(25):
 for iz in range(17):
  x=-2.95+ix*.185; z=.10+iz*.185
  if x<1.58: cube('gold mosaic tile',(x,1.548,z),(.181,.012,.181),random.choice(gold))
cube('white baseboard',(-.7,1.49,.08),(4.5,.08,.16),white,.01)
# stove center, front is negative y
sx=-.25; sy=.80
cube('range body',(sx,sy,.53),(.88,.78,1.06),black,.015)
cube('oven stainless front',(sx,.397,.49),(.83,.035,.84),steel,.01)
cube('oven window',(sx,.372,.47),(.72,.015,.66),glass,.01)
for z in [.25,.5,.68]: cube('rack inside oven',(sx,.359,z),(.63,.009,.008),steel)
cube('oven top edge',(sx,.35,.83),(.84,.04,.06),black,.008)
cube('oven handle',(sx,.29,.86),(.67,.055,.055),steel,.016)
cube('range cooktop',(sx,sy,1.085),(.91,.83,.065),steel,.012)
for x in [sx-.24,sx+.24]:
 for y in [.61,1.00]: cyl('round electric hotplate',(x,y,1.123),.145,.008,burner)
# raised control panel
panel=cube('range control backsplash',(sx,1.24,1.25),(.91,.11,.27),steel,.015); panel.rotation_euler.x=math.radians(-10)
for x in [sx-.32,sx+.32]: cyl('range knob',(x,1.166,1.27),.071,.035,steel,(math.pi/2,0,0))
# wine cooler left
wx=-1.48; wy=.70
cube('wine cooler body',(wx,wy,.53),(1.06,.84,1.06),black,.018)
cube('cooler glass door',(wx,.263,.52),(.94,.025,.9),glass,.01)
for z in [.18,.30,.42,.54,.66,.78]:
 cube('wine rack shelf',(wx,.245,z),(.84,.012,.012),steel)
 for x in [wx-.34,wx-.17,wx,wx+.17,wx+.34]: cube('wine rack divider',(x,.237,z+.035),(.008,.01,.07),steel)
cube('wine cooler handle',(wx,.20,.90),(.83,.05,.045),steel,.01)
# white cubby shelf on back wall next to range
cx=.74; cy=1.28
cube('shelf back',(cx,1.51,.99),(.64,.035,1.36),white)
for x in [cx-.32,cx+.32]: cube('shelf side',(x,cy,.99),(.045,.48,1.4),white)
for z in [.30,.77,1.24,1.69]: cube('shelf board',(cx,cy,z),(.66,.48,.045),white)
cube('shelf vertical divider',(cx,cy,1.47),(.035,.48,.43),white)
# mirror mounted above cooler, reflection hinted with pale shapes
cube('mirror dark frame',(-1.25,1.51,2.31),(1.55,.07,1.13),trim,.015)
mirror=mat('mirror silvery',(.42,.44,.41),.85,.12)
cube('mirror glass',(-1.25,1.466,2.31),(1.49,.012,1.07),mirror)
# white cabinetry reflected impression
for x in [-1.67,-1.10]: cube('reflected cabinet', (x,1.449,2.57),(.45,.01,.55),white)
# doorway right dark opening and brown panel
cube('doorway darkness',(1.95,1.62,1.47),(.72,.06,2.94),trim)
cube('door open panel',(2.33,1.30,1.45),(.12,.70,2.9),door,.01)
for z in [.72,2.05]: cube('door inset',(2.255,1.29,z),(.012,.53,.9),door,.01)
# right counter along side and foreground
cube('right base cabinet',(2.12,-.53,.49),(.87,2.05,.98),white,.01)
cube('white stone countertop',(2.12,-.53,1.02),(.94,2.12,.12),white,.015)
cube('front island countertop',(0,-2.1,.90),(2.4,.80,.10),black,.012)
# camera
bpy.ops.object.camera_add(location=(3.55,-5.35,3.35)); cam=bpy.context.object; cam.name='Camera'; cam.rotation_euler=(Vector((-.2,.55,.95))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.lens=32; bpy.context.scene.camera=cam
# lighting
world=bpy.context.scene.world; world.color=(.23,.23,.23)
def area(loc,power,size,target):
 bpy.ops.object.light_add(type='AREA',location=loc); a=bpy.context.object; a.data.energy=power; a.data.shape='DISK'; a.data.size=size; a.rotation_euler=(Vector(target)-a.location).to_track_quat('-Z','Y').to_euler()
area((0,-2,4.5),500,5,(0,.5,0)); area((2,0,3.6),300,3,(0,1,1))
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True; scene.render.resolution_x=640; scene.render.resolution_y=360; scene.render.resolution_percentage=100; scene.render.image_settings.file_format='PNG'; scene.render.filepath='/app/final.png'; scene.view_settings.view_transform='AgX'; scene.camera.data.lens=32
bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
