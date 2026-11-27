# Scene group historical evidence synthesis

## Coverage and citation key

This audit covers **all 12 inventoried files in batch 1 of 1**, S0202–S0213. Each is a student trajectory; the supplied input consists of complete model-reviewed audit reports, not the raw trajectories or rendered images. The file count is not a count of independent trials: copies, where present, must not be treated as independent. No teacher-only trajectory is included in this group.

For compact citations, all paths below are relative to the common original-source directory:
`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/teacher_self_evolution_human_pilot/tasks/`.
Each entry names its original `trajectory.jsonl`; line numbers are JSONL event lines. The original task prompts and reference images are absent. Scene goals are therefore inferred from code, not verified specifications.

## Evidence matrix

| ID and original path | Observed attempt and outcome | Evidence and limits |
|---|---|---|
| S0202 `E01_M1_R2/trajectory.jsonl` | Cushion fillet exceeded its dimensional bound; a smaller radius preceded a successful render and selection. | Lines 3–5, 7–11. No image-based quality judgment. |
| S0203 `E02_M1_R2/trajectory.jsonl` | Two successful renders; revision changed wall, colors, lighting and camera. | Lines 3, 5–8, 10, 12–14. Improvement unverified. |
| S0204 `D01_M0_R1/trajectory.jsonl` | Two successful renders; revised furniture, flowers, camera and lighting. | Lines 3, 5–8, 10, 12–14. No visual verdict. |
| S0205 `E01_M1_R1/trajectory.jsonl` | Two successful renders; revised room extent, chair, windows, camera and light. | Lines 3, 5–8, 10, 12–14. Intended emission assignment’s effect unverified. |
| S0206 `E02_M0_R1/trajectory.jsonl` | Two successful renders; revised cabinetry, procedural materials, camera and lighting. | Lines 3, 5–8, 10, 12–14. Glass appearance and improvement unknown. |
| S0207 `E01_M0_R2/trajectory.jsonl` | Coincident rod endpoints stopped the first build; a substantive path and naming revision preceded a successful render. | Lines 3–5, 7, 9–11. The causal contribution of individual edits was not isolated. |
| S0208 `E02_M0_R2/trajectory.jsonl` | Two successful renders; revised shell, cabinet heights, colors and camera. | Lines 3, 5–8, 10, 12–14. Visual effect unknown. |
| S0209 `E02_M1_R1/trajectory.jsonl` | Two successful renders; revised wall, island, plank gaps, camera and lighting. | Lines 3, 5–8, 10, 12–14. No independent geometric or visual check. |
| S0210 `D01_M0_R2/trajectory.jsonl` | Pillow fillet bound stopped the first build; reduced fillets preceded successful rendering. | Lines 3–5, 7–11. Connections and fidelity unknown. |
| S0211 `E01_M0_R1/trajectory.jsonl` | A material loop encountered null object data; type/data guards preceded a successful render. | Lines 4–5, 7, 9–11. Image not supplied. |
| S0212 `D02_M0_R2/trajectory.jsonl` | Two successful renders; revised office geometry, camera and lights. | Lines 3–14. Logs report 32 samples despite requests for 48 and 64; visual consequences unknown. |
| S0213 `D02_M0_R1/trajectory.jsonl` | Chair fillet bound stopped the first build; smaller radii preceded successful rendering. | Lines 3–5, 7–11. No quality score. |

## Comparison and interpretation

All 12 trajectories end in a recorded successful build/render and selection. Seven show two technically successful versions; five first fail at construction and then render successfully after a nonempty revision. These are **operational outcomes**, not demonstrated success on the original visual tasks. The failed first builds produced no image: three involved fillet constraints (S0202, S0210, S0213), one coincident rod endpoints (S0207), and one null object data (S0211). The traces support error-associated corrections and subsequent execution, but not an isolated causal test of every changed line.

No empty patch, permission denial, branch stop, CLI stop, timeout or memory interruption is reported in this batch. Those categories should not be conflated with the observed construction errors; nor does their absence here establish their absence elsewhere. No final scene is independently established as partially correct or incorrect. Formal scores are unknown, and the absence of cost records cannot recover old model cost.

The successful-first-build cases are counterexamples to treating the error-retry pattern as universal. They also show that iteration need not follow a visible failure: S0203, for example, selected its first render before executing a revised scene (lines 7–8). The motivation for such changes and whether the student inspected the first image are not recorded.

## Teacher roles, validation and transferable evidence

No teacher message, diagnosis, proposed update, receipt, or adoption is visible in these student traces. A directory name or condition label does not establish that advice was available or received. Student-executed changes and subsequent build/render acceptance are observed; a teacher-directed update is not. Selection and `ok: true` establish neither independent visual quality nor formal task acceptance.

The fillet failures document a transferable API constraint: the radius cannot exceed half the smallest relevant dimension in these calls. S0207 documents a rod-meshing constraint on coincident endpoints, while S0211 documents a null-data access failure. Their particular cushion, window and material-loop edits are task-specific, and successful reruns do not validate all geometry.

Across the group, code specifies objects, materials, camera and lighting, but code placement and render completion do not independently verify contacts, occlusion, material appearance, framing or fidelity. For example, S0205’s room extension was an attempted framing change, not proof that a visible edge existed or was fixed (line 8). Whether closer cameras, darker lighting or other revisions improved a scene remains a hypothesis without the images and target. This is an audit-only synthesis, not evidence of causal superiority or a source of new capability guidance.
