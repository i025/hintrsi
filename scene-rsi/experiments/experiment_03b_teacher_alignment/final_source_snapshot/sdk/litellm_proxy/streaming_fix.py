"""
Monkey-patch for litellm's AnthropicStreamWrapper to fix streaming protocol issues.

Fix 1 — Late-arriving thinking chunks:
GLM-5.1 (and similar models) interleave `reasoning_content` (thinking) chunks
with `tool_calls` chunks in their OpenAI streaming output. litellm's AnthropicStreamWrapper
assigns sequential content block indices (0=thinking, 1=text, 2+=tool_use) and emits
content_block_stop when transitioning between types. But late-arriving thinking chunks
cause a "regression" back to thinking type, which emits content_block_start/delta at a
stale index. Claude Code SDK then throws "Content block not found".

Fix 2 — vLLM/sglang empty text delta:
vLLM sends an initial streaming chunk with content="" (empty text delta). litellm
misidentifies this as a text block, emitting a spurious text content_block_start before
the actual thinking block. This breaks Claude Code's content block parsing.
Additionally, if a response contains only thinking blocks and no text blocks, Claude Code
expects at least one text block before message_delta — we inject an empty one if needed.

Fix 3 — Shared mutable class attributes:
AnthropicStreamWrapper declares `chunk_queue: deque = deque()` and
`current_content_block_start = TextBlock(...)` as class-level defaults. In Python,
mutable class-level defaults are shared between ALL instances. When concurrent requests
(e.g. subagent calls) create multiple AnthropicStreamWrapper instances, they all push/pop
from the same deque — events queued by one request leak into another request's SSE stream,
causing "Content block not found" errors. We reinitialize these in __init__.
"""

import logging
import re
import json as _json
from collections import deque

logger = logging.getLogger("streaming_fix")

_PATCHED = False

_TYPE_ORDER = {"thinking": 0, "text": 1, "tool_use": 2}

_TOOL_CALLS_SECTION_RE = re.compile(
    r'<\|tool_calls_section_begin\|>(.*?)<\|tool_calls_section_end\|>',
    re.DOTALL,
)
_TOOL_CALL_RE = re.compile(
    r'<\|tool_call_begin\|>\s*(.*?)\s*<\|tool_call_argument_begin\|>\s*(.*?)\s*<\|tool_call_end\|>',
    re.DOTALL,
)


def _parse_tool_calls_from_reasoning(reasoning_text):
    """Parse tool calls embedded in reasoning_content (kimi2.6 workaround).

    When kimi2.6 generates tool calls inside <think>, the output contains
    special tokens that vLLM does not interpret. This function extracts them.

    Returns list of (call_id, name, args_dict) or None if no tool calls found.
    """
    section_match = _TOOL_CALLS_SECTION_RE.search(reasoning_text)
    if not section_match:
        return None

    section = section_match.group(1)
    calls = []
    for m in _TOOL_CALL_RE.finditer(section):
        call_id = m.group(1).strip()
        args_str = m.group(2).strip()

        # call_id format: "functions.Read:10" -> name="Read"
        name = call_id
        if call_id.startswith("functions."):
            name_part = call_id[len("functions."):]
            if ":" in name_part:
                name = name_part.split(":")[0]
            else:
                name = name_part

        try:
            args = _json.loads(args_str)
        except (ValueError, _json.JSONDecodeError):
            args = {}

        calls.append((call_id, name, args))

    return calls if calls else None


def _detect_block_type(chunk):
    """Detect the content block type from an OpenAI streaming chunk.

    litellm's _translate_streaming_openai_chunk_to_anthropic_content_block only
    checks delta.thinking_blocks, but GLM-5.1 and other models use
    delta.reasoning_content. This helper checks reasoning_content first, then
    falls back to litellm's detection.

    Returns (block_type, content_block_start) or None if the chunk is an empty
    text delta that should be skipped.
    """
    from litellm.llms.anthropic.experimental_pass_through.adapters.transformation import (
        LiteLLMAnthropicMessagesAdapter,
    )

    if chunk.choices[0].finish_reason is not None:
        return "text", {"type": "text", "text": ""}

    delta = getattr(chunk.choices[0], "delta", None)

    # Check reasoning_content (sglang) or reasoning (vLLM) first.
    # Use truthiness, NOT `is not None`: Qwen sends tool-call chunks with
    # reasoning_content='' (empty string, not None). `'' is not None` is True,
    # so the old check misclassified every tool-call chunk as thinking, hijacking
    # tool_use detection. Treat '' as "no reasoning" and fall through so the
    # tool_calls in the same chunk are detected. A genuine thinking stream whose
    # first delta is an empty placeholder simply starts one chunk later (no loss,
    # that chunk carried no thinking text anyway).
    reasoning = getattr(delta, "reasoning_content", None) if delta else None
    if not reasoning:
        reasoning = getattr(delta, "reasoning", None) if delta else None
    if reasoning:
        return "thinking", {"type": "thinking", "thinking": ""}

    # Fall back to litellm's detection
    (block_type, content_block_start) = (
        LiteLLMAnthropicMessagesAdapter()
        ._translate_streaming_openai_chunk_to_anthropic_content_block(
            choices=chunk.choices
        )
    )

    # vLLM/sglang may send an initial chunk with content="" (empty text delta).
    # Also handle chunks where vLLM's glm45 reasoning parser leaks thinking content
    # into the `content` field with `tool_calls=[]` (empty list, not None).
    if block_type == "text":
        content = getattr(delta, "content", None) if delta else None
        tool_calls = getattr(delta, "tool_calls", None) if delta else None
        # Skip if content is empty or None
        if content is None or content == "":
            return None, None
        # vLLM glm45 parser leak: thinking content ends up in `content` with
        # tool_calls=[]. Fix by moving content to reasoning_content so downstream
        # code treats it as a thinking chunk (instead of skipping it).
        if isinstance(tool_calls, list) and len(tool_calls) == 0:
            existing_rc = getattr(delta, "reasoning_content", None)
            if not existing_rc:
                try:
                    delta.reasoning_content = content
                    delta.content = None
                except (AttributeError, TypeError):
                    pass
                return "thinking", {"type": "thinking", "thinking": ""}
            else:
                return None, None

    return block_type, content_block_start


def _preserve_tool_result_errors():
    """Keep Claude's error flag for this experiment's local Codex bridge."""
    from litellm.llms.anthropic.experimental_pass_through.adapters.transformation import (
        LiteLLMAnthropicMessagesAdapter,
    )

    original = LiteLLMAnthropicMessagesAdapter.translate_anthropic_messages_to_openai

    def translate(self, messages, model=None):
        # Recent Claude CLI versions emit hook context as inline system messages.
        # Preserve their position as conversation input; top-level system is unchanged.
        normalized = [dict(message, role="user") if message.get("role") == "system" else message
                      for message in messages]
        translated = original(self, normalized, model=model)
        errors = {}
        for message in messages:
            content = message.get("content")
            if message.get("role") != "user" or not isinstance(content, list):
                continue
            for block in content:
                if block.get("type") == "tool_result" and "is_error" in block:
                    errors[block["tool_use_id"]] = block["is_error"]
        for message in translated:
            call_id = message.get("tool_call_id")
            if message.get("role") == "tool" and call_id in errors:
                # Local compatibility extension; it is not an OpenAI API field.
                message["is_error"] = errors[call_id]
        return translated

    LiteLLMAnthropicMessagesAdapter.translate_anthropic_messages_to_openai = translate


def apply():
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True
    _preserve_tool_result_errors()

    try:
        from litellm.llms.anthropic.experimental_pass_through.adapters.streaming_iterator import (
            AnthropicStreamWrapper,
        )
    except ImportError:
        logger.warning("streaming_fix: could not import AnthropicStreamWrapper, skipping patch")
        return

    _orig_init = AnthropicStreamWrapper.__init__

    def _patched_init(self, *args, **kwargs):
        _orig_init(self, *args, **kwargs)
        self._highest_block_type_order = 0
        self._initial_block_type_resolved = False
        self._has_emitted_text_block = False
        self._last_emitted_block_index = 0
        self._reasoning_buffer = ""
        self._suppress_reasoning_tool_section = False
        # Fix shared mutable class attributes: each instance MUST have its own copy.
        # The original class declares these as class-level defaults (e.g. deque()),
        # which means all concurrent instances share the same object — events from
        # one request leak into another's SSE stream.
        self.chunk_queue = deque()
        self.current_content_block_start = {"type": "text", "text": ""}
        self.holding_chunk = None
        self.holding_stop_reason_chunk = None

    def _resolve_initial_block_type(self, chunk):
        """Peek at the first chunk to determine the correct initial content_block type.

        Returns None for empty text deltas (vLLM sends content="" as first chunk)
        so the caller can skip and try the next chunk.
        """
        block_type, content_block_start = _detect_block_type(chunk)

        if block_type is None:
            logger.debug("streaming_fix: skipping empty text delta (sglang/vLLM first chunk)")
            return None

        self.current_content_block_type = block_type
        self._highest_block_type_order = _TYPE_ORDER.get(block_type, 1)
        if block_type == "thinking":
            return {"type": "thinking", "thinking": ""}
        elif block_type == "tool_use":
            if isinstance(content_block_start, dict) and content_block_start.get("name"):
                truncated_name = content_block_start["name"]
                original_name = self.tool_name_mapping.get(truncated_name, truncated_name)
                content_block_start["name"] = original_name
            return content_block_start
        else:
            self._has_emitted_text_block = True
            return {"type": "text", "text": ""}

    def _accumulate_reasoning(self, chunk):
        """Buffer reasoning_content/reasoning for potential tool-call extraction (Fix 4)."""
        if not chunk.choices:
            return
        delta = getattr(chunk.choices[0], "delta", None)
        if delta:
            rc = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
            if rc:
                self._reasoning_buffer += rc
                if not self._suppress_reasoning_tool_section and \
                        '<|tool_calls_section_begin|>' in self._reasoning_buffer:
                    self._suppress_reasoning_tool_section = True

    def _strip_tool_section_from_thinking(self, processed_chunk):
        """Strip tool-call markers from thinking deltas once detected.

        Returns True if the chunk should be skipped entirely (nothing left
        after stripping). Returns False if the chunk should still be emitted
        (either untouched or with the tail trimmed).
        """
        if not self._suppress_reasoning_tool_section:
            return False
        if not isinstance(processed_chunk, dict):
            return False
        if processed_chunk.get("type") != "content_block_delta":
            return False
        delta = processed_chunk.get("delta", {})
        if delta.get("type") != "thinking_delta":
            return False

        thinking = delta.get("thinking", "")
        marker = "<|tool_calls_section_begin|>"
        if marker in thinking:
            cleaned = thinking[:thinking.index(marker)]
            if cleaned.strip():
                delta["thinking"] = cleaned
                return False
            return True
        return True

    def _inject_tool_calls_from_reasoning(self, current_max_idx, processed_chunk):
        """If reasoning contains tool calls but no real tool_calls were streamed,
        inject tool_use content blocks and fix the stop_reason. Returns the new
        current_max_idx (unchanged when nothing is injected)."""
        if not self._reasoning_buffer:
            return current_max_idx
        if self._highest_block_type_order >= _TYPE_ORDER["tool_use"]:
            return current_max_idx
        parsed = _parse_tool_calls_from_reasoning(self._reasoning_buffer)
        if not parsed:
            return current_max_idx

        logger.info(
            "streaming_fix: extracting %d tool call(s) from reasoning_content",
            len(parsed),
        )
        tool_name_mapping = getattr(self, "tool_name_mapping", {})
        for call_id, name, args in parsed:
            original_name = tool_name_mapping.get(name, name)
            current_max_idx += 1
            self.chunk_queue.append({
                "type": "content_block_start",
                "index": current_max_idx,
                "content_block": {
                    "type": "tool_use",
                    "id": call_id,
                    "name": original_name,
                    "input": "",
                },
            })
            self.chunk_queue.append({
                "type": "content_block_delta",
                "index": current_max_idx,
                "delta": {
                    "type": "input_json_delta",
                    "partial_json": _json.dumps(args, ensure_ascii=False),
                },
            })
            self.chunk_queue.append({
                "type": "content_block_stop",
                "index": current_max_idx,
            })

        if isinstance(processed_chunk, dict) and "delta" in processed_chunk:
            processed_chunk["delta"]["stop_reason"] = "tool_use"

        return current_max_idx

    def _patched_should_start_new_content_block(self, chunk):
        block_type, content_block_start = _detect_block_type(chunk)

        if block_type is None:
            # Empty/spurious delta (e.g. content='', tool_calls=[]) — must be
            # skipped entirely, otherwise translate_streaming_openai_response_to_anthropic
            # may produce a delta type (e.g. input_json_delta) that doesn't match
            # the current content block type.
            chunk._drop_late = True
            return False

        if chunk.choices[0].finish_reason is not None:
            return False

        # Restore original tool name if it was truncated for OpenAI's 64-char limit
        if block_type == "tool_use":
            from typing import cast
            from litellm.types.llms.anthropic import ToolUseBlock
            tool_block = cast(ToolUseBlock, content_block_start)
            if tool_block.get("name"):
                truncated_name = tool_block["name"]
                original_name = self.tool_name_mapping.get(truncated_name, truncated_name)
                tool_block["name"] = original_name

        incoming_order = _TYPE_ORDER.get(block_type, 1)
        current_highest = getattr(self, "_highest_block_type_order", 0)

        # Key fix: if a chunk regresses to an earlier block type (e.g. thinking
        # arriving after we've moved to text or tool_use), mark it for skipping.
        if incoming_order < current_highest:
            chunk._drop_late = True
            return False

        chunk._drop_late = False
        self._highest_block_type_order = max(current_highest, incoming_order)

        # Normal logic from original _should_start_new_content_block
        if block_type != self.current_content_block_type:
            self.current_content_block_type = block_type
            self.current_content_block_start = content_block_start
            return True

        if block_type == "tool_use":
            from typing import cast
            from litellm.types.llms.anthropic import ToolUseBlock
            tool_block = cast(ToolUseBlock, content_block_start)
            if tool_block.get("name"):
                self.current_content_block_type = block_type
                self.current_content_block_start = content_block_start
                return True

        return False

    # Patch __anext__ to skip chunks marked _drop_late
    _orig_anext = AnthropicStreamWrapper.__anext__

    async def _patched_anext(self):
        from litellm.llms.anthropic.experimental_pass_through.adapters.transformation import (
            LiteLLMAnthropicMessagesAdapter,
        )
        from litellm.types.llms.anthropic import UsageDelta

        try:
            if self.chunk_queue:
                return self.chunk_queue.popleft()

            if self.sent_first_chunk is False:
                self.sent_first_chunk = True
                from litellm._uuid import uuid
                self.chunk_queue.append({
                    "type": "message_start",
                    "message": {
                        "id": "msg_{}".format(uuid.uuid4()),
                        "type": "message",
                        "role": "assistant",
                        "content": [],
                        "model": self.model,
                        "stop_reason": None,
                        "stop_sequence": None,
                        "usage": self._create_initial_usage_delta(),
                    },
                })
                return self.chunk_queue.popleft()

            if self.sent_content_block_start is False:
                self.sent_content_block_start = True
                # Defer: peek first chunk(s) to determine correct block type.
                # Skip empty text deltas from vLLM/sglang (_resolve_initial_block_type returns None).
                async for first_chunk in self.completion_stream:
                    if first_chunk == "None" or first_chunk is None:
                        raise Exception
                    self._accumulate_reasoning(first_chunk)
                    initial_block = self._resolve_initial_block_type(first_chunk)
                    if initial_block is None:
                        # Empty text delta from vLLM — skip and try next chunk
                        continue
                    self._initial_block_type_resolved = True
                    if initial_block.get("type") == "text":
                        self._has_emitted_text_block = True
                    self.chunk_queue.append({
                        "type": "content_block_start",
                        "index": self.current_content_block_index,
                        "content_block": initial_block,
                    })
                    # Process the first chunk as a normal delta
                    processed_chunk = (
                        LiteLLMAnthropicMessagesAdapter()
                        .translate_streaming_openai_response_to_anthropic(
                            response=first_chunk,
                            current_content_block_index=self.current_content_block_index,
                        )
                    )
                    self.chunk_queue.append(processed_chunk)
                    return self.chunk_queue.popleft()
                # Stream was empty
                self._has_emitted_text_block = True
                self.chunk_queue.append({
                    "type": "content_block_start",
                    "index": self.current_content_block_index,
                    "content_block": {"type": "text", "text": ""},
                })
                return self.chunk_queue.popleft()

            async for chunk in self.completion_stream:
                if chunk == "None" or chunk is None:
                    raise Exception

                if (
                    self.holding_stop_reason_chunk is not None
                    and getattr(chunk, "usage", None) is not None
                ):
                    merged_chunk = self.holding_stop_reason_chunk.copy()
                    if "delta" not in merged_chunk:
                        merged_chunk["delta"] = {}
                    usage_dict = {
                        "input_tokens": chunk.usage.prompt_tokens or 0,
                        "output_tokens": chunk.usage.completion_tokens or 0,
                    }
                    if hasattr(chunk.usage, "_cache_creation_input_tokens") and chunk.usage._cache_creation_input_tokens > 0:
                        usage_dict["cache_creation_input_tokens"] = chunk.usage._cache_creation_input_tokens
                    if hasattr(chunk.usage, "_cache_read_input_tokens") and chunk.usage._cache_read_input_tokens > 0:
                        usage_dict["cache_read_input_tokens"] = chunk.usage._cache_read_input_tokens
                    merged_chunk["usage"] = usage_dict
                    self.chunk_queue.append(merged_chunk)
                    self.queued_usage_chunk = True
                    self.holding_stop_reason_chunk = None
                    return self.chunk_queue.popleft()

                self._accumulate_reasoning(chunk)

                should_start_new_block = self._should_start_new_content_block(chunk)

                # --- FIX: skip late-arriving chunks ---
                if getattr(chunk, "_drop_late", False):
                    logger.debug(
                        "streaming_fix: dropping late chunk (current_block_type=%s, "
                        "current_index=%d)",
                        self.current_content_block_type,
                        self.current_content_block_index,
                    )
                    continue

                if should_start_new_block:
                    self._increment_content_block_index()

                processed_chunk = (
                    LiteLLMAnthropicMessagesAdapter()
                    .translate_streaming_openai_response_to_anthropic(
                        response=chunk,
                        current_content_block_index=self.current_content_block_index,
                    )
                )

                if self._strip_tool_section_from_thinking(processed_chunk):
                    continue

                if not self.queued_usage_chunk:
                    if should_start_new_block:
                        # Track if we're emitting a text block
                        if self.current_content_block_start.get("type") == "text":
                            self._has_emitted_text_block = True
                        # Always emit content_block_stop for the previous block
                        # before starting a new one, regardless of sent_content_block_finish
                        if not self.sent_content_block_finish:
                            self.chunk_queue.append({
                                "type": "content_block_stop",
                                "index": max(self.current_content_block_index - 1, 0),
                            })
                        self._last_emitted_block_index = self.current_content_block_index
                        self.chunk_queue.append({
                            "type": "content_block_start",
                            "index": self.current_content_block_index,
                            "content_block": self.current_content_block_start,
                        })
                        self.chunk_queue.append(processed_chunk)
                        self.sent_content_block_finish = False
                        return self.chunk_queue.popleft()

                    if (
                        processed_chunk["type"] == "message_delta"
                        and self.sent_content_block_finish is False
                    ):
                        self.chunk_queue.append({
                            "type": "content_block_stop",
                            "index": self._last_emitted_block_index,
                        })
                        self.sent_content_block_finish = True

                        # If no text block was emitted (only thinking), inject an
                        # empty one before message_delta to prevent Claude Code
                        # "Content block not found" error.
                        current_max_idx = self._last_emitted_block_index
                        if not self._has_emitted_text_block:
                            self._has_emitted_text_block = True
                            current_max_idx += 1
                            self.chunk_queue.append({
                                "type": "content_block_start",
                                "index": current_max_idx,
                                "content_block": {"type": "text", "text": ""},
                            })
                            self.chunk_queue.append({
                                "type": "content_block_stop",
                                "index": current_max_idx,
                            })

                        # Fix 4: extract tool calls from reasoning (kimi2.6)
                        current_max_idx = self._inject_tool_calls_from_reasoning(
                            current_max_idx, processed_chunk
                        )

                        if processed_chunk.get("delta", {}).get("stop_reason") is not None:
                            self.holding_stop_reason_chunk = processed_chunk
                        else:
                            self.chunk_queue.append(processed_chunk)
                        return self.chunk_queue.popleft()
                    elif self.holding_chunk is not None:
                        self.chunk_queue.append(self.holding_chunk)
                        self.chunk_queue.append(processed_chunk)
                        self.holding_chunk = None
                        return self.chunk_queue.popleft()
                    else:
                        self.chunk_queue.append(processed_chunk)
                        return self.chunk_queue.popleft()

            if not self.queued_usage_chunk:
                if self.holding_stop_reason_chunk is not None:
                    self.chunk_queue.append(self.holding_stop_reason_chunk)
                    self.holding_stop_reason_chunk = None
                if self.holding_chunk is not None:
                    self.chunk_queue.append(self.holding_chunk)
                    self.holding_chunk = None

            if not self.sent_last_message:
                self.sent_last_message = True
                self.chunk_queue.append({"type": "message_stop"})

            if self.chunk_queue:
                return self.chunk_queue.popleft()

            raise StopIteration

        except StopIteration:
            if self.chunk_queue:
                return self.chunk_queue.popleft()
            if self.holding_stop_reason_chunk is not None:
                return self.holding_stop_reason_chunk
            if not self.sent_last_message:
                self.sent_last_message = True
                return {"type": "message_stop"}
            raise StopAsyncIteration

    # Patch __next__ (sync version) with same fix
    _orig_next = AnthropicStreamWrapper.__next__

    def _patched_next(self):
        from litellm.llms.anthropic.experimental_pass_through.adapters.transformation import (
            LiteLLMAnthropicMessagesAdapter,
        )
        try:
            # Drain queued chunks first (used for text block injection)
            if self.chunk_queue:
                return self.chunk_queue.popleft()

            if self.sent_first_chunk is False:
                self.sent_first_chunk = True
                from litellm._uuid import uuid
                return {
                    "type": "message_start",
                    "message": {
                        "id": "msg_{}".format(uuid.uuid4()),
                        "type": "message",
                        "role": "assistant",
                        "content": [],
                        "model": self.model,
                        "stop_reason": None,
                        "stop_sequence": None,
                        "usage": self._create_initial_usage_delta(),
                    },
                }
            if self.sent_content_block_start is False:
                self.sent_content_block_start = True
                # Defer: peek first chunk(s) to determine correct block type.
                # Skip empty text deltas from vLLM/sglang.
                for first_chunk in self.completion_stream:
                    if first_chunk == "None" or first_chunk is None:
                        raise Exception
                    self._accumulate_reasoning(first_chunk)
                    initial_block = self._resolve_initial_block_type(first_chunk)
                    if initial_block is None:
                        # Empty text delta from vLLM — skip and try next chunk
                        continue
                    self._initial_block_type_resolved = True
                    if initial_block.get("type") == "text":
                        self._has_emitted_text_block = True
                    self.holding_chunk = (
                        LiteLLMAnthropicMessagesAdapter()
                        .translate_streaming_openai_response_to_anthropic(
                            response=first_chunk,
                            current_content_block_index=self.current_content_block_index,
                        )
                    )
                    return {
                        "type": "content_block_start",
                        "index": self.current_content_block_index,
                        "content_block": initial_block,
                    }
                # Stream was empty
                self._has_emitted_text_block = True
                return {
                    "type": "content_block_start",
                    "index": self.current_content_block_index,
                    "content_block": {"type": "text", "text": ""},
                }

            if self.pending_new_content_block:
                self.pending_new_content_block = False
                self.sent_content_block_finish = False
                return {
                    "type": "content_block_start",
                    "index": self.current_content_block_index,
                    "content_block": self.current_content_block_start,
                }

            for chunk in self.completion_stream:
                if chunk == "None" or chunk is None:
                    raise Exception

                self._accumulate_reasoning(chunk)

                should_start_new_block = self._should_start_new_content_block(chunk)

                # --- FIX: skip late-arriving chunks ---
                if getattr(chunk, "_drop_late", False):
                    continue

                if should_start_new_block:
                    self._increment_content_block_index()

                processed_chunk = (
                    LiteLLMAnthropicMessagesAdapter()
                    .translate_streaming_openai_response_to_anthropic(
                        response=chunk,
                        current_content_block_index=self.current_content_block_index,
                    )
                )

                if self._strip_tool_section_from_thinking(processed_chunk):
                    continue

                if should_start_new_block:
                    # Track if we're emitting a text block
                    if self.current_content_block_start.get("type") == "text":
                        self._has_emitted_text_block = True
                    self._last_emitted_block_index = self.current_content_block_index
                    self.holding_chunk = processed_chunk
                    if not self.sent_content_block_finish:
                        self.sent_content_block_finish = True
                        self.pending_new_content_block = True
                        return {
                            "type": "content_block_stop",
                            "index": max(self.current_content_block_index - 1, 0),
                        }
                    else:
                        self.sent_content_block_finish = False
                        self.pending_new_content_block = False
                        return {
                            "type": "content_block_start",
                            "index": self.current_content_block_index,
                            "content_block": self.current_content_block_start,
                        }

                if (
                    processed_chunk["type"] == "message_delta"
                    and self.sent_content_block_finish is False
                ):
                    self.sent_content_block_finish = True

                    # Inject empty text block if only thinking blocks were emitted
                    current_max_idx = self._last_emitted_block_index
                    if not self._has_emitted_text_block:
                        self._has_emitted_text_block = True
                        current_max_idx += 1
                        self.chunk_queue.append({
                            "type": "content_block_start",
                            "index": current_max_idx,
                            "content_block": {"type": "text", "text": ""},
                        })
                        self.chunk_queue.append({
                            "type": "content_block_stop",
                            "index": current_max_idx,
                        })

                    # Fix 4: extract tool calls from reasoning (kimi2.6)
                    current_max_idx = self._inject_tool_calls_from_reasoning(
                        current_max_idx, processed_chunk
                    )

                    self.chunk_queue.append(processed_chunk)

                    return {
                        "type": "content_block_stop",
                        "index": self._last_emitted_block_index,
                    }
                elif self.holding_chunk is not None:
                    return_chunk = self.holding_chunk
                    self.holding_chunk = processed_chunk
                    return return_chunk
                else:
                    return processed_chunk

            if self.holding_chunk is not None:
                return_chunk = self.holding_chunk
                self.holding_chunk = None
                return return_chunk
            if self.chunk_queue:
                return self.chunk_queue.popleft()
            if self.sent_last_message is False:
                self.sent_last_message = True
                return {"type": "message_stop"}
            raise StopIteration
        except StopIteration:
            if self.chunk_queue:
                return self.chunk_queue.popleft()
            if self.sent_last_message is False:
                self.sent_last_message = True
                return {"type": "message_stop"}
            raise StopIteration
        except Exception as e:
            from litellm import verbose_logger
            verbose_logger.error("Anthropic Adapter - {}\n{}".format(e, __import__("traceback").format_exc()))
            raise StopAsyncIteration

    AnthropicStreamWrapper.__init__ = _patched_init
    AnthropicStreamWrapper._resolve_initial_block_type = _resolve_initial_block_type
    AnthropicStreamWrapper._accumulate_reasoning = _accumulate_reasoning
    AnthropicStreamWrapper._strip_tool_section_from_thinking = _strip_tool_section_from_thinking
    AnthropicStreamWrapper._inject_tool_calls_from_reasoning = _inject_tool_calls_from_reasoning
    AnthropicStreamWrapper._should_start_new_content_block = _patched_should_start_new_content_block
    AnthropicStreamWrapper.__anext__ = _patched_anext
    AnthropicStreamWrapper.__next__ = _patched_next

    logger.info("streaming_fix: AnthropicStreamWrapper patched successfully")

    # Fix 5 — vLLM uses `reasoning` instead of `reasoning_content` in streaming
    # deltas. litellm's Delta.__init__ only accepts `reasoning_content`, so vLLM's
    # `reasoning` field is silently lost during Delta construction (goes into
    # **params and is ignored). By patching Delta.__init__ to intercept `reasoning`
    # and map it to `reasoning_content`, the Delta object is correct from birth.
    # Every downstream path (is_chunk_non_empty, chunk_creator, AnthropicStreamWrapper,
    # translate_streaming_*) then sees a proper `reasoning_content` field — identical
    # to what sglang produces. No other patches needed.
    try:
        from litellm.types.utils import Delta as LiteLLMDelta
    except ImportError:
        logger.warning("streaming_fix: could not import Delta, skipping vLLM reasoning patch")
        return

    _orig_delta_init = LiteLLMDelta.__init__

    def _patched_delta_init(self, *args, reasoning=None, **kwargs):
        if reasoning is not None and kwargs.get("reasoning_content") is None:
            kwargs["reasoning_content"] = reasoning
        _orig_delta_init(self, *args, **kwargs)

    LiteLLMDelta.__init__ = _patched_delta_init
    logger.info("streaming_fix: Delta.__init__ patched for vLLM reasoning field")
