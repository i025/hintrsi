"""Synthetic measurement fixture, unrelated to formal reconstruction cases."""
from pathlib import Path
import math
import bpy
from mathutils import Vector
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
def cube(name,location,dimensions):
 bpy.ops.mesh.primitive_cube_add(size=1,location=location);o=bpy.context.object;o.name=name;o.dimensions=dimensions;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);return o
cube('floor',(0,0,-.05),(8,8,.1))
cube('local floor tile',(-.85,.70,.025),(1.2,1.2,.05))
for i,(x,y,z) in enumerate([(-.85,.70,.17),(1.02,-.68,.09)],1):
 bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.1,depth=.08,location=(x,y,z),rotation=(math.pi/2,0,0));bpy.context.object.name='chair '+str(i)+' caster wheel'
 cube('chair '+str(i)+' seat',(x,y,.6),(.5,.5,.1))
cube('wood door leaf',(0,2,1),(.9,.08,2))
bpy.ops.object.camera_add(location=(4,-6,3));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,.5))-cam.location).to_track_quat('-Z','Y').to_euler();bpy.context.scene.camera=cam
bpy.ops.object.light_add(type='AREA',location=(2,-3,5));bpy.context.object.data.energy=500
scene=bpy.context.scene;scene.world=bpy.data.worlds.new('Probe World');scene.world.color=(.2,.2,.2);scene.render.engine='CYCLES';scene.cycles.samples=4;scene.view_settings.view_transform='AgX';scene.render.resolution_x=640;scene.render.resolution_y=360;scene.render.resolution_percentage=100
bpy.ops.wm.save_as_mainfile(filepath='/capture/probe.blend')
