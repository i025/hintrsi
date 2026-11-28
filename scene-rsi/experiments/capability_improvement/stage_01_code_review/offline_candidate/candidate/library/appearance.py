"""Small editable directional material hypothesis; no scene-specific assets."""
import bpy


def directional_stone(name, scale=(3.0, 0.7, 1.0),
                      colors=((0.6, 0.61, 0.6, 1), (0.9, 0.9, 0.89, 1)),
                      roughness=0.45, distortion=0.3):
    if len(scale) != 3 or len(colors) != 2:
        raise ValueError('scale needs three components and colors two RGBA values')
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get('Principled BSDF')
    bsdf.inputs['Roughness'].default_value = roughness
    coord = nodes.new('ShaderNodeTexCoord')
    multiply = nodes.new('ShaderNodeVectorMath')
    multiply.operation = 'MULTIPLY'
    multiply.inputs[1].default_value = scale
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Distortion'].default_value = distortion
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = colors[0]
    ramp.color_ramp.elements[1].color = colors[1]
    links.new(coord.outputs['Object'], multiply.inputs[0])
    links.new(multiply.outputs['Vector'], noise.inputs['Vector'])
    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    return mat
