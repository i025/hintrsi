# Evidence report: D07 — igel-persist-feature-schema

## Scope and goal

The supplied record identifies the student trajectory as `/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/runs/codex_parallel_12/lanes/codex_parallel_12_lane1/codex_parallel_12_lane1_H_r1/infer_logs/igel-persist-feature-schema/turn_1/trajs.json`. The patch and evaluation are indexed at the adjacent `turn_1/patch.diff` and `eval_output/igel-persist-feature-schema/eval_result.json` paths. This report relies on the supplied parsed sequence, actual system request, patch and evaluation, not an independent inspection of those paths or the separately listed teacher archives.

The original task request is not included. The task identifier, the student’s opening statement and the captured system reference support a goal of persisting and applying a feature-schema contract across training and later workflows; the full original requirements and any instruction concerning the base branch are unavailable. The student said they would trace training, inference and export before implementation (**main_agent, event 1**).

## Teacher knowledge and adoption

The captured actual system prompt, `turn_1/system_prompt_actual.json`, contained a problem-solving reference. It explained that ordered raw feature selection was not persisted, distinguished raw schema from transformed input width, and cautioned that schema persistence alone would not persist encoding, imputation or scaling. It suggested applying a training schema before evaluation and prediction preprocessing; separating targets; handling clustering, validation, dropped-feature metadata, aliases and conflicts; tracing artifacts and older-model compatibility; propagating errors to the API; and testing isolated end-to-end workflows. It named five source files and the existing test directory as location clues. It also directed independent verification and prohibited locating the reference file or benchmark internals.

There is **no direct evidence of implementation adoption**: the student made no patch. The student did search and read the five named source files (**events 4–5, 7–11, 13–17**), consistent with the location clues, but those files also naturally fit the stated task. The sequence cannot establish that the reference caused those choices, nor that any suggested design was adopted. The shared teacher-material paths are listed, but their contents and any separate teacher request are not supplied; they are not treated as audited. No later performance or long-term learning is evidenced.

## Operations, exploration and changes

- **Events 2–3:** The student inspected `/app`, Git status, local branches and the latest commit. The checkout was detached at `bf4544d`; `master` was the only listed local branch, and status produced no changes.
- **Events 4–5:** They checked local and `origin/main` references and searched the named files for feature/workflow terms. Both `show-ref` checks printed fatal invalid-ref messages; the combined shell call nevertheless reported `is_error: false` because subsequent commands ran.
- **Events 6 and 12:** They checked remotes, all branches, remote HEAD, status and project-instruction filenames. Output showed only detached HEAD and `master`; the tool interpreted the final search as “No matches found.” No remote was displayed.
- **Events 7–11 and 13–17:** They read `igel/preprocessing.py`, `igel/igel.py`, `igel/configs.py`, `igel/constants.py` and `igel/servers/fastapi_server.py`. The inspected code showed, for example, that processing converts data to arrays, fit writes a description, and export uses a fixed ONNX input width. This was source exploration and branch verification, not a test of a proposed fix. No student test, edit, commit or behavioral validation appears in the complete sequence.
- **Event 18:** The student stopped and asked for `main` or confirmation to use the current checkout. The supplied patch is empty, with indexed size **0 bytes**; no project file or behavior was changed. This corroborates the student’s report of no changes, rather than relying on that report alone.

## Outcome and limits

The indexed status is **not_solved**. The formal evaluation reports **F2P 0/24**, **P2P 2/2**, reward/binary **0**, and partial score **0.07692307692307693**. The partial score must not be read as evidence of a partially correct schema implementation: the patch is empty, and the two passing P2P tests account for the reported 2-of-26 aggregate. The evaluation exit code was 0 despite failed F2P checks. Its supplied tail includes served-prediction tests failing with `AttributeError: 'NoneType' object has no attribute 'to_csv'` at `igel/igel.py:670`; the tail does not establish every failure’s cause.

This is an **early stop seeking clarification over the unavailable branch**, with an empty patch—not a formally solved attempt, a demonstrated partial fix, or a normal failure of an attempted algorithm. The missing refs were real Git lookup failures, but the session was not technically interrupted: result metadata says `success`, `is_error: false`, `stop_reason: end_turn`, and `terminal_reason: completed`, with no permission denials or recorded API errors. Whether the missing `main` truly prevented authorized work cannot be determined without the omitted task request; using the detached checkout might have been possible, but was not confirmed.

Reported duration was **81.841 seconds**, API duration **55.619 seconds**, and external wall time **93.094 seconds**. Usage was **119,956 input and 540 output tokens**, cost **$0.61328**, nine turns; the model metadata lists a **1,000,000-token context window** and **32,000 maximum output tokens**. No timeout or usage-limit stop is recorded.

The transferable observed practice is verifying repository state and reading relevant workflows before changing code; its effectiveness here was limited by stopping before implementation or tests. The missing branch, fixed export width and particular API failure are task-specific observations. Any claim that the student would have solved the task with a different base, or that teacher guidance produced durable learning, remains unverified.
