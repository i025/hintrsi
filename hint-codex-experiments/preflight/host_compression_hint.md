[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis

Embedded ANSI resets cancel an enclosing style, while raw byte measurement and truncation cannot reliably distinguish terminal controls from visible Unicode text. A shared ANSI-aware interpretation is needed to keep styling, display width, truncation, and terminal state consistent without changing default behavior.

## Suggested Directions

- Suggest first tracing how styles are constructed and rendered, including how output-level defaults reach styles and template helpers.
- The core lies in shared ANSI-aware parsing that preserves control sequences while distinguishing visible text, resets, and hyperlink state.
- Consider grapheme-aware display width and stateful truncation, including tails, terminal cleanup, malformed escapes, and exact-fit input.
- Worth noting that style and output truncation have distinct ASCII behavior, and existing defaults and value-style chaining should remain compatible.
- Test nested resets, control sequences, Unicode widths, option inheritance, templates, and ASCII entry points before running the full suite.

## Key Location Clues

- `ansi/parser.go` — The proposed home for shared ANSI tokenization and sequence classification.
- `ansi/hyperlink.go` — The proposed home for hyperlink-state tracking.
- `ansi/util.go` — The proposed home for ANSI detection, stripping, width calculation, and truncation.
- `ansi_truncate.go` — A possible root-package truncation entry point.
- `ansi_util.go` — A possible home for root-package utility wrappers.
- `style.go` — Style rendering, preservation settings, and style-level truncation may need attention.
- `output.go` — Output defaults, style construction, and output-level truncation meet here.
- `templatehelper.go` — Template helpers and their ASCII alternatives may need consistent option propagation.
- `profile.go` — Existing profile-based style construction provides context for compatibility.
- `hyperlink.go` — The existing hyperlink format provides context for ANSI handling.
- `style_test.go` and `templatehelper_test.go` — Existing tests illustrate relevant conventions.
- `go.mod` — The existing Unicode dependency may support display-width handling.
