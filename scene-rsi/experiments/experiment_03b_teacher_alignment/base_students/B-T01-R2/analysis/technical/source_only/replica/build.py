import bpy, math, random
from mathutils import Vector
random.seed(4)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
def mat(n,c,rough=.5,metal=0):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal; return m
def cube(n,loc,scale,ma,bev=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bev: mod=o.modifiers.new('Soft edges','BEVEL'); mod.width=bev; mod.segments=2; o.modifiers.new('Normals','WEIGHTED_NORMAL')
 return o
def cyl(n,a,b,r,ma,verts=12):
 d=Vector(b)-Vector(a); mid=(Vector(a)+Vector(b))/2; bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=d.length,location=mid); o=bpy.context.object; o.name=n; o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); o.data.materials.append(ma); return o
white=mat('White laminate',(0.86,.88,.87),.3); mint=mat('Pale mint upper walls',(.68,.79,.75),.8); trim=mat('White painted molding',(.83,.85,.82),.45); dark=mat('Charcoal window frames',(.035,.045,.048),.35); glass=mat('Bright opaque window',(.9,.91,.88),.35); metal=mat('Light gray metal',(.68,.7,.68),.3,.45); black=mat('Black chair hardware',(.025,.027,.027),.4); upholstery=mat('Warm gray chair upholstery',(.48,.47,.43),.85); wood=mat('Pale birch door',(.65,.49,.34),.6); floor=mat('Polished dark floor',(.19,.23,.22),.08,.15)
# tiled stone wall procedural
stone=bpy.data.materials.new('Gray marble square tile'); stone.use_nodes=True; nt=stone.node_tree; p=nt.nodes.get('Principled BSDF'); p.inputs['Roughness'].default_value=.66
tex=nt.nodes.new('ShaderNodeTexCoord'); noise=nt.nodes.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value=38; noise.inputs['Detail'].default_value=5; noise.inputs['Roughness'].default_value=.72; nt.links.new(tex.outputs['Generated'],noise.inputs['Vector']); ramp=nt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].position=.25; ramp.color_ramp.elements[0].color=(.35,.37,.35,1); ramp.color_ramp.elements[1].position=.75; ramp.color_ramp.elements[1].color=(.67,.68,.65,1); nt.links.new(noise.outputs['Fac'],ramp.inputs[0]); nt.links.new(ramp.outputs[0],p.inputs['Base Color'])
# room dimensions x +-4.4 y 0..8
cube('Reflective floor',(0,4,-.08),(8.8,8.5,.16),floor)
cube('Left lower tiled wall',(-4.45,4,1.0),(.1,8,2),stone); cube('Left upper wall',(-4.45,4,2.65),(.1,8,1.3),mint)
cube('Back lower tiled wall',(0,8,1), (8.9,.12,2),stone); cube('Back upper wall',(0,8,2.65),(8.9,.12,1.3),mint)
cube('Right lower tiled wall',(4.45,4,1),(.1,8,2),stone); cube('Right upper wall',(4.45,4,2.65),(.1,8,1.3),mint)
cube('Ceiling',(0,4,3.36),(8.9,8.1,.1),trim)
for x in [-4.37,4.37]:
 cube('Baseboard',(x,4,.15),(.12,8,.28),trim); cube('Crown molding',(x,4,3.22),(.16,8,.12),trim)
cube('Back baseboard',(0,7.9,.15),(8.8,.14,.28),trim); cube('Back crown molding',(0,7.9,3.22),(8.8,.15,.12),trim)
# tile grout lines
joint=mat('Tile grout',(.56,.58,.56),.8)
for z in [i*.34 for i in range(1,6)]:
 for x in [-4.385,4.385]: cube('Horizontal tile joint',(x,4,z),(.008,8,.008),joint)
 cube('Horizontal back tile joint',(0,7.93,z),(8.8,.008,.008),joint)
for y in [i*.34 for i in range(24)]:
 for x in [-4.38,4.38]: cube('Vertical tile joint',(x,y,1),(.009,.008,1.95),joint)
for x in [i*.34-4.4 for i in range(27)]: cube('Vertical back tile joint',(x,7.925,1),(.008,.009,1.95),joint)
# window left wall: bright panel and dark perimeter overlays
cube('Window glazing',(-4.36,4.05,2.35),(.035,3.1,1.27),glass)
for y in [2.48,5.62]: cube('Window vertical frame',(-4.31,y,2.35),(.1,.07,1.4),dark)
for z in [1.67,3.03]: cube('Window horizontal frame',(-4.31,4.05,z),(.1,3.2,.07),dark)
for y in [3.53,4.58]: cube('Window mullion',(-4.29,y,2.35),(.12,.09,1.3),dark)
# door back
cube('Wooden door',(1.15,7.88,1.11),(.94,.09,2.22),wood,.015)
for x in [.68,1.62]: cube('Door jamb',(x,7.81,1.12),(.06,.07,2.27),trim)
cube('Door header',(1.15,7.81,2.25),(1,.07,.06),trim)
for z in [.4,.95,1.53,1.95]:
 for x in [.91,1.39]: cube('Door inset panel',(x,7.82,z),(.36,.015,.35 if z<1.8 else .22),wood,.015)
cyl('Door handle spindle',(.82,7.77,1.0),(.82,7.69,1.0),.035,black); bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,radius=.052,location=(.82,7.67,1)); bpy.context.object.data.materials.append(metal)
def desk(x,y,w=1.38,d=.72,legmat=metal):
 cube('White desktop',(x,y,.83),(w,d,.065),white,.015)
 for dx in [-w/2+.065,w/2-.065]:
  for dy in [-d/2+.065,d/2-.065]: cyl('Desk leg',(x+dx,y+dy,.04),(x+dx,y+dy,.8),.025,legmat)
def chair(x,y):
 # seat and back, facing camera/front (-y)
 cube('Chair cushioned seat',(x,y,.48),(.48,.45,.11),upholstery,.08)
 o=cube('Chair rounded back',(x,y+.2,.8),(.47,.10,.56),upholstery,.11); o.rotation_euler[0]=-.08
 cyl('Chair central post',(x,y,.12),(x,y,.47),.04,black)
 for a in range(5):
  ang=a*math.tau/5; end=(x+.31*math.cos(ang),y+.31*math.sin(ang),.08); cyl('Chair five star base',(x,y,.12),end,.025,black); bpy.ops.mesh.primitive_uv_sphere_add(segments=10,ring_count=6,radius=.052,location=end); bpy.context.object.name='Caster wheel'; bpy.context.object.data.materials.append(black)
# desks rows, chairs behind desks
for y in [2.15,3.85,5.55,6.85]:
 for x in [-2.45,-.35,1.75,3.35]:
  if (y==2.15 and x in [-2.45,3.35]) or (y==6.85 and x in [-2.45,3.35]): continue
  desk(x,y,1.35 if x!=3.35 else 1.1,.66); chair(x,y+.54)
desk(-3.35,1.0,1.35,.72,black)
# lighting
world=bpy.context.scene.world; world.color=(.7,.7,.7)
def area(n,loc,power,size,target):
 bpy.ops.object.light_add(type='AREA',location=loc); o=bpy.context.object; o.name=n; o.data.energy=power; o.data.shape='DISK'; o.data.size=size; o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
area('Large soft ceiling light',(0,3.5,3.15),900,5,(0,4,0)); area('Window daylight',(-4,3.7,2.5),650,3,(0,4,1)); area('Front fill',(0,-1,3),350,4,(0,4,1))
bpy.ops.object.camera_add(location=(7.6,-9.2,4.8)); cam=bpy.context.object; cam.rotation_euler=(Vector((-.3,4.6,1.25))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.lens=23; bpy.context.scene.camera=cam
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True; scene.render.resolution_x=640; scene.render.resolution_y=360; scene.render.resolution_percentage=100; scene.render.image_settings.file_format='PNG'; scene.render.filepath='/app/final.png'; scene.view_settings.view_transform='AgX'; scene.render.film_transparent=False
bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
