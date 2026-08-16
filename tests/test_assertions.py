import pytest

from agent_test import AgentTrace, assert_trajectory

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
