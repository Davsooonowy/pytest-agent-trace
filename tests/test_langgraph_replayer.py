from pathlib import Path

import pytest

pytest.importorskip("langgraph")

from langchain_core.language_models.chat_models import BaseChatModel  # noqa: E402
from langchain_core.tools import tool  # noqa: E402
from weather_agent import build_weather_agent  # noqa: E402

from agent_test import AgentTrace, assert_trajectory  # noqa: E402
from agent_test.adapters.langgraph import (  # noqa: E402
    LangGraphRecorder,
    LangGraphReplayer,
    ReplayExhaustedError,
)


class _PoisonChatModel(BaseChatModel):
    """A chat model that fails loudly if it's ever really invoked — proves
    replay never falls through to a real API call."""

    @property
    def _llm_type(self) -> str:
        return "poison"

    def _generate(self, *args, **kwargs):
        raise AssertionError("real chat model was invoked during replay")


@tool("get_weather")
def _poison_get_weather(city: str) -> dict:
    """Return the current weather for a city."""
    raise AssertionError("real tool was invoked during replay")


def _record_weather_cassette(tmp_path: Path) -> tuple[Path, str]:
    agent = build_weather_agent()
    cassette_path = tmp_path / "weather_query.cassette.jsonl"
    run_id = LangGraphRecorder(agent.graph, str(cassette_path)).record(
        {"messages": [("user", "Jaka jest pogoda w Warszawie?")]}
    )
    return cassette_path, run_id


def test_replay_never_calls_the_real_model_or_tool(tmp_path: Path):
    cassette_path, run_id = _record_weather_cassette(tmp_path)

    poison_agent = build_weather_agent(model=_PoisonChatModel(), tool=_poison_get_weather)
    replayer = LangGraphReplayer.from_cassette(cassette_path, run_id=run_id)

    with replayer.patch(poison_agent.model, [poison_agent.tool]):
        result = poison_agent.graph.invoke(
            {"messages": [("user", "Jaka jest pogoda w Warszawie?")]}
        )

    assert result["messages"][-1].content == "W Warszawie jest 18 stopni"


def test_replay_produces_a_trajectory_that_passes_the_same_assertions(tmp_path: Path):
    cassette_path, run_id = _record_weather_cassette(tmp_path)

    poison_agent = build_weather_agent(model=_PoisonChatModel(), tool=_poison_get_weather)
    replayer = LangGraphReplayer.from_cassette(cassette_path, run_id=run_id)

    replay_cassette_path = tmp_path / "replayed.cassette.jsonl"
    with replayer.patch(poison_agent.model, [poison_agent.tool]):
        replay_run_id = LangGraphRecorder(poison_agent.graph, str(replay_cassette_path)).record(
            {"messages": [("user", "Jaka jest pogoda w Warszawie?")]}
        )

    replay_trace = AgentTrace.from_cassette(replay_cassette_path, run_id=replay_run_id)
    (
        assert_trajectory(replay_trace)
        .tool_called("get_weather", times=1)
        .tool_called_with("get_weather", city="Warszawa")
        .final_output_contains("18")
    )


def test_replay_exhausted_raises_past_the_recorded_call_count(tmp_path: Path):
    cassette_path, run_id = _record_weather_cassette(tmp_path)
    replayer = LangGraphReplayer.from_cassette(cassette_path, run_id=run_id)

    poison_model = _PoisonChatModel()
    with replayer.patch_model(poison_model):
        poison_model.invoke([])
        poison_model.invoke([])  # exactly 2 llm_call events were recorded
        with pytest.raises(ReplayExhaustedError):
            poison_model.invoke([])
