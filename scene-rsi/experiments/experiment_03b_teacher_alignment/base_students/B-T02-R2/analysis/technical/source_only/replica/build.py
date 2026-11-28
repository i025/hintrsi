import bpy, math, random
from mathutils import Vector
random.seed(8)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
def mat(n,c,rough=.45,metal=0):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal; return m
def cube(n,loc,scale,ma,bev=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bev: mod=o.modifiers.new('Soft edges','BEVEL'); mod.width=bev; mod.segments=3; o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
 return o
def rod(n,a,b,r,ma):
 d=Vector(b)-Vector(a); mid=(Vector(a)+Vector(b))/2; bpy.ops.mesh.primitive_cylinder_add(vertices=12,radius=r,depth=d.length,location=mid); o=bpy.context.object; o.name=n; o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); o.data.materials.append(ma); return o
pink=mat('Rose pink painted plaster',(.63,.36,.39),.85); white=mat('White baseboard',(.8,.77,.75)); dark=mat('Black metal',(.022,.026,.027),.3,.35); glass=mat('Milky pale window glass',(.68,.69,.66),.22); frame=mat('Warm wooden window frames',(.28,.14,.095),.38); chairmat=mat('Warm ivory upholstery',(.64,.57,.54),.75); green=mat('Door deep teal',(.025,.105,.11),.32); leaf=mat('Plant dark green',(.025,.12,.045),.6)
# floor checker with subtle variation
floor=mat('Glossy small checkerboard tiles',(.2,.15,.14),.23)
nt=floor.node_tree; bs=nt.nodes.get('Principled BSDF'); tex=nt.nodes.new('ShaderNodeTexChecker'); tex.inputs['Color1'].default_value=(.11,.09,.09,1); tex.inputs['Color2'].default_value=(.36,.22,.20,1); tex.inputs['Scale'].default_value=1; geo=nt.nodes.new('ShaderNodeTexCoord'); mapping=nt.nodes.new('ShaderNodeVectorMath'); mapping.operation='SCALE'; mapping.inputs[3].default_value=3.3; nt.links.new(geo.outputs['Generated'],mapping.inputs[0]); nt.links.new(mapping.outputs[0],tex.inputs['Vector']); # use object coordinates for square tiles
nt.links.remove(mapping.inputs[0].links[0]); nt.links.new(geo.outputs['Object'],mapping.inputs[0]); nt.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
cube('Floor',(4.5,3.5,-.08),(9,7,.16),floor)
cube('Left pink wall',(-.08,3.5,2.15),(.16,7,4.3),pink); cube('Back pink wall',(4.5,7.08,2.15),(9,.16,4.3),pink)
cube('Left white skirting',(.03,3.5,.12),(.12,7,.24),white); cube('Back white skirting',(4.5,6.98,.12),(9,.12,.24),white)
# left horizontal window and brown mullions
cube('Left window glass',(.02,3.65,2.62),(.03,5.65,1.48),glass)
for y in [.82,2.23,3.64,4.65,5.35,6.48]: cube('Window vertical wooden mullion',(.055,y,2.62),(.08,.065,1.53),frame)
for z in [1.87,3.37]: cube('Window horizontal wood trim',(.055,3.65,z),(.08,5.72,.065),frame)
# back window
cube('Back window glass',(5.05,6.98,2.76),(2.35,.03,1.27),glass)
for x in [3.86,6.24]: cube('Back window side trim',(x,6.94,2.76),(.055,.07,1.34),frame)
for z in [2.10,3.42]: cube('Back window top bottom trim',(5.05,6.94,z),(2.43,.07,.055),frame)
# wood material procedural
wood=mat('Polished striped rosewood',(.32,.17,.15),.17)
n=wood.node_tree.nodes; links=wood.node_tree.links; p=n.get('Principled BSDF'); noise=n.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value=3; noise.inputs['Detail'].default_value=3; texc=n.new('ShaderNodeTexCoord'); vm=n.new('ShaderNodeVectorMath'); vm.operation='MULTIPLY'; vm.inputs[1].default_value=(.7,18,4); links.new(texc.outputs['Generated'],vm.inputs[0]); links.new(vm.outputs[0],noise.inputs[0]); ramp=n.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color=(.12,.055,.045,1); ramp.color_ramp.elements[1].color=(.48,.27,.25,1); links.new(noise.outputs['Fac'],ramp.inputs[0]); links.new(ramp.outputs[0],p.inputs['Base Color'])
# conference table long along x
cube('Long glossy boardroom table',(5.0,4.35,1.36),(5.9,2.0,.12),wood,.025)
for x in [2.5,7.5]:
 for y in [3.7,5.0]: rod('Splayed table leg',(x,y,1.31),(x+(.22 if x>5 else -.22),y+(.18 if y>4.3 else -.18),.08),.035,dark)
# chairs with rounded seat and back, swivel bases
def chair(x,y,face):
 # face indicates direction toward table: +1 means faces toward back
 cube('Padded seat',(x,y,.79),(.60,.58,.12),chairmat,.11)
 cube('Padded curved back',(x,y-face*.27,1.15),(.60,.12,.76),chairmat,.16)
 rod('Chair central post',(x,y,.18),(x,y,.76),.035,dark)
 for j in range(5):
  a=j*math.tau/5; ex=x+.34*math.cos(a); ey=y+.34*math.sin(a); rod('Five star chair base',(x,y,.18),(ex,ey,.11),.035,dark); bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=6,radius=.065,location=(ex,ey,.08)); bpy.context.object.name='Caster'; bpy.context.object.data.materials.append(dark)
for x in [2.65,3.6,4.55,5.75,6.95]: chair(x,3.02,1)
for x in [2.65,3.75,4.85,5.95,7.05]: chair(x,5.65,-1)
# potted plant in corner behind table
pot=mat('Plant pot',(.18,.17,.15)); cube('Plant planter',(1.65,6.45,.22),(.35,.35,.44),pot,.035)
for i in range(9):
 a=i*math.tau/9; end=(1.65+.32*math.cos(a),6.45+.32*math.sin(a),.75+random.random()*.35); rod('Plant stem',(1.65,6.45,.4),end,.012,leaf)
 mid=Vector(end); bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,location=mid); o=bpy.context.object; o.name='Pointed plant leaf'; o.scale=(.09,.035,.28); o.rotation_euler=(.4*math.sin(a),.4*math.cos(a),a); o.data.materials.append(leaf)
# door slab close to camera on right, paneled, opens inward
# positioned to form near right edge
D=cube('Open dark teal door',(8.55,.15,2.1),(.18,1.85,4.2),green,.025); D.rotation_euler[2]=-.15
for z in [.68,1.75,2.8,3.65]:
 for yy in [-.45,.68]:
  o=cube('Raised door panel border',(8.44,yy,z),(.025,.035,.66),green,.01); o.rotation_euler[2]=-.15
 for zz in [z-.33,z+.33]:
  o=cube('Raised door panel border',(8.44,.11,zz),(.025,1.15,.035),green,.01); o.rotation_euler[2]=-.15
# camera
bpy.ops.object.camera_add(location=(8,-1,2.8)); cam=bpy.context.object; cam.name='Camera'; target=Vector((3.7,4.8,1.85)); cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.lens=24; bpy.context.scene.camera=cam
# illumination
world=bpy.context.scene.world or bpy.data.worlds.new('World'); bpy.context.scene.world=world; world.use_nodes=True; world.node_tree.nodes['Background'].inputs[0].default_value=(.75,.76,.8,1); world.node_tree.nodes['Background'].inputs[1].default_value=.55
def area(loc,power,size,target):
 bpy.ops.object.light_add(type='AREA',location=loc); o=bpy.context.object; o.data.energy=power; o.data.shape='DISK'; o.data.size=size; o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
area((3,1,6),950,5,(4,4,0)); area((6,6,5),700,4,(4,3,0)); area((1,4,4),400,3,(4,4,1))
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True; scene.render.threads_mode='FIXED'; scene.render.threads=8; scene.render.resolution_x=640; scene.render.resolution_y=360; scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'; scene.render.image_settings.file_format='PNG'; scene.render.filepath='/app/final.png'; bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
