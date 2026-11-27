import sys
import json
import math

import bpy


def vector_values(value):
    return [float(component) for component in value]


def matrix_values(value):
    return [vector_values(row) for row in value]


def driver_count(owner):
    animation_data = getattr(owner, "animation_data", None)
    return len(animation_data.drivers) if animation_data else 0


def ancestor_names(obj):
    names = []
    seen = set()
    current = obj.parent
    while current is not None:
        pointer = current.as_pointer()
        if pointer in seen:
            break
        seen.add(pointer)
        names.append(current.name)
        current = current.parent
    return names


def inspect_object(obj, depsgraph):
    record = {"name": obj.name, "type": obj.type}
    errors = []
    fields = (
        ("parent", lambda: obj.parent.name if obj.parent else None),
        ("ancestors", lambda: ancestor_names(obj)),
        ("world_matrix", lambda: matrix_values(obj.matrix_world)),
        ("dimensions", lambda: vector_values(obj.dimensions)),
        ("hide_render", lambda: bool(obj.hide_render)),
        ("material_names", lambda: [slot.material.name if slot.material else None for slot in obj.material_slots]),
        ("object_animation_drivers", lambda: driver_count(obj)),
        ("data_animation_drivers", lambda: driver_count(obj.data) if obj.data else 0),
    )
    for name, get_value in fields:
        try:
            record[name] = get_value()
        except Exception as exc:
            errors.append({"operation": name, "error": str(exc)})

    if obj.type == "MESH":
        evaluated = None
        mesh = None
        try:
            evaluated = obj.evaluated_get(depsgraph)
            mesh = evaluated.to_mesh()
            if mesh is None:
                raise RuntimeError("Evaluated object did not provide a mesh")
            geometry = {
                "vertex_count": len(mesh.vertices),
                "polygon_count": len(mesh.polygons),
                "world_aabb_min": None,
                "world_aabb_max": None,
            }
            if mesh.vertices:
                matrix = evaluated.matrix_world
                minimum = [math.inf, math.inf, math.inf]
                maximum = [-math.inf, -math.inf, -math.inf]
                for vertex in mesh.vertices:
                    world = matrix @ vertex.co
                    for axis in range(3):
                        coordinate = float(world[axis])
                        if not math.isfinite(coordinate):
                            raise ValueError("Evaluated vertex has a non-finite world coordinate")
                        minimum[axis] = min(minimum[axis], coordinate)
                        maximum[axis] = max(maximum[axis], coordinate)
                geometry["world_aabb_min"] = minimum
                geometry["world_aabb_max"] = maximum
            record["evaluated_geometry"] = geometry
        except Exception as exc:
            errors.append({"operation": "evaluated_geometry", "error": str(exc)})
        finally:
            if evaluated is not None and mesh is not None:
                try:
                    evaluated.to_mesh_clear()
                except Exception as exc:
                    errors.append({"operation": "to_mesh_clear", "error": str(exc)})
    if errors:
        record["exceptions"] = errors
    return record


def main():
    args = sys.argv
    if "--" not in args or len(args[args.index("--") + 1:]) != 1:
        raise ValueError("Expected exactly one output path after --")
    output_path = args[args.index("--") + 1]
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    camera = scene.camera
    camera_record = None
    if camera is not None:
        camera_record = {
            "name": camera.name,
            "world_matrix": matrix_values(camera.matrix_world),
            "lens": float(camera.data.lens),
        }

    objects = [inspect_object(obj, depsgraph) for obj in sorted(scene.objects, key=lambda item: item.name)]
    keywords = ("monitor", "screen", "display", "stand")
    candidates = []
    for record in objects:
        if record["type"] != "MESH":
            continue
        names = [record["name"]] + record.get("ancestors", [])
        if not any(keyword in name.lower() for name in names for keyword in keywords):
            continue
        geometry = record.get("evaluated_geometry", {})
        if geometry.get("world_aabb_min") is not None and geometry.get("world_aabb_max") is not None:
            candidates.append(record)

    pairs = []
    for index, first in enumerate(candidates):
        a = first["evaluated_geometry"]
        for second in candidates[index + 1:]:
            b = second["evaluated_geometry"]
            separation = [
                max(0.0, a["world_aabb_min"][axis] - b["world_aabb_max"][axis],
                    b["world_aabb_min"][axis] - a["world_aabb_max"][axis])
                for axis in range(3)
            ]
            pairs.append({
                "objects": [first["name"], second["name"]],
                "axis_separation": separation,
                "aabb_distance_lower_bound": math.hypot(*separation),
            })

    report = {
        "filepath": bpy.data.filepath,
        "blender_version": bpy.app.version_string,
        "current_frame": scene.frame_current,
        "unit_system": scene.unit_settings.system,
        "unit_scale": scene.unit_settings.scale_length,
        "render_engine": scene.render.engine,
        "render_resolution": {
            "x": scene.render.resolution_x,
            "y": scene.render.resolution_y,
            "percentage": scene.render.resolution_percentage,
        },
        "active_camera": camera_record,
        "objects": objects,
        "mesh_aabb_pairs": pairs,
        "scope": "A positive AABB distance lower bound establishes separated bounds; zero establishes neither surface contact nor correctness. This limited observational measurement cannot determine occluded geometry quality, exact mesh intersection, correct semantics, aesthetics, or a teacher's causal effect.",
    }
    with open(output_path, "x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, allow_nan=False, indent=2)
        output.write("\n")


if __name__ == "__main__":
    main()

