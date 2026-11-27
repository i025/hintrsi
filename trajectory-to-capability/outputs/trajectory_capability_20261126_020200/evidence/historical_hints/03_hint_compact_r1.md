[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis

Agent execution currently ends after a single provider response, so delegation requests are neither executed nor returned to the delegating agent. The Anthropic adapter also lacks the tool support needed to advertise delegation and interpret streamed tool calls.

## Suggested Directions

- The core lies in treating delegation as a recursive provider tool round trip, followed by continuation of the delegating agent.
- Consider a provider-neutral tool contract that preserves compatibility with providers that do not support tools.
- The Anthropic adapter may need attention for streamed tool calls and conversion between neutral conversation context and provider-native messages.
- Worth considering target validation, path-specific cycle detection, bounded execution, cancellation, and consistent error feedback.
- Preserve output attribution and outer stream lifecycle while collecting delegated results and maintaining tool-call identity.
- Verification through the public handler and adapter tests can cover nested delegation, errors, continuation, and existing chat and screen-capture behavior.

## Key Location Clues

- `backend/handlers/multiAgentChat.ts` — Central handler for agent execution, delegation, streaming, and screen-capture behavior.
- `backend/providers/types.ts` — Defines the provider request, capability, context, and response contracts.
- `backend/providers/anthropic.ts` — Builds Anthropic requests and interprets streamed responses and conversation context.
- `backend/providers/registry.ts` — Provides existing agent configuration and provider lookup patterns.
- `shared/types.ts` — Defines available agents and shared stream envelopes.
- `backend/tests/handlers/multiAgentChat.test.ts` — Shows mocked providers and public NDJSON stream testing patterns.
- `backend/handlers/chat.ts` — Offers a related example of handling streamed tool input.
