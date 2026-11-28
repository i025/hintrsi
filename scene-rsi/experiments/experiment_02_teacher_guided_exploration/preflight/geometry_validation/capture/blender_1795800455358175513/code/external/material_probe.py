"""Known-value Blender node fixture for the extended passive state extractor."""
import bpy,sys,runpy
bpy.ops.wm.open_mainfile(filepath='/capture/probe.blend',load_ui=False,use_scripts=False)
m=bpy.data.materials.new('Extraction fixture');m.use_nodes=True
nodes=m.node_tree.nodes
mapping=nodes.new('ShaderNodeMapping');mapping.inputs['Scale'].default_value=(2,1,.5)
noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=3.5
ramp=nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.1;ramp.color_ramp.elements[1].position=.9
m.node_tree.links.new(mapping.outputs['Vector'],noise.inputs['Vector']);m.node_tree.links.new(noise.outputs['Fac'],ramp.inputs[0]);m.node_tree.links.new(ramp.outputs['Color'],nodes.get('Principled BSDF').inputs['Base Color'])
bpy.data.objects['wood door leaf'].data.materials.append(m)
bpy.ops.wm.save_as_mainfile(filepath='/capture/material_state_probe.blend')
sys.argv=['inspect_scene.py','--','--input','/capture/material_state_probe.blend','--output','/capture/material_state_probe.json']
runpy.run_path('/analysis/inspect_scene.py',run_name='__main__')
