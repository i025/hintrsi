# Scene historical evidence synthesis: H03, batch 1

## Scope and coverage

This audit-only synthesis covers all **3 supplied files** in `scene_rsi_v3__H03`, batch 1 of 1: student trajectories S0278, S0279 and S0280. The supplied audit reports describe full, model-reviewed source chunks; the raw trajectories and image pixels are not reproduced here. Counts refer to files, not necessarily independent trials; no independence or copy relationship is established in the supplied inventory. Citations below identify the original source paths relative to this common prefix:

`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v3/results/H03/selection/`

No formal final quality scores are visible; they are unknown. The record does not establish old model cost, and absence of cost information cannot recover it.

## Evidence matrix

| Source and original path | Failure and repair | Executed revision and validation | Outcome and limits |
|---|---|---|---|
| **S0278**, `bw_0045/1/trajectory.jsonl` | Step 1 failed before rendering because the frozen import contract rejected `json`; H received the traceback, removed the import and manually formatted diagnostics (lines 7–8, 10–16). | After receiving the reference and step-2 render, H claimed size, framing and rail defects and revised the scene. Step 3 tested four camera candidates and rendered; estimated rail-bend vertical residual remained +0.3181 and curb-right horizontal residual +0.7837 (lines 18, 20–21, 26). | Step 3 was selected (line 27). Build/render success is observed; visual fidelity is not independently established. |
| **S0279**, `bw_0017/1/trajectory.jsonl` | The same import-contract class of failure stopped step 1 before rendering. H received the traceback, removed `json` and produced a successful step-2 render (lines 6–8, 10–16). | H claimed camera and composition defects, then changed camera, lens, palette and scene details. Step 3 rendered; its estimated foreground conveyor point projected to x=−0.4319 against 0.02, despite small residuals for some other anchors (lines 18, 20–21, 23–26). | Step 3 was selected (line 27); the mixed anchor results do not establish image match or visibility. |
| **S0280**, `bw_0031/1/trajectory.jsonl` | Step 1 failed on the frozen import contract; H received the traceback, removed `json` and rendered step 2 (lines 6–17). | H claimed shell occlusion and an undersized desk, then removed the ceiling, changed camera and scene elements, and switched diagnostics from landscape to 374 × 512. Step 3 rendered; estimated vertical residuals included +0.1591 and −0.1683 (lines 3–4, 18–21, 23–27). | Step 3 was selected (line 27). The reported two-photograph interpretation, final visibility and fidelity remain unverified. |

## Comparison and interpretation

All three records show a **failed initial program**, followed by nonempty repairs, successful builds and renders, further executed scene revisions, and final selections. The initial failures were import-contract execution stops—not empty patches, permission or branch stops, CLI stops, or evidence of defective scene geometry. None of those other stop types is reported in this batch. The later renders are technical successes, but the overall reconstruction outcomes remain only partially evidenced: selection and anchor output do not independently establish quality.

The shared repair sequence supports a narrow transferable constraint: address the actual execution traceback before inferring visual defects. It was adopted in all three trajectories. Runner feedback was actually received, and the corresponding import removal was executed; this was not a separate teacher intervention. No distinct teacher message, detection, diagnosis, proposed update or execution appears in these student traces, so teacher-advice receipt and adoption are unestablished. This is an absence in these records, not proof that advice was unavailable elsewhere.

For the visual phase, the students received reference/render comparisons and made diagnoses, then executed updates. Those diagnoses were **their claims**, not independent image observations. S0278's cow and rail changes, S0279's roof/camera and conveyor changes, and S0280's shell removal and room composition are task-specific hypotheses; no subsequent visible review verifies their predicted improvements. S0280 is a particularly clear uncertainty: H chose to combine elements it interpreted as belonging to two photographs, but the relationship was explicitly uncertain (S0280 lines 3–4, 18–21).

Anchor projections provide numerical evidence of framing tradeoffs, not visibility or image similarity. S0279's small machine-top residuals coexist with a large foreground conveyor discrepancy; S0278's selected camera still had substantial residuals. These counterexamples prevent generalizing that successful rendering, candidate selection, or good alignment at some anchors implies a good reconstruction. Correspondences themselves were estimates. Similarly, named meshes, child hierarchies, materials, cameras and lights show what code attempted to construct, not independently verified connections, pose, occlusion, illumination or appearance. In S0278, even the step-3 count description and code differ on loops per divider (line 21).

The available evidence therefore supports traceback-directed repair and careful separation of projection diagnostics from visual validation; it does not establish that any particular scene revision improved fidelity, that one approach was causally superior, or that the final scenes met their intended visual goals.
