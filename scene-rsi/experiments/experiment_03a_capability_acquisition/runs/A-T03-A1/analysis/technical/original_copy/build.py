import bpy, math, random
from mathutils import Vector
random.seed(12)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)

def mat(n,c,metal=0,rough=.5):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Metallic'].default_value=metal; p.inputs['Roughness'].default_value=rough; return m
white=mat('Painted white',(.82,.83,.81)); black=mat('Black enamel',(.018,.019,.018),.3,.25); glass=mat('Smoky oven glass',(.047,.055,.046),.35,.19); steel=mat('Brushed stainless',(.39,.38,.35),.75,.3); burner=mat('Ceramic heating zones',(.10,.12,.105),.15,.35); trim=mat('Dark frame',(.022,.028,.023),.2,.4); brown=mat('Dark wooden door',(.105,.055,.032),0,.5); grout=mat('Tile grout',(.17,.13,.045)); floor=mat('Wood flooring',(.22,.14,.095),0,.55)
def cube(n,loc,scale,ma, bevel=0):
 bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False, rotation=False, scale=True); o.data.materials.append(ma)
 if bevel:
  mod=o.modifiers.new('Soft edges','BEVEL'); mod.width=bevel; mod.segments=2; o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
 return o
# room: back wall y=2
cube('Floor',(0,0,-.08),(5.8,6,.16),floor)
# directional floorboard strips
woods=[mat('Wood tone %d'%i,(.16+i*.012,.095+i*.008,.062+i*.006),0,.52) for i in range(9)]
for i in range(30):
 x=-2.9+i*.2
 cube('Floor plank', (x,0,.006),(.196,6,.012),random.choice(woods))
 for j in range(3):
  yy=-2.8+j*2+random.uniform(-.3,.3); cube('Plank joint',(x,yy,.014),(.195,.009,.002),trim)
# back tiled wall and left extension
cube('Back wall',(0,2.06,1.65),(5.8,.12,3.3),grout)
tiles=[mat('Gold tile %02d'%i,(.20+i*.012,.15+i*.009,.035+i*.003),.2,.43) for i in range(20)]
for ix in range(32):
 for iz in range(18):
  x=-2.85+ix*.18; z=.09+iz*.18
  cube('Individual gold wall tile',(x,1.987,z),(.177,.018,.177),random.choice(tiles))
cube('Baseboard',(0,1.94,.09),(5.8,.09,.18),white)
# main stove, front faces toward camera negative y
sx=-.12; sy=1.13
cube('Range body',(sx,sy,.48),(.98,.77,.96),black,.018)
cube('Oven glass door',(sx,.728,.45),(.88,.035,.67),glass,.012)
cube('Door upper border',(sx,.701,.80),(.94,.045,.07),steel,.008)
cube('Oven handle',(sx,.64,.73),(.78,.065,.055),steel,.016)
for z in [.25,.38,.52]: cube('Oven interior rack',(sx,.704,z),(.70,.008,.007),steel)
cube('Cooktop steel rim',(sx,sy,.985),(1.01,.82,.07),steel,.012)
cube('Cooktop surface',(sx,sy,1.027),(.94,.75,.016),black)
for dx in [-.25,.25]:
 for dy in [-.19,.19]:
  bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=.145 if dx<0 else .125, depth=.008, location=(sx+dx,sy+dy,1.04)); bpy.context.object.name='Circular electric burner'; bpy.context.object.data.materials.append(burner)
cube('Raised control panel',(sx,1.48,1.17),(1,.09,.29),steel,.014)
for x in [sx-.36,sx+.36]:
 bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=.075, depth=.035, location=(x,1.42,1.18), rotation=(math.pi/2,0,0)); bpy.context.object.name='Control dial'; bpy.context.object.data.materials.append(steel)
# second wide black oven to left
cube('Freestanding left oven',(-1.45,.83,.51),(1.15,.86,1.02),black,.015)
cube('Left oven front glass',(-1.45,.385,.48),(1.03,.022,.75),glass,.008)
cube('Left oven handle',(-1.45,.345,.83),(.92,.055,.05),steel,.012)
for z in [.26,.34,.42,.50,.58]: cube('Left oven rack',(-1.45,.369,z),(.86,.01,.009),steel)
# white cubby behind stove right
cube('Shelf left side',(.58,1.74,1.38),(.06,.42,.94),white)
cube('Shelf right side',(1.18,1.74,1.38),(.06,.42,.94),white)
cube('Shelf top',(.88,1.74,1.87),(.66,.42,.06),white)
cube('Shelf bottom',(.88,1.74,.92),(.66,.42,.06),white)
cube('Shelf middle horizontal',(.88,1.74,1.38),(.66,.42,.05),white)
cube('Shelf center divider',(.88,1.74,1.40),(.045,.42,.9),white)
cube('Shelf back',(.88,1.95,1.39),(.66,.025,.95),white)
# wall mirror and suggested reflected cabinetry
cube('Mirror dark frame',(-1.18,1.955,2.25),(1.65,.045,1.18),trim)
mirror=mat('Mirror surface',(.39,.40,.37),.65,.14)
cube('Mirror',(-1.18,1.923,2.25),(1.59,.015,1.12),mirror)
# white cabinet mounted in mirror region suggesting reflection
cube('Reflected upper cabinet',(-1.20,1.90,2.69),(1.18,.045,.63),white)
for x in [-1.55,-.85]:
 cube('Cabinet recessed panel',(x,1.869,2.69),(.28,.012,.48),mat('Cabinet inset '+str(x),(.63,.65,.63)))
 cube('Cabinet shelf',(x,1.852,2.68),(.28,.03,.035),white)
# right doorway, bright opening and open brown leaf
cream=mat('Light beyond doorway',(.94,.86,.69)); cube('Door opening',(1.75,1.96,1.40),(.58,.04,2.8),cream)
cube('Open door leaf',(2.12,1.62,1.35),(.52,.10,2.7),brown,.01)
cube('Door panel inset',(2.12,1.555,1.48),(.39,.025,1.8),brown,.01)
# right counter parallel to picture edge
cube('Right base cabinet',(2.04,-.22,.47),(.95,2.45,.94),white,.008)
cube('White marble countertop',(2.04,-.22,.98),(1.04,2.55,.08),white,.01)
# countertop subtle gray veins
vein=mat('Marble veins',(.58,.60,.60),0,.65)
for i in range(9):
 o=cube('Marble vein',(1.58+random.random()*.88,-1.3+random.random()*2.2,1.026),(.008,random.uniform(.25,.8),.002),vein); o.rotation_euler[2]=random.uniform(-.6,.6)
# foreground dark island
cube('Foreground dark countertop',(.15,-1.87,.84),(2.5,1.05,.10),black,.015)
# lighting
world=bpy.context.scene.world; world.color=(.35,.35,.35)
def area(loc,power,size,target):
 bpy.ops.object.light_add(type='AREA', location=loc); l=bpy.context.object; l.data.energy=power; l.data.shape='DISK'; l.data.size=size; l.rotation_euler=(Vector(target)-l.location).to_track_quat('-Z','Y').to_euler()
area((0,-1,4.7),650,4,(0,1,0)); area((3,-2,3.2),350,3,(0,1,1))
# camera
bpy.ops.object.camera_add(location=(3.35,-4.8,3.65)); cam=bpy.context.object; cam.rotation_euler=(Vector((-.05,.9,.83))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.type='PERSP'; cam.data.lens=25; bpy.context.scene.camera=cam
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True; scene.render.threads_mode='FIXED'; scene.render.threads=8
scene.render.resolution_x=640; scene.render.resolution_y=360; scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'; scene.render.image_settings.file_format='PNG'; scene.render.filepath='/app/final.png'
bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
