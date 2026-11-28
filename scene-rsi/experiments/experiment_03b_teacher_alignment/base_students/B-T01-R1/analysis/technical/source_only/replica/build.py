import bpy, math, random
from mathutils import Vector
random.seed(7)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
def mat(name,color,rough=.5,metal=0):
 m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*color,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal; return m
def cube(name,loc,scale,ma,bev=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=name; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bev: mod=o.modifiers.new('soft edges','BEVEL'); mod.width=bev; mod.segments=2; o.modifiers.new('normals','WEIGHTED_NORMAL')
 return o
def cyl(name,a,b,r,ma,verts=12):
 d=Vector(b)-Vector(a); mid=(Vector(a)+Vector(b))/2; bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=d.length,location=mid); o=bpy.context.object; o.name=name; o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); o.data.materials.append(ma); return o
white=mat('white laminate',(.86,.88,.86),.3); wall=mat('pale mint paint',(.68,.79,.75)); trim=mat('white skirting',(.83,.85,.82)); ceiling=mat('ceiling',(.67,.69,.66)); black=mat('black window frames',(.025,.03,.03),.35); metal=mat('silver desk legs',(.57,.6,.59),.25,.65); dark=mat('chair black plastic',(.035,.04,.04),.38); fabric=mat('warm grey upholstery',(.45,.44,.40),.85); door=mat('light birch door',(.65,.48,.33),.6); panel=mat('door panels',(.69,.52,.36),.7); glass=mat('bright window',(.91,.91,.87),.25); floor=mat('highly polished dark gray floor',(.18,.21,.20),.08,.22)
# procedural stone wall material
stone=bpy.data.materials.new('grey marble tiles'); stone.use_nodes=True
n=stone.node_tree.nodes; l=stone.node_tree.links; p=n.get('Principled BSDF'); p.inputs['Roughness'].default_value=.72
tex=n.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value=6; tex.inputs['Detail'].default_value=5; tex.inputs['Roughness'].default_value=.72
coord=n.new('ShaderNodeTexCoord'); l.new(coord.outputs['Generated'],tex.inputs['Vector']); ramp=n.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color=(.35,.37,.35,1); ramp.color_ramp.elements[1].color=(.68,.69,.65,1); l.new(tex.outputs['Fac'],ramp.inputs[0]); l.new(ramp.outputs[0],p.inputs['Base Color'])
# room, back y=4; left x=-4
cube('floor',(0,0,-.08),(8,9,.16),floor)
cube('back upper wall',(0,4,2.5),(8,.12,1.7),wall); cube('back tiled wall',(0,4,1),(8,.12,2),stone)
cube('left upper wall',(-4,0,2.5),(.12,8,1.7),wall); cube('left tiled wall',(-4,0,1),(.12,8,2),stone)
cube('right upper wall',(4,0,2.5),(.12,8,1.7),wall); cube('right tiled wall',(4,0,1),(.12,8,2),stone)
cube('ceiling',(0,0,3.38),(8,8,.12),ceiling)
for x in [-3.91,3.91]:
 cube('baseboard',(x,0,.14),(.08,8,.24),trim); cube('crown molding',(x,0,3.24),(.10,8,.09),trim)
cube('back baseboard',(0,3.91,.14),(8,.08,.24),trim); cube('back crown molding',(0,3.91,3.24),(8,.1,.09),trim)
# tile grout as thin grid lines
joint=mat('tile grout',(.53,.55,.52))
for z in [.4,.8,1.2,1.6]:
 cube('horizontal grout back',(0,3.932,z),(8,.008,.008),joint)
 for x in [-3.932,3.932]: cube('horizontal grout side',(x,0,z),(.008,8,.008),joint)
for x in [i*.4 for i in range(-10,11)]: cube('vertical grout back',(x,3.931,1),(.007,.008,2),joint)
for y in [i*.4 for i in range(-10,11)]:
 for x in [-3.931,3.931]: cube('vertical grout side',(x,y,1),(.008,.007,2),joint)
# window on left wall facing room, three tall panes
cube('window pale glazing',(-3.925,1.05,2.28),(.035,3.55,1.35),glass)
for y in [-.76,.42,1.62,2.86]: cube('window upright',(-3.88,y,2.28),(.10,.065,1.45),black)
for z in [1.56,3.0]: cube('window frame',(-3.88,1.05,z),(.10,3.7,.07),black)
# door on back
cube('door leaf',(1.55,3.89,1.18),(.88,.08,2.35),door)
for x in [1.34,1.76]:
 for z in [.42,1.04,1.68,2.12]: cube('raised wooden door panel',(x,3.838,z),(.32,.025,.39 if z<2 else .25),panel,.015)
cyl('door handle stem',(1.23,3.82,1.05),(1.23,3.73,1.05),.027,metal); bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,radius=.045,location=(1.23,3.72,1.05)); bpy.context.object.data.materials.append(dark)
# tables and swivel chairs
def desk(x,y,w=1.35,depth=.62,teacher=False):
 cube('white tabletop',(x,y,.78),(w,depth,.065),white,.012)
 for dx in [-w/2+.075,w/2-.075]:
  for dy in [-depth/2+.065,depth/2-.065]: cyl('straight desk leg',(x+dx,y+dy,.04),(x+dx,y+dy,.75),.023,dark if teacher else metal)
def chair(x,y):
 # faces towards camera, back behind desk
 cube('chair seat',(x,y,.47),(.48,.44,.10),fabric,.07)
 cube('chair back',(x,y+.20,.78),(.44,.11,.57),fabric,.10)
 cyl('chair central post',(x,y,.10),(x,y,.46),.035,dark)
 for a in range(5):
  ang=a*math.tau/5; ex=x+.30*math.cos(ang); ey=y+.30*math.sin(ang); cyl('five star chair base',(x,y,.12),(ex,ey,.07),.025,dark); cyl('caster',(ex,ey,.045),(ex,ey,.09),.042,dark)
# grid facing camera: chairs behind each desktop
for y in [-1.0,.35,1.68,2.9]:
 for x in [-1.55,.15,1.85]:
  desk(x,y,1.22,.57); chair(x,y+.47)
desk(-3.03,-1.55,1.1,.64,True)
# lighting
world=bpy.context.scene.world or bpy.data.worlds.new('World'); bpy.context.scene.world=world; world.use_nodes=True; world.node_tree.nodes['Background'].inputs[0].default_value=(.76,.8,.78,1); world.node_tree.nodes['Background'].inputs[1].default_value=.65
def area(name,loc,power,size,target):
 bpy.ops.object.light_add(type='AREA',location=loc); o=bpy.context.object; o.name=name; o.data.energy=power; o.data.shape='DISK'; o.data.size=size; o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
area('large ceiling light',(0,-.3,3.15),600,4,(0,0,0)); area('window light',(-3.5,1.0,2.6),350,2.5,(0,0,1))
bpy.ops.object.camera_add(location=(5.2,-8.7,3.0)); cam=bpy.context.object; cam.rotation_euler=(Vector((-.25,.8,1.48))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.lens=22; bpy.context.scene.camera=cam
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True; scene.render.threads_mode='FIXED'; scene.render.threads=8; scene.render.resolution_x=640; scene.render.resolution_y=360; scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'; scene.render.image_settings.file_format='PNG'; scene.render.filepath='/app/final.png'; bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
