# Historical evidence synthesis: scene / historical_r1_C2_start

## Coverage and scope

This batch covers all **28 supplied student-trajectory files**, S0281–S0308: 12 test, four selection, and 12 development files. Seven files have two audit chunks; both chunks are supplied for each. Counts describe files, including any copies, not necessarily independent trials. The evidence is the model-reviewed audit reports and inventory, not a fresh inspection of raw trajectories or image pixels. Citations below identify original files relative to this common prefix:

`/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/scene_rsi_v3/results/historical_r1_C2_start/`

All cited paths end in `/trajectory.jsonl`; line numbers are original JSONL event lines. The reports do not provide independent visual assessments or formal reconstruction scores. Missing scores are **unknown**, not zero, and old model cost cannot be recovered from absent records.

## Evidence matrix

| Files and original path suffixes | Observed attempt and outcome | Evidence |
|---|---|---|
| S0281 `test/bw_0023/1` | Three builds and renders succeeded; step 3 selected after two student-described revisions. Final visual correctness unknown. | Lines 6–10, 13–20, 23–24, 26, 28–30. |
| S0282 `test/bw_0023/2` | Read-only CLI session timed out before a program, build or render; downstream outcome unknown. | Lines 1–4. |
| S0283–S0284 `test/bw_0056/{1,2}` | Three successful builds/renders each; H revised interpreted cleanroom figures, screen and framing; final match unknown. | Each: lines 3–4, 11–14, 21, 23–24, 26, 28–30. |
| S0285–S0286 `test/bw_0039/{1,2}` | Three successful builds/renders each; H revised an interpreted renovation scene. In S0285, step-2 procedural materials were created but not assigned. | Each: lines 3–4, 13–14, 21, 23–30. |
| S0287–S0288 `test/bw_0011/{1,2}` | Three successful builds/renders each, with mural, cabinet and framing revisions; final match unknown. | Each: lines 3–4, 13–14, 21, 23–30. |
| S0289–S0290 `test/bw_0016/{1,2}` | Three successful builds/renders and step-3 selection each; H changed interpreted workshop framing and contents. | Each: lines 3–4, 13–14, 21–24, 26, 28–30. |
| S0291–S0292 `test/bw_0005/{1,2}` | Three successful builds/renders each; classroom interpretations and furniture/camera revisions are not independently verified. | Each: lines 3–4, 9, 11, 13–14, 19, 21, 23–30. |
| S0293 `selection/bw_0045/1`; S0294 `selection/bw_0017/1` | Three successful builds/renders and step-3 selection each; interpreted barn and industrial scenes respectively. | Each: lines 3–4, 13–14, 23–24, 26, 28–30. |
| S0295–S0296 `selection/bw_0031/{1,2}` | Initial API/code failures prevented rendering; traceback-informed repairs produced successful step-2 and step-3 renders. Final visual quality unknown. | S0295 lines 6–8, 10–17, 18–27; S0296 lines 3–8, 10–17, 18–27. |
| S0297–S0300 `development/commons_104864364/1`, `commons_189918915/1`, `commons_31294395/1`, `commons_187101683/1` | Three successful builds/renders each, with student-reported comparisons and executed revisions. S0298 reversed a camera roll after reporting the prior direction was wrong. | Each: lines 3–4, 11, 13–14, 21, 23–24, 26, 28–30. |
| S0301–S0304 `development/commons_92056365/1`, `commons_105241439/1`, `commons_113438548/1`, `commons_109923183/1` | Three successful builds/renders and step-3 selection each. S0302’s final code places desk legs and chair components below the floor plane, a concrete geometric concern despite successful execution. | Each: lines 3–4, 13–14, 23–24, 26, 28–30. |
| S0305–S0308 `development/commons_192968130/1`, `commons_130842254/1`, `commons_96943062/1`, `commons_118588033/1` | Three successful builds/renders each, with scene-specific camera, material or object revisions; no final visual verification. | Each: lines 3–4, 11, 13–14, 21, 23–24, 26, 28–30. |

## Comparison of outcomes

**Technical success is common, but task success is not established.** Twenty-seven files record a successful final build/render and step-3 selection, including the two that first failed. Selection and `ok: true` validate execution and artifact production, not resemblance to the reference. For example, S0281, `test/bw_0023/1`, lines 23–24 and 28–30, records a stair rotation and bubble adjustment followed by a successful render, but no subsequent visual assessment. Across the group, image pixels are unavailable to this audit; object coverage, occlusion, part contact, pose, material appearance, camera match and lighting quality remain unverified.

**Failure followed by repair is distinct from interruption.** In S0295, `selection/bw_0031/1`, lines 6–8 and 10–17, a world-node access exception stopped the first build; H received the traceback and corrected the access before a successful render. In S0296, `selection/bw_0031/2`, lines 3–8 and 10–17, an invalid `rod()` call stopped execution before rendering; H changed argument usage and explicitly noted that visual comparison was not yet possible. These are observed initial code/API failures and successful technical repairs, not proof of a correct final scene.

S0282, `test/bw_0023/2`, lines 2–4, instead timed out in the model/CLI session after approximately 900 seconds, with zero observed tool calls or file changes and no returned program. It is an interrupted attempt, not a demonstrated algorithmic reconstruction failure or an empty patch. Backend activity and timeout cause are unknown. The supplied group provides no observed empty patch, permission denial or branch stop; none should be substituted for the recorded CLI timeout. No independently established partially correct final reconstruction is available, although intermediate technical progress and student-reported discrepancies are visible.

## Advice, receipt and observed behavior

The records are student trajectories, not separate teacher-role transcripts. General reconstruction instructions were available and received, and the runner supplied execution results, tracebacks or image-comparison requests. No distinct teacher detection, diagnosis, proposed update, student receipt or adoption is visible in these records. That is a visibility finding, not proof that no teacher advice existed elsewhere.

Actual response to runner feedback is nevertheless evidenced. S0284, `test/bw_0056/2`, lines 11–14 and 21–24, shows images supplied, H’s own diagnoses of scale and screen orientation, and executed camera, figure and screen changes. S0296 shows receipt and use of a traceback before its later render-based diagnosis. These sequences establish receipt, attributed diagnosis and executed update; successful subsequent rendering establishes technical validation, and selection establishes a runner selection event—not independent acceptance of visual quality. Zero recorded in-session tool calls does not mean images were unavailable: they were supplied directly in requests, while the runner executed programs, as illustrated by S0302, `development/commons_105241439/1`, lines 2, 11–12 and 21–22.

## Transferable constraints and limits

* **Separate execution, appearance and geometry evidence.** Named assets and child hierarchy show intended structure, not contact or image fidelity. S0302’s below-floor components are a counterexample to treating a successful render as a geometric check. S0285’s unassigned step-2 materials likewise show that creating a material does not establish its application (`test/bw_0039/1`, lines 13–14).
* **Distinguish a reported diagnosis from an implemented change and an improvement.** S0287, `test/bw_0011/1`, lines 23–24, reports a mural-width concern but does not widen the panel. S0294, `selection/bw_0017/1`, lines 23–24, reports misplaced machinery while processor and tank coordinates remain unchanged. These counterexamples prevent equating every stated concern with its direct correction. Simultaneous edits also prevent attributing any unobserved improvement to one change.
* **Treat effective settings as an observation, not an intention.** S0288, `test/bw_0011/2`, lines 24 and 29, requested 48 samples while the render log reported 16. S0281, lines 3–4, also set engine and resolution despite instructions against changing runner settings; effective final settings are not established.
* **Keep local hypotheses local.** S0298’s reported roll reversal, S0283’s intended hand-to-screen contact, and S0307’s carpet-shader selection are case-specific attempts, not validated general fixes (respectively `development/commons_189918915/1`, lines 21, 23–24; `test/bw_0056/1`, lines 21, 23–24; `development/commons_96943062/1`, lines 13–14, 23–24). Their final visual effect remains unknown.

The group supports an audit of observable workflow, repairs and execution outcomes, not a causal superiority claim or a ranking of reconstruction quality.
