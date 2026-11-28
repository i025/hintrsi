"""Posthoc common-world render; no scene, material, or camera repair."""
import argparse
import json
from pathlib import Path
import sys

import bpy


def value(item):
    if isinstance(item, (str, int, float, bool)) or item is None:
        return item
    if hasattr(item, '__iter__'):
        return [value(part) for part in item]
    return str(item)


parser = argparse.ArgumentParser()
parser.add_argument('--input', required=True)
parser.add_argument('--output', required=True)
parser.add_argument('--settings', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
bpy.ops.wm.open_mainfile(filepath=args.input, load_ui=False, use_scripts=False)
scene = bpy.context.scene
camera = scene.camera
camera_state = {'name': camera.name, 'matrix_world': [list(row) for row in camera.matrix_world],
                'data': {key: value(getattr(camera.data, key)) for key in
                         ('type', 'lens', 'sensor_width', 'sensor_height', 'sensor_fit',
                          'ortho_scale', 'shift_x', 'shift_y', 'clip_start', 'clip_end')}} if camera else None
render_changes = {'engine': 'CYCLES', 'resolution_x': 640, 'resolution_y': 360,
                  'resolution_percentage': 100, 'pixel_aspect_x': 1.0, 'pixel_aspect_y': 1.0,
                  'film_transparent': False, 'use_border': False,
                  'use_compositing': False, 'use_sequencer': False}
cycle_changes = {'device': 'CPU', 'samples': 16, 'use_adaptive_sampling': False,
                 'use_denoising': False, 'seed': 0, 'use_animated_seed': False,
                 'max_bounces': 12, 'diffuse_bounces': 4, 'glossy_bounces': 4,
                 'transmission_bounces': 12, 'transparent_max_bounces': 8, 'volume_bounces': 0}
view_changes = {'view_transform': 'AgX', 'look': 'None', 'exposure': 0.0, 'gamma': 1.0}
original = {'render': {key: value(getattr(scene.render, key)) for key in render_changes},
            'cycles': {key: value(getattr(scene.cycles, key)) for key in cycle_changes},
            'view_settings': {key: value(getattr(scene.view_settings, key)) for key in view_changes},
            'display_device': scene.display_settings.display_device,
            'render_filepath': scene.render.filepath,
            'image_settings': {key: value(getattr(scene.render.image_settings, key)) for key in
                               ('file_format', 'color_mode', 'color_depth')},
            'world': {'name': scene.world.name, 'color': list(scene.world.color),
                      'use_nodes': scene.world.use_nodes,
                      'nodes': [{'name': node.name, 'type': node.bl_idname,
                                 'inputs': [{'name': socket.name, 'linked': socket.is_linked,
                                             'default': value(socket.default_value) if hasattr(socket, 'default_value') else None}
                                            for socket in node.inputs]}
                                for node in scene.world.node_tree.nodes] if scene.world.use_nodes else [],
                      'links': [{'from_node': link.from_node.name, 'from_socket': link.from_socket.name,
                                 'to_node': link.to_node.name, 'to_socket': link.to_socket.name}
                                for link in scene.world.node_tree.links] if scene.world.use_nodes else []}
                     if scene.world else None}
lights = [{'name': obj.name, 'hide_render': obj.hide_render, 'data': obj.data.name,
           'type': obj.data.type, 'energy': obj.data.energy, 'color': list(obj.data.color)}
          for obj in bpy.data.objects if obj.type == 'LIGHT']
for obj in bpy.data.objects:
    if obj.type == 'LIGHT':
        obj.hide_render = True
world = bpy.data.worlds.new('EvaluationCommonWhiteWorld')
world.use_nodes = True
world.node_tree.nodes.clear()
background = world.node_tree.nodes.new('ShaderNodeBackground')
background.inputs['Color'].default_value = (1, 1, 1, 1)
background.inputs['Strength'].default_value = 1
terminal = world.node_tree.nodes.new('ShaderNodeOutputWorld')
world.node_tree.links.new(background.outputs['Background'], terminal.inputs['Surface'])
scene.world = world
for key, item in render_changes.items():
    setattr(scene.render, key, item)
for key, item in cycle_changes.items():
    setattr(scene.cycles, key, item)
for key, item in view_changes.items():
    setattr(scene.view_settings, key, item)
scene.display_settings.display_device = 'sRGB'
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.image_settings.color_depth = '8'
scene.render.filepath = args.output
emission_nodes = []
trees = [('material', material.name, material.node_tree) for material in bpy.data.materials if material.use_nodes]
trees += [('node_group', group.name, group) for group in bpy.data.node_groups]
for source_type, name, tree in trees:
    for node in tree.nodes:
        sockets = [socket for socket in node.inputs if 'Emission' in socket.name]
        if node.type == 'EMISSION' or sockets:
            emission_nodes.append({'source_type': source_type, 'source': name,
                                   'node': node.name, 'type': node.bl_idname,
                                   'potentially_unused': True,
                                   'sockets': [{'name': socket.name, 'linked': socket.is_linked,
                                                'default': value(socket.default_value) if hasattr(socket, 'default_value') else None}
                                               for socket in (node.inputs if node.type == 'EMISSION' else sockets)]})
settings = {'input': args.input, 'output': args.output,
            'evaluation_only': True, 'model_calls': 0, 'original_settings': original,
            'mutations': {'render': render_changes, 'cycles': cycle_changes, 'view_settings': view_changes,
                          'display_device': 'sRGB', 'image_settings': {'file_format': 'PNG', 'color_mode': 'RGBA', 'color_depth': '8'},
                          'render_filepath': args.output,
                          'existing_light_objects_hidden': lights,
                          'world': {'name': world.name, 'shader': 'Background', 'color': [1, 1, 1, 1], 'strength': 1}},
            'retained': {'object_count': len(scene.objects), 'material_count': len(bpy.data.materials),
                         'camera': camera_state, 'geometry_and_materials': 'Unmodified actual scene data.',
                         'emission_related_nodes_including_unlinked': emission_nodes},
            'limits': ['This auxiliary view does not fully isolate material quality.',
                       'Original geometry, occlusion, surface normals, UVs, textures, camera viewpoint and optical settings remain confounded.',
                       'Material emission, including linked or unused emission nodes, is retained; this list does not prove active emission.',
                       'Closed rooms or missing windows can receive little uniform-world illumination.',
                       'Compositor, sequencer, original environment and light objects are replaced or disabled; these are evaluation mutations.',
                       'Finite 16-sample renders retain sampling noise and may not resolve all indirect transport.',
                       'The image is evaluator-produced evidence, not student action or reconstruction improvement.'],
            'scene_saved_or_modified_on_disk': False}
Path(args.settings).parent.mkdir(parents=True, exist_ok=True)
Path(args.settings).write_text(json.dumps(settings, indent=2))
if camera:
    bpy.ops.render.render(write_still=True)
else:
    raise RuntimeError('No actual active scene camera; common-light image cannot be rendered.')
