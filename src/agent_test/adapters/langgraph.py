"""LangGraph adapter — records a live agent run as a cassette.

Consumes `astream_events` (LangGraph/LangChain's own event stream) instead of
subclassing `BaseCallbackHandler`. `langchain-replay` (the closest existing
project) made the same choice: `astream_events` is a stable, documented
surface, while callback handler internals get restructured between LangGraph
minor versions. Keeping this file as the only place that touches LangGraph
objects is what lets `core/` stay framework-agnostic (see adapters/crewai.py,
adapters/pydantic_ai.py in the future).

Event shapes below were verified empirically against langgraph==1.2 /
langchain-core==1.5 (a hand-rolled StateGraph + ToolNode agent driven by a
`FakeMessagesListChatModel`), not assumed from docs:

- The very first event yielded is the graph's own top-level `on_chain_start`;
  its `run_id` is the root run. The matching `on_chain_end` (same run_id)
  carries the final state in `data["output"]["messages"][-1]`.
- `on_chat_model_end`'s `data["output"]` is the `AIMessage` itself (not a
  wrapped `ChatResult`/`LLMResult`) under `astream_events(version="v2")`.
- `on_tool_start`'s `data["input"]` is already the plain tool-args dict.
  `on_tool_end`'s `data["output"]` is a `ToolMessage`; its `.content` is
  whatever the tool returned, JSON-encoded by LangChain if it wasn't a string.
  Its `.status` is the string `"success"` or `"error"` — not `"ok"`/`"error"`
  like our own `ToolCall.status` — so the recorder remaps it.
- A tool call whose `_run` *raises* fires `on_tool_error`, not `on_tool_end`
  — even when `ToolNode(handle_tool_errors=True)` goes on to catch that same
  exception and turn it into an error `ToolMessage` for the graph's own
  conversation state. Skipping `on_tool_error` means a raised exception
  (chaos-injected or real) silently disappears from the cassette instead of
  recording as a failed `tool_call` — found while building chaos engineering
  support, where tools are expected to raise on purpose.

Replay (`LangGraphReplayer`) patches a model/tool *instance* so a graph
replays a cassette instead of calling the real API or running real tool
code. This can't use `unittest.mock.patch.object` the normal way: chat
models and tools are pydantic v2 `BaseModel`s, and pydantic's `__setattr__`
rejects setting any attribute that isn't a declared field (`ValueError:
"X" object has no field "invoke"`) — confirmed empirically, not assumed.
Patching the *class* instead (`type(model).invoke = ...`) does work, but is
wrong here: every `@tool`-decorated function is an instance of the same
`StructuredTool` class, so a class-level patch would replay every tool
through the same cursor regardless of which one was actually called.
The fix is `object.__setattr__`/`object.__delattr__`, which bypass
pydantic's `__setattr__` entirely and set/remove a plain instance-`__dict__`
entry that shadows the class method for that one object only.

Chaos injection (`inject_tool_chaos`) reuses the exact same `_run`/`_arun`
patching technique, but doesn't need a cassette at all — it wraps the *real*
tool implementation, letting every call through except the ones a
`ChaosScenario` targets. Two things worth knowing before writing a chaos
test: LangGraph's `ToolNode` does **not** catch a plain exception raised
from a tool by default — `handle_tool_errors` defaults to a function that
only converts LangGraph's own internal `ToolInvocationError` and re-raises
everything else, confirmed empirically (a raised `TimeoutError` propagated
straight out of `graph.invoke()` and killed the run). Build your graph's
`ToolNode` with `handle_tool_errors=True` if you want a chaos-injected
exception to become an error `ToolMessage` the agent can react to instead of
a crash. And a model replayed from a cassette (`LangGraphReplayer`) plays
back the *exact* canned response regardless of what the tool actually
returned — genuinely reactive behavior (retry, escalate) requires either a
live model or a hand-rolled reactive stand-in, not pure cassette replay.
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import time
from collections.abc import Sequence
from contextlib import ExitStack, contextmanager
from typing import Any

from agent_test.core.cassette import CassetteWriter
from agent_test.core.chaos import ChaosScenario
from agent_test.core.trace import AgentTrace


def _duration_ms(started_at: float | None) -> int | None:
    if started_at is None:
        return None
    return round((time.monotonic() - started_at) * 1000)


def _hash_prompt(messages: Any) -> str:
    return hashlib.sha256(str(messages).encode("utf-8")).hexdigest()[:12]


def _decode_tool_result(content: Any) -> Any:
    if isinstance(content, str):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return content
    return content


class LangGraphRecorder:
    """Wraps a compiled LangGraph graph. `arecord(input)` runs it for real
    (real LLM, real tools) and writes every LLM/tool step to a cassette
    (a local JSONL file — see `core/cassette.py`).
    """

    def __init__(self, graph: Any, location: str) -> None:
        self._graph = graph
        self._location = location

    async def arecord(
        self, input: dict[str, Any], run_id: str | None = None, **stream_kwargs: Any
    ) -> str:
        from agent_test.core.events import LLMCall, RunFinished, RunStarted, ToolCall

        writer = CassetteWriter(self._location)
        run_id = run_id or hashlib.sha256(str(input).encode()).hexdigest()[:12]

        last_seq = writer.next_seq()
        writer.append(RunStarted(seq=last_seq, run_id=run_id, input=input))
        last_llm_seq = last_seq

        root_run_id: str | None = None
        pending_starts: dict[str, float] = {}
        final_output: Any = None

        async for event in self._graph.astream_events(input, version="v2", **stream_kwargs):
            kind = event["event"]
            ev_run_id = event.get("run_id", "")
            if root_run_id is None:
                root_run_id = ev_run_id

            if kind == "on_chat_model_start":
                pending_starts[ev_run_id] = time.monotonic()

            elif kind == "on_chat_model_end":
                ai_message = event["data"]["output"]
                tool_calls = getattr(ai_message, "tool_calls", None)
                seq = writer.next_seq()
                writer.append(
                    LLMCall(
                        seq=seq,
                        run_id=run_id,
                        parent_seq=last_seq,
                        prompt_hash=_hash_prompt(event["data"].get("input")),
                        response=getattr(ai_message, "content", str(ai_message)),
                        tool_calls=list(tool_calls) if tool_calls else None,
                        model=event.get("metadata", {}).get("ls_model_name") or event.get("name"),
                        duration_ms=_duration_ms(pending_starts.pop(ev_run_id, None)),
                    )
                )
                last_seq = last_llm_seq = seq

            elif kind == "on_tool_start":
                pending_starts[ev_run_id] = time.monotonic()

            elif kind == "on_tool_end":
                tool_message = event["data"]["output"]
                seq = writer.next_seq()
                writer.append(
                    ToolCall(
                        seq=seq,
                        run_id=run_id,
                        parent_seq=last_llm_seq,
                        tool=event.get("name", "unknown_tool"),
                        args=event["data"].get("input") or {},
                        result=_decode_tool_result(getattr(tool_message, "content", tool_message)),
                        status="error"
                        if getattr(tool_message, "status", None) == "error"
                        else "ok",
                        duration_ms=_duration_ms(pending_starts.pop(ev_run_id, None)),
                    )
                )
                last_seq = seq

            elif kind == "on_tool_error":
                # A tool that *raises* (rather than returning an error value)
                # fires this instead of on_tool_end — even when the graph's
                # ToolNode has handle_tool_errors=True and goes on to convert
                # the exception into an error ToolMessage for the agent's own
                # conversation state. Without handling this event, a raised
                # exception (e.g. from chaos.ChaosScenario.timeout) simply
                # vanishes from the cassette instead of showing up as a
                # failed tool_call.
                error = event["data"].get("error")
                seq = writer.next_seq()
                writer.append(
                    ToolCall(
                        seq=seq,
                        run_id=run_id,
                        parent_seq=last_llm_seq,
                        tool=event.get("name", "unknown_tool"),
                        args=event["data"].get("input") or {},
                        result=str(error) if error is not None else None,
                        status="error",
                        duration_ms=_duration_ms(pending_starts.pop(ev_run_id, None)),
                    )
                )
                last_seq = seq

            elif kind == "on_chain_end" and ev_run_id == root_run_id:
                output = event["data"].get("output") or {}
                messages = output.get("messages") if isinstance(output, dict) else None
                if messages:
                    final_output = getattr(messages[-1], "content", messages[-1])

        seq = writer.next_seq()
        writer.append(
            RunFinished(seq=seq, run_id=run_id, parent_seq=last_seq, final_output=final_output)
        )
        return run_id

    def record(self, input: dict[str, Any], run_id: str | None = None, **stream_kwargs: Any) -> str:
        """Sync convenience wrapper around `arecord` for simple pytest usage."""
        return asyncio.run(self.arecord(input, run_id=run_id, **stream_kwargs))


class ReplayExhaustedError(RuntimeError):
    """Raised when a replayed run calls the model/a tool more times than the
    cassette has recorded events for — the agent's real behavior diverged
    from what was recorded (different control flow, an extra retry, ...).
    """


class LangGraphReplayer:
    """Patches a chat model and its tools so a LangGraph run replays a
    recorded cassette instead of calling the real API or executing real tool
    code — fully offline, deterministic, zero API cost.

    Matching is sequential/index-based: the Nth `arecord`ed llm_call answers
    the Nth model invocation, the Nth tool_call answers the Nth call to that
    tool, regardless of the live prompt/args. This is the simplest strategy
    and the one `langchain-replay` validated in a real implementation (see
    project notes) — a stricter hash/semantic match can be layered on later
    as an opt-in, but sequential is the correct default.
    """

    def __init__(self, trace: AgentTrace) -> None:
        self.trace = trace
        self._llm_calls = iter(trace.llm_calls)
        self._tool_calls_by_name: dict[str, Any] = {}
        for call in trace.tool_calls:
            self._tool_calls_by_name.setdefault(call.tool, []).append(call)
        self._tool_cursors: dict[str, int] = {}

    @classmethod
    def from_cassette(cls, location: str, run_id: str | None = None) -> LangGraphReplayer:
        return cls(AgentTrace.from_cassette(location, run_id=run_id))

    def _next_ai_message(self) -> Any:
        from langchain_core.messages import AIMessage

        try:
            recorded = next(self._llm_calls)
        except StopIteration as exc:
            raise ReplayExhaustedError(
                "cassette has no more recorded llm_call events, but the model was "
                "invoked again — the replayed agent's behavior diverged from the recording"
            ) from exc
        return AIMessage(content=recorded.response, tool_calls=recorded.tool_calls or [])

    def _next_tool_result(self, tool_name: str) -> Any:
        calls = self._tool_calls_by_name.get(tool_name, [])
        cursor = self._tool_cursors.get(tool_name, 0)
        if cursor >= len(calls):
            raise ReplayExhaustedError(
                f'cassette has no more recorded tool_call events for "{tool_name}", but it '
                "was called again — the replayed agent's behavior diverged from the recording"
            )
        self._tool_cursors[tool_name] = cursor + 1
        return calls[cursor].result

    @contextmanager
    def patch_model(self, model: Any):
        """Patch one model instance for the duration of the `with` block.

        Patches `_generate`/`_agenerate` — the *leaf* methods `invoke`/
        `ainvoke` call internally — rather than `invoke`/`ainvoke` themselves.
        Patching `invoke` directly would also work for driving the graph, but
        it bypasses the tracing machinery that emits `on_chat_model_start`/
        `on_chat_model_end`, so a replayed run couldn't be re-recorded into a
        cassette (verified empirically: `astream_events` saw zero llm_call
        events when `invoke` was replaced wholesale). Patching `_generate`
        keeps the outer `invoke`/tracing wrapper intact.

        Uses `object.__setattr__`/`__delattr__`, not `mock.patch.object` —
        see the module docstring for why that fails on a pydantic model.
        """
        from langchain_core.outputs import ChatGeneration, ChatResult

        def make_result(*_args: Any, **_kwargs: Any) -> ChatResult:
            return ChatResult(generations=[ChatGeneration(message=self._next_ai_message())])

        async def async_generate(*_args: Any, **_kwargs: Any) -> ChatResult:
            return make_result()

        object.__setattr__(model, "_generate", make_result)
        object.__setattr__(model, "_agenerate", async_generate)
        try:
            yield model
        finally:
            object.__delattr__(model, "_generate")
            object.__delattr__(model, "_agenerate")

    @contextmanager
    def patch_tool(self, tool: Any):
        """Patch one tool instance's `_run`/`_arun` (not `invoke`/`ainvoke`,
        for the same tracing reason as `patch_model`) for the duration of the
        `with` block, matched by `tool.name` (falls back to `__name__`/
        `str(tool)` for plain callables). The outer `invoke`/`ainvoke`
        wrapper takes care of packaging our raw return value into a
        `ToolMessage` with the correct `tool_call_id`, exactly as it would
        for the real tool function.
        """
        name = str(getattr(tool, "name", None) or getattr(tool, "__name__", str(tool)))

        def sync_run(*_args: Any, **_kwargs: Any) -> Any:
            return self._next_tool_result(name)

        async def async_run(*_args: Any, **_kwargs: Any) -> Any:
            return self._next_tool_result(name)

        object.__setattr__(tool, "_run", sync_run)
        object.__setattr__(tool, "_arun", async_run)
        try:
            yield tool
        finally:
            object.__delattr__(tool, "_run")
            object.__delattr__(tool, "_arun")

    @contextmanager
    def patch(self, model: Any, tools: Sequence[Any] = ()):
        """Patch a model and any number of tools together in one `with`."""
        with ExitStack() as stack:
            stack.enter_context(self.patch_model(model))
            for tool in tools:
                stack.enter_context(self.patch_tool(tool))
            yield


@contextmanager
def inject_tool_chaos(tool: Any, scenario: ChaosScenario):
    """Wrap one *real* tool instance so specific calls (per `scenario`) fail
    while every other call runs the tool's actual implementation.

    Unlike `LangGraphReplayer.patch_tool`, this doesn't replace the tool at
    all — it wraps it, so the agent (and its model) can be live/reactive and
    genuinely respond to the injected fault, not just play back a script.
    """
    call_count = 0
    real_run = tool._run
    real_arun = tool._arun

    # `BaseTool.run`/`arun` decide whether to inject `config`/`run_manager`
    # by inspecting the target callable's signature. `functools.wraps` copies
    # `__wrapped__`, which `inspect.signature` follows by default — so these
    # wrappers get treated exactly like the real `_run`/`_arun` for injection
    # purposes, and forwarding `*args, **kwargs` to `real_run`/`real_arun`
    # below actually has everything it needs (verified empirically: without
    # `wraps`, `real_run(*args, **kwargs)` failed with "missing required
    # keyword-only argument: 'config'").

    @functools.wraps(real_run)
    def sync_run(*args: Any, **kwargs: Any) -> Any:
        nonlocal call_count
        call_count += 1
        should_fault, action = scenario.apply(call_count)
        if should_fault:
            assert action is not None
            return action()
        return real_run(*args, **kwargs)

    @functools.wraps(real_arun)
    async def async_run(*args: Any, **kwargs: Any) -> Any:
        nonlocal call_count
        call_count += 1
        should_fault, action = scenario.apply(call_count)
        if should_fault:
            assert action is not None
            return action()
        return await real_arun(*args, **kwargs)

    object.__setattr__(tool, "_run", sync_run)
    object.__setattr__(tool, "_arun", async_run)
    try:
        yield tool
    finally:
        object.__delattr__(tool, "_run")
        object.__delattr__(tool, "_arun")
