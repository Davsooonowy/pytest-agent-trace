import pytest

from agent_test import AgentTrace, assert_trajectory
from agent_test.core.events import LLMCall, RunFinished, RunStarted

CASSETTE = "examples/weather_query.cassette.jsonl"


def test_tool_called_and_final_output():
    trace = AgentTrace.from_cassette(CASSETTE)

    (
        assert_trajectory(trace)
        .tool_called("get_weather", times=1)
        .tool_called_with("get_weather", city="Warszawa")
        .tool_not_called("send_email")
        .order(["get_weather"])
        .max_llm_calls(2)
        .final_output_contains("18")
    )


def test_tool_called_wrong_count_fails():
    trace = AgentTrace.from_cassette(CASSETTE)
    with pytest.raises(AssertionError, match="get_weather"):
        assert_trajectory(trace).tool_called("get_weather", times=2)


def test_tool_not_called_fails_when_called():
    trace = AgentTrace.from_cassette(CASSETTE)
    with pytest.raises(AssertionError):
        assert_trajectory(trace).tool_not_called("get_weather")


def test_tool_called_with_wrong_args_fails():
    trace = AgentTrace.from_cassette(CASSETTE)
    with pytest.raises(AssertionError):
        assert_trajectory(trace).tool_called_with("get_weather", city="Krakow")


def test_max_llm_calls_fails_when_exceeded():
    trace = AgentTrace.from_cassette(CASSETTE)
    with pytest.raises(AssertionError):
        assert_trajectory(trace).max_llm_calls(1)


def test_max_total_tokens_fails_clearly_when_provider_never_reported_usage():
    trace = AgentTrace.from_cassette(CASSETTE)
    with pytest.raises(AssertionError, match="reports token usage"):
        assert_trajectory(trace).max_total_tokens(1000)


def test_max_total_tokens_sums_across_llm_calls():
    trace = AgentTrace(
        [
            RunStarted(seq=1, run_id="r1", input={}),
            LLMCall(seq=2, run_id="r1", response="thinking", total_tokens=150),
            LLMCall(seq=3, run_id="r1", response="18 stopni", total_tokens=200),
            RunFinished(seq=4, run_id="r1", final_output="18 stopni"),
        ]
    )

    assert_trajectory(trace).max_total_tokens(500)
    with pytest.raises(AssertionError, match="used 350"):
        assert_trajectory(trace).max_total_tokens(300)
