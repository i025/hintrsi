import bpy, math, random
from mathutils import Vector
random.seed(4)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)

def mat(n,c,metal=0,rough=.5):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Metallic'].default_value=metal; p.inputs['Roughness'].default_value=rough; return m
white=mat('white painted cabinetry',(.82,.82,.8),0,.34); trim=mat('white trim',(.92,.9,.86)); black=mat('black enamel',(.015,.017,.018),.35,.22); glass=mat('dark smoky oven glass',(.035,.03,.025),.4,.17); steel=mat('brushed stainless steel',(.43,.4,.37),.75,.27); burner=mat('ceramic burner rings',(.075,.08,.075),.2,.35); dark=mat('cabinet interior shadow',(.045,.04,.03)); wood=mat('door walnut',(.15,.075,.038),0,.45)
tiles=[mat('ochre tile %02d'%i,(.24+random.random()*.17,.17+random.random()*.12,.035+random.random()*.055),.2,.32) for i in range(18)]
# wood material procedural
floor=mat('dark wood floor',(.17,.105,.07),0,.43); nt=floor.node_tree; p=nt.nodes.get('Principled BSDF'); tex=nt.nodes.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value=4; tex.inputs['Detail'].default_value=3; mapping=nt.nodes.new('ShaderNodeMapping'); mapping.inputs['Scale'].default_value=(3,35,3); coord=nt.nodes.new('ShaderNodeTexCoord'); nt.links.new(coord.outputs['Generated'],mapping.inputs['Vector']); nt.links.new(mapping.outputs['Vector'],tex.inputs['Vector']); ramp=nt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color=(.055,.03,.02,1); ramp.color_ramp.elements[1].color=(.28,.17,.11,1); nt.links.new(tex.outputs['Fac'],ramp.inputs[0]); nt.links.new(ramp.outputs[0],p.inputs['Base Color'])
def cube(n,loc,scale,ma,bev=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bev: mod=o.modifiers.new('soft edges','BEVEL'); mod.width=bev; mod.segments=2; o.modifiers.new('weighted normals','WEIGHTED_NORMAL')
 return o
def cyl(n,loc,r,depth,ma,rot=(0,0,0)):
 bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r,depth=depth,location=loc,rotation=rot); o=bpy.context.object;o.name=n;o.data.materials.append(ma);return o
# floor and back wall tiles
cube('floor',(0,0,-.07),(5.8,5,.14),floor)
cube('back wall',(0,2.02,1.6),(5.8,.1,3.2),dark)
for ix in range(29):
 for iz in range(16):
  x=-2.8+ix*.2; z=.1+iz*.2
  cube('square gold wall tile',(x,1.959,z),(.196,.025,.196),random.choice(tiles))
cube('back baseboard',(0,1.91,.09),(5.7,.1,.18),trim,.015)
# range positioned at back center; front faces negative Y
x=-.15;y=1.10
cube('range body',(x,y,.48),(1.18,.91,.96),black,.025)
cube('oven front',(x,.625,.49),(1.10,.045,.70),steel,.015)
cube('oven glass',(x,.594,.46),(.97,.018,.55),glass,.01)
cube('oven bottom lip',(x,.577,.19),(1.02,.03,.04),black)
cube('oven handle',(x,.51,.78),(.94,.065,.055),steel,.018)
for xx in [x-.42,x+.42]:cube('handle mounting',(xx,.56,.78),(.055,.12,.07),steel,.01)
cube('cooktop',(x,1.10,.99),(1.18,.94,.075),steel,.018)
for xx in [x-.31,x+.31]:
 for yy in [.87,1.31]:cyl('electric hotplate',(xx,yy,1.032),.155,.009,burner)
cube('raised control panel',(x,1.56,1.18),(1.18,.14,.33),steel,.015)
for xx in [x-.42,x+.42]:cyl('range control dial',(xx,1.474,1.19),.075,.035,steel,(math.pi/2,0,0))
# wine cooler left of range
x=-1.55
cube('wine fridge black housing',(x,1.12,.48),(1.30,.9,.96),black,.025)
cube('wine cooler glass door',(x,.651,.46),(1.18,.035,.78),glass,.01)
cube('wine cooler top rail',(x,.62,.84),(1.18,.045,.055),steel,.01)
for z in [.28,.4,.52,.64]:
 cube('wine rack shelf',(x,.613,z),(1.03,.012,.012),steel)
 for j in range(7):cube('wine rack vertical grid',(x-.45+j*.15,.61,z+.045),(.009,.012,.09),steel)
cube('wine cooler handle',(x,.585,.80),(1.0,.04,.035),steel,.012)
# cubby unit behind and right
x=.85
cube('shelf back',(x,1.83,.84),(.75,.06,1.52),white)
for xx in [x-.375,x,x+.375]:cube('shelf upright',(xx,1.62,.84),(.045,.44,1.52),white)
for z in [.09,.81,1.59]:cube('shelf horizontal',(x,1.62,z),(.79,.44,.045),white)
# wall mirror on left
cube('mirror dark frame',(-1.45,1.915,2.40),(1.65,.045,1.20),black)
mirror=mat('mirror silver',(.58,.59,.57),.85,.08)
cube('mirror glass',(-1.45,1.882,2.40),(1.59,.015,1.14),mirror)
# reflected cabinet representation in mirror
for xx in [-1.91,-1.38]:cube('reflected upper cabinet',(xx,1.866,2.63),(.46,.025,.66),white)
# right doorway and door panel
cube('doorway darkness',(2.0,1.93,1.42),(.76,.04,2.84),dark)
cube('door casing left',(1.60,1.87,1.45),(.075,.13,2.9),trim)
cube('dark open door',(2.36,1.68,1.42),(.56,.13,2.84),wood,.01)
for z in [.65,1.65,2.42]:cube('door inset panel',(2.36,1.605,z),(.42,.012,.55),wood,.02)
# right countertop and white cabinets foreground
cube('right base cabinets',(2.12,-.53,.48),(1.13,2.05,.96),white,.01)
cube('right white marble countertop',(2.12,-.53,1.0),(1.20,2.1,.10),trim,.02)
for yy in [-1.12,-.35,.42]:
 cube('cabinet door seam',(1.548,yy,.48),(.012,.012,.76),dark)
 cube('cabinet handle',(1.53,yy+.12,.76),(.025,.20,.025),steel,.008)
# upper cabinet partially visible on right
cube('upper cabinet',(2.47,.45,2.35),(.65,1.45,.95),white,.015)
# foreground island counter
cube('foreground island',(0,-2.52,.66),(2.4,1.0,1.28),white)
cube('dark island top',(0,-2.52,1.34),(2.48,1.08,.08),black,.01)
# lighting
world=bpy.context.scene.world; world.color=(.25,.25,.25)
def area(loc,power,size,target):
 bpy.ops.object.light_add(type='AREA',location=loc); o=bpy.context.object;o.data.energy=power;o.data.shape='DISK';o.data.size=size;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
area((-.5,-1.5,4.8),650,4,(0,.8,.4)); area((2,-2,3.8),350,3,(0,1,1))
bpy.ops.object.camera_add(location=(3.2,-5.3,3.45));cam=bpy.context.object;cam.rotation_euler=(Vector((-.15,.9,.9))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=24;bpy.context.scene.camera=cam
s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.samples=32;s.cycles.use_denoising=True;s.render.resolution_x=640;s.render.resolution_y=360;s.render.resolution_percentage=100
s.view_settings.view_transform='AgX';s.render.image_settings.file_format='PNG';s.render.filepath='/app/final.png';s.render.threads_mode='FIXED';s.render.threads=8
bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend');bpy.ops.render.render(write_still=True)
