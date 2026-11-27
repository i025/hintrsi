[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis
Delegation currently stops at streamed provider output: the handler neither executes delegated tasks nor returns their results for the delegating agent to continue. The Anthropic adapter also lacks the tool advertisement and streamed tool-call handling needed to complete that round trip.

## Suggested Directions
- Treat delegation as a recursive provider tool round trip, with the handler managing execution and the adapter translating provider-specific messages.
- Extend the provider-neutral contract with optional capabilities while preserving existing providers and their unsupported-tool behavior.
- Consider validation, per-path cycle detection, bounded continuation, cancellation, and consistent tool-call identity throughout recursive execution.
- Preserve ordered text, agent attribution, conversation context, and outer-stream lifecycle across nested calls and failures.
- Verify public-handler streaming and provider continuation alongside adapter parsing, error cases, and existing chat and screen-capture behavior.

## Key Location Clues
- `backend/handlers/multiAgentChat.ts` — Central handler for agent execution, delegation, streaming, and related screen-capture behavior.
- `backend/providers/types.ts` — Provider-neutral contracts for capabilities, requests, and responses.
- `backend/providers/anthropic.ts` — Anthropic request construction, streamed response parsing, and context conversion.
- `backend/providers/registry.ts` — Existing agent configuration and provider lookup patterns.
- `shared/types.ts` — Shared agent availability and stream envelope types.
- `backend/tests/handlers/multiAgentChat.test.ts` — Mocked-provider and public NDJSON handler test patterns.
- `backend/handlers/chat.ts` — Related example of streamed tool-input handling.

## Critical Warnings
- Avoid treating the presence of another provider as a request to replace it: that assumption can halt a compatible change; instead, inspect the requested scope and applicable guidance, preserve existing providers, and distinguish optional interface and adapter extensions from an SDK switch. Clarification may still be appropriate when applicable guidance requires it.
