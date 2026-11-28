# Semantic projection engineering preflight

Seven artificial Blender scenes validate the posthoc two-dimensional measurement chain. No scientific student run, model reviewer, human label, teacher capability, or learned reconstruction was used. Known fixture correspondences are explicit test inputs. Their GT segmentation comes from known fixture object masks.

The actual Blender pipeline confirms aligned objects, a translated object, increased partial occlusion, an Empty-root two-object semantic union, a missing exact object name, an unresolved correspondence, and a named object outside the camera. Host-side checks additionally confirm duplicate GT assignments remain unknown and nearest resizing preserves 16-bit IDs.

All actual checks are in actual_checks.json. Source, commands, scenes, masks, overlays, crops, logs, exceptions and per-run measurements are retained. The original student-shaped scene files remain byte-for-byte unchanged. The namespace_probe proves both the private synthetic GT and the real project GT paths are inaccessible inside the mask renderer.

The initial real preflight exposed an invalid retained DepsgraphObjectInstance iterator reference. The renderer now snapshots objects, matrices and instance parents while iterating, before creating proxy data. The original failure log is initial_depsgraph_iterator_failure.log. No formal run was affected.

Baseline left-object IoU is 0.98865 and union IoU 0.99511 rather than exactly one because thresholded multisample object edges can tie when converted to a single-label GT segmentation. These differences are preserved. Glass/alpha/transmission are replaced by opaque geometry, so the method is an approximate geometric visibility comparison and can disagree with appearance-based visibility. Original render borders are unsupported and produce unknown rather than a spurious measurement.

After all formal students and SDK technical reviewers finish:

    /srv/lab-disks/disk2/users/xymo/miniforge3/envs/scenemosaic/bin/python analysis/measure_acquisition_projection.py --workers 4

Expected annotations: acquisition_reviews/technical/<run>/workspace/technical_annotation.json. Per-run results: runs/<run>/analysis/projection/result.json. End marker: analysis/projection_summary.json, with complete, expected_run_count and runs[].completed. Missing actual reviewer annotations keep complete false; low-confidence, ambiguous or unmapped entries finish as unknown. The quality of a high-confidence model correspondence is not human verified. No 3D coordinate, scale, position or orientation alignment is performed.
