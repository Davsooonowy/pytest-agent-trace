"""AgentTrace — a queryable view over a cassette's events for one run."""

from __future__ import annotations

from pathlib import Path

from agent_test.core.cassette import load_cassette
from agent_test.core.events import AgentEvent, LLMCall, RunFinished, ToolCall


class AgentTrace:
    """In-memory view over the events of a single agent run.

    Multiple runs can share one cassette file (multiple `run_id`s); a trace
    is scoped to one run so assertions never leak across recordings.
    """

    def __init__(self, events: list[AgentEvent], run_id: str | None = None) -> None:
        if run_id is None and events:
            run_id = min(events, key=lambda e: e.seq).run_id
        self.run_id = run_id
        self.events: list[AgentEvent] = (
            events if run_id is None else [e for e in events if e.run_id == run_id]
        )
        self.events.sort(key=lambda e: e.seq)

    @classmethod
    def from_cassette(cls, path: str | Path, run_id: str | None = None) -> "AgentTrace":
        return cls(load_cassette(path), run_id=run_id)

    @property
    def tool_calls(self) -> list[ToolCall]:
        return [e for e in self.events if isinstance(e, ToolCall)]

    @property
    def llm_calls(self) -> list[LLMCall]:
        return [e for e in self.events if isinstance(e, LLMCall)]

    @property
    def final_output(self) -> object | None:
        for e in reversed(self.events):
            if isinstance(e, RunFinished):
                return e.final_output
        return None

    def tool_call_count(self, tool_name: str) -> int:
        return sum(1 for e in self.tool_calls if e.tool == tool_name)
