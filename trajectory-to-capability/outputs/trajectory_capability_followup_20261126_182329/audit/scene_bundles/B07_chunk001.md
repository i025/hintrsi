## B07 audit: selected record

The supplied source is `experiments/scene_rsi_pilot/results/external/fixed_h0/selected/external/bw_0005/functional/summary.json` in `/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/work/scene_archive/bundles/external--fixed_h0.tar.gz` (characters 0–361).

**What the record says.** For the target object `back left cabinet`, `structure_pass`, `material_pass`, `composite_required`, `composite_pass`, and `functional_pass` are all `true`. Both `semantic_object_completeness` and `support_collision_truth` are `null`. The `interpretation` describes the result as “Structural/edit operability only” and states that an expected composite being absent counts as failure, never N/A.

**Scope and substantiation.** This is a reported functional result, not an independently observable demonstration of how the checks were executed. It states an acceptance-related rule for expected composites, but the supplied record does not expose the test implementation or evidence supporting the individual pass values. `material_pass: true` does not establish texture quality or image appearance. The null completeness and support/collision fields do not establish multi-object semantic coverage, part connections, physical contact, or collision truth. No evidence here evaluates pose, camera, lighting, or render quality.

The supplied excerpt contains no teacher problem detection, diagnostic hypothesis, proposed H/M/code update, student mechanism execution, or candidate-acceptance decision. It also does not document a technical or quality failure. Those matters cannot be reconstructed from this summary; the reported passes should not be treated as proof of visual quality or of unseen execution.
