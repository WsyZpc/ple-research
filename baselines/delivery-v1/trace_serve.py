"""Run the official agent with request-scoped telemetry for local experiments."""
import asyncio
from itertools import count
import time

import serve
from api_trace import ApiCall, TracedHttpClient, new_session_id


class TracedAgent(serve.Agent):
    def __init__(self, session):
        super().__init__(session)
        self.trace_session = new_session_id()
        self.turns = count(1)
        self.turn = None
        self.result_call = None

    async def complete(self, *args, **kwargs):
        previous = self.turn
        self.turn = (next(self.turns), count(1))
        try:
            return await super().complete(*args, **kwargs)
        finally:
            self.turn = previous

    async def stream(self, messages, tool_choice, reserve, head=None):
        summary = bool(messages and messages[-1].get("content") == serve.SUMMARY_PROMPT)
        if summary or self.turn is None:
            turn, attempt = next(self.turns), 1
        else:
            turn, attempts = self.turn
            attempt = next(attempts)
        if summary:
            purpose = "context_summary"
        elif tool_choice == "none":
            purpose = "final_answer"
        elif head:
            purpose = "continue_truncated_reply"
        elif any(message.get("role") == "tool" for message in messages):
            purpose = "continue_after_tools"
        else:
            purpose = "initial_task"
        call = ApiCall(self.trace_session, turn, attempt, serve.MODEL, purpose)
        started = time.monotonic()
        with call.active():
            try:
                reply = await super().stream(messages, tool_choice, reserve, head)
            except (Exception, asyncio.CancelledError) as error:
                call.record("model_error", status="api_error", error_type=type(error).__name__, retry_scheduled=None)
                raise
        if reply.finish is None:
            call.record("model_error", status="incomplete_stream", error_type="StreamCut", retry_scheduled=None)
        else:
            usage = reply.usage
            call.record(
                "model_reply", finish_reason=reply.finish,
                input_tokens=getattr(usage, "prompt_tokens", None),
                output_tokens=getattr(usage, "completion_tokens", None),
                cached_input_tokens=getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", None),
                selected_tools=[tool["name"] for tool in reply.calls.values()],
                stream_duration_ms=round((time.monotonic() - started) * 1000),
            )
        if not summary:
            self.result_call = call
        return reply

    async def run_tool(self, name, args):
        call = self.result_call
        try:
            output = await super().run_tool(name, args)
        except (Exception, asyncio.CancelledError):
            if call is not None:
                call.record("tool_result", tool=name, outcome="raised", output_chars=0, exit_code=None)
            raise
        if call is not None:
            call.record("tool_result", tool=name, outcome="returned", output_chars=len(output), exit_code=None)
        return output


if __name__ == "__main__":
    serve.client = serve.client.with_options(http_client=TracedHttpClient(timeout=serve.client.timeout))
    serve.Agent = TracedAgent
    serve.taskbridge.run(serve.solve)
