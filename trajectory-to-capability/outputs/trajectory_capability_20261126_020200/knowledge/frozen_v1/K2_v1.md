<persistent_capabilities>

### 1. Inspect state across transitions
- **Applicable problems:** Workflows where a later request, operation, or component consumes state produced earlier.
- **Transferable knowledge/behavior constraint:** Preserve the information and ordering the next consumer needs. Distinguish new input from continuation state rather than assuming prior context replaces it.
- **Candidate methods:** Capture the representation immediately before and after the boundary; compare ordinary requests with continuations, including mixed input types where relevant.
- **Verification steps:** Exercise both paths and inspect the next consumer’s actual input, not just whether it was invoked.
- **When not applicable:** No meaningful state crosses the boundary, or the task explicitly requires discarding it.
- **Evidence sources:** D05 events 49–57, 95–100; D02 events 30–33, 59–61. D05’s later saved-context change was not separately exercised by the displayed probe.

### 2. Check identity and failure feedback end to end
- **Applicable problems:** Delegation, callbacks, or other multi-step operations requiring responses to be associated with requests.
- **Transferable knowledge/behavior constraint:** Preserve request identity through the round trip and distinguish materially different failure classes in feedback to the consumer.
- **Candidate methods:** Trace identifiers and payloads through a mock or public entry point; exercise success, worker failure, and unknown targets where relevant.
- **Verification steps:** Compare the outward result and the next consumer’s input; test repeated cycles if supported. Call count alone is insufficient.
- **When not applicable:** There is no associated response or downstream consumer, or the task defines different error semantics.
- **Evidence sources:** D05 events 84–85, 108–109; the probes followed an online teacher prompt.

### 3. Carry input contracts into later use
- **Applicable problems:** Systems that learn or establish an input schema and later accept fresh data for evaluation or execution.
- **Transferable knowledge/behavior constraint:** A later consumer should receive inputs consistent with the established selection, names, and order; raw inputs and transformed representations may have different contracts.
- **Candidate methods:** Make the contract explicit at the boundary, persist it when needed, and validate or reorder later inputs according to the task’s semantics.
- **Verification steps:** Compare the inputs actually used during establishment and later use; exercise relevant aliases, missing or extra inputs, and error propagation.
- **When not applicable:** Inputs have no persistent contract, or the task specifies a different reconciliation policy.
- **Evidence sources:** D06 events 25–26, 27–54, 68–70. Some targeted output was truncated, and the recorded result was partial.

### 4. Preserve meaning when changing representation
- **Applicable problems:** Formatters, serializers, and other transformations that alter surface structure while expected to retain meaning.
- **Transferable knowledge/behavior constraint:** A safety comparison must reflect the representation’s meaningful units; physical layout alone may be either too strict or too permissive.
- **Candidate methods:** Inspect how the existing parser or tokenizer represents the input; use an appropriately scoped equivalence check without disabling safety for unrelated categories.
- **Verification steps:** Check representative semantic edge cases, transformation idempotence, focused tests, and existing regression suites.
- **When not applicable:** The task intentionally changes meaning or has no meaningful equivalence relation.
- **Evidence sources:** D08 events 18–21, 53–63, 78–79. Focused checks passed, but the formal record also reported change and preservation failures whose causes are not visible.

</persistent_capabilities>
