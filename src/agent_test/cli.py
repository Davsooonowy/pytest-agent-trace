"""`agent-trace` CLI — cassette inspection utilities (recording/diffing lives in the pytest plugin)."""

from __future__ import annotations

import typer

from agent_test.core.trace import AgentTrace

app = typer.Typer(help="pytest-agent-trace: inspect and manage agent trajectory cassettes.")


@app.command()
def show(cassette: str) -> None:
    """Print a human-readable timeline of a cassette's events."""
    trace = AgentTrace.from_cassette(cassette)
    for event in trace.events:
        typer.echo(f"[{event.seq:>3}] {event.type:<12} {event.model_dump_json(exclude={'seq', 'type'})}")


if __name__ == "__main__":
    app()
