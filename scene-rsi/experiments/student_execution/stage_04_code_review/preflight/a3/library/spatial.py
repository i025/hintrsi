"""Parameterized camera projection and vertical-hinge candidate helpers for Blender."""
import math
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view


def project_points(scene, camera, points):
    """Return dictionaries of normalized image coordinates and signed camera depth."""
    inv = camera.matrix_world.inverted()
    out = []
    for p in points:
        p = Vector(p)
        uv = world_to_camera_view(scene, camera, p)
        out.append({'x': uv.x, 'y': uv.y, 'depth': -(inv @ p).z,
                    'inside_frame': 0 <= uv.x <= 1 and 0 <= uv.y <= 1 and uv.z > 0})
    return out


def hinge_positions(hinge, width, angles, local_direction=(1, 0)):
    """Free edge positions for angles in radians, hinge world XYZ, direction XY."""
    if width <= 0:
        raise ValueError('width must be positive')
    x, y = local_direction
    n = math.hypot(x, y)
    if not n:
        raise ValueError('local direction must be nonzero')
    x, y = x/n, y/n
    return [(hinge[0] + width*(x*math.cos(a)-y*math.sin(a)),
             hinge[1] + width*(x*math.sin(a)+y*math.cos(a)), hinge[2]) for a in angles]
