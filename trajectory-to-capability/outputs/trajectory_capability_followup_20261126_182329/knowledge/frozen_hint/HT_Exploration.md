<persistent_capabilities>

## 1. Trace integration boundaries before modifying behavior

**Applicable problems:** Changes spanning handlers, registries, shared types, providers, and consumers, especially where an apparent local defect may cross several interfaces.

**Transferable knowledge/behavior constraint:** Map the producer, intermediate representation, consumer, and existing conventions before assuming the visible entry point owns the whole behavior. Use targeted searches when broad searches obscure relevant results.

**Candidate methods:** Inspect call sites and type definitions; follow representative data and error paths; compare existing integrations and tests; narrow searches by component or symbol.

**Verification steps:** Check that the resulting map accounts for both directions of communication and identifies the boundary where each transformation occurs. Treat an incomplete map as a hypothesis, not proof of the defect’s location.

**When not applicable:** A self-contained change with no meaningful interface or data flow may not justify a broad integration survey.

**Evidence sources:** Development descriptions, events 1–24: boundary inspection and a broad search followed by narrower searches; general knowledge of interface tracing.

## 2. Preserve recursive execution protocol invariants

**Applicable problems:** Recursive orchestration, delegated operations, or workflows that must return child results to a suspended caller.

**Transferable knowledge/behavior constraint:** Define termination and cycle detection per active path; preserve request/result identity; distinguish empty output from failure; and make child versus outer error-channel semantics explicit. These are design constraints, not universally verified properties.

**Candidate methods:** Track active ancestry, accumulate output, correlate calls and results, and explicitly model resumption and error propagation.

**Verification steps:** Construct small observable reproductions for instruction delivery and feedback. Where feasible, add negative, repeated, nested, and continuation cases. Report which paths actually ran rather than inferring coverage of all edge cases.

**When not applicable:** Flat operations without delegation, correlation, or continuation do not require the full recursive model.

**Evidence sources:** Development descriptions, events 25–44: one simulated path initially failed instruction delivery and later passed; events 29–38 describe the implementation attempt. General knowledge supports the proposed edge cases.

## 3. Exercise the real adapter boundary

**Applicable problems:** Streamed integrations where an internal mock can satisfy a contract that a provider adapter may not advertise or produce.

**Transferable knowledge/behavior constraint:** Verify both capability advertisement in outgoing requests and translation of incoming streamed events; ensure continuation retains context required by the receiving protocol. A cooperative handler mock alone cannot establish adapter compatibility.

**Candidate methods:** Simulate a streamed structured call through the adapter; inspect request summaries and emitted events; compare identity and arguments with consumer requirements.

**Verification steps:** Check both directions before and after a change, then rerun relevant handler and type checks. Treat live-service behavior, other adapters, and untested stream fragmentation as unresolved unless separately exercised.

**When not applicable:** Systems with no adapter or streaming translation boundary need a test suited to their actual interface instead.

**Evidence sources:** Development descriptions, events 46–72: the first simulation printed no advertised tool and only completion; a later simulation showed an advertised tool and structured call. General integration-testing knowledge.

## 4. Report verification limits and preserve regression value

**Applicable problems:** Changes with mixed test results, generated dependencies, temporary reproductions, or noisy formatting changes.

**Transferable knowledge/behavior constraint:** Separate command or environment failures from behavioral evidence, distinguish observed failures from unconfirmed baseline causes, and avoid treating a formal pass as exhaustive correctness or causal learning.

**Candidate methods:** Correct invalid test invocations, generate required artifacts, run focused and broader checks, review the diff, and retain targeted regression tests where feasible.

**Verification steps:** Record commands and outcomes, including unresolved failures and removed temporary checks; inspect unrelated diff expansion before finalizing. A missing comparison result is not a zero or evidence of an advantage.

**When not applicable:** A purely descriptive task with no executable artifact may not warrant test execution, though evidence limits still matter.

**Evidence sources:** Development descriptions, events 41–47 and 73–87: a missing generated file, failed test runs, reported unresolved suite failures, removed reproductions, and a commit. The reported formal checks passed, without establishing exhaustive correctness.

</persistent_capabilities>
