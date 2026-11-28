import json
import os
import asyncio
import logging
import time
from pathlib import Path
from litellm.integrations.custom_logger import CustomLogger

from logging_utils import setup_logging
import streaming_fix

CC_LOG_IN_CONTAINER_PATH = Path(os.getenv("SCENE_PROXY_LOG_DIR", "/tmp"))
_WRITE_LOCK = asyncio.Lock()
logger = setup_logging(CC_LOG_IN_CONTAINER_PATH / "claude_code_handler.log")

SYSTEM_PROMPT_ACTUAL_PATH = CC_LOG_IN_CONTAINER_PATH / "system_prompt_actual.json"

streaming_fix.apply()


def _convert_thinking_blocks_to_reasoning_content(messages):
    """Convert thinking_blocks in assistant messages to reasoning/reasoning_content.

    litellm sends history with thinking_blocks=[{type:'thinking', thinking:'...'}],
    but vLLM/sglang chat templates read reasoning_content. vLLM 0.21+ API layer
    only accepts the `reasoning` field and silently drops `reasoning_content`,
    while sglang uses `reasoning_content`. We write both fields for compatibility.
    """
    if not messages:
        return messages
    modified = False
    for msg in messages:
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        existing_rc = msg.get("reasoning_content") or msg.get("reasoning")
        if existing_rc:
            stripped = existing_rc.strip()
            if stripped != existing_rc:
                msg["reasoning_content"] = stripped
                msg["reasoning"] = stripped
                modified = True
            else:
                if not msg.get("reasoning"):
                    msg["reasoning"] = existing_rc
                    modified = True
                if not msg.get("reasoning_content"):
                    msg["reasoning_content"] = existing_rc
                    modified = True
            continue
        thinking_blocks = msg.get("thinking_blocks")
        if not thinking_blocks:
            continue
        reasoning_parts = []
        for block in thinking_blocks:
            if isinstance(block, dict) and block.get("thinking"):
                reasoning_parts.append(block["thinking"])
        if reasoning_parts:
            reasoning_text = "\n".join(reasoning_parts).strip()
            msg["reasoning_content"] = reasoning_text
            msg["reasoning"] = reasoning_text
            modified = True
    if modified:
        logger.info(
            "thinking_blocks_fix: converted thinking_blocks to reasoning_content "
            "in %d assistant message(s)",
            sum(1 for m in messages if isinstance(m, dict)
                and m.get("role") == "assistant" and m.get("reasoning_content")),
        )
    return messages


def _is_anthropic_route(model: str) -> bool:
    """Whether we're routing to a native-Anthropic backend.

    Native anthropic uses `content=[{type:'thinking',thinking:'...',signature:'...'}]`
    where `signature` is the opaque, server-signed carrier of the actual thinking
    state — the `thinking` field is only a human-readable summary. We MUST NOT
    downgrade thinking_blocks into plain reasoning_content on this route, or
    the signature is lost and next-turn responses silently degrade to
    "summary-only" (no real thinking continuity), and can be rejected outright
    with "Expected `signature` for thinking block".
    """
    if not isinstance(model, str):
        return False
    m = model.lower()
    return m.startswith("anthropic/") or ("claude" in m and not m.startswith("openai/"))


def _audit_thinking_signatures(messages, model_hint=""):
    """Log a warning if any assistant thinking block on the anthropic route
    is missing its `signature`. Cheap belt-and-braces detector -- we shouldn't
    normally see this unless upstream dropped the field somewhere."""
    if not messages:
        return
    missing = 0
    total = 0
    for msg in messages:
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        # content may be a list of blocks (anthropic style) or a string (openai style)
        content = msg.get("content")
        if isinstance(content, list):
            for blk in content:
                if isinstance(blk, dict) and blk.get("type") == "thinking":
                    total += 1
                    if not blk.get("signature"):
                        missing += 1
        # some litellm paths park thinking under `thinking_blocks` instead
        for blk in (msg.get("thinking_blocks") or []):
            if isinstance(blk, dict):
                total += 1
                if not blk.get("signature"):
                    missing += 1
    if missing:
        logger.warning(
            "anthropic route: %d/%d assistant thinking block(s) missing 'signature' "
            "(model=%s). Next-turn thinking continuity may be broken.",
            missing, total, model_hint,
        )


class MyCustomHandler(CustomLogger):
    # Optional max_tokens clamp. Claude Code always sends max_tokens=128000 in
    # its Anthropic-format requests, which (via litellm) takes precedence over
    # the YAML litellm_params.max_tokens. When resuming a session the full
    # prior conversation is replayed as input; with a 262144-token context
    # window, 134K input + 128K reserved output overflows by 1 token. Setting
    # PROXY_MAX_TOKENS_CLAMP forces a smaller output reservation so multi-turn
    # resume fits. Default "0" = no clamp (preserves existing behavior).
    MAX_TOKENS_CLAMP = int(os.getenv("PROXY_MAX_TOKENS_CLAMP", "0") or "0")

    # Preserve the previous system text to avoid redundant file writes.
    _last_system_prompt: str = ""

    @staticmethod
    def _extract_system_prompt(kwargs) -> str:
        """Extract the system prompt text from litellm request kwargs.

        litellm may carry the system prompt in several places depending on
        the entry endpoint (/v1/messages vs /v1/chat/completions) and the
        translation stage at which the hook fires:

        1. kwargs["messages"] — OpenAI-style: first message(s) with
           role == "system" (content may be a string or a list of blocks).
        2. kwargs["system"] — Anthropic-style top-level ``system`` param
           (string or list of {type:"text", text:"..."} blocks).
        3. kwargs["optional_params"]["system"] — same, parked in optional
           params by litellm's param routing.

        Returns the concatenated system text, or "" if none found.
        """
        # --- 1. OpenAI-style system messages in kwargs["messages"] ---
        messages = kwargs.get("messages") or kwargs.get("input") or []
        if isinstance(messages, list):
            parts = []
            for msg in messages:
                if not isinstance(msg, dict) or msg.get("role") != "system":
                    continue
                content = msg.get("content")
                if isinstance(content, str):
                    parts.append(content)
                elif isinstance(content, list):
                    for blk in content:
                        if isinstance(blk, dict) and blk.get("text"):
                            parts.append(blk["text"])
                        elif isinstance(blk, str):
                            parts.append(blk)
            if parts:
                return "\n".join(parts)

        # --- 2. Anthropic-style top-level system param ---
        system = kwargs.get("system")
        if isinstance(system, str) and system:
            return system
        if isinstance(system, list):
            parts = []
            for blk in system:
                if isinstance(blk, dict) and blk.get("text"):
                    parts.append(blk["text"])
                elif isinstance(blk, str):
                    parts.append(blk)
            if parts:
                return "\n".join(parts)

        # --- 3. system in optional_params ---
        op = kwargs.get("optional_params")
        if isinstance(op, dict):
            sys_op = op.get("system")
            if isinstance(sys_op, str) and sys_op:
                return sys_op
            if isinstance(sys_op, list):
                parts = []
                for blk in sys_op:
                    if isinstance(blk, dict) and blk.get("text"):
                        parts.append(blk["text"])
                    elif isinstance(blk, str):
                        parts.append(blk)
                if parts:
                    return "\n".join(parts)

        return ""

    def _capture_system_prompt(self, kwargs):
        """Write the actual system prompt (from the API request) to a JSON file.

        Called on every pre-call hook; only writes when the system prompt
        content changes to avoid redundant I/O.

        Output file: /tmp/system_prompt_actual.json
        Contains: timestamp, model, char_count, contains_system_reminder flag,
                  and the full system_prompt text.
        """
        try:
            sys_text = self._extract_system_prompt(kwargs)
            if not sys_text:
                return
            if sys_text == self._last_system_prompt:
                return  # unchanged since last capture
            self._last_system_prompt = sys_text

            record = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "model": kwargs.get("model") or "",
                "char_count": len(sys_text),
                "contains_system_reminder": "<system-reminder>" in sys_text,
                "system_prompt": sys_text,
            }
            with open(SYSTEM_PROMPT_ACTUAL_PATH, "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
            logger.info(
                "system_prompt captured: %d chars, contains_system_reminder=%s -> %s",
                record["char_count"],
                record["contains_system_reminder"],
                SYSTEM_PROMPT_ACTUAL_PATH,
            )
        except Exception:
            logger.exception("failed to capture system prompt")

    async def async_pre_call_deployment_hook(self, kwargs, call_type):
        model = kwargs.get("model") or ""
        messages = kwargs.get("messages")
        # Capture the actual system prompt from the API request (verifies
        # that the hint append reached the model). Writes to
        # /tmp/system_prompt_actual.json only when content changes.
        # Done before the messages check because system may live in
        # kwargs["system"] even when messages is empty.
        self._capture_system_prompt(kwargs)
        if not messages:
            return None
        if _is_anthropic_route(model):
            # Native anthropic: leave thinking_blocks + content[type=thinking] alone
            # so `signature` survives to the API. Just audit and log.
            _audit_thinking_signatures(messages, model_hint=model)
        else:
            # vLLM / sglang / other OpenAI-compat backends need reasoning_content
            # instead of thinking_blocks -- see the docstring on the converter.
            _convert_thinking_blocks_to_reasoning_content(messages)
        # Clamp max_tokens so input + max_tokens stays within the context window.
        # Client-sent max_tokens (e.g. Claude Code's 128000) overrides the YAML
        # litellm_params value, so the only reliable place to cap it is here.
        #
        # NOTE: at this point in the litellm pipeline (inside the @client
        # decorator's wrapper_async, BEFORE acompletion/anthropic_messages
        # runs), `optional_params` has NOT been created yet — it is built
        # inside the original function (main.py:get_optional_params). So
        # max_tokens lives at the TOP LEVEL of kwargs, not in
        # kwargs["optional_params"]. We check both locations for robustness.
        if self.MAX_TOKENS_CLAMP > 0:
            mt = kwargs.get("max_tokens")
            mt_source = "kwargs"
            if not isinstance(mt, int):
                op = kwargs.get("optional_params")
                if isinstance(op, dict):
                    mt = op.get("max_tokens")
                    mt_source = "optional_params"
            if isinstance(mt, int) and mt > self.MAX_TOKENS_CLAMP:
                logger.info(
                    "clamping max_tokens %s -> %s (PROXY_MAX_TOKENS_CLAMP, source=%s)",
                    mt, self.MAX_TOKENS_CLAMP, mt_source,
                )
                if mt_source == "kwargs":
                    kwargs["max_tokens"] = self.MAX_TOKENS_CLAMP
                else:
                    kwargs["optional_params"]["max_tokens"] = self.MAX_TOKENS_CLAMP
        return None

    async def _dump(self, kwargs, response_obj, start_time, end_time, status):
        user = kwargs.get("user") or "unknown_user"
        try:
            if hasattr(response_obj, "model_dump"):
                response = response_obj.model_dump()
            elif isinstance(response_obj, dict):
                response = response_obj
            else:
                response = {"raw": str(response_obj)}
        except Exception as e:
            logger.exception("failed to serialize proxy response for user=%s", user)
            response = {"error": f"serialize_failed: {e!r}"}

        record = {
            "Model": kwargs.get("model"),
            "Messages": kwargs.get("input"),
            "tools": kwargs.get("optional_params", {}).get("tools") or kwargs.get("tools"),
            "User": user,
            "Response": response,
            "Status": status,
            "start_time": str(start_time),
            "end_time": str(end_time),
        }
        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"

        logger.info(
            "proxy callback status=%s user=%s model=%s",
            status,
            user,
            record["Model"],
        )

        try:
            async with _WRITE_LOCK:
                with open(CC_LOG_IN_CONTAINER_PATH / f"{user}.jsonl", "a", encoding="utf-8") as fw:
                    fw.write(line)
                with open(CC_LOG_IN_CONTAINER_PATH / "litellm_requests.jsonl", "a", encoding="utf-8") as fw:
                    fw.write(line)
        except Exception:
            logger.exception("failed to write proxy jsonl log for user=%s", user)
            raise

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        await self._dump(kwargs, response_obj, start_time, end_time, "success")

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        logger.warning(
            "proxy failure user=%s model=%s error=%s",
            kwargs.get("user") or "unknown_user",
            kwargs.get("model"),
            response_obj,
        )
        await self._dump(kwargs, response_obj, start_time, end_time, "failure")

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            resp = response_obj.model_dump() if hasattr(response_obj, "model_dump") else response_obj
        except Exception:
            resp = {"raw": str(response_obj)}
        user = kwargs.get("user") or "unknown_user"
        record = {
            "Model": kwargs.get("model"),
            "Messages": kwargs.get("input"),
            "tools": kwargs.get("optional_params", {}).get("tools") or kwargs.get("tools"),
            "User": user,
            "Response": resp,
            "Status": "success-sync",
            "start_time": str(start_time),
            "end_time": str(end_time),
        }
        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
        logger.info("proxy callback status=success-sync user=%s model=%s", user, record["Model"])
        try:
            with open(CC_LOG_IN_CONTAINER_PATH / f"{user}.jsonl", "a", encoding="utf-8") as fw:
                fw.write(line)
            with open(CC_LOG_IN_CONTAINER_PATH / "litellm_requests.jsonl", "a", encoding="utf-8") as fw:
                fw.write(line)
        except Exception:
            logger.exception("failed to write sync proxy jsonl log for user=%s", user)
            raise


proxy_handler_instance = MyCustomHandler()

# Diagnostic: log the clamp value at import time so proxy.log shows whether
# PROXY_MAX_TOKENS_CLAMP reached the litellm process (it is read from os.environ
# when this module is imported by litellm's callback loader).
logger.info(
    "claude_code_proxy loaded: PROXY_MAX_TOKENS_CLAMP=%s MAX_TOKENS_CLAMP=%s",
    os.getenv("PROXY_MAX_TOKENS_CLAMP", "(unset)"),
    MyCustomHandler.MAX_TOKENS_CLAMP,
)
