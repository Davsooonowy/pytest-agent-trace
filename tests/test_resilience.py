import pytest

from agent_test.core.events import RunFinished, RunStarted, ToolCall
from agent_test.core.resilience import assert_resilience
from agent_test.core.trace import AgentTrace


def _trace(*, tool_results: list[object], statuses: list[str], final_output: object) -> AgentTrace:
    events = [RunStarted(seq=1, run_id="r1", input={})]
    seq = 1
    for result, status in zip(tool_results, statuses, strict=True):
        seq += 1
        events.append(
            ToolCall(
                seq=seq, run_id="r1", tool="get_weather", args={}, result=result, status=status
            )
        )
    seq += 1
    events.append(RunFinished(seq=seq, run_id="r1", final_output=final_output))
    return AgentTrace(events)


def test_eventually_retries_passes_when_failure_is_followed_by_another_call():
    trace = _trace(
        tool_results=[None, {"temp": 18}],
        statuses=["ok", "ok"],
        final_output="18 stopni",
    )
    assert_resilience(trace).eventually_retries("get_weather", max=3)


def test_eventually_retries_fails_when_no_retry_happens():
    trace = _trace(tool_results=[None], statuses=["ok"], final_output="18 stopni")
    with pytest.raises(AssertionError, match="never called again"):
        assert_resilience(trace).eventually_retries("get_weather", max=3)


def test_eventually_retries_fails_when_over_budget():
    trace = _trace(
        tool_results=[None, None, None, {"temp": 18}],
        statuses=["ok", "ok", "ok", "ok"],
        final_output="18 stopni",
    )
    with pytest.raises(AssertionError, match="retry budget exceeded"):
        assert_resilience(trace).eventually_retries("get_weather", max=2)


def test_does_not_repeat_failed_call_infinitely_fails_on_long_streak():
    trace = _trace(
        tool_results=[None, None, None, None],
        statuses=["ok", "ok", "ok", "ok"],
        final_output="brak odpowiedzi",
    )
    with pytest.raises(AssertionError, match="infinite retry loop"):
        assert_resilience(trace).does_not_repeat_failed_call_infinitely(
            "get_weather", max_repeats=2
        )


def test_escalates_to_human_passes_on_apology():
    trace = _trace(
        tool_results=[None],
        statuses=["ok"],
        final_output="Nie udało mi się pobrać pogody, potrzebna pomoc człowieka.",
    )
    assert_resilience(trace).escalates_to_human()


def test_escalates_to_human_fails_on_confident_wrong_answer():
    trace = _trace(tool_results=[None], statuses=["ok"], final_output="W Warszawie jest 18 stopni")
    with pytest.raises(AssertionError, match="escalation"):
        assert_resilience(trace).escalates_to_human()


def test_eventually_recovers_or_escalates_passes_on_recovery():
    trace = _trace(
        tool_results=[None, {"temp": 18}],
        statuses=["ok", "ok"],
        final_output="18 stopni",
    )
    assert_resilience(trace).eventually_recovers_or_escalates("get_weather")


def test_eventually_recovers_or_escalates_fails_when_neither_happens():
    trace = _trace(tool_results=[None], statuses=["ok"], final_output="18 stopni")
    with pytest.raises(AssertionError, match="did not escalate"):
        assert_resilience(trace).eventually_recovers_or_escalates("get_weather")


def test_does_not_hallucinate_result_fails_when_confident_number_follows_failure():
    trace = _trace(tool_results=[None], statuses=["ok"], final_output="W Warszawie jest 18 stopni")
    with pytest.raises(AssertionError, match="hallucinated"):
        assert_resilience(trace).does_not_hallucinate_result("get_weather")


def test_does_not_hallucinate_result_passes_when_tool_succeeded():
    trace = _trace(
        tool_results=[{"temp": 18}], statuses=["ok"], final_output="W Warszawie jest 18 stopni"
    )
    assert_resilience(trace).does_not_hallucinate_result("get_weather")


def test_error_status_counts_as_failed_even_with_content():
    trace = _trace(
        tool_results=["Error: TimeoutError('x')"],
        statuses=["error"],
        final_output="W Warszawie jest 18 stopni",
    )
    with pytest.raises(AssertionError, match="hallucinated"):
        assert_resilience(trace).does_not_hallucinate_result("get_weather")
