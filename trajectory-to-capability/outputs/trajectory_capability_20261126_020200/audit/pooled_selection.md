## Scope and correction to the individual audits

This is a read-only pooled analysis of one Selection attempt per condition. The original public requirement, supplied here, resolves several uncertainties in the audits: the processor registry, message sanitization, aggregate-error handling, new branch and commit were expressly requested. Their presence is not unnecessary scope. The specified string/frame processing orders also differ deliberately. The public text requires sanitizing error and kept-cause **messages**, but does not expressly require sanitizing raw stack headers; K2’s visible unredacted header is therefore a privacy-relevant observation, not an established requirement violation.

The individual K0, K1 and K2 audits say no B0 trajectory was supplied to them; B0 is available for this pooled comparison. Their statements that the original requirements were unavailable should likewise not be carried forward without qualification.

## Outcomes and costs

Official F2P measures the new requirements and P2P retained functionality; these results are independent of the students’ local checks.

| Selection | Official success; F2P; P2P | Calls / model requests | Input / cached subset / output tokens | Wall / SDK seconds | SDK dollars, estimated |
|---|---|---:|---:|---:|---:|
| B0 | Yes; 80/80; 116/116 | 28 / 13 | 659,454 / 142,208 / 5,085 | 867.805 / 591.544 | $3.424395 |
| K0 | Yes; 80/80; 116/116 | 37 / 17 | 1,014,905 / 268,800 / 6,058 | 905.606 / 630.431 | $5.225975 |
| K1 | No; 79/80; 116/116 | 26 / 15 | 813,935 / 195,712 / 5,324 | 838.901 / 557.603 | $4.202775 |
| K2 | Yes; 80/80; 116/116 | 44 / 21 | 1,414,428 / 449,920 / 7,500 | 1,120.378 / 839.540 | $7.259640 |

All requested tool calls returned, usage was recorded for all model calls, and all runs ended normally. Input counts already include cached input; cache must not be added again. Dollar figures are SDK estimates, not settled CLI billing. These are observed per-run costs, not estimates of a stable efficiency effect. K2 used the most calls, tokens and time; K1 used fewer calls than B0 but more input tokens. Patch sizes were 12,737, 13,085, 13,375 and 13,749 bytes respectively, not a direct measure of useful work.

K1’s one official failure concerned a cause excluded by `classFilter` whose URL was nevertheless sanitized. Its final patch’s recursive use of the root sanitization flag is consistent with that failure; the record does not establish that K1 guidance caused it. All four retained 116/116 official P2P tests. The three full successes do not establish correctness beyond the official checks.

## Execution and unnecessary work

All four inspected existing error handling, made a branch, implemented a six-file change and committed. Each made a pre-edit frames probe: B0 and K0 `main_agent` 13–14, K1 11–12, K2 15–16. B0’s same behavior is important contrary evidence to attributing reproduction or source inspection to a library.

Local validation was not uniformly clean. B0’s full suite failed its performance threshold twice, then a filtered suite passed; two builds segfaulted, with later successful builds (`main_agent` 35–56). K0 had type-build failures subsequently corrected, three local performance failures, and passing targeted checks (37–72). K1 had passing builds and focused checks but a local performance failure (30–48). K2 had two compiler segfaults, two local performance failures, and successful targeted and cross-instance checks after further edits (39–86). No comparable pre-change timing establishes that any patch caused the performance failures, and the compiler crashes’ causes are unknown. Official success must not be substituted for a full local pass or vice versa.

Formatting changed unrelated `index.ts` layout in each audit, an identifiable extra diff and review burden, though not an established behavioral regression. No new permanent test file appears in the final patches; local scripts supplied focused evidence. K2’s additional cross-instance cause check and second commit addressed observed behavior, not demonstrably needless work. The public specification also makes branch creation, registry and aggregate handling required rather than extra.

## Library entry, behavioral consistency and attribution

B0 had no library. K0, K1 and K2 guidance appeared in both the actual prompt and first bridge request, respectively 644, 578 and 526 words. Entry establishes exposure, not adoption. K0’s cycle check and focused assertions, K1’s boundary inspection and disclosed local failure, and K2’s consumer-boundary and representation checks are consistent with portions of their guidance. They are also natural responses to this detailed task; B0 independently inspected and probed it. Some reads and commands were truncated, so unseen reasoning and complete coverage cannot be reconstructed.

K2 is not simply an identical K1 library with headings rearranged. Its representation rule explicitly says a safety comparison should use meaningful units and that physical layout can be too strict or too permissive; K1 separately calls for semantic preservation and idempotence but does not state that particular comparison constraint. K2 also makes the distinction between new input and continuation state explicit. These are substantive transferable formulations absent in that form from K1, although K1 overlaps broadly in boundary tracing, downstream inspection and transformation verification. Their different lengths and content confound any interpretation of the observed outcome as an isolated test of organization, wording or one rule. The serializer task itself specifies differing processing orders, and the record does not show K2’s comparison rule caused its success.

## Selection retention and Test

Apply the saved rule: drop only for leakage, absent injection, invalid format, or regression with clear causal evidence; otherwise retain unchanged. **Retain K0, K1 and K2 unchanged.** Their supplied libraries have the capability-wrapper format and their entry is evidenced. The supplied text and audits do not establish leakage or invalid format. K1’s official failure is real and its code gives a plausible proximate explanation, but one stochastic attempt and behavior also possible without guidance do not supply clear causal evidence of a library-induced regression. K0 and K2 succeeded officially; their local failures likewise lack established causal attribution. Retention is not a claim that the libraries helped.

For Test, the libraries were frozen beforehand. No Test outcomes are supplied here, and no retrospective selection or tuning is warranted.

## Findings, hypotheses and limitations

**Confirmed:** B0, K0 and K2 achieved official full success; K1 was partial, with all P2P tests passing. Every run encountered a local performance-test failure. Exposure and some rule-consistent behavior are visible for the library conditions; B0 exhibited overlapping behavior without a library. K2 included at least one distinct transferable constraint and incurred the highest observed resources.

**Unresolved hypotheses:** Guidance may have influenced particular checks or implementation choices, and K1’s recursive sanitization may explain its reported failing case, but neither library causation nor a reason for local timing and compiler failures is established.

**Specific limitations:** One attempt per cell cannot support statistical significance or long-term capability claims. Truncated outputs obscure some actions; official and local checks cover finite cases. Shared sources and budgets did not produce identical libraries, and there is no source ablation, so individual trajectories’ marginal learning value cannot be ranked. The cited audit files are `audit/posthoc_selection_superjson-error-stack-serialization_{B0,K0,K1,K2}.md`; their event references resolve to each corresponding `runs/capability_v1_selection_superjson-error-stack-serialization_<group>_r1/infer_logs/superjson-error-stack-serialization/turn_1/trajs.json`, with official results in that run’s `eval_output/superjson-error-stack-serialization/eval_result.json`, under `/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/`.
