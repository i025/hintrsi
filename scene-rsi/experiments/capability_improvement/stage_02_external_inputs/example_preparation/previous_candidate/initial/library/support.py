"""Sampled world-vertical support diagnostics, not a contact solver."""
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def _vertices(obj, dg):
    ev = obj.evaluated_get(dg)
    mesh = ev.to_mesh()
    try:
        return [ev.matrix_world @ v.co for v in mesh.vertices]
    finally:
        ev.to_mesh_clear()


def world_bounds(obj):
    """Return world-space minimum and maximum evaluated vertex coordinates."""
    vertices = _vertices(obj, bpy.context.evaluated_depsgraph_get())
    if not vertices:
        return None
    return (tuple(min(v[i] for v in vertices) for i in range(3)),
            tuple(max(v[i] for v in vertices) for i in range(3)))


def sample_support(obj, supports, tolerance=0.001, band=0.001, ray_margin=10.0):
    """Return sampled gaps and classification; unknown for any missing support ray."""
    if tolerance < 0 or band < 0 or ray_margin <= 0:
        raise ValueError('nonnegative tolerance/band and positive margin required')
    dg = bpy.context.evaluated_depsgraph_get()
    vertices = _vertices(obj, dg)
    if not vertices or not supports:
        return {'category': 'unknown support', 'gaps': [], 'misses': 0}
    low = min(v.z for v in vertices)
    samples = [v for v in vertices if v.z <= low + band]
    trees = []
    for support in supports:
        ev = support.evaluated_get(dg)
        mesh = ev.to_mesh()
        try:
            vs = [ev.matrix_world @ v.co for v in mesh.vertices]
            faces = [tuple(p.vertices) for p in mesh.polygons]
            if vs and faces:
                trees.append(BVHTree.FromPolygons(vs, faces, all_triangles=False))
        finally:
            ev.to_mesh_clear()
    gaps, misses = [], 0
    for v in samples:
        origin = Vector((v.x, v.y, v.z + ray_margin))
        hits = [tree.ray_cast(origin, Vector((0, 0, -1)), 2*ray_margin)[0] for tree in trees]
        hits = [p for p in hits if p is not None]
        if hits:
            gaps.append(v.z - max(p.z for p in hits))
        else:
            misses += 1
    if misses or not gaps:
        category = 'unknown support'
    elif min(gaps) < -tolerance:
        category = 'possible penetration'
    elif min(gaps) > tolerance:
        category = 'positive gap'
    else:
        category = 'near-zero sample'
    return {'category': category, 'gaps': gaps, 'misses': misses, 'samples': len(samples)}
