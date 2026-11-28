"""Parameterized Blender reconstruction diagnostics; call from Blender Python."""
import math
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

def landmarks(scene, camera, points):
    """Project {label: world xyz}; returns normalized x,y, camera depth and visibility."""
    out = {}
    for name, co in points.items():
        q = world_to_camera_view(scene, camera, Vector(co))
        out[name] = {'x': q.x, 'y': q.y, 'depth': q.z,
                     'in_frame': q.z > 0 and 0 <= q.x <= 1 and 0 <= q.y <= 1}
    return out

def landmark_error(projected, targets):
    """Weighted squared 2-D error, targets {name: (x,y,weight)}; y measured upward."""
    total = 0.0
    for name, (x, y, weight) in targets.items():
        p = projected[name]
        if p['depth'] <= 0:
            return float('inf')
        total += weight * ((p['x']-x)**2 + (p['y']-y)**2)
    return total

def hinge_pose(pivot, hinge_world, angle_radians):
    """Position an unparented pivot; its parented leaf must be modeled about local origin."""
    if pivot.parent:
        raise ValueError('pivot must be unparented')
    pivot.location = hinge_world
    pivot.rotation_mode = 'XYZ'
    pivot.rotation_euler.z = angle_radians
    bpy.context.view_layer.update()

def hinge_error(pivot, jamb_point):
    """World-space distance of pivot origin to specified jamb anchor."""
    bpy.context.view_layer.update()
    return (pivot.matrix_world.translation - Vector(jamb_point)).length

def support_samples(obj, support, tolerance=0.002, max_distance=10.0, sample_limit=2000):
    """World vertical downward ray sample from evaluated vertices to evaluated support.

    Returns sample distribution and states, not proof of contact. Assumes support surface
    is below points; misses and penetration yield unknown. No automatic scene changes.
    """
    if tolerance <= 0 or max_distance <= 0 or sample_limit < 1:
        raise ValueError('positive tolerances and sample_limit required')
    dg = bpy.context.evaluated_depsgraph_get()
    a = obj.evaluated_get(dg); b = support.evaluated_get(dg)
    mesh = a.to_mesh()
    try:
        verts = [a.matrix_world @ v.co for v in mesh.vertices]
    finally:
        a.to_mesh_clear()
    if not verts:
        return {'state': 'unknown support', 'samples': 0}
    low = min(v.z for v in verts)
    bottom = [v for v in verts if v.z <= low + tolerance]
    step = max(1, math.ceil(len(bottom)/sample_limit))
    inv = b.matrix_world.inverted()
    direction = inv.to_3x3() @ Vector((0, 0, -1))
    gaps = []; misses = 0
    for v in bottom[::step]:
        # Start above vertex to detect shallow penetration without requiring a signed SDF.
        origin = v + Vector((0, 0, tolerance * 2))
        hit, loc, normal, face = b.ray_cast(inv @ origin, direction.normalized(), distance=max_distance * direction.length)
        if hit:
            world = b.matrix_world @ loc
            gap = v.z - world.z
            if gap <= max_distance: gaps.append(gap)
            else: misses += 1
        else: misses += 1
    if not gaps: state = 'unknown support'
    elif min(gaps) < -tolerance: state = 'possible penetration'
    elif misses: state = 'unknown support'
    elif min(gaps) > tolerance: state = 'positive gap'
    else: state = 'near-zero'
    return {'state': state, 'minimum_gap': min(gaps) if gaps else None,
            'maximum_gap': max(gaps) if gaps else None, 'samples': len(gaps),
            'misses': misses, 'tolerance': tolerance}

def world_bounds(obj):
    """Evaluated world AABB; broad-phase only, not connectivity/contact."""
    o = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    m = o.to_mesh()
    try:
        v = [o.matrix_world @ x.co for x in m.vertices]
    finally:
        o.to_mesh_clear()
    if not v: return None
    return [[min(x[i] for x in v), max(x[i] for x in v)] for i in range(3)]

def bounds_separation(a, b):
    """AABB Euclidean separation; zero means only that boxes overlap."""
    a, b = world_bounds(a), world_bounds(b)
    if a is None or b is None: return None
    return math.sqrt(sum(max(a[i][0]-b[i][1], b[i][0]-a[i][1], 0)**2 for i in range(3)))

def directional_material(name, scale=(1.0, 5.0, 1.0), colors=((0.65,0.65,0.65,1),(0.85,0.85,0.85,1)), roughness=0.55, coordinate='Generated'):
    """Create editable mapped procedural color. scale controls inverse feature size."""
    if coordinate not in ('Generated', 'Object', 'UV'):
        raise ValueError('coordinate must be Generated, Object or UV')
    m = bpy.data.materials.new(name); m.use_nodes = True
    n = m.node_tree.nodes; links = m.node_tree.links
    bs = n.get('Principled BSDF'); bs.inputs['Roughness'].default_value = roughness
    tex = n.new('ShaderNodeTexCoord'); mapping = n.new('ShaderNodeMapping')
    mapping.inputs['Scale'].default_value = scale
    noise = n.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 3
    ramp = n.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = colors[0]; ramp.color_ramp.elements[1].color = colors[1]
    links.new(tex.outputs[coordinate], mapping.inputs['Vector'])
    links.new(mapping.outputs['Vector'], noise.inputs['Vector'])
    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bs.inputs['Base Color'])
    return m
