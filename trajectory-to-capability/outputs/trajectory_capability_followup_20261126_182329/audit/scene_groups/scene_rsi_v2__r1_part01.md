# Historical evidence synthesis: scene_rsi_v2__r1, batch 1 of 1

## Coverage and citation key

The inventory contains eight student-trajectory files, S0031–S0038: four selection and four development files. The supplied reports cover all explicit model-reviewed chunks for this group. Chunk reports sometimes repeat earlier events embedded in later requests; these are not additional trials. File counts can include copies and must not be treated as independent-trial counts. The reports do not expose reference or render pixels, independent geometric inspection, formal visual scores, or historical model cost. Missing scores are unknown; cost cannot be recovered from its absence.

Original source paths below share this prefix:

`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v2/results/r1/fixed_h0/H0/`

- S0031: `selection/commons_184317253/trajectory.jsonl`
- S0032: `selection/commons_186238614/trajectory.jsonl`
- S0033: `selection/commons_138884680/trajectory.jsonl`
- S0034: `selection/commons_135156253/trajectory.jsonl`
- S0035: `development/commons_129095630/trajectory.jsonl`
- S0036: `development/commons_105241439/trajectory.jsonl`
- S0037: `development/commons_113438548/trajectory.jsonl`
- S0038: `development/commons_130842254/trajectory.jsonl`

## Evidence matrix

| Source | Executed attempts and observed result | Final evidence and limit |
|---|---|---|
| S0031 | Three nonempty scene builds reported successful renders; the student changed camera, geometry and lighting between them (lines 3–5, 9–12, 15–18). | Images were supplied for review and the student returned `DONE` (lines 19–21). Selection and completion do not establish visual fidelity. |
| S0032 | A fillet-constraint failure and then a missing-world failure preceded a successful third render (lines 3–16). | Final image paths were supplied and `DONE` returned (lines 17–19); reconstruction quality remains unknown. |
| S0033 | A fillet failure was followed by a roughly 600-second timeout and an object-data failure (lines 3–15). | A further program was returned with no executions remaining; it was not tested (lines 16–18). No successful render is recorded. |
| S0034 | A missing-world failure was followed by two successful renders, the latter after a substantive scene and camera revision (lines 3–17). | The final session received image paths and returned `DONE` (lines 19–20). No independent quality judgment is visible. |
| S0035 | A missing-world failure was followed by a successful second render; a further revision timed out at about 576 seconds (lines 3–16). | The second render is the last visible execution-level success. The timeout’s cause and final submission are unknown. |
| S0036 | A fillet failure, approximately 600-second timeout, and missing-world failure produced no render (lines 3–15). | A final world-handling revision was returned without remaining executions (lines 16–18); its effectiveness is unknown. |
| S0037 | A substantial initial program failed on missing world state; the subsequent student session timed out (lines 3–9). | No revised response, second execution, or render is visible. |
| S0038 | An initial approximately 600-second timeout and then a missing-world failure preceded a successful third render and selection (lines 3–16). | The final review was supplied the reference and render and returned `DONE` (lines 17–19); accuracy remains unknown. |

## Comparison of attempts and feedback

**Execution success is narrower than task success.** S0031, S0032, S0034, S0035 and S0038 each produced at least one reported successful render. S0035 is a partial process outcome: its successful intermediate build was followed by an interrupted revision, not an independently verified partial visual match. S0033, S0036 and S0037 have no recorded successful render. None has a visible formal visual-correctness score. Selection, saved files and `DONE` establish runner or student actions, not acceptance of reconstruction quality.

The failures are distinguishable. S0032’s excessive chair fillet was reduced before execution advanced to a different missing-world error; its third build rendered (lines 5–15). S0033 also encountered a fillet error, but its subsequent rounded-panel approach timed out and its next approach failed on missing object data; the final descendant-search revision was untested (lines 5–18). S0036 simplified geometry after a timeout but then encountered missing world state, with its final change untested (lines 8–18). These are counterexamples to treating one correction as proof that an entire scene program works.

Timeouts are interruptions, not diagnoses. S0035’s third execution and S0038’s first execution returned no image and no diagnostic output; their causes are not established (S0035 line 16; S0038 line 5). S0037’s timeout occurred in the student session after a failed build, rather than in a second scene execution (lines 5–9). The visible programs and revisions were substantive; the records do not establish an empty patch as the cause of these outcomes. Nor do these eight reports identify permission, branch, or CLI-access stops as causes. Their absence here should not be recast as algorithmic failure or generalized beyond the group.

## Teacher roles, receipt and Scene quality

All eight sources are student trajectories. The supplied audits identify no teacher message, teacher diagnosis, proposed teacher update, actual receipt of such advice, or adoption in these records. Thus neither teacher-effectiveness nor teacher-adoption claims are supported. This is distinct from runner feedback: for example, S0032 received concrete tracebacks and revised its program (lines 6–13), and S0034 received a comparison prompt and image inputs before a further revision (lines 12–15). Those events do not establish a teacher’s involvement or expose the student’s visual diagnosis.

For Scene specifically, image paths or image inputs were supplied to later sessions in S0031, S0032, S0034 and S0038; this establishes availability to those sessions, not what the student perceived or whether its assessment was correct. Subsequent executed changes are observable in S0031 and S0034, but their visual benefit is not (S0031 lines 9–18; S0034 lines 12–17). In S0035, a post-render revision was executed but timed out (lines 12–16). In S0033 and S0036, final proposed changes were not executed. These distinctions prevent an available input, proposed update, execution, selection and independently observed quality from being collapsed into one outcome.

## Transferable constraints and unresolved hypotheses

The traces support separating primitive-parameter violations, absent Blender world state, timeouts and later object-data errors. In S0034 and S0035, world creation followed an explicit exception and the next build rendered (S0034 lines 5–11; S0035 lines 5–11). S0037 shows that receiving the same kind of traceback need not lead to an observed repair: its subsequent session timed out. The records show sequence and execution outcomes, not causal superiority of one approach.

The requested separate-mesh reconstructions required viewpoint, framing, materials and placement, but the named chamber, office, vestibule, garden, workshop, classroom and kitchen scenes are student interpretations of unseen photographs. Code specifies objects, part positions, materials, cameras and lights; it does not independently verify contact, pose, occlusion or resemblance. Several successful render logs report 16 samples despite higher program settings, including S0031 lines 3–5 and 15–17 and S0034 lines 14–16; the reason and visual effect are unknown. Whether any revision improved fidelity, whether timeouts reflected complexity, and whether the final untested repairs worked remain hypotheses, not findings.

This synthesis is audit-only and does not enter capability generation.
