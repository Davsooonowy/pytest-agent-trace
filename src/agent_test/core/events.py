"""Cassette event schema.

Kaseta to append-only strumień zdarzeń (JSONL) — jeden event = jedna linia.
Nowy typ zdarzenia to nowy wariant tej unii, nie migracja istniejących kaset.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class RunStarted(BaseModel):
    seq: int
    type: Literal["run_started"] = "run_started"
    run_id: str
    parent_seq: int | None = None
    input: dict[str, Any]


class LLMCall(BaseModel):
    seq: int
    type: Literal["llm_call"] = "llm_call"
    run_id: str
    parent_seq: int | None = None
    prompt_hash: str | None = None
    response: str
    tool_calls: list[dict[str, Any]] | None = None
    model: str | None = None
    duration_ms: int | None = None
    status: Literal["ok", "error"] = "ok"


class ToolCall(BaseModel):
    seq: int
    type: Literal["tool_call"] = "tool_call"
    run_id: str
    parent_seq: int | None = None
    tool: str
    args: dict[str, Any]
    result: Any = None
    duration_ms: int | None = None
    status: Literal["ok", "error"] = "ok"


class RunFinished(BaseModel):
    seq: int
    type: Literal["run_finished"] = "run_finished"
    run_id: str
    parent_seq: int | None = None
    final_output: Any = None


AgentEvent = Annotated[
    RunStarted | LLMCall | ToolCall | RunFinished,
    Field(discriminator="type"),
]

EVENT_TYPES: dict[str, type[BaseModel]] = {
    "run_started": RunStarted,
    "llm_call": LLMCall,
    "tool_call": ToolCall,
    "run_finished": RunFinished,
}
