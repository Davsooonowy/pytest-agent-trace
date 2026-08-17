from pathlib import Path

import pytest

pytest.importorskip("langgraph")

from resilient_weather_agent import build_resilient_weather_agent  # noqa: E402
from weather_agent import build_weather_agent  # noqa: E402

from agent_test import AgentTrace, ChaosScenario, assert_resilience  # noqa: E402
from agent_test.adapters.langgraph import (  # noqa: E402
    LangGraphRecorder,
    LangGraphReplayer,
    inject_tool_chaos,
)

_INPUT = {"messages": [("user", "Jaka jest pogoda w Warszawie?")]}


def test_inject_tool_chaos_faults_only_the_targeted_call():
    agent = build_resilient_weather_agent()
    scenario = ChaosScenario.timeout(at_step=1, message="boom")

    call = {"name": "get_weather", "args": {"city": "Warszawa"}, "type": "tool_call"}
    with inject_tool_chaos(agent.tool, scenario):
        with pytest.raises(TimeoutError, match="boom"):
            agent.tool.invoke({**call, "id": "c1"})
        # second call isn't targeted -> falls through to the real tool
        result = agent.tool.invoke({**call, "id": "c2"})
        assert result.content == '{"temp": 18}'


def test_reactive_agent_retries_and_recovers_from_transient_timeout(tmp_path: Path):
    agent = build_resilient_weather_agent()
    scenario = ChaosScenario.timeout(at_step=1)
    cassette_path = tmp_path / "chaos_recover.cassette.jsonl"

    with inject_tool_chaos(agent.tool, scenario):
        run_id = LangGraphRecorder(agent.graph, str(cassette_path)).record(_INPUT)

    trace = AgentTrace.from_cassette(cassette_path, run_id=run_id)

    (
        assert_resilience(trace)
        .eventually_retries("get_weather", max=2)
        .does_not_hallucinate_result("get_weather")
        .eventually_recovers_or_escalates("get_weather")
    )
    assert trace.final_output == 'W Warszawa jest {"temp": 18}'


def test_reactive_agent_escalates_after_exhausting_retries(tmp_path: Path):
    agent = build_resilient_weather_agent(max_retries=1)
    scenario = ChaosScenario.timeout([1, 2])
    cassette_path = tmp_path / "chaos_escalate.cassette.jsonl"

    with inject_tool_chaos(agent.tool, scenario):
        run_id = LangGraphRecorder(agent.graph, str(cassette_path)).record(_INPUT)

    trace = AgentTrace.from_cassette(cassette_path, run_id=run_id)

    (
        assert_resilience(trace)
        .does_not_repeat_failed_call_infinitely("get_weather", max_repeats=2)
        .escalates_to_human()
        .eventually_recovers_or_escalates("get_weather")
    )


def test_naive_replayed_agent_hallucinates_under_chaos(tmp_path: Path):
    """The contrast case: weather_agent.py's canned FakeMessagesListChatModel
    doesn't look at the tool result at all, so a chaos-injected tool failure
    exposes a real weakness — the agent confidently repeats its scripted
    answer as if the tool had actually succeeded.

    Uses `empty_result` rather than `timeout`: a *raised* exception would
    propagate straight out of `graph.invoke()` and crash the run, because
    `weather_agent.py`'s `ToolNode` (unlike the resilient demo agent's) was
    never built with `handle_tool_errors=True`. `empty_result` fails the
    same way a real integration silently returning `None` would — no
    exception, just a bad value — which is exactly the case a naive agent
    has no way to notice on its own.
    """
    baseline_agent = build_weather_agent()
    baseline_path = tmp_path / "baseline.cassette.jsonl"
    baseline_run_id = LangGraphRecorder(baseline_agent.graph, str(baseline_path)).record(_INPUT)

    naive_agent = build_weather_agent()
    replayer = LangGraphReplayer.from_cassette(baseline_path, run_id=baseline_run_id)
    chaos_path = tmp_path / "chaos.cassette.jsonl"

    with (
        replayer.patch_model(naive_agent.model),
        inject_tool_chaos(naive_agent.tool, ChaosScenario.empty_result(at_step=1)),
    ):
        chaos_run_id = LangGraphRecorder(naive_agent.graph, str(chaos_path)).record(_INPUT)

    chaos_trace = AgentTrace.from_cassette(chaos_path, run_id=chaos_run_id)

    assert chaos_trace.tool_calls[0].result is None
    with pytest.raises(AssertionError, match="hallucinated"):
        assert_resilience(chaos_trace).does_not_hallucinate_result("get_weather")
