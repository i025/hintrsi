## Scope and findings

The supplied records contain three functional summaries, not the full archive or teacher, program, execution, and candidate-acceptance histories. They support a narrow finding: each recorded target passed the archive’s structural/edit-operability checks. They do not establish visual quality or explain how a candidate was produced or accepted.

All paths below are members of `/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/work/scene_archive/bundles/replay_s1--H_start.tar.gz` (bundle B21).

- **Development:** `experiments/scene_rsi_pilot/results/replay_s1/H_start/H_start/replay_development/commons_2238909/functional/summary.json`, characters [0,352): `target_object` is `bank_00`; `structure_pass`, `material_pass`, `composite_required`, `composite_pass`, and `functional_pass` are all `true`.
- **Selection:** `experiments/scene_rsi_pilot/results/replay_s1/H_start/H_start/replay_selection/commons_29206714/functional/summary.json`, characters [0,350): the same five keys are `true` for target `China`.
- **Test:** `experiments/scene_rsi_pilot/results/replay_s1/H_start/H_start/replay_test/commons_52210054/functional/summary.json`, characters [0,353): the same five keys are `true` for target `Far lamp`.

In all three, `interpretation` limits the result to “Structural/edit operability only” and states that an expected but absent composite counts as failure, never N/A. Thus the records state an evaluation rule and report passes under it; they do not expose the checks or underlying scene evidence needed to independently verify those passes. In each summary, both `semantic_object_completeness` and `support_collision_truth` are `null`.

## Limits of the audit

- **Multi-object coverage and part connections:** Three different targets are named across the summaries, but this does not establish complete coverage of all objects within any scene. `composite_pass: true` is a reported operability result, not evidence of semantic completeness, correct connections, or physical contact; the relevant semantic and support/collision fields are `null`.
- **Material and texture:** `material_pass: true` is reported for each target. The summaries do not identify materials or textures, their appearance, or the test behind the flag.
- **Pose, camera, lighting, and render:** No supplied key documents these aspects or a quality assessment of them. No image appearance can be inferred.
- **Technical versus quality failures:** No failure is reported in these summaries’ listed pass fields. That is not proof that there were no visual or other quality failures: the summaries expressly restrict their interpretation, and the semantic and collision fields are unassessed or unspecified as `null`.
- **Process and acceptance:** The supplied records do not show teacher problem detection, a diagnostic hypothesis, a proposed H/M/code update, actual student mechanism execution, or a candidate-acceptance decision. The functional pass flags should not be conflated with evidence of any of those stages or with a broader candidate-acceptance rule.
