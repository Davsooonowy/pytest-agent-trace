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
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any

from agent_test.core.cassette import CassetteWriter


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
                seq = writer.next_seq()
                writer.append(
                    LLMCall(
                        seq=seq,
                        run_id=run_id,
                        parent_seq=last_seq,
                        prompt_hash=_hash_prompt(event["data"].get("input")),
                        response=getattr(ai_message, "content", str(ai_message)),
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
