# E01: post-freeze historical baseline audit

**Scope and evidence.** This is a supplementary, read-only audit, excluded from K0/K1/K2 extraction, Selection, Test prompts, and updates. The historical solver was Ofox model `deepseek/deepseek-v4.1-flash-1017`, not the Codex CLI Terra/low model specified for new analysis. Launch record 3 identifies group B, independent attempt 1, `completed_fail`, and reward 0.

The supplied trajectory identifies every event by one-based ID, but long fields are clipped at 1,800 characters. Conclusions below use the visible excerpts and supplied patch and evaluation; missing field contents are not inferred. All event citations refer to `main_agent` in `/srv/lab-disks/disk2/users/xymo/hint-baseline-run/runs/baseline_ds1017_claudecode_a1_20261120_r1/infer_logs/claude-code-by-agents-recursive-delegation/turn_1/trajs.json`. The supplied patch is indexed at `/srv/lab-disks/disk2/users/xymo/hint-baseline-run/runs/baseline_ds1017_claudecode_a1_20261120_r1/infer_logs/claude-code-by-agents-recursive-delegation/turn_1/patch.diff`; the formal result is indexed at `/srv/lab-disks/disk2/users/xymo/hint-baseline-run/runs/baseline_ds1017_claudecode_a1_20261120_r1/eval_output/claude-code-by-agents-recursive-delegation/eval_result.json`. These are supplied records, not independently accessed files.

## Task, discovery, and intervention

The public task required recursive `delegate_task` execution, returning accumulated child text or an error in one JSON-stringified `tool_result`, matching the streamed tool-use ID, and re-invoking the delegator. It distinguished unknown-agent stream errors from child-run errors, required circular-delegation detection, and requested a new branch from `main` and a commit.

The visible record contains **no supplied task-teacher Hint**. The public contract itself was detailed. The hook messages at events 36, 64, and 72 denied historical Git/upstream lookup and directed the solver to local code; they were access restrictions, not evidence of a task-specific teacher intervention.

The solver independently searched the repository and inspected the handler, registry, provider types, tests, and frontend stream handling (events 8–32, 37–45, 74–80). It noticed that `/api/chat` and `/api/multi-agent-chat` use different handlers and reasoned about which flow the task targeted (events 39–45, 82–89). Its guesses about hidden tests and the intended handler were hypotheses, not established facts. Attempts to search Git refs and reflog were denied; a broad filesystem search timed out and its attempted termination returned exit 144 (events 35–36, 62–64, 70–72, 105–109).

## Historical changes and local validation

Event 103 records creation of `fix/recursive-agent-delegation` from the checked-out baseline. The patch and events 115–130, 161–190 show changes to `backend/handlers/multiAgentChat.ts`, `backend/providers/types.ts`, and `backend/providers/claude-code.ts`. The handler added recursive registry-based runs, text accumulation, streamed tool-use/result envelopes, JSON feedback, path-based cycle detection, and a ten-iteration bound. The provider type gained an optional tool-use ID, and the Claude Code provider propagated the SDK ID. Event 231 records commit `ac970fb`, with three files changed; event 243 shows a clean tracked status.

Validation was mixed:

- The baseline backend suite timed out initially; its later output reported 4 test files failed, 2 passed, and 5 tests failed, including visible image-handling failures (events 90–100). The piped command’s recorded exit code is not proof of a passing suite.
- Existing handler tests gave 6/7 passes. The abort-controller assertion also failed after the changes were stashed, supporting the solver’s claim that this observed failure was present on the baseline in that environment (events 133–138).
- An initial typecheck reported missing `cli/version.ts`; after generating that ignored file, `tsc --noEmit` returned 0 (events 140–141, 212–216). Modified-file lint produced no output (events 192–193).
- A temporary six-test mock contract suite passed after its placeholder test was corrected to consume the response stream; a second four-test edge-case suite passed. Both were removed (events 144–159, 195–196, 212–213, 234–240). These local mock checks are **not formal success** or proof of real-provider behavior. A separate OpenAI provider test failed during transformation with no tests collected; its cause is not established by the clipped output (events 218–219).

## Formal outcome and stop

The verifier applied the patch and reported **P2P 31/31**, **F2P 2/7**, partial **0.868421052631579**, binary reward **0**. Five F2P failures concerned child errors, executing the specified agent, empty output, unknown agents, and A→B→C delegation. The summary reports null or undefined expectations but does not establish their root cause. Verifier exit code 0 means the verifier ran, not that the solution passed.

Historical metadata records 88 turns, `end_turn`, terminal reason `completed`, no API error, and a final implementation report. It does not show a budget exhaustion or explain the formal failures. Duration was 5,356,269 ms, including reported API duration 3,491,197 ms. SDK usage fields report zero tokens and $0, with model cost basis `unknown`; the system also reports an estimated 2,410 thinking tokens. These are historical proxy fields, not new CLI billing or reliable evidence of actual historical paid cost. Actual historical token use and paid cost remain unknown.

## Interpretation and cautious comparison

Reusable constraints visible in the public contract include preserving call identity, distinguishing stream-level and tool-result errors, handling empty output, and checking the active delegation path. The registry, endpoint split, NDJSON envelopes, generated version file, and provider interfaces are task-specific. The solver’s independent inspection and mock tests show concrete investigation, but neither its local passes nor its design hypotheses establish transfer or the cause of the formal failures.

The supplied earlier D02 audit reports a different, teacher-reference-bearing attempt: P2P 31/31 and F2P 6/7, also binary reward 0, with one mock continuation reproduction and no completed requested commit. E01 had no visible task Hint and committed a larger three-file patch, but its F2P result was 2/7. Different models, runtimes, and budgets preclude a causal group comparison. A formally successful attempt would not necessarily teach more than a failure; neither source ablation nor an independent transfer test ranks these attempts’ learning value.
