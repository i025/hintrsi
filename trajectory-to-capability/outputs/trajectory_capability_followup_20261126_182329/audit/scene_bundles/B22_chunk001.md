## B22 archive audit

The supplied selection contains two functional summaries, not teacher, program, student-execution, or candidate-acceptance records. The archive is `/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/work/scene_archive/bundles/replay_s1_r1--M_descendant.tar.gz`. Both cited members are reproduced in full at characters [0,357).

- **Development target—architecture:** `experiments/scene_rsi_pilot/results/replay_s1_r1/M_descendant/C1/replay_development/commons_2238909/functional/summary.json` reports `structure_pass`, `material_pass`, `composite_required`, `composite_pass`, and `functional_pass` all `true`. Its `semantic_object_completeness` and `support_collision_truth` are `null`.
- **Selection target—Cream teapot:** `experiments/scene_rsi_pilot/results/replay_s1_r1/M_descendant/C1/replay_selection/commons_29206714/functional/summary.json` reports the same five true flags and the same two null fields.

Both summaries explicitly limit their `interpretation` to “Structural/edit operability only” and state the rule that an expected composite absent counts as failure, never N/A. The true `composite_required` and `composite_pass` flags report a pass under that functional assessment; the records do not expose the underlying checks or establish semantic completeness. The null collision fields do not establish physical support or contact.

**Coverage and limitations.** The two targets show assessment of separate architecture and teapot cases, but do not demonstrate multi-object coverage within either scene. `material_pass: true` is a reported functional result, not evidence of texture or visual quality. The records do not describe part connections, pose, camera, lighting, or rendering. No image appearance can be established from them.

**Failure and process distinction.** Neither selected summary reports a technical functional failure; neither provides a quality evaluation sufficient to rule out quality failures. No supplied record identifies a teacher-detected problem, diagnostic hypothesis, proposed H/M/code update, actual student mechanism execution, or candidate acceptance. In particular, the functional pass flags should not be treated as proof of candidate acceptance or of an acceptance rule beyond the stated composite rule. These conclusions concern only the selected records, not the entire archive.
