# Scene replay evidence synthesis — batch 1 of 1

## Coverage and source key

This group contains three supplied student trajectory files, each inventoried at 25 JSONL lines. All source chunks were model-reviewed; this synthesis uses their audit reports, not the raw trajectories or image pixels. Repeated programs and feedback embedded in later requests are not additional trials. The three files represent three recorded trajectories, not a basis for estimating independent-trial performance or general success rates.

- **S0091:** `/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_pilot/results/replay_s1/H_start/H_start/replay_test/commons_52210054/trajectory.jsonl`
- **S0092:** `/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_pilot/results/replay_s1/H_start/H_start/replay_development/commons_2238909/trajectory.jsonl`
- **S0093:** `/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_pilot/results/replay_s1/H_start/H_start/replay_selection/commons_29206714/trajectory.jsonl`

Citations below identify JSONL lines in these original files. The reports support operational history, but do not expose the reference or rendered image pixels for independent visual judgment.

## Evidence matrix

| Trajectory | Executed behavior and feedback | Validation and selection | Quality and intervention limits |
|---|---|---|---|
| **S0091** | An initial multi-object bedroom interpretation was revised after the student diagnosed wall occlusion, framing and pale materials; a further revision changed camera target and lens, chair position, materials and lighting (lines 3–4, 8, 10–11, 16–18). | All three builds reported `ok: true` and renders; step 3 was selected (lines 5, 12, 19–21, 24–25). | No separate teacher advice or adoption is visible. Render success and selection do not establish a faithful scene or improvement. |
| **S0092** | An archive-corridor interpretation included 25 shelving banks. The student revised camera and brightness, then added a foreground handle, lowered plaques and changed materials and camera target after its own diagnoses (lines 3–4, 8, 10–11, 17–18). | All three builds reported `ok: true`; step 3 was selected (lines 5, 12, 19–21, 24–25). Logs reported 16 samples although code requested 32; the cause is unknown (lines 5, 19, 22). | No separate teacher advice or adoption is visible. The sample discrepancy is not itself a demonstrated failure or explanation of quality. |
| **S0093** | A historic-kitchen interpretation was revised for framing, wheel silhouette and timber; a subsequent build narrowed the cabinet and related objects, moved the wheel and changed door inserts (lines 3–4, 8, 10–11, 15–18). | All three builds reported success; step 3 was selected, including after `SELECT 3` (lines 5, 12, 19–21, 24–25). | No separate teacher advice or adoption is visible. The wheel, cabinet and material changes remain unverified as improvements. |

## Comparison and interpretation

**Successful execution is the observed success; reconstruction quality is unknown.** Each trajectory contains three nonempty scene-building executions reported successful and a final selection of step 3. Each student made two revisions after receiving render feedback. The outputs were editable multi-object scenes, and the code specified cameras, lighting and materials. Grouped parts and coordinates show intended assemblies, not independently verified contact, pose or fidelity. Selection records a choice, not acceptance by an independent evaluator or proof that the chosen image was best. Relevant final evidence is S0091 lines 19–25, S0092 lines 19–25 and S0093 lines 19–25.

The group does **not** supply a demonstrated failed or interrupted attempt for comparison: the reports identify no empty patch, permission or branch stop, CLI interruption, or algorithmic failure in these trajectories. Zero tool calls in recorded student sessions, including final selection sessions, are session observations, not evidence of a failed build. Nor does a successful render prove an algorithm succeeded at visual matching. Missing formal visual scores are unknown, and absence of cost information cannot recover old model cost.

**Feedback and agency must be separated.** Harness instructions and render results were actually supplied, and students responded with their own diagnoses and executed changes—for example, S0091 lines 8–12 and 16–19; S0092 lines 8–12 and 17–19; S0093 lines 8–12 and 15–19. Across the supplied reports, no separate teacher diagnosis or proposed update is visible; availability, actual receipt and adoption of teacher advice therefore cannot be established. The runner’s comparison request is not a teacher intervention. Formal execution and final selection are visible; independent visual acceptance and quality are not.

**Transferable constraints versus local hypotheses.** The evidence supports distinguishing build/render validation from visual and geometric validation, and distinguishing a student’s diagnosis from the changes actually executed. Camera, occlusion, materials and object geometry are identifiable categories of revision, but these students often changed several together, so their individual effects cannot be isolated. The counterexample to treating code structure as proof is common to all three: separately modeled, grouped components do not establish physical connection or correct appearance.

Specific wall shortening and chair relocation in S0091, foreground-handle and plaque choices in S0092, and cabinet narrowing and wheel orientation in S0093 are task-specific responses to each student’s interpretation of an unavailable reference. Their adoption in code is documented; the correctness of the underlying diagnoses and the effectiveness of the updates are unverified. No causal superiority among builds or trajectories follows from the selection events.
