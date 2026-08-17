"""`agent-trace` CLI — cassette inspection and standalone baseline diffing."""

from __future__ import annotations

import typer

from agent_test.core.diff import diff_trajectories
from agent_test.core.trace import AgentTrace

app = typer.Typer(help="pytest-agent-trace: inspect and manage agent trajectory cassettes.")


@app.command()
def show(cassette: str) -> None:
    """Print a human-readable timeline of a cassette's events."""
    trace = AgentTrace.from_cassette(cassette)
    for event in trace.events:
        payload = event.model_dump_json(exclude={"seq", "type"})
        typer.echo(f"[{event.seq:>3}] {event.type:<12} {payload}")


@app.command()
def diff(baseline: str, current: str) -> None:
    """Diff two cassettes and print the trajectory changes (outside pytest)."""
    result = diff_trajectories(
        AgentTrace.from_cassette(baseline), AgentTrace.from_cassette(current)
    )
    typer.echo(result.render())
    if result.is_significant:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
