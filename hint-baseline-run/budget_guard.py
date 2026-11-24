#!/usr/bin/env python3
"""Single-upstream budget guard. No third-party modules; no automatic retries.

Start explicitly with OFOX_GUARD_REAL_KEY and OFOX_GUARD_TOKEN in the environment.
The real key must never be passed to the experiment/container. Give that process
the guard token and http://127.0.0.1:18443/v1 instead. The ledger must already
exist. An interrupted/uncertain request is charged its full reservation locally
and locks this ledger against additional requests, including after restart.
"""
import argparse
import datetime
from decimal import Decimal
import fcntl
import hmac
import http.server
import json
import os
from pathlib import Path
import threading
import urllib.error
import urllib.request
import uuid


MODEL = "deepseek/deepseek-v4.1-flash-1017"
UPSTREAM = "https://api.ofox.ai/v1/chat/completions"
BALANCE_UPSTREAM = "https://api.ofox.ai/v1/user/balance"
COMPONENT = "hint_baseline_budget_guard"
BALANCE_COMPONENT = "hint_baseline_balance_monitor"
HARD_LIMIT = Decimal("3.90")
RESERVATION = Decimal("0.80")
PROMPT_PRICE = Decimal("0.0000003")
CACHED_PROMPT_PRICE = Decimal("0.000000006")
OUTPUT_PRICE = Decimal("0.0000012")
MAX_INPUT = 1000000
MAX_OUTPUT = 65536
MAX_BODY = 32 * 1024 * 1024
MAX_EVENT = 32 * 1024 * 1024
ALLOWED_FIELDS = {
    "model", "messages", "max_tokens", "max_completion_tokens", "n", "stream",
    "stream_options", "temperature", "top_p", "frequency_penalty",
    "presence_penalty", "stop", "tools", "tool_choice", "parallel_tool_calls",
    "response_format", "seed", "user", "reasoning_effort", "thinking",
    "logprobs", "top_logprobs", "metadata", "reasoning_content",
    "chat_template_kwargs", "allow_external",
    "context_management", "output_config",
}
ORIGINAL_CHAT_TEMPLATE = {
    "thinking": True, "drop_thinking": False, "enable_thinking": True,
    "clear_thinking": False, "preserve_thinking": True,
}
OBSERVED_CONTEXT_MANAGEMENT = {
    "edits": [{"type": "clear_thinking_20251015", "keep": "all"}],
}
OBSERVED_OUTPUT_CONFIG = {"effort": "high"}


class Rejected(Exception):
    pass


class Uncertain(Exception):
    pass


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Rejected("duplicate_json_key")
        result[key] = value
    return result


def parse_json(raw):
    return json.loads(raw, object_pairs_hook=no_duplicates,
                      parse_constant=lambda _value: (_ for _ in ()).throw(
                          Rejected("nonfinite_json_number")))


def integer(value):
    return type(value) is int and value >= 0


def checked_balance(value):
    if not isinstance(value, dict) or value.get("currency") != "USD" or value.get("is_active") is not True:
        raise Rejected("invalid_balance_account_state")
    result = {}
    for key in ("balance", "used", "total"):
        amount = value.get(key)
        if type(amount) not in (int, float, Decimal):
            raise Rejected("invalid_balance_amount")
        amount = Decimal(str(amount))
        if not amount.is_finite() or amount < 0:
            raise Rejected("invalid_balance_amount")
        result[key] = amount
    return result


def validate_request(body):
    if not isinstance(body, dict) or set(body) - ALLOWED_FIELDS:
        raise Rejected("unsupported_request_fields")
    if body.get("model") != MODEL:
        raise Rejected("model_not_allowed")
    if type(body.get("n", 1)) is not int or body.get("n", 1) != 1:
        raise Rejected("multiple_completions_not_allowed")
    caps = [body[key] for key in ("max_tokens", "max_completion_tokens")
            if key in body]
    if len(caps) != 1 or not integer(caps[0]) or not 0 < caps[0] <= MAX_OUTPUT:
        raise Rejected("one_valid_output_cap_required")
    if type(body.get("stream", False)) is not bool:
        raise Rejected("invalid_stream_flag")
    if "allow_external" in body and body["allow_external"] is not True:
        raise Rejected("unexpected_external_flag")
    if "chat_template_kwargs" in body:
        template = body["chat_template_kwargs"]
        if not isinstance(template, dict) or set(template) != set(ORIGINAL_CHAT_TEMPLATE):
            raise Rejected("unexpected_chat_template")
        if any(template[key] is not expected for key, expected in ORIGINAL_CHAT_TEMPLATE.items()):
            raise Rejected("unexpected_chat_template")
    if "thinking" in body and body["thinking"] != {"type": "enabled", "keep": "all"}:
        raise Rejected("unexpected_thinking_options")
    if "context_management" in body and body["context_management"] != OBSERVED_CONTEXT_MANAGEMENT:
        raise Rejected("unexpected_context_management")
    if "output_config" in body and body["output_config"] != OBSERVED_OUTPUT_CONFIG:
        raise Rejected("unexpected_output_config")
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        raise Rejected("messages_required")
    for message in messages:
        if not isinstance(message, dict):
            raise Rejected("invalid_message")
        content = message.get("content")
        if isinstance(content, list):
            if any(not isinstance(part, dict) or part.get("type") != "text"
                   for part in content):
                raise Rejected("only_text_content_allowed")
        elif content is not None and not isinstance(content, str):
            raise Rejected("invalid_message_content")
        if any(key in message for key in ("audio", "image", "video")):
            raise Rejected("only_text_content_allowed")
    tools = body.get("tools", [])
    if not isinstance(tools, list) or any(
            not isinstance(tool, dict) or tool.get("type") != "function"
            for tool in tools):
        raise Rejected("only_local_function_tools_allowed")
    choice = body.get("tool_choice", "auto")
    if isinstance(choice, dict):
        if choice.get("type") != "function" or not isinstance(choice.get("function"), dict):
            raise Rejected("only_local_function_tools_allowed")
    elif choice not in ("auto", "none", "required"):
        raise Rejected("invalid_tool_choice")
    options = body.get("stream_options", {})
    if not isinstance(options, dict) or set(options) - {"include_usage"}:
        raise Rejected("unsupported_stream_options")
    if "include_usage" in options and type(options["include_usage"]) is not bool:
        raise Rejected("invalid_usage_option")
    # This asks for accounting metadata; generation parameters stay unchanged.
    if body.get("stream"):
        body = dict(body)
        body["stream_options"] = {"include_usage": True}
    return body, caps[0]


def checked_cache(value, prompt):
    """Grant cache credit only for explicit, mutually consistent hit counts.

    Ofox documents prompt_tokens_details.cached_tokens as cache-priced tokens:
    https://ofox.ai/zh/docs/develop/models/deepseek
    DeepSeek documents cached_tokens == prompt_cache_hit_tokens, and
    prompt_tokens == prompt_cache_hit_tokens + prompt_cache_miss_tokens:
    https://api-docs.deepseek.com/api/create-chat-completion/
    Ambiguous/invalid cache metadata forfeits the discount, never the reserve.
    """
    hits = []
    sources = []
    if "prompt_tokens_details" in value:
        details = value["prompt_tokens_details"]
        if not isinstance(details, dict):
            return 0, "invalid_details"
        if "cached_tokens" in details:
            cached = details["cached_tokens"]
            if not integer(cached) or cached > prompt:
                return 0, "invalid_cached_tokens"
            hits.append(cached)
            sources.append("openai_cached_tokens")
    if "prompt_cache_hit_tokens" in value:
        hit = value["prompt_cache_hit_tokens"]
        if not integer(hit) or hit > prompt:
            return 0, "invalid_hit_tokens"
        hits.append(hit)
        sources.append("deepseek_hit_tokens")
    miss = None
    if "prompt_cache_miss_tokens" in value:
        miss = value["prompt_cache_miss_tokens"]
        if not integer(miss) or miss > prompt:
            return 0, "invalid_miss_tokens"
    if not hits:
        return 0, "no_explicit_cache_hits"
    if any(hit != hits[0] for hit in hits):
        return 0, "conflicting_cache_hits"
    if miss is not None and hits[0] + miss != prompt:
        return 0, "inconsistent_hit_miss"
    return hits[0], "+".join(sources)


def checked_usage(value, cap):
    if not isinstance(value, dict):
        raise Uncertain("missing_usage")
    prompt = value.get("prompt_tokens")
    completion = value.get("completion_tokens")
    total = value.get("total_tokens")
    if not all(integer(item) for item in (prompt, completion, total)):
        raise Uncertain("invalid_usage_counts")
    if not 0 < prompt <= MAX_INPUT or completion > cap or total != prompt + completion:
        raise Uncertain("usage_exceeds_expected_bounds")
    details = value.get("completion_tokens_details") or {}
    if not isinstance(details, dict):
        raise Uncertain("invalid_reasoning_usage")
    reasoning = details.get("reasoning_tokens", 0)
    if not integer(reasoning) or reasoning > cap:
        raise Uncertain("invalid_reasoning_usage")
    cached, cache_basis = checked_cache(value, prompt)
    # Deliberately double-count reasoning if completion already includes it.
    charge = ((prompt - cached) * PROMPT_PRICE + cached * CACHED_PROMPT_PRICE
              + (completion + reasoning) * OUTPUT_PRICE)
    if charge > RESERVATION:
        raise Uncertain("usage_exceeds_reservation")
    return {"prompt_tokens": prompt, "completion_tokens": completion,
            "reasoning_tokens": reasoning, "cached_prompt_tokens": cached,
            "uncached_prompt_tokens": prompt - cached,
            "cache_credit_basis": cache_basis}, charge


class SSEUsage:
    def __init__(self, cap):
        self.cap = cap
        self.buffer = b""
        self.data = []
        self.done = False
        self.usage = None
        self.charge = None
        self.last_event_had_usage = False

    def feed(self, chunk):
        self.buffer += chunk
        if len(self.buffer) > MAX_EVENT:
            raise Uncertain("sse_line_too_large")
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            line = line.rstrip(b"\r")
            if not line:
                self._event()
            elif line.startswith(b"data:"):
                self.data.append(line[5:].lstrip(b" "))
                if sum(map(len, self.data)) > MAX_EVENT:
                    raise Uncertain("sse_event_too_large")

    def _event(self):
        if not self.data:
            return
        raw = b"\n".join(self.data)
        self.data = []
        if self.done:
            raise Uncertain("sse_data_after_done")
        if raw == b"[DONE]":
            self.done = True
            return
        try:
            event = parse_json(raw)
        except Exception:
            raise Uncertain("invalid_sse_json")
        if not isinstance(event, dict) or "error" in event:
            raise Uncertain("upstream_sse_error")
        self.last_event_had_usage = event.get("usage") is not None
        if event.get("usage") is not None:
            usage, charge = checked_usage(event["usage"], self.cap)
            # Cache details may first appear only in the final usage event;
            # only total token counts are required to be monotonic.
            if self.usage and any(usage[key] < self.usage[key] for key in
                                  ("prompt_tokens", "completion_tokens", "reasoning_tokens")):
                raise Uncertain("regressing_sse_usage")
            self.usage, self.charge = usage, charge

    def finish(self):
        # A trailing [DONE] line without a final blank separator is tolerated.
        if self.buffer:
            line = self.buffer.rstrip(b"\r")
            if line.startswith(b"data:"):
                self.data.append(line[5:].lstrip(b" "))
            elif line.strip():
                raise Uncertain("incomplete_sse_line")
            self.buffer = b""
        self._event()
        if not self.done or self.usage is None or not self.last_event_had_usage:
            raise Uncertain("incomplete_stream_or_missing_usage")
        return self.usage, self.charge


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class BudgetGuard:
    def __init__(self, ledger, real_key, guard_token, opener=None, balance_fetcher=None):
        if not real_key or not guard_token or real_key == guard_token:
            raise ValueError("distinct_real_key_and_guard_token_required")
        self.ledger = Path(ledger)
        self.real_key = real_key
        self.guard_token = guard_token
        self.execution_lock = threading.Lock()
        self.state_lock = threading.RLock()
        self.spent = Decimal("0")
        self.pending = {}
        self.locked = False
        self.reason = None
        self.balance_anchor = None
        self.last_account_delta = None
        if not self.ledger.is_file():
            raise ValueError("existing_ledger_required")
        # O_APPEND preserves other monitor writers' entries between our writes.
        self.ledger_handle = self.ledger.open("a+", encoding="utf-8")
        try:
            fcntl.flock(self.ledger_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._restore()
        except Exception:
            self.ledger_handle.close()
            raise
        # Ignore proxy environment variables, and never follow redirects.
        self.opener = opener or urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect())
        self.balance_fetcher = balance_fetcher or self._fetch_balance

    def _restore(self):
        if not self.ledger.is_file():
            raise ValueError("existing_ledger_required")
        with self.ledger.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                event = parse_json(line)
                if not isinstance(event, dict):
                    continue
                if event.get("component") == BALANCE_COMPONENT:
                    if event.get("version") != 1:
                        raise ValueError("unknown_balance_ledger_version")
                    kind = event.get("event")
                    if kind == "anchor":
                        anchor = checked_balance({
                            "currency": event.get("currency"), "is_active": event.get("is_active"),
                            **{key: Decimal(event[key + "_usd"]) for key in ("balance", "used", "total")},
                        })
                        if self.balance_anchor is not None and anchor != self.balance_anchor:
                            raise ValueError("conflicting_balance_anchors")
                        self.balance_anchor = anchor
                    elif kind not in ("snapshot", "error"):
                        raise ValueError("unknown_balance_ledger_event")
                    continue
                if event.get("component") != COMPONENT:
                    continue
                if event.get("version") != 1:
                    raise ValueError("unknown_ledger_version")
                kind, request_id = event.get("event"), event.get("request_id")
                if kind == "reserve":
                    if request_id in self.pending:
                        raise ValueError("duplicate_ledger_reservation")
                    amount = Decimal(event["reservation_usd"])
                    if not amount.is_finite() or amount != RESERVATION:
                        raise ValueError("invalid_ledger_reservation")
                    self.pending[request_id] = amount
                elif kind == "reconcile":
                    if request_id not in self.pending:
                        raise ValueError("unmatched_ledger_reconciliation")
                    charge = Decimal(event["charge_usd"])
                    if not charge.is_finite() or not 0 <= charge <= self.pending[request_id]:
                        raise ValueError("invalid_ledger_charge")
                    self.pending.pop(request_id)
                    self.spent += charge
                elif kind == "error":
                    self.locked, self.reason = True, "previous_uncertain_request"
                else:
                    raise ValueError("unknown_ledger_event")
        if self.pending:
            self.locked, self.reason = True, "pending_reservation_after_restart"
        if self.spent > HARD_LIMIT:
            self.locked, self.reason = True, "restored_budget_exceeded"

    def _record(self, event, request_id, **fields):
        record = {"component": COMPONENT, "version": 1, "event": event,
                  "request_id": request_id,
                  "time": datetime.datetime.now(datetime.timezone.utc).isoformat()}
        record.update(fields)
        try:
            # Detect replacement/rotation instead of losing the budget history.
            current = self.ledger.stat()
            opened = os.fstat(self.ledger_handle.fileno())
            if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
                raise OSError("ledger_replaced")
            self.ledger_handle.seek(0, os.SEEK_END)
            self.ledger_handle.write(json.dumps(record, ensure_ascii=True, allow_nan=False) + "\n")
            self.ledger_handle.flush()
            os.fsync(self.ledger_handle.fileno())
        except Exception:
            self.locked, self.reason = True, "ledger_write_failed"
            raise Uncertain("ledger_write_failed")

    def close(self):
        self.ledger_handle.close()

    def _fetch_balance(self):
        request = urllib.request.Request(BALANCE_UPSTREAM, method="GET", headers={
            "Authorization": "Bearer " + self.real_key,
            "Accept": "application/json", "Accept-Encoding": "identity",
        })
        with self.opener.open(request, timeout=20) as response:
            if response.status != 200:
                raise Rejected("balance_http_error")
            raw = response.read(65537)
            if len(raw) > 65536:
                raise Rejected("balance_response_too_large")
            return json.loads(raw, object_pairs_hook=no_duplicates, parse_float=Decimal,
                              parse_constant=lambda _value: (_ for _ in ()).throw(
                                  Rejected("invalid_balance_number")))

    def _record_balance(self, event, request_id, **fields):
        self._record(event, request_id, component=BALANCE_COMPONENT,
                     scope="account", **fields)

    def _check_balance(self, request_id, stage):
        try:
            balance = checked_balance(self.balance_fetcher())
        except Exception:
            # Never persist an exception's text, response body, or headers.
            with self.state_lock:
                self._record_balance("error", request_id, stage=stage,
                                     reason="balance_query_unavailable")
            if stage == "before":
                raise Rejected("balance_unavailable_before_upstream")
            return
        with self.state_lock:
            amounts = {key + "_usd": str(value) for key, value in balance.items()}
            if self.balance_anchor is None:
                self._record_balance("anchor", request_id, currency="USD", is_active=True,
                                     **amounts)
                self.balance_anchor = balance
            delta = max(Decimal("0"), balance["used"] - self.balance_anchor["used"],
                        self.balance_anchor["balance"] - balance["balance"])
            self._record_balance("snapshot", request_id, stage=stage, currency="USD",
                                 is_active=True, account_delta_usd=str(delta), **amounts)
            self.last_account_delta = delta
            if stage == "before" and delta + RESERVATION > HARD_LIMIT:
                raise Rejected("account_balance_budget_exhausted")

    def snapshot(self):
        with self.state_lock:
            committed = self.spent + sum(self.pending.values(), Decimal("0"))
            return {"model": MODEL, "hard_limit_usd": str(HARD_LIMIT),
                    "reservation_usd": str(RESERVATION),
                    "settled_upper_bound_usd": str(self.spent),
                    "committed_upper_bound_usd": str(committed),
                    "pending_requests": len(self.pending), "locked": self.locked,
                    "lock_reason": self.reason,
                    "account_anchor_set": self.balance_anchor is not None,
                    "last_account_delta_usd": str(self.last_account_delta) if self.last_account_delta is not None else None,
                    "can_reserve_next": not self.locked and committed + RESERVATION <= HARD_LIMIT}

    def reserve(self, request_id=None):
        with self.state_lock:
            if self.locked:
                raise Rejected("budget_guard_locked")
            committed = self.spent + sum(self.pending.values(), Decimal("0"))
            if committed + RESERVATION > HARD_LIMIT:
                raise Rejected("hard_budget_exhausted")
            request_id = request_id or uuid.uuid4().hex
            self._record("reserve", request_id, reservation_usd=str(RESERVATION))
            self.pending[request_id] = RESERVATION
            return request_id

    def reconcile(self, request_id, usage, charge):
        with self.state_lock:
            if request_id not in self.pending or not 0 <= charge <= self.pending[request_id]:
                raise Uncertain("invalid_reconciliation")
            self._record("reconcile", request_id, charge_usd=str(charge), usage=usage)
            self.pending.pop(request_id)
            self.spent += charge

    def uncertain(self, request_id, reason, http_status=None):
        with self.state_lock:
            self.locked, self.reason = True, reason
            fields = {}
            if type(http_status) is int and 100 <= http_status <= 599:
                fields["http_status"] = http_status
            self._record("error", request_id, reason=reason,
                         reservation_retained_usd=str(RESERVATION), **fields)

    def forward(self, handler, body, cap):
        with self.execution_lock:
            request_id = uuid.uuid4().hex
            self._check_balance(request_id, "before")
            self.reserve(request_id)
            delivery_open = True

            def deliver(callback, *args):
                nonlocal delivery_open
                if delivery_open:
                    try:
                        callback(*args)
                    except (OSError, ValueError):
                        # A closed client cannot cancel the upstream accounting.
                        # Keep the reservation until its complete response is checked.
                        delivery_open = False

            try:
                raw = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
                request = urllib.request.Request(UPSTREAM, data=raw, method="POST", headers={
                    "Authorization": "Bearer " + self.real_key,
                    "Content-Type": "application/json", "Accept-Encoding": "identity",
                    "Accept": "text/event-stream" if body.get("stream") else "application/json",
                })
                with self.opener.open(request, timeout=6000) as response:
                    if response.status != 200:
                        raise Uncertain("upstream_http_error")
                    if body.get("stream"):
                        if not response.headers.get("Content-Type", "").lower().startswith("text/event-stream"):
                            raise Uncertain("unexpected_stream_content_type")
                        handler.response_started = True
                        deliver(handler.send_response, 200)
                        deliver(handler.send_header, "Content-Type", "text/event-stream")
                        deliver(handler.send_header, "Cache-Control", "no-cache")
                        deliver(handler.send_header, "Connection", "close")
                        deliver(handler.end_headers)
                        parser = SSEUsage(cap)
                        reader = getattr(response, "read1", response.read)
                        while True:
                            chunk = reader(65536)
                            if not chunk:
                                break
                            parser.feed(chunk)
                            deliver(handler.wfile.write, chunk)
                            deliver(handler.wfile.flush)
                        usage, charge = parser.finish()
                    else:
                        raw_response = response.read(MAX_BODY + 1)
                        if len(raw_response) > MAX_BODY:
                            raise Uncertain("response_too_large")
                        result = parse_json(raw_response)
                        if not isinstance(result, dict) or "error" in result:
                            raise Uncertain("invalid_upstream_response")
                        usage, charge = checked_usage(result.get("usage"), cap)
                        handler.response_started = True
                        deliver(handler.send_response, 200)
                        deliver(handler.send_header, "Content-Type", "application/json")
                        deliver(handler.send_header, "Content-Length", str(len(raw_response)))
                        deliver(handler.send_header, "Connection", "close")
                        deliver(handler.end_headers)
                        deliver(handler.wfile.write, raw_response)
                        deliver(handler.wfile.flush)
                    self.reconcile(request_id, usage, charge)
            except Exception as exc:
                reason = str(exc) if isinstance(exc, Uncertain) else "upstream_or_delivery_failed"
                http_status = None
                if isinstance(exc, urllib.error.HTTPError):
                    reason, http_status = "upstream_http_error", exc.code
                self.uncertain(request_id, reason, http_status=http_status)
                if not handler.response_started:
                    handler.json_response(502, {"error": reason, "budget_guard_locked": True})
            finally:
                self._check_balance(request_id, "after")


class GuardHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.response_started = False
        self.connection.settimeout(60)

    def log_message(self, _format, *args):
        pass  # Never log headers, request bodies, keys, or upstream errors.

    def json_response(self, status, payload):
        raw = json.dumps(payload, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.response_started = True
        self.wfile.write(raw)
        self.close_connection = True

    def authenticated(self):
        provided = self.headers.get_all("Authorization", [])
        expected = ("Bearer " + self.server.guard.guard_token).encode("utf-8")
        if len(provided) != 1 or not hmac.compare_digest(provided[0].encode("utf-8"), expected):
            self.json_response(401, {"error": "guard_authentication_required"})
            return False
        return True

    def do_GET(self):
        if not self.authenticated():
            return
        if self.path not in ("/health", "/budget"):
            self.json_response(404, {"error": "endpoint_not_allowed"})
            return
        self.json_response(200, self.server.guard.snapshot())

    def do_POST(self):
        self.close_connection = True
        if not self.authenticated():
            return
        if self.path != "/v1/chat/completions":
            self.json_response(404, {"error": "endpoint_not_allowed"})
            return
        try:
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or self.headers.get("Transfer-Encoding") or self.headers.get("Content-Encoding"):
                raise Rejected("unambiguous_uncompressed_length_required")
            length = int(lengths[0])
            if not 0 < length <= MAX_BODY:
                raise Rejected("invalid_request_length")
            if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
                raise Rejected("json_content_type_required")
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise Rejected("incomplete_request_body")
            body, cap = validate_request(parse_json(raw))
        except Rejected as exc:
            self.json_response(400, {"error": str(exc)})
            return
        except (ValueError, UnicodeError):
            self.json_response(400, {"error": "request_rejected_before_upstream"})
            return
        try:
            self.server.guard.forward(self, body, cap)
        except Rejected as exc:
            self.json_response(402, {"error": str(exc), "budget": self.server.guard.snapshot()})
        except Exception:
            # Fail closed if persistence failed before a network request.
            if not self.response_started:
                self.json_response(503, {"error": "guard_unavailable_no_further_calls"})


class GuardServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    # Reuse TIME_WAIT sockets after restart; never enable SO_REUSEPORT.
    allow_reuse_address = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--port", type=int, default=18443)
    args = parser.parse_args()
    real_key = os.environ.pop("OFOX_GUARD_REAL_KEY", "")
    token = os.environ.pop("OFOX_GUARD_TOKEN", "")
    guard = BudgetGuard(args.ledger, real_key, token)
    server = GuardServer(("127.0.0.1", args.port), GuardHandler)
    server.guard = guard
    print(json.dumps({"status": "listening", "host": "127.0.0.1", "port": args.port,
                      "budget": guard.snapshot()}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        guard.close()


if __name__ == "__main__":
    main()
