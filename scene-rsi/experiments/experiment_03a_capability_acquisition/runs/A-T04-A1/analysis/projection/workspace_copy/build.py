import bpy, math, random
from mathutils import Vector
random.seed(4)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
def mat(n,c,rough=.7,metal=0):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal; return m
def box(n,loc,dim,ma,bev=0):
 bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o=bpy.context.object; o.name=n; o.dimensions=dim; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bev:
  mod=o.modifiers.new('Soft edges','BEVEL'); mod.width=bev; mod.segments=4; o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
 return o
def cylinder(n,loc,r,depth,ma,vertices=32):
 bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=depth,location=loc); o=bpy.context.object; o.name=n; o.data.materials.append(ma); return o
def track(o,pt): o.rotation_euler=(Vector(pt)-o.location).to_track_quat('-Z','Y').to_euler()
wall=mat('Pale lilac plaster',(.69,.67,.76)); floor=mat('Ivory floor',(.77,.75,.76)); white=mat('Warm white painted furniture',(.89,.89,.87)); blue=mat('Powder blue upholstery',(.57,.79,.83)); rug=mat('Blush pink rug',(.75,.66,.70)); wood=mat('Light natural oak',(.67,.43,.30)); dark=mat('Dark bronze',(.12,.085,.075),.35,.55); mirror=mat('Mirror glass',(.50,.56,.56),.13,.65); table=mat('Glossy brown tabletop',(.30,.19,.17),.12,.32); black=mat('Black metal',(.035,.032,.038),.4); cream=mat('Lampshade',(.87,.84,.82)); navy=mat('Artwork dark blue',(.09,.09,.32)); pink=mat('Artwork coral',(.84,.36,.47)); yellow=mat('Artwork yellow',(.95,.68,.37))
# shell, open at camera side
box('Floor',(0,0,-.07),(6.5,8,.14),floor)
box('Back wall',(0,2.25,1.8),(6.4,.12,3.6),wall)
box('Left wall',(-2.45,-.5,1.8),(.12,5.5,3.6),wall)
box('Back baseboard',(0,2.16,.095),(4.8,.06,.19),white,.01)
box('Left baseboard',(-2.37,-.25,.095),(.06,4.9,.19),white,.01)
# couch base, arms, three cushions
box('Sofa lower plinth',(-.25,1.45,.27),(2.75,.79,.28),blue,.1)
box('Sofa back',(-.25,1.82,.72),(2.76,.20,.95),blue,.1)
for x in [-1.13,-.25,.63]:
 box('Seat cushion', (x,1.29,.48),(.86,.82,.25),blue,.105)
 box('Back cushion',(x,1.76,.88),(.86,.25,.61),blue,.12)
for x in [-1.72,1.22]:
 box('Sofa arm',(x,1.45,.65),(.22,.92,.85),blue,.065)
for x in [-1.42,.95]:
 for y in [1.14,1.73]: cylinder('Sofa foot',(x,y,.09),.035,.18,dark,16)
# projecting chaise footrest
box('Chaise extension',(.64,.72,.39),(.9,.85,.20),blue,.12)
for x in [.30,.98]: cylinder('Chaise foot',(x,.4,.12),.025,.24,dark,16)
# round rug
cylinder('Round pale pink rug',(0,-.65,.015),1.82,.025,rug,96)
# coffee table foreground
box('Coffee table rim',(0,-1.30,.47),(1.62,1.12,.08),dark,.018)
box('Coffee table glossy top',(0,-1.30,.52),(1.55,1.05,.035),table,.012)
for x in [-.70,.70]:
 for y in [-1.75,-.85]: box('Coffee table leg',(x,y,.24),(.035,.035,.48),dark,.008)
# glossy striped reflected bands on tabletop
stripe=mat('Pale reflections',(.67,.56,.52),.2,.15)
for i in range(11):
 x=-.69+i*.14
 box('Table inlay', (x,-1.3,.541),(.012,1.02,.004),stripe)
# white low cabinet left foreground
box('Low console top',(-2.03,-1.06,.68),(.64,2.05,.09),white,.01)
box('Low console bottom',(-2.03,-1.06,.10),(.64,2.05,.08),white,.01)
for y in [-2.05,-1.08,-.07]: box('Console partition',(-2.03,y,.39),(.64,.07,.58),white,.01)
# tall white cabinet to right of sofa
box('Tall cupboard body',(1.75,1.42,1.05),(.70,.62,2.05),white,.025)
for x in [1.58,1.92]:
 box('Cupboard door',(x,1.095,1.07),(.32,.025,1.96),white,.012)
 box('Cupboard handle',(x+(.11 if x<1.75 else -.11),1.069,1.06),(.028,.035,.19),cream,.01)
# tall open wooden bookcase on right facing into room, shelves extend toward camera
for x in [2.12,2.90]: box('Bookcase side',(x,-.25,1.65),(.10,1.65,3.3),wood,.008)
for z in [.06,.70,1.34,1.98,2.62,3.26]: box('Bookcase shelf',(2.51,-.25,z),(.80,1.65,.09),wood,.008)
box('Bookcase central divider',(2.51,-.25,1.65),(.06,1.65,3.2),wood,.004)
# mirror above sofa
box('Mirror backing',(-.20,2.165,2.14),(1.02,.055,1.10),dark,.01)
box('Mirror reflective face',(-.20,2.13,2.14),(.94,.012,1.02),mirror)
for x in [-.70,.30]: box('Mirror frame',(x,2.115,2.14),(.045,.05,1.10),wood,.006)
for z in [1.60,2.68]: box('Mirror frame',(-.20,2.115,z),(1.04,.05,.045),wood,.006)
# floor lamp at sofa end
cylinder('Lamp base',(1.34,1.96,.04),.18,.05,black)
cylinder('Lamp stem',(1.34,1.96,.89),.018,1.7,black,16)
bpy.ops.mesh.primitive_cone_add(vertices=48,radius1=.20,radius2=.15,depth=.36,location=(1.34,1.96,1.73)); bpy.context.object.name='White tapered lampshade'; bpy.context.object.data.materials.append(cream)
# framed abstract map on left wall
box('Artwork frame',(-2.365,.50,2.02),(.06,1.80,1.45),dark,.01)
box('Artwork blue field',(-2.328,.50,2.02),(.012,1.73,1.38),navy)
# irregular flat shapes on image-facing plane
def blob(n,pts,ma):
 mesh=bpy.data.meshes.new(n); mesh.from_pydata([(-2.315,y,z) for y,z in pts],[],[list(range(len(pts)))]); mesh.materials.append(ma); ob=bpy.data.objects.new(n,mesh); bpy.context.collection.objects.link(ob)
blob('Coral landmass',[(.12,2.70),(.78,2.70),(.92,2.52),(.83,2.39),(1.01,2.22),(.90,2.05),(.72,1.96),(.58,1.83),(.38,1.88),(.30,2.03),(.09,2.14),(-.05,2.32)],pink)
blob('Gold coastline',[(.31,2.02),(.39,1.89),(.58,1.83),(.73,1.96),(.90,2.05),(1.01,2.22),(.95,2.31),(.87,2.17),(.70,2.08),(.56,1.98),(.46,2.01)],yellow)
# illumination
world=bpy.context.scene.world or bpy.data.worlds.new('World'); bpy.context.scene.world=world; world.use_nodes=True; world.node_tree.nodes['Background'].inputs[0].default_value=(.72,.70,.79,1); world.node_tree.nodes['Background'].inputs[1].default_value=.7
bpy.ops.object.light_add(type='AREA', location=(-.4,-1.0,4.5)); light=bpy.context.object; light.name='Large soft ceiling light'; light.data.energy=550; light.data.shape='DISK'; light.data.size=5; track(light,(0,1,0))
bpy.ops.object.camera_add(location=(0,-5.45,3.35)); cam=bpy.context.object; cam.name='Camera'; track(cam,(0,1.05,.95)); cam.data.lens=27; bpy.context.scene.camera=cam
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True; scene.render.threads_mode='FIXED'; scene.render.threads=8; scene.render.resolution_x=640; scene.render.resolution_y=360; scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'; scene.render.image_settings.file_format='PNG'; scene.render.filepath='/app/final.png'; bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
