from pathlib import Path

from agent_test.core.cassette import CassetteWriter, load_cassette, save_cassette
from agent_test.core.events import LLMCall, RunFinished, RunStarted, ToolCall

CASSETTE = "examples/weather_query.cassette.jsonl"


def test_load_cassette_parses_discriminated_union():
    events = load_cassette(CASSETTE)

    assert [type(e).__name__ for e in events] == [
        "RunStarted",
        "LLMCall",
        "ToolCall",
        "LLMCall",
        "RunFinished",
    ]
    assert isinstance(events[0], RunStarted)
    assert events[0].input == {"query": "Jaka jest pogoda w Warszawie?"}
    assert isinstance(events[2], ToolCall)
    assert events[2].tool == "get_weather"
    assert events[2].args == {"city": "Warszawa"}


def test_save_and_reload_roundtrip(tmp_path: Path):
    events = load_cassette(CASSETTE)
    out = tmp_path / "roundtrip.jsonl"

    save_cassette(out, events)
    reloaded = load_cassette(out)

    assert reloaded == events


def test_cassette_writer_appends_and_assigns_seq(tmp_path: Path):
    out = tmp_path / "recorded.jsonl"
    writer = CassetteWriter(out)

    run_id = "r1"
    writer.append(RunStarted(seq=writer.next_seq(), run_id=run_id, input={"query": "hi"}))
    writer.append(LLMCall(seq=writer.next_seq(), run_id=run_id, parent_seq=1, response="thinking"))
    writer.append(
        RunFinished(seq=writer.next_seq(), run_id=run_id, parent_seq=2, final_output="done")
    )

    reloaded = load_cassette(out)
    assert [e.seq for e in reloaded] == [1, 2, 3]
    assert writer.events == reloaded
