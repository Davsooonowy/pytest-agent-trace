"""Cassette event schema.

A cassette is an append-only stream of events (JSONL) — one event per line.
A new event type is a new variant of this union, not a migration of every
cassette already recorded.
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
    # Populated from the AIMessage's `usage_metadata` when the provider
    # reports it (OpenAI, Anthropic, Ollama, ... all do via LangChain's
    # standard UsageMetadata) - None when it isn't available.
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


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
