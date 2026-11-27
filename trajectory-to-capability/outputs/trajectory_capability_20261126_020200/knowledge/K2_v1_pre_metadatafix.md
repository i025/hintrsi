<persistent_capabilities>

### 1. Establish the authorized starting state
- **Applicable problems:** Changes involving repository permissions, provider-specific instructions, or a required base revision.
- **Transferable knowledge/behavior constraint:** Check applicable instructions and the available starting state before editing. A missing base or explicit permission conflict is a blocker, not evidence that an implementation failed.
- **Candidate methods:** Inspect relevant instructions and refs; ask for clarification when the requested change cannot be reconciled with them.
- **Verification steps:** Confirm the selected base and permissions before changing files; report any unresolved blocker.
- **When not applicable:** Do not repeat checks already established by reliable task context.
- **Evidence sources:** D01 e1–3, e18, e29; D03 e3–7; D04 e1–6; D07 e3–5, e18. These observations do not establish that alternative decisions would have improved outcomes.

### 2. Reproduce at the relevant boundary
- **Applicable problems:** Bugs whose effects emerge through a public handler, API, parser, or downstream consumer.
- **Transferable knowledge/behavior constraint:** A local reproduction can show a specific state transition, but a passing example alone does not establish compatibility or completeness.
- **Candidate methods:** Construct a focused failing case through the relevant boundary, make the smallest appropriate repair, and rerun the same case.
- **Verification steps:** Inspect the resulting content and state, not just completion or activity counts; add targeted regression cases for material risks.
- **When not applicable:** A new feature without a preexisting failure may need contract examples rather than a failing bug reproduction.
- **Evidence sources:** D02 e30–33, e59–62; D05 e27–28, e77–79; D08 e36–37, e58–63. Visible successes were limited in scope.

### 3. Preserve contracts across representation boundaries
- **Applicable problems:** Conversation continuation, persisted model inputs, syntax transformations, and other workflows that pass state between components.
- **Transferable knowledge/behavior constraint:** Identify what must survive conversion and verify it where the next consumer receives it. Distinguish raw metadata from fitted transformations when both matter.
- **Candidate methods:** Trace required content, ordering, identity, schema, and meaning from producer to consumer; test both initial input and continuation or reload paths where relevant.
- **Verification steps:** Inspect the actual downstream request or restored input, and compare transformed output against the appropriate semantic contract.
- **When not applicable:** Skip boundary tracing when the task has no relevant cross-component or persistence transition.
- **Evidence sources:** D05 e49–57, e95–100; D06 e27–54, e68–70; D08 e52–59. The visible checks do not prove comprehensive preservation.

### 4. Check feedback and failure semantics
- **Applicable problems:** Multi-step execution, streaming, dispatch, or workflows that return results to a caller for continuation.
- **Transferable knowledge/behavior constraint:** Continuation activity alone does not show that the next step received correctly attributed results or errors.
- **Candidate methods:** Exercise success and relevant failure paths; inspect ordered chunks, identifiers, feedback content, and error propagation at the next boundary.
- **Verification steps:** Compare returned feedback with the originating operation and verify the expected distinction between recoverable results and surfaced errors.
- **When not applicable:** Omit multi-step feedback checks for purely local operations without such a contract.
- **Evidence sources:** D05 e58–61, e77–85; online teacher check 2. These checks do not cover every nested or malformed case.

### 5. Separate verification environment from product behavior
- **Applicable problems:** Tests or builds sensitive to working directory, generated artifacts, or existing baseline failures.
- **Transferable knowledge/behavior constraint:** Repairing test prerequisites enables a meaningful check but does not itself establish product correctness. A successful final shell command is not necessarily a successful earlier test.
- **Candidate methods:** Record required invocation context, inspect individual command results, and compare suspected preexisting failures against an appropriate baseline.
- **Verification steps:** Rerun the intended check under its expected conditions and report its result separately from setup and baseline observations.
- **When not applicable:** Avoid extra baseline work when the result and environment are already unambiguous.
- **Evidence sources:** D05 e64–71, e92–93, e112; D06 e57–63. Some displayed output was truncated.

### 6. Report the observed scope honestly
- **Applicable problems:** Any change with partial checks, unsupported cases, or unresolved failures.
- **Transferable knowledge/behavior constraint:** Distinguish implemented behavior, observed checks, environmental limitations, and unverified claims. Commits and broad existing suites are not proof of full specification coverage.
- **Candidate methods:** Summarize focused passes and failures, unrun checks, and known fallbacks without inferring omitted output or the cause of an unexplained outcome.
- **Verification steps:** Match each claim to an observed result and state material limitations or uncertainty.
- **When not applicable:** Scale the report to the task; do not add a lengthy checklist when a concise result is sufficient.
- **Evidence sources:** D02 e54–62; D05 e101, e109–112; D06 e75–81; D08 e68–82. The small, non-random evidence set does not establish causal transfer.

</persistent_capabilities>
