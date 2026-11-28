"""Inspect real Blender data for evaluation and GT-authorized development roles."""
import argparse
import json
from pathlib import Path
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


def value(item):
    if isinstance(item, (str, int, float, bool)) or item is None:
        return item
    if isinstance(item, (tuple, list, Vector)) or hasattr(item, 'to_list'):
        return [value(x) for x in item]
    if isinstance(item, bpy.types.ID):
        return {'name': item.name, 'type': item.bl_rna.identifier}
    return str(item)


def matrix(item):
    return [list(row) for row in item]


def node_tree(tree):
    nodes = []
    for node in tree.nodes:
        row = {'name': node.name, 'label': node.label, 'type': node.bl_idname,
               'mute': node.mute,
               'inputs': [{'name': socket.name, 'identifier': socket.identifier,
                           'linked': socket.is_linked,
                           'default': value(socket.default_value) if hasattr(socket, 'default_value') else None}
                          for socket in node.inputs],
               'outputs': [{'name': socket.name, 'identifier': socket.identifier,
                            'linked': socket.is_linked} for socket in node.outputs],
               'properties': {key: value(getattr(node, key)) for key in
                              ('operation', 'blend_type', 'vector_type', 'noise_dimensions',
                               'noise_type', 'normalize', 'projection', 'projection_blend',
                               'interpolation', 'extension', 'distribution', 'data_type',
                               'uv_map', 'attribute_name', 'wave_type', 'wave_profile',
                               'bands_direction', 'rings_direction', 'gradient_type',
                               'distance', 'feature', 'voronoi_dimensions', 'space',
                               'invert', 'is_active_output', 'target', 'component')
                              if hasattr(node, key)}}
        if hasattr(node, 'image'):
            row['image'] = node.image.name if node.image else None
        if hasattr(node, 'node_tree'):
            row['node_group'] = node.node_tree.name if node.node_tree else None
        if hasattr(node, 'object'):
            row['coordinate_object'] = node.object.name if node.object else None
        if hasattr(node, 'color_ramp'):
            row['color_ramp'] = {'interpolation': node.color_ramp.interpolation,
                                 'elements': [{'position': item.position, 'color': list(item.color)}
                                              for item in node.color_ramp.elements]}
        if hasattr(node, 'texture_mapping'):
            mapping = node.texture_mapping
            row['texture_mapping'] = {key: value(getattr(mapping, key)) for key in
                                      ('translation', 'rotation', 'scale', 'mapping_x', 'mapping_y', 'mapping_z')}
        nodes.append(row)
    return {'nodes': nodes, 'links': [{'from_node': link.from_node.name,
                                      'from_socket': link.from_socket.identifier,
                                      'to_node': link.to_node.name,
                                      'to_socket': link.to_socket.identifier,
                                      'valid': link.is_valid} for link in tree.links]}


parser = argparse.ArgumentParser()
parser.add_argument('--input', required=True)
parser.add_argument('--output', required=True)
parser.add_argument('--render')
parser.add_argument('--samples', type=int, default=16)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
source = Path(args.input).resolve()
bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
scene = bpy.context.scene
camera = scene.camera
depsgraph = bpy.context.evaluated_depsgraph_get()
gt_path = source.parent / 'GT.json'
gt = json.loads(gt_path.read_text()) if gt_path.exists() else {}
gt_objects = {item['id']: item for item in gt.get('scene', {}).get('objects', [])}
objects = []
for obj in scene.objects:
    row = {'name': obj.name, 'type': obj.type, 'parent': obj.parent.name if obj.parent else None,
           'children': [child.name for child in obj.children], 'location': list(obj.location),
           'rotation_euler': list(obj.rotation_euler), 'rotation_mode': obj.rotation_mode,
           'rotation_quaternion': list(obj.rotation_quaternion), 'scale': list(obj.scale),
           'dimensions': list(obj.dimensions), 'matrix_world': matrix(obj.matrix_world),
           'matrix_local': matrix(obj.matrix_local), 'matrix_basis': matrix(obj.matrix_basis),
           'matrix_parent_inverse': matrix(obj.matrix_parent_inverse),
           'world_local_axes': [list(obj.matrix_world.to_3x3().col[i].normalized()) for i in range(3)],
           'hide_render': obj.hide_render, 'hide_viewport': obj.hide_viewport,
           'pass_index': obj.pass_index, 'instance_type': obj.instance_type,
           'instance_collection': obj.instance_collection.name if obj.instance_collection else None,
           'materials': [slot.material.name if slot.material else None for slot in obj.material_slots],
           'semantic_gt_exact_name_match': gt_objects.get(obj.name),
           'modifiers': [{'name': modifier.name, 'type': modifier.type,
                          'show_render': modifier.show_render,
                          'parameters': {key: value(getattr(modifier, key)) for key in
                                         ('width', 'segments', 'levels', 'render_levels', 'thickness',
                                          'offset', 'count', 'relative_offset_displace',
                                          'constant_offset_displace', 'operation', 'object',
                                          'use_axis', 'node_group') if hasattr(modifier, key)}}
                         for modifier in obj.modifiers],
           'constraints': [{'name': constraint.name, 'type': constraint.type,
                            'influence': constraint.influence, 'mute': constraint.mute,
                            'target': value(constraint.target) if hasattr(constraint, 'target') else None}
                           for constraint in obj.constraints]}
    if obj.type in ('MESH', 'CURVE', 'SURFACE', 'FONT', 'META'):
        evaluated = obj.evaluated_get(depsgraph)
        corners = [evaluated.matrix_world @ Vector(corner) for corner in evaluated.bound_box]
        row['evaluated_world_bbox_corners'] = [list(corner) for corner in corners]
        row['world_bounds'] = {'min': [min(c[i] for c in corners) for i in range(3)],
                               'max': [max(c[i] for c in corners) for i in range(3)]}
        if camera:
            projected = [world_to_camera_view(scene, camera, point) for point in corners]
            row['bbox_projection_unclipped'] = {'coordinate_convention': 'x left-to-right, y bottom-to-top, normalized; z is camera depth; bbox is not a visible silhouette.',
                                                'corners': [list(point) for point in projected],
                                                'min_xy': [min(point[i] for point in projected) for i in range(2)],
                                                'max_xy': [max(point[i] for point in projected) for i in range(2)]}
    if obj.type == 'MESH':
        mesh = obj.data
        usage = {}
        for face in mesh.polygons:
            key = str(face.material_index)
            usage[key] = usage.get(key, 0) + 1
        uv_layers = []
        for layer in mesh.uv_layers:
            coordinates = [list(item.uv) for item in layer.data]
            uv_layers.append({'name': layer.name, 'active_render': layer.active_render,
                              'loop_count': len(coordinates),
                              'min': [min(uv[i] for uv in coordinates) for i in range(2)] if coordinates else None,
                              'max': [max(uv[i] for uv in coordinates) for i in range(2)] if coordinates else None,
                              'first_16_loop_uv': coordinates[:16]})
        row['mesh'] = {'vertices': len(mesh.vertices), 'edges': len(mesh.edges),
                       'polygons': len(mesh.polygons), 'uv_layers': uv_layers,
                       'material_polygon_counts_by_slot': usage,
                       'attributes': [{'name': a.name, 'domain': a.domain, 'data_type': a.data_type}
                                      for a in mesh.attributes]}
    if obj.type == 'CURVE':
        row['curve'] = {'splines': len(obj.data.splines), 'bevel_depth': obj.data.bevel_depth,
                        'bevel_resolution': obj.data.bevel_resolution,
                        'spline_types': [s.type for s in obj.data.splines]}
    if obj.type == 'CAMERA':
        row['camera'] = {key: value(getattr(obj.data, key)) for key in
                         ('type', 'lens', 'sensor_width', 'sensor_height', 'sensor_fit',
                          'ortho_scale', 'shift_x', 'shift_y', 'clip_start', 'clip_end')}
    if obj.type == 'LIGHT':
        row['light'] = {key: value(getattr(obj.data, key)) for key in
                        ('type', 'energy', 'color', 'size', 'size_y', 'spot_size', 'spot_blend',
                         'shadow_soft_size') if hasattr(obj.data, key)}
    objects.append(row)
materials = [{'name': material.name, 'diffuse_color': list(material.diffuse_color),
              'roughness': material.roughness, 'metallic': material.metallic,
              'use_nodes': material.use_nodes,
              'tree': node_tree(material.node_tree) if material.use_nodes else None}
             for material in bpy.data.materials]
groups = [{'name': group.name, 'type': group.bl_idname, 'tree': node_tree(group),
           'interface': [{'name': item.name, 'item_type': item.item_type,
                          'in_out': getattr(item, 'in_out', None),
                          'socket_type': getattr(item, 'socket_type', None),
                          'default': value(item.default_value) if hasattr(item, 'default_value') else None}
                         for item in group.interface.items_tree]}
          for group in bpy.data.node_groups]
images = []
for image in bpy.data.images:
    absolute = bpy.path.abspath(image.filepath)
    packed = bool(image.packed_file) or bool(image.packed_files)
    images.append({'name': image.name, 'source': image.source, 'filepath': image.filepath,
                   'absolute_filepath': absolute, 'size': list(image.size), 'packed': packed,
                   'has_data': image.has_data, 'colorspace': image.colorspace_settings.name,
                   'missing_external': image.source in ('FILE', 'TILED') and not packed and not Path(absolute).exists()})
state = {'file': str(source), 'blender_version': bpy.app.version_string,
         'camera': camera.name if camera else None,
         'render': {key: value(getattr(scene.render, key)) for key in
                    ('engine', 'resolution_x', 'resolution_y', 'resolution_percentage',
                     'pixel_aspect_x', 'pixel_aspect_y', 'film_transparent', 'use_compositing')},
         'cycles': {key: value(getattr(scene.cycles, key)) for key in
                    ('samples', 'device', 'use_denoising', 'seed', 'use_animated_seed')},
         'view_settings': {key: value(getattr(scene.view_settings, key)) for key in
                           ('view_transform', 'look', 'exposure', 'gamma')},
         'objects': objects, 'materials': materials, 'node_groups': groups, 'images': images,
         'world': {'name': scene.world.name, 'color': list(scene.world.color),
                   'tree': node_tree(scene.world.node_tree) if scene.world.use_nodes else None}
                  if scene.world else None,
         'compositor': node_tree(scene.node_tree) if hasattr(scene, 'node_tree') and scene.node_tree else None,
         'libraries': [{'name': lib.name, 'filepath': lib.filepath} for lib in bpy.data.libraries],
         'view_layers': [{'name': layer.name, 'use_pass_object_index': layer.use_pass_object_index}
                         for layer in scene.view_layers],
         'interpretation_limits': ['Bounding-box projections do not measure visible masks or occlusion.',
                                   'Object local axes are Blender transform axes, not inferred semantic orientation.',
                                   'Dataset GT is one implementation and contains no original generation trajectory.',
                                   'No student reconstruction is generated or repaired by this extractor.']}
target = Path(args.output)
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(state, ensure_ascii=False, indent=2))
if args.render:
    scene.render.resolution_x = 640
    scene.render.resolution_y = 360
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = str(Path(args.render).resolve())
    scene.cycles.device = 'CPU'
    scene.cycles.samples = args.samples
    bpy.ops.render.render(write_still=True)
