# Historical evidence synthesis: Scene replay pilot

## Coverage and interpretation

This report covers batch 1 of 1, all four inventoried student trajectory files: S0094–S0097. The supplied audits cover three chunks each for S0094–S0096 and seven for S0097. Chunk-local statements that later events were unseen are resolved where another supplied chunk records them. These are four files, not necessarily four independent trials: the two development files share one source case and the two selection files share another; file counts can include copies. The audits do not expose the reference or rendered pixels for independent review.

**Source path key.** All paths below have the common prefix `/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_pilot/results/replay_s1_r1/`:

- **S0094:** `M_descendant/C1/replay_development/commons_2238909/trajectory.jsonl`
- **S0095:** `M_descendant/C1/replay_selection/commons_29206714/trajectory.jsonl`
- **S0096:** `M_initial/C1/replay_development/commons_2238909/trajectory.jsonl`
- **S0097:** `M_initial/C1/replay_selection/commons_29206714/trajectory.jsonl`

Line references below are to those original JSONL files, as supported by the supplied audits.

## Evidence matrix

| Source and case | Executed behavior and reported validation | Final selection and quality limit | Teacher evidence |
|---|---|---|---|
| S0094, descendant/development | Three nonempty builds rendered successfully. The student revised shelving, opening and illumination, then shelving and exposure; lines 3–5, 10–12, 17–19. | Selected step 3, lines 24–25. Visual match and physical connections remain unknown. | Runner comparison instructions and renders were received, line 8; no distinct teacher diagnosis or update is identified. |
| S0095, descendant/selection | Three builds reported successful; revisions combined camera, wheel, fireplace and other changes, lines 10–12, 17–19. | Selected **step 2**, not the later step 3, lines 24–25. Independent visual correctness is unknown. | Runner review was received, line 8; no separate teacher advice or adoption is visible. |
| S0096, initial/development | Three builds reported successful. Camera pitch and lighting were changed together, then the cabinet layout and book bay were revised; lines 10–12, 17–19. Assertions checked limited construction properties. | Selected step 3, lines 24–25. Whether the bay is visible or the image matches is unknown. | System and runner comparison instructions were received, line 15; no distinct teacher diagnosis or proposed update is visible. |
| S0097, initial/selection | Three builds reported usable/successful. Lens and wheel geometry changed together; a later program adjusted cabinet proportions and wheel pose, lines 10–12, 17–19 and 22. | Selected step 3, lines 24–25. Assertions and selection do not establish contact or visual fidelity. | General review guidance was received, lines 8 and 15; no separately identified teacher diagnosis or update is visible. |

## Comparison of attempts and outcomes

All four records show **technical execution success** for three builds and a final selection. This is a narrower outcome than a successful reconstruction: the audits cannot independently compare the images or establish camera alignment, appearance, occlusion, object support or connections. No formal quality score is supplied, so scores and overall correctness are unknown. S0095 is a useful counterexample to equating the latest executed revision with acceptance: step 3 executed successfully, but the student ultimately chose step 2 (lines 19, 24–25). Selection itself is not independent evidence that either version was better.

The records show substantive, nonempty programs and revisions, not an established empty-patch failure. S0097’s step-2 log says `Total files 0 | Changed 0 | Failed 0` (line 12), but that log alone does not establish an empty scene update: the preceding executed program is visible at lines 10–11 and the runner reported a completed render. No permission, branch or CLI stop, algorithmic failure, or interrupted execution is evidenced in these records. S0096 and S0097 reached their execution budget before final selection (line 22); that is a workflow limit, not proof that a running build failed. Audit chunk boundaries likewise are not runtime interruptions. The evidence supports neither a verified partial reconstruction nor a failed one; both quality and any unobserved failure modes remain unknown. Historical model cost cannot be recovered from its absence in these reports.

The two development trajectories illustrate different hypotheses on the same named case. S0094’s student attributed discrepancies to cabinet proportions, opening placement and brightness, and executed changes to geometry and appearance (lines 10–12, 17–19). S0096’s student instead hypothesized pitch and lighting problems, then overlap obscuring books; it changed the camera and lights, followed by carriage and bay geometry (lines 10–12, 17–19). Neither diagnosis nor improvement is independently confirmed. The selection trajectories likewise differ: S0095 moved the camera across the scene and adjusted the wheel after hypothesizing a camera-side problem (lines 17–19), whereas S0097 changed lens and wheel parameters together, then cabinet proportions and wheel pose (lines 10–12, 17–19). These are task-specific responses, not evidence that one model or intervention was superior.

## Advice, adoption and transferable constraints

The observed advice chain is limited. Ordinary system and runner instructions were **available and actually received**, including requests to compare supplied renders with the reference. Students stated their own diagnoses and executed updates consistent with those review requests. The runner then reported render completion, and students selected builds. No supplied audit identifies a separate teacher message, teacher diagnosis or teacher-proposed patch in these trajectories. Consequently, teacher-specific availability, receipt and adoption cannot be established; generic review guidance must not be relabeled as teacher advice. Nor does technical acceptance or selection establish independently observed quality.

Several constraints transfer across the cases without prescribing a new solution:

- **Execution is not fidelity.** Saved renders, object counts and limited assertions establish aspects of the pipeline, not visual match or physical support. S0096’s bay-clearance assertion, for example, did not establish that books were visible (lines 17–19).
- **Ownership is not contact.** Groups and hinge or wheel constructions document intended relationships, but do not prove collision-free connections, support or correct pose; S0095’s raised wheel and S0097’s calculated winder placement remain unverified (S0095 lines 17–19; S0097 lines 17–19).
- **A reported discrepancy is not its cause.** Concurrent changes confound attribution: S0094 changed geometry and appearance, and S0097 changed camera and wheel geometry in the same revisions. Their particular dimensions, labels and semantic scene interpretations are hypotheses tied to those images, not general findings.
- **A render-informed revision is not independent exploration.** Students received renders and revised programs, but the audited sessions report zero tool calls; this does not demonstrate autonomous external investigation. Conversely, zero tool calls does not negate the observed program revisions.

No reference or render pixels, independent geometric checks, teacher-specific intervention, formal scores, or verified quality outcomes are available in the supplied reports. The report is therefore an audit of recorded behavior and its evidential limits, not a capability-generation input or a claim of causal superiority.
