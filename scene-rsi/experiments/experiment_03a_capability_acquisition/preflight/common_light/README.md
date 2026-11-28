# Common-world appearance-control preflight

Two artificial scenes share actual geometry, materials, emission and camera, but differ in original world color/strength, light color/energy (500 versus 3500) and exposure (0 versus 1.25). A third completed-session fixture deliberately has no scene file. No model or formal student result was used.

The actual isolated Blender pipeline produced four 640x360 RGBA images (two student-shaped scenes and two reference-shaped scenes). Under the common world, they are pixel-identical. Original scene files remain byte-for-byte equal to their evaluation copies, camera data are retained, material emission strength0.2 remains present, and all original differing settings are recorded. Missing scene delivery is recorded with image:null and no fabricated result. See actual_checks.json and actual command/log/settings records.

This control hides existing Light objects, replaces the world with a uniform white Background strength1, uses the existing CPU8 wrapper, 16 fixed Cycles samples, no adaptive sampling or denoising, seed0, 640x360 RGBA, AgX/None/exposure0/gamma1/sRGB, and disables borders/compositing/sequencer. Geometry, materials, texture coordinates, optical camera settings and material emission are preserved. Geometry, camera, opacity, occlusion and indirect transport remain confounded; this is not a complete material-quality isolation and is never credited as student validation or improvement. No scene is saved by the renderer.

After all formal students end, run after independent technical extraction has created its output folders, before preparing SDK technical reviewer inputs:

    /srv/lab-disks/disk2/users/xymo/miniforge3/envs/scenemosaic/bin/python analysis/render_acquisition_common_light.py --workers 4

Student output: runs/<run>/analysis/technical/common_light/capture/{common_light.png,common_light_settings.json}; original GT output: data_preparation/new_scene_validation/<task>/common_light/capture/{common_light.png,common_light_settings.json}. Every output folder retains command, execution log, result and copied workspace. The final index is analysis/common_light_index.json. Missing scenes and render failures remain separate status/counts.
