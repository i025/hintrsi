# Historical evidence synthesis: Scene RSI pilot, batch 1

## Coverage and citation key

The supplied inventory identifies **72 files** in `scene_rsi_pilot__r1`, batch 1 of 1. This report synthesizes their supplied model-reviewed chunk reports, not the raw trajectories, reference photographs, renders, stderr files, or scene files. The files include copies and must not be counted as independent trials. Chunk-local statements about unseen material are resolved only where another supplied chunk reports it. Formal scores not shown are **unknown**; old model cost cannot be recovered from missing usage records.

Citations use source IDs and original JSONL line IDs. For compactness, all paths below are relative to this original prefix:

`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_pilot/`

Each suffix ends in `/trajectory.jsonl`; a path group applies to its cited sources in the same order.

- **Interrupted quota-restored examples:** S0051 `quota_restored_20261103/retired/results/r1/generic_rsi/C2/selection/commons_138420790`; S0053 `quota_restored_20261103/retired/results/r1/generic_rsi/C1/test/commons_163096530`.
- **Generic RSI:** S0132 `results/r1/generic_rsi/C2/test/commons_163096530`; S0133 `results/r1/generic_rsi/C2/test/commons_16007442`; S0139 `results/r1/generic_rsi/C2/development/commons_118588033`; S0141 `results/r1/generic_rsi/C1/selection/commons_133800864`; S0142 `results/r1/generic_rsi/C1/development/commons_109923183`.
- **Scene pilot:** S0146 `results/r1/scene_rsi_pilot/C2/test/commons_155212263`; S0153 `results/r1/scene_rsi_pilot/C1/selection/commons_133800864`; S0154 `results/r1/scene_rsi_pilot/C1/development/commons_109923183`; S0155 `results/r1/scene_rsi_pilot/C1/development/commons_118588033`.
- **SceneEvolve CLI:** S0158 `results/r1/sceneevolve_cli/C2/test/commons_155212263`; S0159 `results/r1/sceneevolve_cli/C2/test/commons_199974832`; S0162 `results/r1/sceneevolve_cli/C2/development/commons_109923183`; S0163 `results/r1/sceneevolve_cli/C2/development/commons_118588033`; S0166 `results/r1/sceneevolve_cli/C1/development/commons_109923183`.
- **Fixed H0:** S0168 `results/r1/fixed_h0/H0/test/commons_163096530`; S0169 `results/r1/fixed_h0/H0/test/commons_16007442`; S0170 `results/r1/fixed_h0/H0/test/commons_155212263`; S0173 `results/r1/fixed_h0/H0/selection/commons_133800864`; S0174 `results/r1/fixed_h0/H0/development/commons_109923183`.
- **Service-incident example:** S0190 `service_incident_01/retired/results/r1/sceneevolve_cli/C2/selection/commons_138420790`.

## Evidence matrix

| Observed outcome | Evidence and distinction |
|---|---|
| **Operational success, quality unknown** | S0132, lines 3–5, 9–11, 15–17 and 21–22: a multipart scene and two revisions ran, three renders were reported successful, and step 3 was selected. S0133, lines 9–12, 15–18 and 21–22: a monitor revision and later material revision ran and step 3 was selected. Neither record independently verifies resemblance or establishes a formal scene score. |
| **Partial operational progress, then interruption** | S0139, lines 3–10: initial render succeeded and was selected, but the review CLI exited 1 before a revision. S0141, lines 3–16: two renders succeeded before the next model session timed out. S0163, lines 25–31: three renders succeeded, but final comparison exited 1; ultimate submission remains unknown. |
| **Fallback after failed revision** | S0142, lines 15–18: step 3 timed out without an image and step 2 was selected. S0166, lines 20–24: a substantive upholstery revision timed out and the prior step was selected. These are partial workflows, not verified partial visual correctness. |
| **Executed failure and recovery** | S0173, lines 5–16: an oversized fillet stopped step 1; step 2 then failed on a null world; substantive revisions preceded a successful step-3 render. S0168, lines 5–10 and 13–16: a null-world error was followed by a successful render, then a later revision timed out. |
| **No successful render in the recorded attempt** | S0169, lines 5–18: invalid fillet, timeout, and null-world error consumed three executions; a final world fix was returned but not executed. S0170, lines 5–10: an initial timeout and a simplified retry both timed out. Neither establishes scene-algorithm inferiority or the timeout bottleneck. |
| **CLI stop before visible construction** | S0051 and S0053, lines 2–4, and S0190, lines 2–4: student sessions exited 1 with zero recorded tool calls; stderr contents are unavailable. No program or patch is shown. This is not an evidenced empty patch or a reconstruction failure. |

The supplied cases do not establish a permission-denied or branch-policy stop. Read-only sessions and disabled tools are recorded constraints, not themselves proof of a permission failure. Likewise, `READY`, `DONE`, a missing response, and render-log file counts are not empty patches. Nonempty programs and executed changes are explicit in, for example, S0159, lines 14–17, and S0173, lines 8–15.

## What changed, and what was actually assessed

The successful render sequences contain actual student-authored scene programs, not just instructions. S0132’s code modeled room and bunk assemblies and procedural surfaces; later programs changed bunk orientation, camera and materials (lines 3–5, 9–11, 15–17). S0153’s kitchen interpretation included separate fixtures and procedural materials; its same-role review corrected fillet and material-selection issues before execution, followed by camera and towel revisions (lines 3–8, 12–15, 18–21). These descriptions establish **coded components and intended relationships**, not that the reference contained those objects, that every part was visible or connected, or that poses, textures, lighting and camera matched it.

The distinction matters even when a student reports improvement. In S0159, the student attributed an apparent obstruction to a Boolean bowl and executed a replacement plus shelf and light changes; step 2 rendered successfully (lines 10, 14–17). The alleged obstruction, its cause, the effect on shelf support, and any improvement remain unverified. S0162’s wall move, pillow changes and material changes were combined despite an initially conditional wall proposal (lines 10, 14–17, 22–25); individual effects cannot be isolated. Conversely, S0133 separated a local monitor change from a later color change while retaining camera and lighting, making the intended interventions more traceable, but not proving either improved fidelity (lines 9–11, 15–17).

Operational recovery is also not uniform. In S0154, simplifying repeated geometry and render settings followed an approximately 600-second timeout and preceded a successful step-2 render; a later camera revision timed out and step 2 was retained (lines 8–14, 17–21). Several changes coincided with recovery, so the timeout cause is not established. S0170 is a counterexample to assuming simplification guarantees recovery: its revised attempt also timed out (lines 5–10). S0169’s final null-world correction is a proposal without an observed execution, unlike S0173’s executed correction and successful render.

## Advice, receipt, validation and limits

The visible sources in this batch are student trajectories. **No distinct teacher-authored detection, diagnosis, proposed update, or teacher-directed execution is identified in the supplied reports.** Therefore teacher-specific receipt, adoption, acceptance and impact cannot be established; possible availability elsewhere is not actual receipt. This does not mean that the students received no guidance: runner requests supplied render images or error feedback and asked for comparison or repair. For example, S0158’s student produced its own visual diagnosis after a runner audit request, but the subsequent implementation session failed before a revised program appeared (lines 8–15). By contrast, S0155’s own diagnosis of a potentially occluded fixture was followed by an executed owner translation and successful render (lines 16, 18–21). The latter establishes self-review adoption, not teacher adoption or independent improvement.

S0153’s pre-execution review was explicitly the same student role, not an independent teacher (lines 4–7). Selection or `DONE` records acceptance by the workflow or student, not an independent quality verdict; S0174’s two failed builds were followed by a successful render and `DONE`, with no independent image assessment (lines 5–19). A counterexample to treating every stated review procedure as fully performed is S0146: its ostensibly camera-focused revision also changed lathe ownership handling (lines 10–12). Prompts, stated intent, actual code and observed results must remain separate.

## Transferable constraints and unresolved hypotheses

- **Execution evidence is narrower than scene validation.** A saved render demonstrates reported operability; a selection demonstrates a choice. Neither establishes object coverage, physical contact, collision-free assemblies, pose, texture appearance, camera match, lighting, occlusion or similarity. The audit has no image pixels for independent assessment.
- **Trace diagnosis through execution.** Concrete runtime errors can support observable repairs, as in the fillet and world failures in S0173. CLI exit codes without stderr, timeouts without a bottleneck, and student visual diagnoses without accessible images support weaker conclusions.
- **Treat scene-specific corrections as hypotheses.** Bunk rotations, kitchen occluders, workshop lighting, towel shape and chaise wall angles concern particular student interpretations. Their apparent benefits and even reference-scene identities are not independently established. Simultaneous changes, as in S0162, further limit attribution.

No causal superiority among conditions follows from these records, and missing formal scores remain unknown. This synthesis is an audit of observed history only; it is not capability generation, new Test feedback, or a proposed solution.
