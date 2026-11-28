import bpy, math, random
from mathutils import Vector
random.seed(4)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)

def mat(n,c,rough=.7,metal=0):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal; return m
white=mat('Warm ivory walls',(.78,.76,.74)); floor=mat('Pale stone floor',(.76,.75,.73)); grout=mat('Subtle hexagonal grout',(.60,.58,.57)); black=mat('Black powder coated steel',(.025,.023,.022),.4); desk=mat('Charcoal grey tabletops',(.22,.21,.20)); shell=mat('White molded chair plastic',(.86,.86,.85),.33); frame=mat('Dark bronze window frame',(.075,.065,.06),.4); glass=mat('Pale blue window glass',(.65,.74,.78),.3); brass=mat('Lamp warm bronze',(.43,.31,.27),.45); shade=mat('Taupe linen lampshade',(.52,.46,.42)); baseboard=mat('White skirting',(.88,.86,.83))
def cube(n,loc,scale,ma,bevel=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=n; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(ma)
 if bevel: mod=o.modifiers.new('Soft edges','BEVEL'); mod.width=bevel; mod.segments=3; o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
 return o
def cyl(n,a,b,r,ma,verts=16):
 d=Vector(b)-Vector(a); mid=(Vector(a)+Vector(b))/2; bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=d.length,location=mid); o=bpy.context.object; o.name=n; o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); o.data.materials.append(ma); return o
def curve(n,pts,r,ma):
 cu=bpy.data.curves.new(n,'CURVE'); cu.dimensions='3D'; cu.resolution_u=1; cu.bevel_depth=r; cu.bevel_resolution=1; sp=cu.splines.new('POLY'); sp.points.add(len(pts)-1)
 for p,co in zip(sp.points,pts): p.co=(*co,1)
 ob=bpy.data.objects.new(n,cu); bpy.context.collection.objects.link(ob); ob.data.materials.append(ma); return ob
# room, back wall at y=4
cube('Floor',(0,0,-.08),(13,13,.16),floor)
cube('Back wall',(0,4.05,2.2),(12,.1,4.4),white)
cube('Right wall',(5.65,-.1,2.2),(.1,8.3,4.4),white)
cube('Right baseboard',(5.57,-.1,.10),(.07,8.2,.20),baseboard)
# thin honeycomb on walls, combined curves
cu=bpy.data.curves.new('Fine honeycomb wall tile lines','CURVE'); cu.dimensions='3D'; cu.bevel_depth=.0023; cu.bevel_resolution=0
r=.155
for wall in [0,1]:
 for i in range(-30,31):
  for j in range(-2,23):
   u=i*1.5*r; z=j*math.sqrt(3)*r+(i%2)*math.sqrt(3)*r/2
   if z<.05 or z>4.4: continue
   if wall==0 and (u < -6 or u > 5.6): continue
   if wall==1 and (u < -4 or u > 4): continue
   sp=cu.splines.new('POLY'); sp.points.add(6)
   for k in range(7):
    a=k*math.pi/3; uu=u+r*math.cos(a); zz=z+r*math.sin(a)
    sp.points[k].co=((uu,3.987,zz,1) if wall==0 else (5.587,uu,zz,1))
ob=bpy.data.objects.new('Continuous subtle hex tile pattern',cu); bpy.context.collection.objects.link(ob); ob.data.materials.append(grout)
# window mounted on back wall
cube('Window dark outer frame',(-.15,3.92,2.75),(2.35,.12,1.75),frame)
cube('Left luminous pane',(-.72,3.84,2.75),(1.04,.03,1.58),glass)
cube('Right luminous pane',(.43,3.84,2.75),(1.04,.03,1.58),glass)
cube('Center window mullion',(-.15,3.80,2.75),(.10,.07,1.68),frame)
# tables in rows, separate slender legs
def table(x,y,w=2.05):
 cube('Rectangular dark tabletop',(x,y,.77),(w,.70,.045),desk,.012)
 for dx in [-w/2+.09,w/2-.09]:
  for dy in [-.27,.27]: cube('Thin square table leg',(x+dx,y+dy,.38),(.035,.035,.76),black,.004)
for y in [2.15,.72]:
 for x in [-4.35,-2.15,.05,2.25,4.45]: table(x,y)
# molded seat shell curved mesh; faces toward tables (+Y), visible rear
def chair(x,y,ang=0):
 # chair local coords width x, forward y
 def tr(p):
  a=ang; return (x+p[0]*math.cos(a)-p[1]*math.sin(a),y+p[0]*math.sin(a)+p[1]*math.cos(a),p[2])
 # smoothly curved bucket back, variable silhouette
 verts=[]; faces=[]; N=20; M=12
 for j in range(M+1):
  t=j/M; z=.48+.64*t; width=.47*(1-.22*t*t)*math.sqrt(max(.001,1-(max(0,t-.68)/.34)**2)) if t>.68 else .47*(1-.13*t)
  for i in range(N+1):
   u=2*i/N-1; xx=width*u; yy=-.18-.12*t + .13*u*u; verts.append(tr((xx,yy,z+.045*u*u)))
 for j in range(M):
  for i in range(N):
   a=j*(N+1)+i; faces.append((a,a+1,a+N+2,a+N+1))
 me=bpy.data.meshes.new('Chair shell mesh'); me.from_pydata(verts,[],faces); me.update(); o=bpy.data.objects.new('Curved white chair back',me); bpy.context.collection.objects.link(o); o.data.materials.append(shell)
 for p in me.polygons:p.use_smooth=True
 so=o.modifiers.new('Shell thickness','SOLIDIFY'); so.thickness=.025; su=o.modifiers.new('Soft shell edge','SUBSURF'); su.levels=2
 # seat elliptical flattened sphere
 bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,location=tr((0,.02,.48))); o=bpy.context.object; o.name='White rounded chair seat'; o.scale=(.47,.41,.055); o.rotation_euler.z=ang; o.data.materials.append(shell); bpy.ops.object.shade_smooth()
 cyl('Chair central pedestal',tr((0,0,.12)),tr((0,0,.46)),.035,black)
 for k in range(5):
  a=2*math.pi*k/5+.2; end=(.44*math.cos(a),.44*math.sin(a),.08); cyl('Five star chair base spoke',tr((0,0,.13)),tr(end),.035,black,12)
  p=tr(end); bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,radius=1,location=(p[0],p[1],.075)); w=bpy.context.object; w.name='Black caster wheel'; w.scale=(.075,.052,.075); w.data.materials.append(black)
for x,y,a in [(-3.85,-1.15,0),(-.35,-1.10,0),(2.7,-.85,-.15),(5,-.72,-.4),(-5.1,1.2,0),(-2.7,1.25,0),(-.6,1.27,0),(1.5,1.35,0),(3.4,1.34,0)]: chair(x,y,a)
# two floor lamps near right wall
for y in [2.45,-.15]:
 x=5.15
 cyl('Lamp round foot',(x,y,.035),(x,y,.055),.22,brass,32); cyl('Slender lamp stem',(x,y,.05),(x,y,1.62),.018,brass)
 bpy.ops.mesh.primitive_cone_add(vertices=32,radius1=.25,radius2=.20,depth=.32,location=(x,y,1.68)); bpy.context.object.name='Taupe drum lamp shade'; bpy.context.object.data.materials.append(shade)
 for z,energy in [(1.49,85),(1.86,65)]:
  bpy.ops.object.light_add(type='POINT',location=(x,y,z)); l=bpy.context.object; l.name='Warm lamp glow'; l.data.energy=energy; l.data.color=(1,.72,.52); l.data.shadow_soft_size=.24
# light
world=bpy.context.scene.world; world.color=(.7,.7,.7); world.use_nodes=True; world.node_tree.nodes['Background'].inputs['Color'].default_value=(.7,.72,.75,1); world.node_tree.nodes['Background'].inputs['Strength'].default_value=.55
bpy.ops.object.light_add(type='AREA',location=(-2,-3,5.5)); bpy.context.object.data.energy=850; bpy.context.object.data.shape='DISK'; bpy.context.object.data.size=7
bpy.ops.object.light_add(type='AREA',location=(1,1,5)); bpy.context.object.data.energy=450; bpy.context.object.data.size=5
# camera
bpy.ops.object.camera_add(location=(0,-8.8,2.65)); cam=bpy.context.object; cam.rotation_euler=(Vector((0,1.3,1.45))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.type='PERSP'; cam.data.lens=32; bpy.context.scene.camera=cam
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.samples=32; sc.cycles.use_denoising=True; sc.render.threads_mode='FIXED'; sc.render.threads=8; sc.render.resolution_x=640; sc.render.resolution_y=360; sc.render.resolution_percentage=100
sc.view_settings.view_transform='AgX'; sc.render.image_settings.file_format='PNG'; sc.render.filepath='/app/final.png'
bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend'); bpy.ops.render.render(write_still=True)
