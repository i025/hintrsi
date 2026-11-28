"""Reusable Blender reconstruction diagnostics; import inside Blender."""
import math
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view


def projected_landmarks(scene, camera, points):
    """World xyz -> normalized image xy (origin bottom left), depth, in-frame flag."""
    result = {}
    for name, xyz in points.items():
        p = world_to_camera_view(scene, camera, Vector(xyz))
        result[name] = {'xy': (p.x, p.y), 'depth': p.z,
                        'in_frame': p.z > 0 and 0 <= p.x <= 1 and 0 <= p.y <= 1}
    return result


def landmark_loss(scene, camera, points, targets):
    """Weighted squared normalized image-coordinate residual; does not test visibility."""
    projected = projected_landmarks(scene, camera, points)
    total = weight = 0.0
    for name, target in targets.items():
        if name not in projected or projected[name]['depth'] <= 0:
            raise ValueError('missing or behind-camera landmark: ' + name)
        x, y, w = target
        if w < 0:
            raise ValueError('weight must be nonnegative')
        px, py = projected[name]['xy']
        total += w * ((px-x)**2 + (py-y)**2)
        weight += w
    if not weight:
        raise ValueError('positive total weight required')
    return total / weight


def world_bounds(obj, depsgraph=None):
    """World AABB of evaluated mesh vertices; raises on empty/non-mesh."""
    dg = depsgraph or bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(dg)
    if evaluated.type != 'MESH':
        raise ValueError('mesh object required')
    mesh = evaluated.to_mesh()
    try:
        if not mesh.vertices:
            raise ValueError('empty mesh')
        vertices = [evaluated.matrix_world @ v.co for v in mesh.vertices]
        return tuple(min(v[i] for v in vertices) for i in range(3)), tuple(max(v[i] for v in vertices) for i in range(3))
    finally:
        evaluated.to_mesh_clear()


def support_diagnostic(child, support, tolerance=0.01):
    """Conservative world-axis AABB vertical gap diagnostic, not contact proof."""
    if tolerance < 0:
        raise ValueError('nonnegative tolerance required')
    try:
        a, b = world_bounds(child), world_bounds(support)
    except (ValueError, RuntimeError):
        return {'classification': 'unknown support', 'gap': None}
    overlaps = [min(a[1][i], b[1][i]) - max(a[0][i], b[0][i]) for i in (0, 1)]
    gap = a[0][2] - b[1][2]
    if min(overlaps) <= 0:
        classification = 'unknown support'
    elif gap > tolerance:
        classification = 'positive gap'
    elif gap < -tolerance:
        classification = 'possible penetration'
    else:
        classification = 'near-zero'
    return {'classification': classification, 'gap': gap, 'xy_aabb_overlap': overlaps}


def assembly_links(objects):
    """Return explicit in-set parenting and object constraints; not mesh connectivity."""
    objects = list(objects)
    members = set(objects)
    links = []
    for obj in objects:
        if obj.parent in members:
            links.append((obj.name, obj.parent.name, 'parent'))
        for c in obj.constraints:
            target = getattr(c, 'target', None)
            if target in members:
                links.append((obj.name, target.name, 'constraint:' + c.type))
    return links


def make_directional_material(name, color_a, color_b, scale=(1, 1, 1), roughness=0.6):
    """Create editable object-coordinate noise material; scale controls axis frequencies."""
    if len(scale) != 3 or any(s <= 0 for s in scale):
        raise ValueError('three positive scale values required')
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    links = mat.node_tree.links
    tex = nodes.new('ShaderNodeTexCoord')
    mapping = nodes.new('ShaderNodeVectorMath')
    mapping.operation = 'MULTIPLY'
    mapping.inputs[1].default_value = scale
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 1.0
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = color_a
    ramp.color_ramp.elements[1].color = color_b
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = roughness
    out = nodes.new('ShaderNodeOutputMaterial')
    links.new(tex.outputs['Object'], mapping.inputs[0])
    links.new(mapping.outputs[0], noise.inputs['Vector'])
    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat
