import bpy, math, random
from mathutils import Vector
random.seed(10)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
def mat(n,c,metal=0,rough=.5):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Metallic'].default_value=metal; p.inputs['Roughness'].default_value=rough; return m
def box(n,loc,sc,m,bevel=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=n; o.dimensions=sc; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(m)
 if bevel:
  mod=o.modifiers.new('Soft edges','BEVEL'); mod.width=bevel; mod.segments=2; o.modifiers.new('Normals','WEIGHTED_NORMAL')
 return o
def cyl(n,loc,r,depth,m,rot=(0,0,0)):
 bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r,depth=depth,location=loc,rotation=rot); o=bpy.context.object; o.name=n; o.data.materials.append(m); return o
white=mat('painted white',(0.82,.82,.81),rough=.4); dark=mat('black enamel',(.015,.018,.018),.35,.24); glass=mat('dark oven glass',(.045,.042,.035),.35,.18); steel=mat('brushed steel',(.43,.40,.37),.75,.29); black=mat('burner glass',(.032,.045,.041),.3,.28); trim=mat('dark frame',(.018,.023,.019),.3,.3); gold=mat('tile grout',(.18,.13,.035)); wood=mat('wood floor',(.25,.16,.11),rough=.6); walnut=mat('door walnut',(.15,.075,.045),rough=.4); cream=mat('bright doorway',(.9,.8,.63)); marble=mat('white countertop',(.82,.83,.82),rough=.27)
# procedural floor grain
p=wood.node_tree.nodes.get('Principled BSDF'); nt=wood.node_tree; tex=nt.nodes.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value=4; tex.inputs['Detail'].default_value=3; tex.inputs['Roughness'].default_value=.7; mapping=nt.nodes.new('ShaderNodeMapping'); mapping.inputs['Scale'].default_value=(2,35,3); coord=nt.nodes.new('ShaderNodeTexCoord'); nt.links.new(coord.outputs['Generated'],mapping.inputs['Vector']); nt.links.new(mapping.outputs['Vector'],tex.inputs['Vector']); ramp=nt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color=(.075,.039,.022,1); ramp.color_ramp.elements[1].color=(.37,.24,.17,1); nt.links.new(tex.outputs['Fac'],ramp.inputs[0]); nt.links.new(ramp.outputs[0],p.inputs['Base Color'])
box('floor',(0,0,-.06),(5.5,5,.12),wood)
# back wall in small golden square tiles
box('wall backing',(0,1.48,1.65),(5.5,.10,3.3),gold)
tiles=[]
for i in range(18):
 col=(random.uniform(.22,.38),random.uniform(.15,.26),random.uniform(.035,.085)); tiles.append(mat('ochre tile %02d'%i,col,.27,.33))
for ix in range(28):
 for iz in range(17):
  x=-2.72+ix*.2; z=.10+iz*.2
  # doorway opening on right
  if 1.55<x<2.45 and z<2.65: continue
  box('square gold tile',(x,1.418,z),(.195,.025,.195),random.choice(tiles))
box('baseboard',(-.5,1.35,.075),(4.05,.08,.15),white)
# doorway and open dark wood door
box('doorway glow',(1.99,1.52,1.34),(.9,.05,2.68),cream)
box('door dark threshold',(1.99,1.49,.15),(.9,.04,.3),dark)
box('door jamb',(2.46,1.31,1.38),(.11,.17,2.76),walnut)
door=box('open wooden door',(2.43,.97,1.35),(.12,.75,2.7),walnut,.015)
for z in (.65,1.8): box('door panel',(2.35,.96,z),(.02,.53,.82),walnut,.01)
# main range oven, fronts toward viewer
x=-.05; y=.83
box('range body',(x,y,.52),(1.08,.78,1.04),dark,.025)
box('oven door',(x,.405,.47),(.99,.045,.73),glass,.015)
box('oven lower rim',(x,.377,.12),(.99,.04,.045),dark)
box('oven handle',(x,.32,.83),(.87,.07,.07),steel,.02)
box('stovetop',(x,y,1.065),(1.12,.82,.09),steel,.015)
for xx in (-.29,.29):
 for yy in (.60,1.02): cyl('circular electric burner',(x+xx,yy,1.117),.145,.008,black)
box('range rear control panel',(x,1.17,1.25),(1.1,.12,.31),steel,.018)
for xx in (-.38,.38):
 cyl('control knob',(x+xx,1.095,1.25),.085,.04,steel,(math.pi/2,0,0)); box('knob mark',(x+xx,1.069,1.29),(.01,.01,.048),dark)
# separate black oven at left
x=-1.35
box('freestanding black oven',(x,.76,.52),(1.05,.8,1.04),dark,.015)
box('oven glass front',(x,.342,.48),(.95,.035,.80),glass,.01)
box('oven upper fascia',(x,.32,.88),(1,.05,.11),dark)
box('oven handle',(x,.275,.79),(.85,.055,.045),steel,.012)
for z in (.26,.39,.52,.65): box('visible oven rack',(x,.316,z),(.78,.012,.012),steel)
# open white cubby on right behind stove
x=.87
box('shelf back',(x,1.37,.81),(.75,.045,1.58),white)
for xx in (x-.38,x+.38): box('shelf side',(xx,1.14,.81),(.045,.48,1.62),white)
for z in (.04,.80,1.60): box('shelf horizontal',(x,1.14,z),(.8,.48,.045),white)
box('shelf divider',(x,1.14,1.2),(.04,.48,.77),white)
# mirror on wall with inset reflection-like white cabinets
box('mirror frame',(-1.18,1.37,2.23),(1.52,.06,1.13),trim)
mirror=mat('mirror',(.46,.50,.46),.85,.12)
box('mirror surface',(-1.18,1.325,2.23),(1.46,.02,1.07),mirror)
# reflected white wall cabinetry to evoke reference
for xx in (-1.61,-1.03):
 box('reflected cabinet',(xx,1.30,2.48),(.47,.03,.61),white)
 box('reflected cabinet inset',(xx,1.275,2.47),(.37,.015,.49),marble)
box('reflected countertop',(-1.18,1.29,1.83),(1.05,.03,.07),white)
# right foreground cabinets and marble counter
box('right base cabinet',(2.15,-.63,.49),(1.12,1.9,.98),white)
box('right counter',(2.15,-.63,1.02),(1.18,1.98,.09),marble,.015)
box('right upper cabinet',(2.5,.28,2.36),(.65,1.18,1.0),white)
# foreground dark island surface
box('foreground island',(.20,-2.0,.80),(2.4,1.05,.11),dark,.015)
# white cabinet fragment at near left
box('left foreground cabinet',(-2.45,-1.65,.4),(.7,.8,.8),white)
# illumination
world=bpy.context.scene.world; world.color=(.35,.35,.35)
def area(loc,power,size,target):
 bpy.ops.object.light_add(type='AREA',location=loc); l=bpy.context.object; l.data.energy=power; l.data.shape='DISK'; l.data.size=size; l.rotation_euler=(Vector(target)-l.location).to_track_quat('-Z','Y').to_euler()
area((-.5,-2.5,4.8),650,4,(0,.5,.5)); area((2,-.3,3.5),350,3,(0,.7,1))
bpy.ops.object.camera_add(location=(-3.4,-5.4,3.55)); cam=bpy.context.object; cam.rotation_euler=(Vector((.0,.58,1.0))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.lens=38; bpy.context.scene.camera=cam
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.samples=32; sc.cycles.use_denoising=True; sc.render.threads_mode='FIXED'; sc.render.threads=8; sc.render.resolution_x=640; sc.render.resolution_y=360; sc.render.resolution_percentage=100
sc.view_settings.view_transform='AgX'; sc.render.image_settings.file_format='PNG'; sc.render.filepath='/app/final.png'; bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
