# Historical evidence synthesis: scene_rsi_v2_2__smoke

## Evidence matrix

| Attempt or stage | Evidence | Observed outcome | Limits |
|---|---|---|---|
| Initial scene build | S0025, `trajectory.jsonl`, lines 1, 3–5 | The student attempted a separate-mesh reconstruction from one indoor RGB image. The build failed at `scene.bind` with “Constraint endpoints must belong to this scene”; the image was null. | This was an API/execution failure before rendering, not evidence of a visual defect or timeout. |
| Revised build | S0025, lines 8–10 | The student diagnosed string endpoints, changed them to scene nodes `plant, table`, and reran the retained scene. Step 2 returned `ok: true` in 33.28 seconds and saved a render and Blender scene. | This was an executed update, not an empty patch. The successful rerun supports the repair for this failure, but does not establish scene fidelity. |
| Selection and final review | S0025, lines 11–14 | The successful result was selected. The reference and render were supplied to a final student call with no executions left; the student answered `DONE` without a visible discrepancy analysis. | Selection and `DONE` do not independently establish visual quality. The audit does not provide the image pixels. |

## Synthesis

This trajectory contains an initial **failed execution** followed by a **successful technical build and render**. It does not establish a successful reconstruction in the visual sense. The first failure was specific: a bind constraint rejected endpoints that did not belong to the scene. The student’s endpoint diagnosis led to a real code change and a successful rerun. There is no evidence here of an empty patch, a permission or branch stop, a CLI stop, or a timeout.

The student’s inferred inventory included a sofa, leaning pillow, coffee table, tea settings, flowering plant, curtain, wall and floor. The code constructed named assets and child parts and specified materials, camera and lighting (S0025, lines 3–4). Those facts show what was attempted, not that the reference was accurately interpreted or reproduced. In particular, the plant–table constraint’s visible effect, object placement and occlusion, silhouettes, materials, pillow pose, framing and lighting remain unverified. The student also explicitly regarded the prior camera and geometry as unverified when revising the build (lines 8–9). There was no visible post-render revision.

No teacher message, diagnosis or proposed teacher update appears in this student trajectory. Thus teacher advice availability and receipt are not established, and there is no evidence of teacher-advice adoption. The observed diagnosis and executed update were the student’s. Runner success validates execution and artifact production; selection records acceptance for the run, not an independent quality judgment. No formal score is reported, so it is unknown. Old model cost cannot be recovered from its absence.

The transferable constraint is to separate traceback-supported execution repair from visual validation: success at one does not demonstrate the other. The endpoint change resolving this particular bind failure is a task-specific inference supported by the rerun, rather than proof that all scene relationships were correct. The record offers a counterexample to treating either an initial failure as final failure or a later `DONE` as independently verified visual success.

## Coverage

This batch covers the group’s **one supplied file**, S0025, with 14 JSONL lines, reported as completely reviewed across explicit chunks. Its source is `/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v2_2/results/smoke/fixed_h/r1_C2/smoke/old_dev_excluded_smoke/trajectory.jsonl`. It is one trajectory, not multiple independent trials; file counts in the broader inventory can include copies. Conclusions are limited to the supplied audit observations, not unavailable image pixels or unreported events.
