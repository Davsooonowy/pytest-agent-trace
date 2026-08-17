from agent_test.core.diff import diff_trajectories
from agent_test.core.events import LLMCall, RunFinished, RunStarted, ToolCall
from agent_test.core.trace import AgentTrace


def _trace(
    *, tool_calls: list[tuple[str, dict]], responses: list[str], final_output: object
) -> AgentTrace:
    """Build an AgentTrace from a compact spec, interleaving llm_call/tool_call
    events in the shape a real recording would produce: llm, tool, llm, tool, ...
    """
    events = [RunStarted(seq=1, run_id="r1", input={})]
    seq = 1
    for i, (tool, args) in enumerate(tool_calls):
        seq += 1
        events.append(
            LLMCall(seq=seq, run_id="r1", response=responses[i] if i < len(responses) else "")
        )
        seq += 1
        events.append(ToolCall(seq=seq, run_id="r1", tool=tool, args=args))
    seq += 1
    events.append(LLMCall(seq=seq, run_id="r1", response=responses[-1] if responses else ""))
    seq += 1
    events.append(RunFinished(seq=seq, run_id="r1", final_output=final_output))
    return AgentTrace(events)


def test_identical_trajectories_have_no_significant_diff():
    baseline = _trace(
        tool_calls=[("get_weather", {"city": "Warszawa"})],
        responses=["thinking", "18 stopni"],
        final_output="18 stopni",
    )
    current = _trace(
        tool_calls=[("get_weather", {"city": "Warszawa"})],
        responses=["thinking", "18 stopni"],
        final_output="18 stopni",
    )

    diff = diff_trajectories(baseline, current)

    assert not diff
    assert diff.is_significant is False


def test_new_tool_call_is_significant():
    baseline = _trace(tool_calls=[], responses=["ok"], final_output="ok")
    current = _trace(
        tool_calls=[("send_email", {"to": "x@example.com"})],
        responses=["thinking", "ok"],
        final_output="ok",
    )

    diff = diff_trajectories(baseline, current)

    assert diff.is_significant
    assert any("send_email" in e.message and e.severity == "significant" for e in diff.entries)


def test_missing_tool_call_is_significant():
    baseline = _trace(
        tool_calls=[("get_weather", {"city": "Warszawa"})],
        responses=["thinking", "ok"],
        final_output="ok",
    )
    current = _trace(tool_calls=[], responses=["ok"], final_output="ok")

    diff = diff_trajectories(baseline, current)

    assert diff.is_significant
    assert any(
        "get_weather" in e.message and "missing" in e.message and e.severity == "significant"
        for e in diff.entries
    )


def test_renamed_tool_is_significant():
    baseline = _trace(
        tool_calls=[("get_weather", {"city": "Warszawa"})],
        responses=["thinking", "ok"],
        final_output="ok",
    )
    current = _trace(
        tool_calls=[("get_weather_v2", {"city": "Warszawa"})],
        responses=["thinking", "ok"],
        final_output="ok",
    )

    diff = diff_trajectories(baseline, current)

    assert diff.is_significant
    assert any('"get_weather" → tool "get_weather_v2"' in e.message for e in diff.entries)


def test_changed_tool_args_is_significant():
    baseline = _trace(
        tool_calls=[("get_weather", {"city": "Warszawa"})],
        responses=["thinking", "ok"],
        final_output="ok",
    )
    current = _trace(
        tool_calls=[("get_weather", {"city": "Krakow"})],
        responses=["thinking", "ok"],
        final_output="ok",
    )

    diff = diff_trajectories(baseline, current)

    assert diff.is_significant
    assert any("args changed" in e.message for e in diff.entries)


def test_different_llm_wording_is_informational_only():
    baseline = _trace(
        tool_calls=[("get_weather", {"city": "Warszawa"})],
        responses=["Sprawdzam pogodę", "W Warszawie jest 18 stopni"],
        final_output="W Warszawie jest 18 stopni",
    )
    current = _trace(
        tool_calls=[("get_weather", {"city": "Warszawa"})],
        responses=["Muszę sprawdzić pogodę", "Aktualnie w Warszawie 18 stopni"],
        final_output="Aktualnie w Warszawie 18 stopni",
    )

    diff = diff_trajectories(baseline, current)

    assert diff.entries  # something to report
    assert diff.is_significant is False
    assert all(e.severity == "informational" for e in diff.entries)
