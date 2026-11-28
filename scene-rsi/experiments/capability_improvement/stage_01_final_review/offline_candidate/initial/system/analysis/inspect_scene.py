"""Extract an existing Blender scene without adding reconstruction instructions."""
import argparse
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def value(item):
    if isinstance(item, (str, int, float, bool)) or item is None:
        return item
    if isinstance(item, (tuple, list, Vector)) or hasattr(item, 'to_list'):
        return [value(x) for x in item]
    return str(item)


parser = argparse.ArgumentParser()
parser.add_argument('--input', required=True)
parser.add_argument('--output', required=True)
parser.add_argument('--render')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
bpy.ops.wm.open_mainfile(filepath=str(Path(args.input).resolve()), load_ui=False, use_scripts=False)
scene = bpy.context.scene
objects = []
for obj in scene.objects:
    row = {'name': obj.name, 'type': obj.type, 'parent': obj.parent.name if obj.parent else None,
           'children': [c.name for c in obj.children], 'location': list(obj.location),
           'world_location': list(obj.matrix_world.translation), 'rotation_euler': list(obj.rotation_euler),
           'rotation_mode': obj.rotation_mode, 'scale': list(obj.scale), 'dimensions': list(obj.dimensions),
           'hide_render': obj.hide_render, 'hide_viewport': obj.hide_viewport,
           'instance_type': obj.instance_type,
           'instance_collection': obj.instance_collection.name if obj.instance_collection else None,
           'materials': [slot.material.name if slot.material else None for slot in obj.material_slots],
           'modifiers': [{'name': m.name, 'type': m.type, 'show_render': m.show_render,
                          'parameters': {key: value(getattr(m, key)) for key in
                                         ('width', 'segments', 'levels', 'render_levels', 'thickness', 'offset')
                                         if hasattr(m, key)}} for m in obj.modifiers]}
    if obj.type == 'MESH':
        row['mesh'] = {'vertices': len(obj.data.vertices), 'edges': len(obj.data.edges),
                       'polygons': len(obj.data.polygons), 'uv_layers': list(obj.data.uv_layers.keys())}
    if obj.type in ('MESH', 'CURVE', 'SURFACE', 'FONT', 'META'):
        row['world_bbox_corners'] = [list(obj.matrix_world @ Vector(c)) for c in obj.bound_box]
    if obj.type == 'CURVE':
        row['curve'] = {'splines': len(obj.data.splines), 'bevel_depth': obj.data.bevel_depth,
                        'bevel_resolution': obj.data.bevel_resolution,
                        'spline_types': [s.type for s in obj.data.splines]}
    if obj.type == 'CAMERA':
        row['camera'] = {key: value(getattr(obj.data, key)) for key in
                         ('type', 'lens', 'sensor_width', 'sensor_height', 'ortho_scale', 'shift_x', 'shift_y', 'clip_start', 'clip_end')}
    if obj.type == 'LIGHT':
        row['light'] = {'type': obj.data.type, 'energy': obj.data.energy, 'color': list(obj.data.color),
                        'parameters': {key: value(getattr(obj.data, key)) for key in
                                       ('size', 'size_y', 'spot_size', 'spot_blend', 'shadow_soft_size')
                                       if hasattr(obj.data, key)}}
    objects.append(row)
materials = []
for material in bpy.data.materials:
    nodes, links = [], []
    if material.use_nodes and material.node_tree:
        for node in material.node_tree.nodes:
            inputs = {socket.name: value(socket.default_value) for socket in node.inputs
                      if hasattr(socket, 'default_value') and not socket.is_linked}
            nodes.append({'name': node.name, 'type': node.bl_idname, 'inputs': inputs,
                          'image': node.image.name if node.type == 'TEX_IMAGE' and node.image else None,
                          'node_group': node.node_tree.name if node.type == 'GROUP' and node.node_tree else None,
                          'properties': {key: value(getattr(node, key)) for key in
                                         ('operation', 'blend_type', 'vector_type', 'noise_dimensions',
                                          'noise_type', 'normalize', 'projection', 'projection_blend',
                                          'interpolation', 'extension', 'distribution') if hasattr(node, key)},
                          'color_ramp': {'interpolation': node.color_ramp.interpolation,
                                         'elements': [{'position': e.position, 'color': list(e.color)}
                                                      for e in node.color_ramp.elements]}
                                        if node.type == 'VALTORGB' else None,
                          'coordinate_object': node.object.name if node.type == 'TEX_COORD' and node.object else None})
        links = [{'from_node': link.from_node.name, 'from_socket': link.from_socket.name,
                  'to_node': link.to_node.name, 'to_socket': link.to_socket.name} for link in material.node_tree.links]
    materials.append({'name': material.name, 'diffuse_color': list(material.diffuse_color),
                      'roughness': material.roughness, 'metallic': material.metallic,
                      'nodes': nodes, 'links': links})
images = []
for image in bpy.data.images:
    absolute = bpy.path.abspath(image.filepath)
    packed = bool(image.packed_file) or bool(image.packed_files)
    images.append({'name': image.name, 'source': image.source, 'filepath': image.filepath,
                   'size': list(image.size), 'packed': packed,
                   'has_data': image.has_data, 'colorspace': image.colorspace_settings.name,
                   'missing_external': image.source in ('FILE', 'TILED') and not packed and not Path(absolute).exists()})
state = {'file': args.input, 'blender_version': bpy.app.version_string,
         'camera': scene.camera.name if scene.camera else None,
         'render': {'engine': scene.render.engine, 'resolution_x': scene.render.resolution_x,
                    'resolution_y': scene.render.resolution_y, 'resolution_percentage': scene.render.resolution_percentage,
                    'view_transform': scene.view_settings.view_transform,
                    'look': scene.view_settings.look, 'exposure': scene.view_settings.exposure,
                    'gamma': scene.view_settings.gamma, 'cycles_samples': scene.cycles.samples},
         'objects': objects, 'materials': materials, 'images': images,
         'node_groups': [{'name': group.name, 'nodes': [n.bl_idname for n in group.nodes]} for group in bpy.data.node_groups],
         'world': {'name': scene.world.name, 'color': list(scene.world.color),
                   'nodes': [{'type': node.bl_idname,
                              'inputs': {socket.name: value(socket.default_value) for socket in node.inputs
                                         if hasattr(socket, 'default_value') and not socket.is_linked}}
                             for node in scene.world.node_tree.nodes] if scene.world.use_nodes else []}
                  if scene.world else None,
         'libraries': [lib.filepath for lib in bpy.data.libraries]}
Path(args.output).parent.mkdir(parents=True, exist_ok=True)
Path(args.output).write_text(json.dumps(state, ensure_ascii=False, indent=2))
if args.render:
    scene.render.resolution_x = 640
    scene.render.resolution_y = 360
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = str(Path(args.render).resolve())
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 32
    bpy.ops.render.render(write_still=True)
