<persistent_capabilities>

### 1. Verify guidance against the project and constraints
- **Applicable problems:** Tasks accompanied by proposed fixes, prior analysis, or reference material.
- **Transferable knowledge/behavior constraint:** Treat guidance as a hypothesis, not proof or authorization. Actual instructions, permissions, and observed project behavior take priority.
- **Candidate methods:** Inspect relevant boundaries and contracts before applying a proposal; clarify an instruction or missing prerequisite when required rather than silently substituting one.
- **Verification steps:** Check that the proposed change fits the inspected code and permitted scope; report unresolved blockers and any unconfirmed substitutions.
- **When not applicable:** Do not add a separate investigation when the task and observations already establish the relevant facts.
- **Evidence sources:** D01 events 1–3, 17–20, 29; D03 events 1–7; D07 events 2–18. These show constraints and interruptions, not implementation correctness.

### 2. Reproduce through a boundary and inspect the payload
- **Applicable problems:** Changes to request handling, delegation, callbacks, or other multi-component flows.
- **Transferable knowledge/behavior constraint:** A call count or success message alone does not establish that the right context, input, identity, and results crossed the boundary.
- **Candidate methods:** Create a focused reproduction through a public entry point; inspect requests and feedback before and after the change, including continuation and failure cases where relevant.
- **Verification steps:** Confirm the original failure, then check the changed behavior and payload contents, attribution, and error feedback. State which scenarios remain untested.
- **When not applicable:** For changes without a meaningful external or component boundary, use a proportionate direct check instead.
- **Evidence sources:** D02 events 30–33, 59–62; D05 online teacher checks 1–2 and events 49–57, 84–85, 95–98. These demonstrate focused checks, not complete coverage or established causal transfer.

### 3. Separate capability from request-specific availability
- **Applicable problems:** Systems exposing tools, delegates, plugins, or other optional capabilities.
- **Transferable knowledge/behavior constraint:** A registered capability is not necessarily supported, available, or authorized for a particular request. Preserve attribution and bound recursive flows where those concerns apply.
- **Candidate methods:** Trace capability advertisement, request-specific eligibility, execution, and feedback across interfaces; consider path-local cycle detection and depth limits for recursive delegation.
- **Verification steps:** Exercise an eligible target, an unavailable or unknown target, failures, and relevant cycles; check identity and feedback as well as execution.
- **When not applicable:** Nonrecursive, unconditional operations may not need delegation-specific checks.
- **Evidence sources:** D03 events 4–7 and supplied teacher material; D05 events 84–85, 108–109. The authorization warning was proposed guidance, not an observed implementation result.

### 4. Preserve persisted data contracts separately from transformations
- **Applicable problems:** Models or pipelines that save metadata and later accept raw inputs for inference or export.
- **Transferable knowledge/behavior constraint:** Ordered raw-input requirements, transformed model dimensions, and fitted preprocessing are distinct contracts. Saving a raw selection alone does not establish that fitted transformations are reused.
- **Candidate methods:** Trace data and metadata through training, persistence, loading, inference, export, and any public API; make ordering and missing or extra input behavior explicit where required.
- **Verification steps:** Test a save-and-reload path with representative raw inputs and verify both selection/order and any required fitted transformation; check error propagation.
- **When not applicable:** Tasks without persisted input contracts or preprocessing do not need this full trace.
- **Evidence sources:** Feature-schema teacher material; D06 events 31–35, 57–63, 68–70, 75–77. Some targeted output was truncated, so successful command statuses establish only their actual assertions.

### 5. Check formatter safety beyond output shape
- **Applicable problems:** Formatters or source transformations that must preserve meaning.
- **Transferable knowledge/behavior constraint:** Attractive output and idempotence do not by themselves prove semantic equivalence; parser representations may also be sensitive to layout.
- **Candidate methods:** Reproduce the unsupported or misformatted input, inspect its parsed representation, and choose a conservative equivalence check appropriate to the language. Decline unsafe cases when needed.
- **Verification steps:** Check semantic preservation and idempotence alongside representative expressions, comments, quoted constructs, and mixed statements as relevant; run existing regression tests.
- **When not applicable:** Purely presentational changes with no source transformation need not introduce a new equivalence mechanism.
- **Evidence sources:** D08 events 18–25, 34–37, 52–63, 78–82. Passing checks did not establish coverage of every dialect or mixed case.

### 6. Separate verification results from environment and outcome claims
- **Applicable problems:** Any implementation with tests, generated prerequisites, or environment-dependent behavior.
- **Transferable knowledge/behavior constraint:** A commit or selected passing checks is not proof of complete success. Report observed failures, blocked checks, baseline comparisons, and incomplete work independently.
- **Candidate methods:** Run focused tests and relevant regressions; identify required working directories or generated artifacts; compare a failure against the baseline when practical.
- **Verification steps:** Inspect the actual test result rather than relying on a compound command's final status; distinguish a confirmed pre-existing failure from an uncertain comparison and disclose truncated output.
- **When not applicable:** Scale the checks to the task; avoid extensive environment investigation when a direct, reliable verification suffices.
- **Evidence sources:** D05 events 62–71, 81–93, 99–101, 112; D06 events 57–63, 79–81; D08 events 78–82. Formal outcomes and visible checks differed, and the reasons for unsuccessful outcomes are not established.

</persistent_capabilities>
