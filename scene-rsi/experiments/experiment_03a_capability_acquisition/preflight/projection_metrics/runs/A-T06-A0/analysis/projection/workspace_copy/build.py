import bpy
from mathutils import Vector
LEFT_X = -.8
OCCLUDER_SCALE = 1
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
def cube(name, location, dimensions, color):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj=bpy.context.object;obj.name=name;obj.dimensions=dimensions
    mat=bpy.data.materials.new(name+'_material');mat.use_nodes=True
    mat.node_tree.nodes.clear()
    emission=mat.node_tree.nodes.new('ShaderNodeEmission');emission.inputs['Color'].default_value=(*color,1)
    out=mat.node_tree.nodes.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(emission.outputs[0],out.inputs['Surface'])
    obj.data.materials.append(mat)
    return obj
assembly=bpy.data.objects.new('assembly',None);bpy.context.scene.collection.objects.link(assembly)
left=cube('left',(LEFT_X,0,0),(.8,.6,1.2),(.8,.2,.1));left.parent=assembly
right=cube('right',(.8,0,0),(.8,.6,1.2),(.1,.3,.8));right.parent=assembly
cube('occluder',(-.8,-1,.25),(.4*OCCLUDER_SCALE,.2,.6*OCCLUDER_SCALE),(.2,.2,.2))
bpy.ops.object.camera_add(location=(0,-8,0))
cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,0))-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.type='ORTHO';cam.data.ortho_scale=4
s=bpy.context.scene;s.camera=cam;s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=4
s.render.resolution_x=640;s.render.resolution_y=360;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.render.filepath='/app/final.png'
bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend')
bpy.ops.render.render(write_still=True)
