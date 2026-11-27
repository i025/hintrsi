# Evidence report: D05

## Sources and scope

The supplied records identify one student attempt, group I, round 2, task `claude-code-by-agents-recursive-delegation`. Its trajectory is:

`/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/runs/codex_parallel_12/lanes/codex_parallel_12_lane0/codex_parallel_12_lane0_I_r2/infer_logs/claude-code-by-agents-recursive-delegation/turn_1/trajs.json`

The same turn directory contains the captured `system_prompt_actual.json`, `online_teacher_events.json`, `online_teacher_state.json`, and `patch.diff`. The indexed evaluation path is `/srv/lab-disks/disk2/users/xymo/hint-codex-experiments/runs/codex_parallel_12/lanes/codex_parallel_12_lane0/codex_parallel_12_lane0_I_r2/eval_output/claude-code-by-agents-recursive-delegation/eval_result.json`. This report uses the supplied contents, not an inspection of additional archives. All numbered events below are **main_agent** events.

## Goal and actual work

The task, as evidenced by the task identifier, captured guidance, and work, was to implement recursive agent delegation: execute delegated work, return results or errors to the delegator, and let it continue, including Anthropic tool-call support. The original user task text is not supplied, so any additional requirements are unknown.

The agent searched provider integrations and created branch `recursive-agent-delegation` from `main` (events 1–3, 9). It read the handler, provider contracts and adapters, registry, shared types, and existing tests (events 4–24). A mocked baseline reproduction returned only one provider call instead of a delegation round trip (events 27–28).

The nonempty final patch changed three files (events 105–107; supplied patch):

- `backend/providers/types.ts`: optional delegation capability, tool definitions, continuation flag, and tool-use identity.
- `backend/providers/anthropic.ts`: tool advertisement, streamed tool-input parsing, and reconstruction of tool-use/result context.
- `backend/handlers/multiAgentChat.ts`: recursive execution, result/error feedback, input and cycle checks, shared cancellation, and a 20-round continuation bound. It also preserves base64 image content in reconstructed context.

Other providers were not replaced. The agent generated `backend/cli/version.ts` locally to type-check, but it is not in the committed three-file patch (events 70–71, 107). Commit `e7c4f0b` recorded 137 insertions and 44 deletions (events 110–111).

## Teacher knowledge and adoption

The **captured actual system prompt**, rather than the names of planned shared hint files, establishes initial teacher knowledge. It identified the missing handler/provider round trip, suggested optional provider-neutral capabilities, cycle detection, bounded continuation, cancellation, identity and context preservation, and named relevant files. It also warned not to replace another provider merely because it existed. It required independent source inspection and verification.

Two online checks delivered additional advice; neither stopped the session. Check 1, at tool count 20, asked the student to inspect a provider request containing prior context plus a new instruction or image, ensuring input was retained without continuation duplication. Check 2, at tool count 40, asked it to inspect the delegator’s next request and compare feedback and tool-use identity for successful, failing, and unknown workers. The online teacher state reports two checks; the separate shared teacher-material paths are pointers, not evidence that their contents were received.

There is direct behavioral evidence of adoption, not merely advice or self-report. Following check 1, the agent’s request probe showed that its then-current condition dropped both the new instruction and image (events 49–50); it revised the condition and introduced an explicit continuation flag (events 52–57). A later mocked request inspection showed the initial instruction and image present and a continuation containing the matching tool-use/result without a duplicate new message (events 95–97); it then added image preservation to handler context (events 98–100). Following check 2, events 84–85 implement precisely the requested success, worker-error, and unknown-agent comparisons, asserting result content, error flag, and matching tool-use ID. These actions support adoption within this attempt, not proof that the teacher caused every design choice or that durable learning occurred.

## Independent exploration and validation

The student read the named source before editing and also inspected the OpenAI and Claude Code adapters and related chat handler (events 15–24). Its baseline reproduction and post-change rerun showed one versus three mocked provider calls, with worker and orchestrator output in the latter (events 27–28, 77–79). The more discriminating check verified feedback and identity, while a separate circular-delegation mock passed (events 84–85, 108–109). These were mocked local checks, not evidence of a live Anthropic round trip.

Type-checking initially failed because it was run in the wrong location and then because generated `cli/version.ts` was missing; generation from the backend directory resolved it (events 62–71). Subsequent type-checks passed, including after the final image-context edit (events 102–104, 108–109). An initial test command duplicated `--run` and failed before tests (events 72–74). The handler suite then showed six passes and one abort-controller cleanup failure (events 76–78, 81–83, 86–88). The agent temporarily substituted the `main` handler and observed the same failure, restoring its version afterward (events 92–93); this supports a baseline failure in that setup, not a universal diagnosis of its cause. The OpenAI provider suite failed to transform because `await` was outside an async function (events 99–101). No Anthropic test file was present in the provider test directory (events 103–105).

## Outcome, limits, and uncertainty

The supplied formal evaluation reports **solved**: patch applied, exit code 0, **F2P 7/7 and P2P 31/31**, partial score 1.0 and binary reward 1. This is a formal result for that test set, distinct from the student’s local handler failure and blocked OpenAI suite. It is not an empty patch, an early refusal, a normal algorithmic failure, or a technically interrupted attempt. Passing the formal tests does not establish complete production correctness or long-term learning.

Metadata reports `end_turn`, terminal reason `completed`, success and no API error or permission denials. Duration was 1,102.846 seconds, API duration 483.310 seconds, wall time 1,115.432 seconds, and teacher wait 53.067 seconds. Usage was 56 turns, 55 main tools, 1,918,192 input and 8,005 output tokens, and $9.791085; the listed model context window was 1,000,000 and maximum output 32,000 tokens. These are recorded usage/configuration figures, not evidence that a time or token limit was hit. The implementation’s 20-round bound is a code limit, not the session’s stop reason.

Transferable practices visible here include reproducing before editing, inspecting actual request payloads, testing failure paths and comparing against a baseline. The precise TypeScript interfaces, Anthropic streaming format and repository paths are task-specific. Whether live providers behave correctly across all nested, cancellation, image and streaming edge cases remains unverified. The original task wording, detailed formal test cases, and any unprovided teacher requests or archives are not available; blank F2P fields in the index are superseded by the supplied formal evaluation, not interpreted as zero.
