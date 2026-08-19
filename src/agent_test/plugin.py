"""pytest plugin — registers the `agent_cassette` fixture and record/diff CLI flags.

Registered via the `pytest11` entry point (see pyproject.toml), following the
same pattern pytest-recording/vcr-langchain use for their `vcr` fixture.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import pytest

from agent_test.core.diff import TrajectoryDiff, diff_trajectories
from agent_test.core.trace import AgentTrace

RecordMode = Literal["none", "once", "all"]


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("agent-trace")
    group.addoption(
        "--record-mode",
        choices=["none", "once", "all"],
        default="none",
        help=(
            "none (default): only replay, never run the real agent. "
            "once: run the real agent and record only if the cassette doesn't exist yet, "
            "otherwise replay it. all: always run the real agent and overwrite the cassette."
        ),
    )
    group.addoption(
        "--agent-diff-baseline",
        action="store_true",
        default=False,
        help="Diff the current trajectory against the stored baseline cassette (regression check).",
    )


class AgentCassetteFixture:
    """Handle exposed as the `agent_cassette` fixture inside tests."""

    def __init__(self, record_mode: RecordMode, diff_baseline: bool) -> None:
        self.record_mode = record_mode
        self.diff_baseline = diff_baseline
        # "all" is unambiguous without knowing the path yet; "once" gets
        # refined in load() once we know whether the cassette already exists.
        self.record = record_mode == "all"
        self.trace: AgentTrace | None = None
        self._path: Path | None = None

    def load(self, path: str | Path) -> AgentTrace | None:
        """Point the fixture at a cassette location.

        In replay mode (the default), reads it immediately. In record mode
        there's usually nothing to read yet — that's the point of recording
        — so this only remembers the path; call `record_langgraph` (or
        another framework's `record_*` once it exists) to actually run the
        agent and populate `self.trace`.
        """
        self._path = Path(path)
        if self.record_mode == "once":
            self.record = not self._path.exists()
        if self.record:
            self.trace = None
            return None
        self.trace = AgentTrace.from_cassette(self._path)
        return self.trace

    def record_langgraph(
        self, graph: Any, input: dict[str, Any], run_id: str | None = None, **stream_kwargs: Any
    ) -> AgentTrace:
        """Run a compiled LangGraph graph for real and record it to the path
        given to `load(...)`, then load the result back as `self.trace`.

        Imports `adapters.langgraph` lazily so this plugin has no hard
        dependency on LangGraph — only tests that actually call this need it
        installed.
        """
        assert self._path is not None, "call agent_cassette.load(...) before record_langgraph(...)"
        from agent_test.adapters.langgraph import LangGraphRecorder

        recorded_run_id = LangGraphRecorder(graph, str(self._path)).record(
            input, run_id=run_id, **stream_kwargs
        )
        self.trace = AgentTrace.from_cassette(self._path, run_id=recorded_run_id)
        return self.trace

    def assert_matches(self, result: object) -> None:
        assert self.trace is not None, "call agent_cassette.load(...) before assert_matches(...)"
        expected = self.trace.final_output
        assert result == expected, (
            f"Live result {result!r} does not match the recorded final_output {expected!r} "
            f"from {self._path}"
        )

    def diff_against_baseline(self, baseline_path: str | Path) -> TrajectoryDiff:
        """Diff the loaded/recorded trace against a stored baseline cassette.

        Always returns the `TrajectoryDiff` for inspection. Only raises when
        `--agent-diff-baseline` was passed on the command line *and* the diff
        contains a significant (tool-call-level) change — informational-only
        diffs (LLM wording, final answer phrasing) never fail the test.
        """
        assert self.trace is not None, (
            "call agent_cassette.load(...) before diff_against_baseline(...)"
        )
        baseline_trace = AgentTrace.from_cassette(baseline_path)
        diff = diff_trajectories(baseline_trace, self.trace)
        if self.diff_baseline and diff.is_significant:
            raise AssertionError(diff.render())
        return diff


@pytest.fixture
def agent_cassette(request: pytest.FixtureRequest) -> AgentCassetteFixture:
    return AgentCassetteFixture(
        record_mode=request.config.getoption("--record-mode"),
        diff_baseline=request.config.getoption("--agent-diff-baseline"),
    )
