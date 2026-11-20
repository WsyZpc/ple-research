"""Structured HTTP attempt and tool logs for the local PLE minimal baseline."""

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import re
import sys
import time
from uuid import uuid4

from openai import DefaultAsyncHttpxClient

PREFIX = "PLE_API_TRACE "
KNOWN_TOOLS = {"read_file", "write_file", "bash"}
_active_call = ContextVar("ple_api_call", default=None)


def tool_label(name):
    return name if isinstance(name, str) and name in KNOWN_TOOLS else "unknown_tool"


def new_session_id():
    return uuid4().hex


class ApiCall:
    def __init__(self, session_id, turn, harness_try, model, purpose):
        self.fields = {
            "session_id": session_id,
            "turn": turn,
            "harness_try": harness_try,
            "model": model,
            "purpose": purpose,
        }
        self.http_try = 0

    @contextmanager
    def active(self):
        token = _active_call.set(self)
        try:
            yield
        finally:
            _active_call.reset(token)

    def record(self, event, **fields):
        record = {
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "http_try": self.http_try,
            **self.fields,
            **fields,
        }
        try:
            print(PREFIX + json.dumps(record, separators=(",", ":")), file=sys.stderr, flush=True)
        except OSError:
            # A closed diagnostic stream must not change the evaluation result.
            pass

    def reply(self, response):
        usage = response.usage
        details = getattr(usage, "prompt_tokens_details", None)
        choice = response.choices[0] if response.choices else None
        self.record(
            "model_reply",
            finish_reason=choice.finish_reason if choice else "missing_choice",
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
            cached_input_tokens=getattr(details, "cached_tokens", None),
            selected_tools=[
                tool_label(getattr(getattr(call, "function", None), "name", None))
                for call in (choice.message.tool_calls or [])
            ] if choice else [],
        )


class TracedHttpClient(DefaultAsyncHttpxClient):
    async def send(self, request, **kwargs):
        call = _active_call.get()
        if call is None:
            return await super().send(request, **kwargs)

        call.http_try += 1
        kind = "sdk_retry" if call.http_try > 1 else (
            "harness_retry" if call.fields["harness_try"] > 1 else "initial"
        )
        started = time.monotonic()
        call.record("request_started", attempt_kind=kind)
        result = {"transport_status": "interrupted"}
        try:
            response = await super().send(request, **kwargs)
            request_id = response.headers.get("x-request-id") or response.headers.get(
                "request-id", ""
            )
            result = {
                "http_status": response.status_code,
                "transport_status": "http_ok" if 200 <= response.status_code < 300 else "http_error",
                "provider_request_id": (
                    request_id if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", request_id) else None
                ),
                "redirect_count": len(response.history),
            }
            return response
        except asyncio.CancelledError:
            result = {"transport_status": "cancelled"}
            raise
        except Exception as exc:
            result = {
                "transport_status": "transport_error",
                "transport_error_type": type(exc).__name__,
            }
            raise
        finally:
            call.record(
                "request_finished",
                duration_ms=round((time.monotonic() - started) * 1000),
                **result,
            )
