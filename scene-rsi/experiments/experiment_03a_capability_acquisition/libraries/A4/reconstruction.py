"""Editable scene reconstruction helpers; run inside Blender."""
import math
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view


def project_points(scene, camera, points):
    """World points -> image-normalized (x,y top-down, depth); depth <= 0 is behind camera."""
    result = []
    for p in points:
        q = world_to_camera_view(scene, camera, Vector(p))
        result.append((q.x, 1-q.y, q.z))
    return result


def landmark_error(scene, camera, landmarks):
    """Iterable of (world point, normalized image point, weight); returns weighted RMS."""
    acc = total = 0.0
    for point, target, weight in landmarks:
        if weight < 0:
            raise ValueError('negative weight')
        x, y, depth = project_points(scene, camera, [point])[0]
        if depth <= 0:
            raise ValueError('landmark behind camera')
        acc += weight*((x-target[0])**2+(y-target[1])**2)
        total += weight
    if total == 0:
        raise ValueError('no positive weights')
    return math.sqrt(acc/total)


def aim_camera(camera, location, target, lens=None):
    """Set camera pose with local -Z toward target and local Y approximately up."""
    camera.location = Vector(location)
    direction = Vector(target)-camera.location
    if direction.length < 1e-8:
        raise ValueError('camera and target coincide')
    camera.rotation_euler = direction.to_track_quat('-Z','Y').to_euler()
    if lens is not None:
        if lens <= 0: raise ValueError('lens must be positive')
        camera.data.lens = lens
    bpy.context.view_layer.update()


def hinge_pose(door, hinge_world, angle_radians, local_hinge):
    """Rotate a door about a world vertical hinge; local_hinge is a point in door local space.

    Keeps current scale and tilt; angle is an incremental world-Z rotation. Does not cut a wall.
    """
    from mathutils import Matrix
    H = Vector(hinge_world)
    before = door.matrix_world @ Vector(local_hinge)
    if (before-H).length > 1e-4:
        raise ValueError('local hinge is not at specified world hinge')
    door.matrix_world = Matrix.Translation(H) @ Matrix.Rotation(angle_radians, 4, 'Z') @ Matrix.Translation(-H) @ door.matrix_world
    bpy.context.view_layer.update()


def make_directional_material(name, color_a, color_b, axis_scale=(1, 8, 8), noise_scale=4.0, roughness=0.7):
    """Create editable object-coordinate stretched-noise material; color inputs are linear RGBA.

    Object coordinates are in object-local units. Apply scales or tune mapping per object.
    """
    if noise_scale <= 0 or any(v <= 0 for v in axis_scale):
        raise ValueError('scales must be positive')
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    nt = mat.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bs = nt.nodes.new('ShaderNodeBsdfPrincipled'); bs.inputs['Roughness'].default_value = roughness
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mapping = nt.nodes.new('ShaderNodeMapping'); mapping.inputs['Scale'].default_value = axis_scale
    noise = nt.nodes.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = noise_scale
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = color_a; ramp.color_ramp.elements[1].color = color_b
    for a, ao, b, bi in [(tc,'Object',mapping,'Vector'),(mapping,'Vector',noise,'Vector'),(noise,'Fac',ramp,'Fac'),(ramp,'Color',bs,'Base Color'),(bs,'BSDF',out,'Surface')]:
        nt.links.new(a.outputs[ao], b.inputs[bi])
    return mat


def support_bounds(upper, lower, tolerance=0.01):
    """Conservative world-AABB screening only, not a physical contact test.

    Returns vertical separation and status. Requires actual mesh objects; evaluated bounds
    include modifiers. Horizontal bounds must overlap; tilted and hollow shapes are uncertain.
    """
    if tolerance < 0: raise ValueError('negative tolerance')
    if upper.type != 'MESH' or lower.type != 'MESH': return {'status':'unknown support','gap':None}
    deps = bpy.context.evaluated_depsgraph_get()
    def bounds(o):
        o = o.evaluated_get(deps)
        if len(o.data.vertices) == 0: return None
        p = [o.matrix_world @ Vector(c) for c in o.bound_box]
        return [(min(v[i] for v in p), max(v[i] for v in p)) for i in range(3)]
    a,b = bounds(upper),bounds(lower)
    if a is None or b is None: return {'status':'unknown support','gap':None}
    if any(min(a[i][1],b[i][1]) <= max(a[i][0],b[i][0]) for i in (0,1)):
        return {'status':'unknown support','gap':None}
    gap = a[2][0]-b[2][1]
    status = 'positive gap' if gap > tolerance else 'possible penetration' if gap < -tolerance else 'near-zero'
    return {'status':status,'gap':gap,'warning':'AABB only; does not establish contact or support'}


def assembly_components(objects):
    """Connected components of parent relationships within supplied objects; not physical support."""
    objects = list(objects); members = set(objects); adj = {o:set() for o in objects}
    for o in objects:
        if o.parent in members:
            adj[o].add(o.parent); adj[o.parent].add(o)
    components=[]; unseen=set(objects)
    while unseen:
        stack=[unseen.pop()]; comp=[]
        while stack:
            o=stack.pop(); comp.append(o.name)
            for p in adj[o] & unseen:
                unseen.remove(p); stack.append(p)
        components.append(sorted(comp))
    return sorted(components)
