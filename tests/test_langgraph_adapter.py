from pathlib import Path

import pytest

pytest.importorskip("langgraph")

from weather_agent import build_weather_agent  # noqa: E402

from agent_test import AgentTrace, assert_trajectory  # noqa: E402
from agent_test.adapters.langgraph import LangGraphRecorder  # noqa: E402


def test_records_a_real_run_into_a_valid_cassette(tmp_path: Path):
    graph = build_weather_agent()
    cassette_path = tmp_path / "weather_query.cassette.jsonl"
    recorder = LangGraphRecorder(graph, str(cassette_path))

    run_id = recorder.record({"messages": [("user", "Jaka jest pogoda w Warszawie?")]})

    assert cassette_path.exists()
    trace = AgentTrace.from_cassette(cassette_path, run_id=run_id)

    (
        assert_trajectory(trace)
        .tool_called("get_weather", times=1)
        .tool_called_with("get_weather", city="Warszawa")
        .tool_not_called("send_email")
        .final_output_contains("18")
    )

    tool_event = trace.tool_calls[0]
    assert tool_event.result == {"temp": 18}
    assert tool_event.duration_ms is not None and tool_event.duration_ms >= 0

    llm_events = trace.llm_calls
    assert len(llm_events) == 2
    assert llm_events[1].parent_seq == tool_event.seq


def test_cassette_is_plain_jsonl_lines(tmp_path: Path):
    graph = build_weather_agent()
    cassette_path = tmp_path / "weather_query.cassette.jsonl"
    LangGraphRecorder(graph, str(cassette_path)).record(
        {"messages": [("user", "Jaka jest pogoda w Warszawie?")]}
    )

    lines = cassette_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 5
    assert '"type":"run_started"' in lines[0]
    assert '"type":"run_finished"' in lines[-1]
