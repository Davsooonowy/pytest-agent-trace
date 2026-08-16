"""pytest plugin — registers the `agent_cassette` fixture and record/diff CLI flags.

Registered via the `pytest11` entry point (see pyproject.toml), following the
same pattern pytest-recording/vcr-langchain use for their `vcr` fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_test.core.assertions import assert_trajectory
from agent_test.core.trace import AgentTrace


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("agent-trace")
    group.addoption(
        "--record",
        action="store_true",
        default=False,
        help="Record a fresh cassette against the real agent/LLM instead of replaying.",
    )
    group.addoption(
        "--agent-diff-baseline",
        action="store_true",
        default=False,
        help="Diff the current trajectory against the stored baseline cassette (regression check).",
    )


class AgentCassetteFixture:
    """Handle exposed as the `agent_cassette` fixture inside tests."""

    def __init__(self, record: bool, diff_baseline: bool) -> None:
        self.record = record
        self.diff_baseline = diff_baseline
        self.trace: AgentTrace | None = None
        self._path: Path | None = None

    def load(self, path: str | Path) -> AgentTrace:
        self._path = Path(path)
        self.trace = AgentTrace.from_cassette(self._path)
        return self.trace

    def assert_matches(self, result: object) -> None:
        assert self.trace is not None, "call agent_cassette.load(...) before assert_matches(...)"
        expected = self.trace.final_output
        assert result == expected, (
            f"Live result {result!r} does not match the recorded final_output {expected!r} "
            f"from {self._path}"
        )


@pytest.fixture
def agent_cassette(request: pytest.FixtureRequest) -> AgentCassetteFixture:
    return AgentCassetteFixture(
        record=request.config.getoption("--record"),
        diff_baseline=request.config.getoption("--agent-diff-baseline"),
    )
