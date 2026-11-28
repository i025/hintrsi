"""Posthoc viewpoint evidence; never fed to the student or saved over its scene."""
import math
from pathlib import Path
import json

import bpy
from mathutils import Matrix, Vector

scene = bpy.context.scene
camera = scene.camera
original_location = camera.location.copy()
original_rotation = camera.rotation_euler.to_matrix()
points = [obj.matrix_world @ Vector(corner) for obj in scene.objects
          if obj.type == 'MESH' and not obj.hide_render for corner in obj.bound_box]
low = Vector(tuple(min(point[axis] for point in points) for axis in range(3)))
high = Vector(tuple(max(point[axis] for point in points) for axis in range(3)))
center = (low + high) / 2
forward = original_rotation @ Vector((0, 0, -1))
distance = max((center - original_location).dot(forward), (high - low).length / 4)
target = original_location + forward * distance
scene.render.resolution_x = 320
scene.render.resolution_y = 180
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.cycles.device = 'CPU'
scene.cycles.samples = min(scene.cycles.samples, 16)
results = []
for angle in (-15, 15):
    rotation = Matrix.Rotation(math.radians(angle), 3, 'Z')
    camera.location = target + rotation @ (original_location - target)
    camera.rotation_euler = (rotation @ original_rotation).to_euler()
    scene.render.filepath = '/capture/view_' + str(angle) + '.png'
    bpy.ops.render.render(write_still=True)
    results.append({'yaw_degrees': angle, 'camera_location': list(camera.location),
                    'rotation_euler': list(camera.rotation_euler), 'render': scene.render.filepath})
Path('/capture/extra_views.json').write_text(json.dumps({'purpose': 'Posthoc depth evidence, not student output or GT-aligned error',
                                                       'original_location': list(original_location), 'views': results}, indent=2))
