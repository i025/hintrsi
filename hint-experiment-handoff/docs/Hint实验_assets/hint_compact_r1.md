[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis
Anko's grammar only accepts bare-identifier parameter lists, and the lexer rejects the `=` token inside function headers. The VM binds arguments purely by position/arity with no concept of missing values. The generated `parser.go` is a checked-in goyacc artifact and goyacc is unavailable in this environment, so grammar-only changes won't take effect. Changing AST/VM also isn't enough — the lexer would still reject `=` in a parameter list. The viable route is a **source-level rewrite** at the parse entry: convert default-arg function heads into ordinary variadic functions and inject a prologue that does the arity check, per-parameter binding, and default evaluation.

## Suggested Directions
- The core logic may need to live in a **new file in `package parser`** — this file owns: scanning source while skipping strings/comments, recognizing `func`, splitting top-level arguments and top-level `=`, validating declarations, and building a rewritten header plus a prologue string.
- The rewrite should hook into the lowest public parse entry (`Parse`) rather than only `ParseSrc`, so direct `Scanner` callers and `core.load` are all covered; `ParseSrc` then inherits it automatically.
- A function header with no top-level `=` must be returned byte-for-byte unchanged — this preserves existing syntax errors (e.g., malformed comma forms) and VM behavior. Key boundary checks: keyword boundary detection, leading `=` only, empty param lists, trailing commas.
- In the prologue, bind each parameter with `var` (to create function-local bindings and avoid overwriting outer variables); evaluate defaults left-to-right at call time, unmodified, so later defaults can reference earlier parameters and outer scope.
- Arity checks should run *before* any default evaluation. Error messages for upper bound vs. lower bound (`requires at most` vs `at least`) must be exact, and errors must be `*parser.Error` with `Fatal=true` and the canonical message — avoid `fmt.Errorf` wrapping.
- Worth noting: `toString` is defined via `core.Import`, not present in bare `vm` test environments — concatenating the integer directly will still produce the same message and is safer.
- Also worth noting: an empty original function body means the last prologue statement becomes the implicit return value — consider a harmless trailing expression statement to preserve `nil` return. Be aware nested functions inside default expressions aren't recursively rewritten.

## Key Location Clues
- `parser/default_args.go` (new file): all scanning/validation/prologue-generation logic; must be in `package parser` to reuse lexer helpers and `Error`.
- `parser/lexer.go`: contains `Parse` (the preferred rewrite hook), `ParseSrc`, `Scanner`, `Error`, and `isLetter`/`isDigit`.
- `core/core.go`: the `load` builtin currently builds a `Scanner` manually — routing it through `ParseSrc` keeps preprocessing uniform; preserve its `*parser.Error` filename/panic handling.
- `parser/parser.go.y` / `parser/parser.go` / `parser/Makefile`: grammar and checked-in generated parser — cannot be regenerated here, so understanding (not editing) is the point.
- `vm/vmExprFunction.go`: `funcExpr` / `makeCallArgs` — explains why a rewritten variadic function receives all call arguments as a slice, and why VM needs no changes.
- `ast/expr.go` (`FuncExpr`): no new fields needed; rewritten functions remain plain `Params` + `VarArg`.
- `vm/vmStmt.go` (`ThrowStmt`): the prologue's `throw` for arity errors; message propagates to `err.Error()`.
