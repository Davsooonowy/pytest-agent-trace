"""Read/write cassettes as JSON Lines event logs."""

from __future__ import annotations

from pathlib import Path

from pydantic import TypeAdapter

from agent_test.core.events import AgentEvent

_EVENT_ADAPTER: TypeAdapter[AgentEvent] = TypeAdapter(AgentEvent)


def load_cassette(path: str | Path) -> list[AgentEvent]:
    path = Path(path)
    events: list[AgentEvent] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(_EVENT_ADAPTER.validate_json(line))
    return events


def save_cassette(path: str | Path, events: list[AgentEvent]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(event.model_dump_json())
            f.write("\n")


class CassetteWriter:
    """Append-only writer used by adapters while recording a live run."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._events: list[AgentEvent] = []
        self._next_seq = 1

    def next_seq(self) -> int:
        seq = self._next_seq
        self._next_seq += 1
        return seq

    def append(self, event: AgentEvent) -> None:
        self._events.append(event)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(event.model_dump_json())
            f.write("\n")

    @property
    def events(self) -> list[AgentEvent]:
        return list(self._events)
