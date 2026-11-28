# Experiment 03 shared harness changes

Only three existing shared harness files changed. The existing Claude Agent SDK remains the sole tool executor, and the existing Codex CLI Bridge remains the model backend. No model request conversion, SDK library, reconstruction prompt, or Experiment 01/02 scientific record changed.

- `initial_images`: optional complete list of `{path, label}` image descriptors. Omission preserves the old reference/current/additional-image behavior. An explicit list can provide multiple development references or a reference-only input despite a checkpoint.
- `readonly_mounts`: optional controller-supplied list of `{source, target}` directory mounts. These are attached using `--ro-bind` and included in SDK `add_dirs`. There are no implicit GT mounts. The controller must provide only the permitted development GT to learning sessions, and only the frozen capability library to test students.
- `persistent_capability_enabled`: optional session metadata, default `false`. Hint and online-teacher defaults remain disabled.

`before/`, `after/`, and `shared_harness_changes.diff` preserve the exact source boundary. `isolation_check.json` records actual namespace checks and actual SDK Read/Write tool results for a student capability mount and a teacher development-GT mount. Both sessions used CPU affinity 32–39, succeeded in permitted reads, failed reads of the opposite mount and host GT path, and received EROFS on writes. Host project and old scene directories were absent. Legacy default image selection, explicit reference-only input, and multiple explicit images were checked.

The SDK transport fixture uses deterministic local synthetic API responses inside each isolated network namespace. It invokes no underlying model, does not start a host model service, and does not validate model image understanding. These fixture sessions are infrastructure evidence, not research runs.

## Runtime mount restriction (shared v2)

The original whole `/harness` mount became an information leak when research controller scripts were added there: their source can contain teacher principles, case mapping and learning instructions. Data-path checks alone did not cover this access. The shared v2 change replaces that directory mount with only `/harness/sdk_student.py` and `/harness/socket_tunnel.py`; the existing Blender wrapper remains separately mounted at `/runtime/bin/blender`. Generic `/sdk` source remains available and contains no experiment data.

`shared_v2_before/`, `shared_v2_after/`, `shared_v2.diff`, and `shared_v2_source_origin.json` preserve this boundary separately from the first source snapshot. New sessions use the restricted namespace; sessions already running retain their old namespace and must be handled by their experiment controller. No Experiment 01/02 record or previous snapshot was modified.

Actual student and teacher SDK Read calls confirmed `run_teacher_alignment.py`, `run_capability_acquisition.py`, and `run_exploration.py` are absent, while both runtime files remain readable. `shared_v2_checks/isolation_check.json` records these checks. A second check executes the real `/harness/sdk_student.py` entrypoint, its socket tunnel, actual SDK tools, and an actual Blender process through the unchanged wrapper; all passed. `shared_v2_entrypoint/entrypoint_check.json` preserves the results. Both checks use synthetic local API responses, make zero underlying model calls, and use CPUs 32–39.
