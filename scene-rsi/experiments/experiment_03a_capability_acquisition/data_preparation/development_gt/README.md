# Development GT technical package

This package is a deterministic inspection of the three existing IDEAL-Scenes Blender files. It is not a teacher diagnosis and supplies no reconstructed student solution.

Each S01/S02/S03 directory contains the original reference RGB, structured GT, visible-object annotation, camera/render metadata, instance segmentation, actual Blender data in full_state.json, reference mask statistics, and source.json pointing to the original scene.blend. Full Blender files remain in their original data/evaluation_gt directories and must be mounted read-only for authorized A4/A5 teachers.

The extracted data include complete material and node-group trees and connections, linked and unlinked socket defaults, UV layer ranges and samples, material polygon assignments, transforms and local axes, hierarchy, modifiers, camera, lights, image availability, and unoccluded bounding-box projections. Semantic GT matching is exact object name matching only. Blender axes are not asserted to be semantic object facing. Bounding-box projections are not instance silhouettes or occlusion measurements. Reference instance statistics come directly from the dataset segmentation and its metadata index map.

Teachers may use actual Blender queries under the common validation budget. Knowledge intended for students must exclude these scene files, image assets, dedicated textures, exact example coordinates, and evidence records. These are development scenes; test GT is kept separately. The original dataset is CC-BY-4.0, https://huggingface.co/datasets/IDEAL-Benchmark/IDEAL-Scenes.
