"""Tests against a real (not fake) reasoning model.

`test_replay_*` never touches the network — it patches the model/tool before
any real call happens, same as the other replay tests — so it always runs.
`test_records_a_real_run_against_live_ollama` needs an actual local Ollama
server with `llama3.2:3b` pulled; it's skipped everywhere else instead of
failing the suite.
"""

from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest

pytest.importorskip("langgraph")
pytest.importorskip("langchain_ollama")

from f1_agent import build_f1_agent  # noqa: E402

from agent_test import AgentTrace, assert_trajectory  # noqa: E402
from agent_test.adapters.langgraph import LangGraphRecorder, LangGraphReplayer  # noqa: E402

CASSETTE = (Path(__file__).parent.parent / "examples" / "f1_standings.cassette.jsonl").resolve()
QUESTION = {"messages": [("user", "Who won the F1 drivers championship in 2024?")]}


def _ollama_is_running() -> bool:
    try:
        urlopen("http://localhost:11434/api/tags", timeout=1)
    except (URLError, OSError):
        return False
    return True


def test_replay_reproduces_the_recorded_trajectory_offline():
    agent = build_f1_agent()
    replayer = LangGraphReplayer.from_cassette(CASSETTE)

    with replayer.patch(agent.model, [agent.tool]):
        result = agent.graph.invoke(QUESTION)

    assert "Verstappen" in result["messages"][-1].content


def test_recorded_cassette_passes_trajectory_assertions():
    trace = AgentTrace.from_cassette(CASSETTE)

    (
        assert_trajectory(trace)
        .tool_called("get_f1_standings", times=1)
        .tool_called_with("get_f1_standings", season=2024)
        .final_output_contains("Verstappen")
    )


@pytest.mark.skipif(not _ollama_is_running(), reason="requires a local Ollama server")
def test_records_a_real_run_against_live_ollama(tmp_path: Path):
    agent = build_f1_agent()
    cassette_path = tmp_path / "f1_live.cassette.jsonl"

    run_id = LangGraphRecorder(agent.graph, str(cassette_path)).record(QUESTION)

    trace = AgentTrace.from_cassette(cassette_path, run_id=run_id)
    assert_trajectory(trace).tool_called("get_f1_standings", times=1)
    assert trace.final_output is not None
