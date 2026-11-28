# Experiment 02: fixed teacher guidance from common scene checkpoints

Recorded before formal student execution. This is a checkpoint branch experiment, not restored model state, full RSI, long-term learning, or a human-aligned teacher.

## Fixed cases and conditions

S01 starts from Experiment 01 S01-R1 and targets the two chairs' support relation. S02 starts from S02-R3 and targets the bedroom door's orientation and foreground occlusion. S03 starts from S03-R2 and targets the right kitchen countertop material and texture. Selection follows the user-specified repeated-defect cases, not a score ranking. Every condition receives the identical copied workspace, reference RGB, initial render, base prompt, and fresh SDK session; the original conversation is not resumed.

E0 receives the base continuation task. E1 additionally receives a generic comparison and self-check request. E2 receives a fixed teacher's defect-only hint. E3 receives the exact E2 text plus one technical strategy and verification direction. E4 receives the exact E2 text plus at least two substantially different candidate hypotheses/methods and a comparison request. Teachers generate all case-specific hint content before formal runs. Hint length and actual token consumption are measured rather than claimed equal. No hint is revised using formal outcomes.

The fixed candidate teacher sees the reference, initial reconstruction, current source, saved reconstruction state, original observed trajectory, and existing objective defect evidence. It has Read/Glob/Grep/Write tools to inspect evidence and write a diagnosis. It cannot run Blender or edit a student workspace, and neither teacher nor student has any GT filesystem mount. The teacher input contains the selected run only, not other students. The teacher's proposed technical knowledge is a prior, not an experimentally acquired ability.

## Shared execution

Claude Agent SDK 0.2.186 and the existing hintrsi execution loop own tools and conversation. The existing model-only Codex CLI bridge uses gpt-6.1-terra, reasoning low, including the completed 235-second backend timeout cancellation fix. No native CLI agent executes student tools. Every student has Bash, Read, Write, Edit, Glob, Grep, an isolated workspace/network namespace, no external network, no old memory/skills, and no GT/other-run access. The SDK generic coding system prompt is retained equally.

Students receive reference and initial reconstruction as real initial image blocks, with explicit labels, plus local copies. Each run has a 1500-second additional execution limit and 120 bridge-request/SDK-turn limits, CPU rendering with eight threads, nice 15, 32 GiB per-process address-space limit, final 640x360. Two equal workers use CPU sets 32-39 and 40-47; CPU sampling will record contention rather than claim exclusive cores. All may finish early. Calls and observed tokens are distinct from budget limits; SDK dollar estimates are not actual subscription billing.

The fixed core order, saved in configs/frozen_design.json after teacher outputs are checked, interleaves cases and conditions. Fifteen core branches run once each. If the core ends within three hours and at least 150 minutes remain, one complete independent repeat of all fifteen branches may run in reversed order. This decision uses elapsed time and completion capacity, not condition performance. Core and extra repeats are reported separately. No second checkpoint or E5 is included in this batch, preserving time for complete paired evaluation and evidence analysis.

## Preflight and preservation

A separate non-formal sphere checkpoint with an unseen RGB label tests two initial images, the real specified model, SDK Read/Bash/Write, unchanged-source Blender regeneration, subsequent render Read, explicit guidance receipt, and filesystem/network isolation. It supplies no reconstruction experience to formal runs. Teacher Read/Write is checked through actual diagnostic execution. All teacher outputs and exact prompts are saved before freezing.

Experiment 01 is read only. Copies include all source, images, scene files and related local resources, but no .git metadata. All groups use identical context restoration. Current source and configurations are snapshotted for Experiment 02; formal source does not depend on later analysis edits. The passive Blender wrapper preserves source versions/diffs, commands, stdout/stderr, images and actual scene files after each real execution. SDK tool records preserve writes and edits even when not executed. Unsaved or overwritten states that cannot be recovered are explicitly unavailable; no synthetic trajectory states are invented.

## Independent evaluation, after every student has ended

Evaluation has no feedback path to students or teachers. A fixed anonymous random permutation labels images independently of condition; visual evaluators receive reference, baseline and one candidate, never E0-E4, hints, expected results, or other candidate outputs. All model-based teachers, visual evaluators and trajectory annotators use the same SDK/bridge/model/effort. Automated judgments, objective geometry measurements and empty human fields remain separate.

Technical checks open each delivered .blend, independently execute delivered build.py and its local dependencies in an isolated copy, and compare regenerated artifacts. Failure or unchanged output is preserved without controller repair. The controller does not select a preferred candidate or replace a student's final decision. Evaluator renders and diagnostics never overwrite deliverables.

S01 geometry uses evaluated world-space meshes, separately assigned full chair assemblies and their wheel/base/post parts. The predeclared numerical tolerance is 1e-4 student Blender units. Report each chair's minimum geometry, local floor height at supporting locations, signed vertical gap and gap/chair-height. Strict gap above tolerance establishes no support contact. A zero gap or bounding-box intersection is not proof of mesh contact. Floor penetration, wheel orientation, wheel/base/post connections and unintended other-object changes are checked separately, with uncertain cases marked unknown. Closing a gap while penetrating the floor is not complete success. Actual mesh intersections and surface-distance samples are evidence with stated limits, not a dynamics simulation.

S02 records the door leaf/hinge/frame transforms and visible projection, camera/framing changes and relevant occlusion. Only reliably matched semantic door geometry is used for reference-view masks or GT instance comparisons. If matching is ambiguous, exact IoU is unavailable. A mask improvement alone does not establish plausible hinges or full visual recovery. Invisible GT differences are not student errors.

S03 records actual material bindings, nodes, coordinates, scales, geometric veins, execution cost and editability. Posthoc auxiliary renders reuse the initial camera, lights, world and display settings, leaving candidate geometry/materials intact; remaining geometry changes are therefore a documented confound. Crops show local appearance. Reducing geometric veins or adding nodes alone is not automatically an improvement.

Visual evaluators report target resolution (resolved/partial/unresolved/unknown), before/after target and overall change, visible side effects and image evidence. They cannot infer true support contact from RGB alone. Objective measurements are reported alongside their observations. SSIM is auxiliary, never an overall quality ranking. Human scores are null until real humans fill the anonymous offline form.

## Exploration and strategy evidence

For every actual candidate, distinguish proposed, written, executed, verified and finally retained techniques. Evidence cites SDK event IDs, source snapshots, actual Blender exit/results and saved states/images. Record rejected candidates and side effects, not only final scenes. Do not count repeated failure, a longer trace, or changing a numeric value as a new modeling technique by itself.

Report strategy Jaccard for (1) all evidence-backed semantic techniques, (2) excluding Experiment 01's twelve common generic labels, and (3) target-local techniques. Also distinguish inherited checkpoint techniques from additional actions, since inherited code alone inflates overlap. Unknown is not an absent technique. No code-text similarity substitutes for strategy similarity. Repeated pairs are not independent tasks; no statistical significance, causal certainty or model-capability ceiling is claimed.

Candidate knowledge records distinguish the teacher prior, natural checkpoint knowledge, methods actually discovered/executed in branches, and untested hypotheses. Include applicability, observed defect, evidence, side effects, validation method and any actually produced reusable snippet. Whole scene programs are not general skills. Cross-scene transfer and no-teacher capability acquisition remain untested.

## Deadline and repairs

Preparation began 2026-11-28 00:35:33 Beijing time; the six-hour deadline is 06:35:33. Reserve at least the last hour for analysis and cleanup. Preserve interruptions and actual integration fixes, recording affected runs and any change in conditions. No outcome-driven retries. Student modeling mistakes are observations and are never repaired by the controller. Stop only processes owned by this experiment and remove copied authentication after each model session.
