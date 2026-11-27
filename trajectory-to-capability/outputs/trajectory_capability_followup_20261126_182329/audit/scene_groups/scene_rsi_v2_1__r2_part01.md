# Historical evidence synthesis: scene_rsi_v2_1__r2, batch 1

## Coverage and citation key

The supplied inventory covers all **10 source files** in this group and its only batch. The audits cover all stated chunks, including both chunks of S0216 and S0219. These are trajectory files, not necessarily 10 independent task instances: several concern the same `commons` image under different conditions. The reference and rendered images are not visible to this audit, even where the student received them. No formal visual scores are reported; they are unknown. Old model cost cannot be recovered from its absence.

All original paths share this prefix:

`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v2_1/results/r2/`

The matrix gives each source’s remaining path; append `/trajectory.jsonl`. Line numbers refer to the original JSONL files, not the audit reports.

## Evidence matrix

| Source and path suffix | Observed attempt and outcome | Evidence and limit |
|---|---|---|
| **S0214** `scene_rsi_v2_1/C2/test/commons_189918915` | Nonempty warehouse-interpreted scene; first execution timed out, no image. | Lines 3–5: ~490 seconds, `ok: false`. No correction or visual validation. |
| **S0215** `scene_rsi_v2_1/C2/test/commons_80372956` | Nonempty ceiling/chandelier-interpreted scene; first execution timed out, no image. | Lines 3–5: ~488 seconds; no comparison or revision. |
| **S0216** `scene_rsi_v2_1/C2/selection/commons_194983350` | First execution succeeded and was selected; after render receipt, student diagnosed discrepancies, executed a revision, and step 2 succeeded and was selected. | Lines 5–7 and 9–12. Selection establishes neither image fidelity nor improvement. |
| **S0217** `scene_rsi_v2_1/C2/development/commons_187101683` | First execution succeeded and was selected; student compared, revised several scene parameters, and step 2 succeeded and was selected. | Lines 5–7 and 9–12. Diagnoses and improvement are not independently verified. |
| **S0218** `scene_rsi_v2_1/C1/selection/commons_194983350` | Nonempty café-interpreted program; first execution timed out, no image. | Lines 3–5: 472.508 seconds; no render-guided revision. |
| **S0219** `scene_rsi_v2_1/C1/development/commons_187101683` | First execution succeeded; student revised after comparison. Step 2 succeeded and was selected; student later returned `DONE`. | Lines 5–12 and 15. The `DONE` response is not an independent quality assessment. |
| **S0220** `fixed_h0/H0/test/commons_189918915` | Nonempty warehouse-interpreted program; first execution timed out, no image. | Lines 3–5: ~483 seconds; no observed revision. |
| **S0221** `fixed_h0/H0/test/commons_80372956` | Nonempty ceiling/chandelier-interpreted program; first execution timed out, no image. | Lines 3–5: ~516.7 seconds; no observed revision. |
| **S0222** `fixed_h0/H0/selection/commons_194983350` | Nonempty café-interpreted program; first execution timed out, no image. | Lines 3–5: ~464 seconds; no observed revision. |
| **S0223** `fixed_h0/H0/development/commons_187101683` | First build failed on a missing scene world; student revised initialization and camera, then step 2 succeeded and was selected; student returned `DONE`. | Lines 5–14. The traceback identifies the initial failure; later execution does not establish visual fidelity. |

## Comparison of attempts

The six timeout traces—S0214, S0215, S0218, S0220, S0221 and S0222—each contain a substantive scene program and one launched execution, not an empty patch. Their results had empty stdout/stderr and no image. They are interrupted technical attempts, not demonstrated geometric or visual algorithm failures. Dense geometry or rendering settings might have contributed, but the logs do not locate the time spent. No permission, branch or CLI stop is reported in these traces; those categories should not be substituted for the observed timeouts.

S0223 is a different kind of failure: its first build exposed a concrete `None` world at `world.use_nodes` (line 5). The subsequent code conditionally created a world and also changed camera settings; the second execution succeeded (lines 8–11). The sequence supports resolution of that reported build blocker in this run, not a claim that the camera change improved the image.

S0216, S0217 and S0219 show successful initial and revised executions, with selected second renders. They are successful **execution and selection** records, not established successful reconstructions. They also provide more than a mere proposal: after receiving a reference and first render, students stated diagnoses and executed nonempty changes. For example, S0216 reported a shared framing discrepancy and changed the lens and several object/material parameters (lines 7, 9–12); S0217 changed camera, table, cups, flowers, materials and lighting after its own discrepancy ledger (lines 7, 9–12); S0219 retained its camera while rotating the table and changing cup, plant, upholstery and lighting parameters (lines 7, 9–12). Those are student judgments and implemented changes, not independently measured defects or verified improvements.

This distinction also prevents treating a technically successful render as a partial visual success. The audits do not expose the pixels needed to establish even partial fidelity. S0216, S0217 and S0219 report 16 rendered samples despite programs requesting 48; S0223 reports 16 despite requesting 64. The reason and visual effect are unknown (respectively S0216 lines 3–5, 10–11; S0217 lines 3–5, 10–11; S0219 lines 3–5; S0223 lines 9–10).

## Teacher roles, receipt and validation

Across these ten student trajectories, **no teacher message, detection, diagnosis or proposed update is recorded**; therefore neither teacher receipt nor adoption is established. This is an observation about the supplied trajectories, not proof that no advice existed elsewhere. No teacher-side availability or acceptance record is included.

The later comparison requests in S0216, S0217 and S0219 are runner/user input, not identified teacher diagnoses. Their requests supplied the reference and first render to the student; the subsequent diagnoses are student-led. S0223 instead received an operational traceback and later a reference/render review request with no executions remaining (lines 5–6, 12–14). Its `DONE` records the student’s response, not independent acceptance of scene quality. The documented selections similarly identify chosen executions, not visual scores.

## Transferable constraints and uncertainty

The task constraints included separate 3D meshes and matching viewpoint, framing, geometry and materials; S0218 and S0222 explicitly prohibited using the image as a texture (line 1 in each). Programs’ named parts, placements and intended supports do not establish actual contact, occlusion or fidelity. Successful rendering is necessary evidence of technical execution but is not evidence of matching the reference; timeout without logs cannot identify a modeling defect. S0223’s diagnosed build error is a counterexample to treating every failure as an unexplained timeout.

Separating camera-wide discrepancies from local placement, size, spacing and material changes is an auditable distinction, not a proven superior method. S0216 changed both framing and local objects, while S0219 retained its camera and made local changes; neither result is independently ranked. Specific café, warehouse, chandelier and sitting-room inventories are student interpretations of unseen photographs. Their particular coordinates, lens choices, object contacts and claimed discrepancies remain task-specific hypotheses. No causal superiority, visual improvement, recovered score or cost follows from these records.
