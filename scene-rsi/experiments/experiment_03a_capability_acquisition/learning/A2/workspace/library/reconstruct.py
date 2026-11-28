"""Parameterized Blender reconstruction diagnostics; no scene-specific assets."""
import math
import bpy
from mathutils import Vector, Matrix
from bpy_extras.object_utils import world_to_camera_view


def project_points(scene, camera, points):
    """Return normalized image coordinates (origin bottom left) and camera depth."""
    return [tuple(world_to_camera_view(scene, camera, Vector(p))) for p in points]


def landmark_errors(scene, camera, landmarks):
    """landmarks: iterable of (name, world_xyz, target_xy, weight)."""
    result = []
    for name, xyz, target, weight in landmarks:
        p = project_points(scene, camera, [xyz])[0]
        error = math.hypot(p[0] - target[0], p[1] - target[1])
        result.append(dict(name=name, projected=p, target=tuple(target), error=error,
                           weighted_error=weight * error, behind=p[2] <= 0))
    return result


def point_camera(camera, location, target, lens=None):
    """Explicit trial: move camera, aim -Z, optionally set lens in mm."""
    camera.location = location
    direction = Vector(target) - Vector(location)
    if direction.length < 1e-8:
        raise ValueError('camera and target coincide')
    camera.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    if lens is not None:
        camera.data.lens = lens
    bpy.context.view_layer.update()


def hinge_pose(hinge, child, hinge_world, closed_vector, angle):
    """Set unparented hinge and parent a leaf whose local geometry is already authored relative to its hinge.

    closed_vector is the world XY direction of the leaf in the closed state;
    angle is in radians. Caller must author child local offset and dimensions.
    This intentionally changes parenting and transforms; duplicate first.
    """
    v = Vector(closed_vector)
    if v.xy.length < 1e-8:
        raise ValueError('closed direction has no horizontal component')
    hinge.location = hinge_world
    hinge.rotation_euler = (0, 0, math.atan2(v.y, v.x) + angle)
    child.parent = hinge
    child.matrix_parent_inverse = Matrix.Identity(4)
    bpy.context.view_layer.update()


def hinge_report(hinge_world, leaf_hinge_world, opening_edge_world, tolerance):
    """Return two independent distances; does not establish actual connectivity."""
    a, b, c = map(Vector, (hinge_world, leaf_hinge_world, opening_edge_world))
    return {'leaf_to_hinge': (a-b).length, 'hinge_to_jamb': (a-c).length,
            'within_tolerance': (a-b).length <= tolerance and (a-c).length <= tolerance}


def support_probe(obj, support_objects, tolerance=0.002, samples=16, reach=1.0):
    """Ray sample beneath evaluated lowest vertices. Returns evidence, not physical contact.

    Uses only explicitly supplied support meshes. Signed gaps can be negative if a
    surface is found between a lowest point and the ray origin. Supports are
    sampled at lowest vertices, not across the full footprint.
    """
    if tolerance <= 0 or samples < 1 or reach <= 0:
        raise ValueError('positive tolerance, sample count and reach required')
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    mesh = ev.to_mesh()
    try:
        vertices = [ev.matrix_world @ v.co for v in mesh.vertices]
    finally:
        ev.to_mesh_clear()
    if not vertices:
        return {'status':'unknown support', 'samples':[]}
    zmin = min(v.z for v in vertices)
    lowest = [v for v in vertices if v.z <= zmin + tolerance]
    stride = max(1, math.ceil(len(lowest)/samples))
    rows = []
    for p in lowest[::stride][:samples]:
        origin = p + Vector((0,0,reach))
        best = None
        for support in support_objects:
            if support == obj or support.type != 'MESH':
                continue
            se = support.evaluated_get(dg)
            inv = se.matrix_world.inverted_safe()
            direction = inv.to_3x3() @ Vector((0,0,-1))
            if direction.length < 1e-12:
                continue
            ok, loc, normal, face = se.ray_cast(inv @ origin, direction.normalized(), distance=reach*10000)
            if ok:
                hit = se.matrix_world @ loc
                gap = p.z - hit.z
                if -reach <= gap <= reach and (best is None or hit.z > best[1]):
                    best = (support.name, hit.z, gap)
        if best is None:
            rows.append({'point':tuple(p), 'status':'unknown support'})
        else:
            gap=best[2]
            status = 'positive gap' if gap > tolerance else ('possible penetration' if gap < -tolerance else 'near-zero')
            rows.append({'point':tuple(p), 'support':best[0], 'gap':gap, 'status':status})
    states = {r['status'] for r in rows}
    return {'status': next(iter(states)) if len(states)==1 else 'mixed', 'samples':rows}


def aabb_relation(a, b):
    """World evaluated AABB separation; overlap is only a broad-phase candidate."""
    dg = bpy.context.evaluated_depsgraph_get()
    def bounds(o):
        e=o.evaluated_get(dg); m=e.to_mesh()
        try: pts=[e.matrix_world @ v.co for v in m.vertices]
        finally: e.to_mesh_clear()
        if not pts: raise ValueError('empty mesh')
        return [(min(p[i] for p in pts),max(p[i] for p in pts)) for i in range(3)]
    aa,bb=bounds(a),bounds(b)
    sep=[max(bb[i][0]-aa[i][1],aa[i][0]-bb[i][1],0) for i in range(3)]
    return {'axis_separations':sep,'aabb_distance':math.sqrt(sum(x*x for x in sep)),
            'aabb_overlap':not any(sep), 'interpretation':'broad phase only; not contact or connectivity'}


def mapped_stone(name, scale=(3.0,0.5,2.0), low=(0.55,0.55,0.55,1), high=(0.85,0.85,0.85,1), coord_object=None):
    """Create a new editable material. Object coordinates are in the chosen object's local frame.

    Scale controls frequency per axis, not physical vein widths; smaller scale
    elongates along that axis. Caller binds material and compares under fixed lights.
    """
    if len(scale)!=3 or min(scale)<=0: raise ValueError('scale must be positive')
    m=bpy.data.materials.new(name); m.use_nodes=True
    n=m.node_tree.nodes; l=m.node_tree.links
    bs=n.get('Principled BSDF')
    tc=n.new('ShaderNodeTexCoord'); tc.object=coord_object
    vec=n.new('ShaderNodeVectorMath'); vec.operation='MULTIPLY'; vec.inputs[1].default_value=scale
    noise=n.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value=1.0
    ramp=n.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color=low; ramp.color_ramp.elements[1].color=high
    l.new(tc.outputs['Object'],vec.inputs[0]); l.new(vec.outputs['Vector'],noise.inputs['Vector']); l.new(noise.outputs['Fac'],ramp.inputs[0]); l.new(ramp.outputs[0],bs.inputs['Base Color'])
    return m
