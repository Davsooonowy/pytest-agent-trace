"""Resilience assertions — a class of assertion deliberately separate from
`assert_trajectory` (see core/assertions.py). Trajectory assertions check
*what happened*; resilience assertions check *how the agent behaved when
something went wrong* — did it retry, give up cleanly, or keep hammering a
broken tool forever. Meant to be used against a trace produced under chaos
(see core/chaos.py + adapters.langgraph.inject_tool_chaos).
"""

from __future__ import annotations

import json

from agent_test.core.events import ToolCall
from agent_test.core.trace import AgentTrace

_ESCALATION_MARKERS = (
    "nie udało",
    "nie mogę",
    "spróbuj ponownie",
    "skontaktuj",
    "pomoc człowieka",
    "human",
    "unable to",
    "please try again",
    "i cannot",
    "i'm unable",
)


def _tool_call_failed(call: ToolCall) -> bool:
    if call.status == "error":
        return True
    result = call.result
    if result is None:
        return True
    if isinstance(result, str):
        if not result:
            return True
        try:
            json.loads(result)
        except json.JSONDecodeError:
            return True
    return False


class ResilienceAssertion:
    def __init__(self, trace: AgentTrace) -> None:
        self.trace = trace

    def _calls(self, tool_name: str) -> list[ToolCall]:
        calls = [c for c in self.trace.tool_calls if c.tool == tool_name]
        assert calls, f'Tool "{tool_name}" was never called'
        return calls

    def eventually_retries(self, tool_name: str, max: int) -> ResilienceAssertion:
        calls = self._calls(tool_name)
        failed_indexes = [i for i, c in enumerate(calls) if _tool_call_failed(c)]
        assert failed_indexes, (
            f'Tool "{tool_name}" never failed in this trace — nothing to retry after'
        )
        for i in failed_indexes:
            assert i + 1 < len(calls), (
                f'Tool "{tool_name}" failed on call {i + 1} but was never called again '
                "(no retry) before the run ended"
            )
        assert len(calls) <= max, (
            f'Tool "{tool_name}" was called {len(calls)} times, expected at most {max} '
            "(retry budget exceeded)"
        )
        return self

    def does_not_repeat_failed_call_infinitely(
        self, tool_name: str, max_repeats: int
    ) -> ResilienceAssertion:
        calls = self._calls(tool_name)
        worst_streak = 0
        streak = 0
        for c in calls:
            streak = streak + 1 if _tool_call_failed(c) else 0
            worst_streak = max(worst_streak, streak)
        assert worst_streak <= max_repeats, (
            f'Tool "{tool_name}" failed {worst_streak} times in a row '
            f"(max allowed: {max_repeats}) — looks like an infinite retry loop"
        )
        return self

    def escalates_to_human(self) -> ResilienceAssertion:
        output = self.trace.final_output
        assert output is not None, "Trace has no final_output to check for escalation"
        lowered = str(output).lower()
        assert any(marker in lowered for marker in _ESCALATION_MARKERS), (
            f"final_output does not read like an escalation/apology: {output!r}"
        )
        return self

    def eventually_recovers_or_escalates(self, tool_name: str) -> ResilienceAssertion:
        calls = self._calls(tool_name)
        if not _tool_call_failed(calls[-1]):
            return self
        try:
            return self.escalates_to_human()
        except AssertionError as exc:
            raise AssertionError(
                f'Tool "{tool_name}" never succeeded, and the agent did not escalate to a human '
                f"either: {exc}"
            ) from exc

    def does_not_hallucinate_result(self, tool_name: str) -> ResilienceAssertion:
        calls = self._calls(tool_name)
        if not _tool_call_failed(calls[-1]):
            return self
        output = str(self.trace.final_output or "")
        assert not any(ch.isdigit() for ch in output), (
            f'Tool "{tool_name}" never returned a real result, but final_output still contains a '
            f"confident-looking number: {output!r} — looks like a hallucinated result"
        )
        return self


def assert_resilience(trace: AgentTrace) -> ResilienceAssertion:
    return ResilienceAssertion(trace)
