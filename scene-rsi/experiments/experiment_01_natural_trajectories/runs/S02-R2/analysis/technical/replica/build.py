import bpy, math, random
from mathutils import Vector
random.seed(4)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)

def mat(name,color,rough=0.65,metal=0):
 m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*color,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal; return m
white=mat('Warm white painted furniture',(0.88,0.89,0.87)); wall=mat('Pale sage ceramic tile',(0.68,0.73,0.68)); grout=mat('Fine grey grout',(0.45,0.50,0.46)); floor=mat('Grey polished concrete',(0.32,0.33,0.31)); trim=mat('White trim',(0.91,0.92,0.88)); dark=mat('Dark bronze lamp',(0.12,0.105,0.09),0.35,0.5); shade=mat('Ivory linen shades',(0.91,0.90,0.83)); wood=mat('Light natural oak',(0.69,0.52,0.36)); panel=mat('Oak inset panels',(0.76,0.62,0.48)); mattress=mat('Pale lilac white bed linen',(0.87,0.85,0.87)); rugmat=mat('Mottled sand rug',(0.60,0.51,0.43)); glass=mat('Cabinet glass muted',(0.54,0.63,0.60),0.24); black=mat('Door gap',(0.025,0.025,0.022))
def box(n,loc,scale,ma,bevel=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bevel: mod=o.modifiers.new('Soft edges','BEVEL'); mod.width=bevel; mod.segments=2; o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
 return o
def cyl(n,loc,r,depth,ma,verts=32):
 bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=depth,location=loc); o=bpy.context.object; o.name=n; o.data.materials.append(ma); return o
def cone(n,loc,r1,r2,depth,ma):
 bpy.ops.mesh.primitive_cone_add(vertices=48,radius1=r1,radius2=r2,depth=depth,location=loc); o=bpy.context.object; o.name=n; o.data.materials.append(ma); return o
def point(n,loc,power,color,size=0.3):
 bpy.ops.object.light_add(type='POINT',location=loc); o=bpy.context.object; o.name=n; o.data.energy=power; o.data.color=color; o.data.shadow_soft_size=size
# floor and walls: rear wall y=3, right wall x=3
box('Floor',(0,0,-0.08),(6.5,7,0.16),floor)
box('Back tiled wall',(0,3,1.65),(6.4,0.10,3.3),wall)
box('Right tiled wall',(3.15,0,1.65),(0.1,6,3.3),wall)
# tile lines on both walls
for x in [i*0.42 for i in range(-8,9)]: box('Back vertical grout',(x,2.943,1.65),(0.007,0.006,3.3),grout)
for z in [i*0.42 for i in range(1,9)]: box('Back horizontal grout',(0,2.94,z),(6.35,0.006,0.006),grout)
for y in [i*0.42 for i in range(-7,8)]: box('Right vertical grout',(3.092,y,1.65),(0.006,0.007,3.3),grout)
for z in [i*0.42 for i in range(1,9)]: box('Right horizontal grout',(3.09,0,z),(0.006,6,0.006),grout)
box('Back baseboard',(0,2.87,0.12),(6.3,0.12,0.24),trim,0.015); box('Right baseboard',(3.02,0,0.12),(0.12,6,0.24),trim,0.015)
# left bookshelf, open front facing camera
bx=-1.65; by=2.38
box('Bookshelf back',(bx,2.76,1.04),(1.75,0.08,1.95),white,0.012)
for x in [bx-.85,bx+.85]: box('Bookshelf side',(x,by,0.95),(0.07,0.78,1.85),white,0.01)
for z in [0.18,0.58,0.98,1.38]: box('Bookshelf shelf',(bx,by,z),(1.72,0.8,0.065),white,0.008)
# little knob high on back
cyl('Small shelf peg',(bx,2.70,1.82),0.025,0.045,dark)
# narrow display cabinet
cx=-0.20; cy=2.42
box('Cabinet body',(cx,cy,0.78),(0.82,0.65,1.52),white,0.015)
# dark recessed glass areas on front y toward camera
for x in [cx-.20,cx+.20]:
 box('Cabinet glass pane',(x,2.077,1.10),(0.30,0.016,0.68),glass)
 box('Cabinet door bottom panel',(x,2.055,0.38),(0.35,0.035,0.58),white,0.006)
 for z in [0.75,1.46]: box('Glass frame rail',(x,2.04,z),(0.37,0.035,0.045),trim)
 for xx in [x-.17,x+.17]: box('Glass frame stile',(xx,2.04,1.105),(0.04,0.035,0.73),trim)
box('Cabinet top',(cx,cy,1.57),(0.88,0.72,0.06),white,0.006)
# lamps
for x,y,h,r in [(-2.85,1.3,1.9,.28),(.47,2.48,2.0,.19)]:
 cyl('Lamp round base',(x,y,0.025),r,0.045,dark); cyl('Lamp slender stem',(x,y,h/2),0.016,h,dark)
 cone('Tapered ivory lampshade',(x,y,h),r*.88,r*.62,.38,shade)
 point('Warm lamp glow',(x,y,h-.12),65,(1.0,.75,.49),.25)
# door gap at right of back wall and open oak door angled into room
box('Dark doorway reveal',(1.30,2.925,1.55),(0.22,0.025,3.1),black)
# door panel with geometry parent rotated around hinge
bpy.ops.object.empty_add(type='PLAIN_AXES',location=(1.42,2.86,0)); pivot=bpy.context.object; pivot.name='Open door hinge'; pivot.rotation_euler[2]=math.radians(-48)
def doorpart(n,loc,dim,ma):
 o=box(n,(0,0,0),dim,ma,0.008); o.parent=pivot; o.location=loc; return o
# door extends right along x from hinge, open angled toward viewer
doorpart('Natural oak door slab',(0.48,0,1.50),(.96,.09,3.0),wood)
for z,h in [(.70,1.13),(2.18,1.20)]:
 doorpart('Recessed door panel',(0.48,-.053,z),(.72,.018,h),panel)
 for x in [.12,.84]: doorpart('Door panel vertical molding',(x,-.067,z),(.022,.018,h),wood)
 for zz in [z-h/2,z+h/2]: doorpart('Door panel horizontal molding',(.48,-.067,zz),(.74,.018,.022),wood)
# bedside carpet
box('Sand rug',(0.4,1.35,0.015),(2.05,2.45,.025),rugmat,0.02)
# bed foreground extending toward camera
box('Bed timber base',(-.32,-.86,.30),(2.05,3.1,.38),wood,0.025)
box('Thick pale mattress',(-.32,-.86,.58),(2.12,3.15,.28),mattress,0.055)
# right foreground white bed end/headboard
box('White bed end panel',(2.48,-1.40,.88),(1.28,.10,1.76),white,0.015)
box('White bed along right wall',(2.55,-.20,.65),(1.18,2.4,.35),mattress,0.025)
# left foreground wall sliver
box('Left foreground dark wall',(-3.25,-.8,1.5),(.14,4.5,3),mat('Olive wall',(0.18,.22,.16)))
# illumination and camera
world=bpy.context.scene.world; world.color=(.3,.3,.3); world.use_nodes=True; world.node_tree.nodes['Background'].inputs[0].default_value=(.65,.69,.67,1); world.node_tree.nodes['Background'].inputs[1].default_value=.55
bpy.ops.object.light_add(type='AREA',location=(-1,-1,5)); bpy.context.object.data.energy=550; bpy.context.object.data.shape='DISK'; bpy.context.object.data.size=5
bpy.ops.object.camera_add(location=(-4.6,-6.9,4.65)); cam=bpy.context.object; direction=Vector((0,1.10,0.85))-cam.location; cam.rotation_euler=direction.to_track_quat('-Z','Y').to_euler(); cam.data.type='PERSP'; cam.data.lens=34; bpy.context.scene.camera=cam
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True; scene.render.resolution_x=640; scene.render.resolution_y=360; scene.render.resolution_percentage=100; scene.render.image_settings.file_format='PNG'; scene.render.filepath='/app/final.png'; scene.view_settings.view_transform='AgX'; scene.render.threads_mode='FIXED'; scene.render.threads=8
bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
