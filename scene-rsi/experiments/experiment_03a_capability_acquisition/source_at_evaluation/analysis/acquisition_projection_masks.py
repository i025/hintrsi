"""Render opaque semantic unions from an unchanged scene's evaluated geometry."""
import argparse
import json
from pathlib import Path
import sys

import bpy


parser = argparse.ArgumentParser()
parser.add_argument('--input', required=True)
parser.add_argument('--mappings', required=True)
parser.add_argument('--output', required=True)
parser.add_argument('--samples', type=int, default=4)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
output = Path(args.output)
output.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=args.input, load_ui=False, use_scripts=False)
scene = bpy.context.scene
camera = scene.camera
mappings = json.loads(Path(args.mappings).read_text())
original_objects = list(scene.objects)
original_settings = {'camera': camera.name if camera else None,
                     'resolution': [scene.render.resolution_x, scene.render.resolution_y],
                     'percentage': scene.render.resolution_percentage,
                     'pixel_aspect': [scene.render.pixel_aspect_x, scene.render.pixel_aspect_y],
                     'render_border': scene.render.use_border,
                     'film_transparent': scene.render.film_transparent}
by_name = {obj.name: obj for obj in original_objects}
resolved = []
for mapping in mappings:
    roots = [by_name.get(name) for name in mapping['student_object_names']]
    missing = [name for name, obj in zip(mapping['student_object_names'], roots) if obj is None]
    members = set()
    for root in roots:
        if root:
            members.add(root.name)
            members.update(child.name for child in root.children_recursive)
    resolved.append({**mapping, 'resolved_original_names': sorted(members),
                     'missing_student_names': missing})


def emission(name, color):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.node_tree.nodes.clear()
    shader = material.node_tree.nodes.new('ShaderNodeEmission')
    shader.inputs['Color'].default_value = (*color, 1)
    shader.inputs['Strength'].default_value = 1
    terminal = material.node_tree.nodes.new('ShaderNodeOutputMaterial')
    material.node_tree.links.new(shader.outputs['Emission'], terminal.inputs['Surface'])
    return material


black, white = emission('EvaluationBlack', (0, 0, 0)), emission('EvaluationWhite', (1, 1, 1))
renderable = {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}
for obj in original_objects:
    for modifier in obj.modifiers:
        modifier.show_viewport = modifier.show_render
        if modifier.type == 'SUBSURF':
            modifier.levels = modifier.render_levels
depsgraph = bpy.context.evaluated_depsgraph_get()
proxies = []
unsupported = []
instances = [{'object': item.object, 'original': item.object.original,
              'matrix_world': item.matrix_world.copy(),
              'instance_parent': item.parent.original.name if item.is_instance and item.parent else None}
             for item in depsgraph.object_instances]
for instance in instances:
    obj = instance['object']
    original = instance['original']
    if original.hide_render:
        continue
    if obj.type not in renderable:
        if obj.type not in {'EMPTY', 'LIGHT', 'CAMERA'}:
            unsupported.append({'object': original.name, 'type': obj.type})
        continue
    mesh = bpy.data.meshes.new_from_object(obj, preserve_all_data_layers=True, depsgraph=depsgraph)
    if not mesh:
        unsupported.append({'object': original.name, 'type': obj.type})
        continue
    mesh.materials.clear()
    mesh.materials.append(black)
    for face in mesh.polygons:
        face.material_index = 0
    proxy = bpy.data.objects.new('EvaluationProxy_' + str(len(proxies)), mesh)
    proxy.matrix_world = instance['matrix_world']
    parent = instance['instance_parent']
    proxies.append({'proxy': proxy, 'original_name': original.name, 'instance_parent': parent})
for obj in original_objects:
    if obj != camera:
        obj.hide_render = True
for row in proxies:
    scene.collection.objects.link(row['proxy'])
world = bpy.data.worlds.new('EvaluationWorld')
world.use_nodes = True
world.node_tree.nodes.get('Background').inputs['Color'].default_value = (0, 0, 0, 1)
world.node_tree.nodes.get('Background').inputs['Strength'].default_value = 0
scene.world = world
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = args.samples
scene.cycles.use_denoising = False
scene.cycles.seed = 0
scene.cycles.max_bounces = 1
scene.render.resolution_x = 640
scene.render.resolution_y = 360
scene.render.resolution_percentage = 100
scene.render.use_border = False
scene.render.film_transparent = False
scene.render.use_compositing = False
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'None'
scene.view_settings.exposure = 0
scene.view_settings.gamma = 1
results = []
for mapping in resolved:
    names = set(mapping['resolved_original_names'])
    selected = [row for row in proxies if row['original_name'] in names or row['instance_parent'] in names]
    row = {**mapping, 'selected_proxy_count': len(selected),
           'selected_evaluated_sources': [{'object': item['original_name'], 'instance_parent': item['instance_parent']}
                                         for item in selected]}
    if mapping['missing_student_names'] or not selected or not camera:
        row.update({'status': 'unknown', 'reason': 'Missing exact object name, no resolved renderable geometry, or no active camera.'})
        results.append(row)
        continue
    selected_names = {item['proxy'].name for item in selected}
    for item in proxies:
        item['proxy'].data.materials[0] = white if item['proxy'].name in selected_names else black
    target = output / ('mapping_' + str(mapping['mapping_index']).zfill(3) + '.png')
    scene.render.filepath = str(target)
    bpy.ops.render.render(write_still=True)
    row.update({'status': 'rendered', 'mask': str(target)})
    results.append(row)
record = {'input': args.input, 'original_settings': original_settings,
          'resolution': [640, 360], 'engine': 'CYCLES', 'device': 'CPU',
          'samples': args.samples, 'proxy_count': len(proxies), 'unsupported_geometry': unsupported,
          'mappings': results, 'original_scene_saved_or_modified_on_disk': False,
          'approximation': ['Opaque evaluated geometry proxies preserve original object transforms and active camera.',
                            'All selected geometry uses white emission; other geometry uses black emission.',
                            'Glass, alpha blending, transmission, hair, volumes and shader displacement are not appearance-faithful masks.',
                            'Opaque non-target geometry can hide a target that was visible through glass in the RGB.',
                            str(args.samples) + ' primary-path samples and a later 0.5 threshold approximate antialiasing boundaries.',
                            'Viewport evaluated geometry is used after matching modifier visibility and subdivision render levels.',
                            'Original render borders and compositor effects are disabled; their presence is recorded.',
                            'No GT image, mask, scene, camera or transform is available to this rendering process.']}
(output / 'render_record.json').write_text(json.dumps(record, indent=2))
