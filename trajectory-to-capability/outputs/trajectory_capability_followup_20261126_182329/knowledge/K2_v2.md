<persistent_capabilities>

## 1. Preserve usable state during continuation

**Applicable problems:** Refinement, resumption, incremental processing, or other operations where a later consumer needs earlier results alongside new input.

**Transferable knowledge/behavior constraint:** Preserve the prior values, ordering, and context required by the consumer. When the contract distinguishes successful and failed components, repair failures without unnecessarily replacing successful work. This is an inferred shared constraint, not evidence that the tasks used the same implementation.

**Candidate methods:** Inspect what the next consumer actually receives; represent successful, failed, and nested state distinctly when needed; compare ordinary and continuation paths.

**Verification steps:** Exercise a partial result before and after refinement, checking both the repaired component and retained successful values. Check relevant nested cases separately; bound conclusions to those exercised.

**When not applicable:** Prior state is intentionally discarded or the operation has no continuation contract.

**Evidence sources:** Cattrs / `main_agent` / 41–42, 63–64 observed a passing reproduction and a nested child retaining a structured value; D05 events 49–57, 95–100 and D06 events 25–26, 27–54 provide related development descriptions. D05’s later saved-context edit was not separately probed.

## 2. Preserve meaningful identity across transitions

**Applicable problems:** Comparing entities across lifecycle changes, snapshots, serialization, or other boundaries where surface labels may change or collide.

**Transferable knowledge/behavior constraint:** Use the identity meaningful to the consumer rather than assuming a name or other convenient representation is stable and unique. Identity policy depends on the contract.

**Candidate methods:** Inspect representations on both sides of the transition; identify the intended continuity and distinguish it from display labels; compare independently captured states.

**Verification steps:** Test both retained identity across the relevant transition and distinction between separate entities. Include lifecycle and eviction cases where applicable, and state explicitly which transitions were not exercised.

**When not applicable:** The contract deliberately treats each representation as a new entity, or no identity comparison is needed.

**Evidence sources:** Snapshot / `main_agent` / 33–45 describes an identity-field change and a passing selected probe; the probe did not establish a hooked running-to-terminated identity match. D05 events 84–85, 108–109 describe teacher-prompted identifier and error checks.

## 3. Reconcile representations without weakening contracts

**Applicable problems:** Typed fields, schemas, serialized forms, or formatted syntax crossing representation boundaries.

**Transferable knowledge/behavior constraint:** Preserve contractually meaningful names, types, ordering, and behavior while adapting representations. Reconciliation should not bypass unrelated validation; the appropriate policy is task-specific.

**Candidate methods:** Inspect existing adapters and helpers before introducing a new conversion path; consider optional wrappers, aliases, nested structures, generic types, and missing or extra input as relevant.

**Verification steps:** Reproduce a relevant mismatch, check the adapted case, and rerun earlier reproductions after subsequent edits. Treat focused passes as evidence for those cases rather than universal equivalence.

**When not applicable:** No representation boundary exists, or the intended contract explicitly changes the information being carried.

**Evidence sources:** Cattrs / `main_agent` / 43–45, 47–62, 65–84 observed a wrapper repair and a generic repair that initially regressed, then passed, the basic reproduction. D06 events 68–70 were partly truncated; D08 events 53–63, 78–79 had focused passes alongside unexplained formal failures.

</persistent_capabilities>
