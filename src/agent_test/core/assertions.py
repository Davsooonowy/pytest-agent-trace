"""Fluent trajectory assertions.

Testujemy proces (kolejność/argumenty wywołań narzędzi, liczbę kroków LLM),
nie tylko finalny output. Każda metoda zwraca `self`, więc wywołania się
łańcuchują i każde niepowodzenie ujawnia dokładnie, który krok trajektorii
nie zgadza się z oczekiwaniem.
"""

from __future__ import annotations

from typing import Any

from agent_test.core.trace import AgentTrace


class TrajectoryAssertion:
    def __init__(self, trace: AgentTrace) -> None:
        self.trace = trace

    def tool_called(self, name: str, times: int | None = None) -> "TrajectoryAssertion":
        count = self.trace.tool_call_count(name)
        if times is None:
            assert count > 0, f'Tool "{name}" was never called (trajectory: {self._tool_names()})'
        else:
            assert count == times, (
                f'Tool "{name}" expected {times} call(s), got {count} '
                f"(trajectory: {self._tool_names()})"
            )
        return self

    def tool_not_called(self, name: str) -> "TrajectoryAssertion":
        count = self.trace.tool_call_count(name)
        assert count == 0, f'Tool "{name}" was called {count} time(s), expected 0'
        return self

    def tool_called_with(self, name: str, **kwargs: Any) -> "TrajectoryAssertion":
        calls = [c for c in self.trace.tool_calls if c.tool == name]
        assert calls, f'Tool "{name}" was never called'
        for call in calls:
            if all(call.args.get(k) == v for k, v in kwargs.items()):
                return self
        actual_args = [c.args for c in calls]
        raise AssertionError(
            f'Tool "{name}" was called, but never with args {kwargs}. Actual args: {actual_args}'
        )

    def order(self, tool_names: list[str]) -> "TrajectoryAssertion":
        actual = self._tool_names()
        it = iter(actual)
        for expected_name in tool_names:
            if expected_name not in it:
                raise AssertionError(
                    f"Expected tool order {tool_names} as a subsequence, "
                    f"but got {actual} — missing/out-of-order: {expected_name!r}"
                )
        return self

    def max_llm_calls(self, n: int) -> "TrajectoryAssertion":
        count = len(self.trace.llm_calls)
        assert count <= n, f"Expected at most {n} LLM call(s), got {count}"
        return self

    def final_output_contains(self, substring: str) -> "TrajectoryAssertion":
        output = self.trace.final_output
        assert output is not None, "Trace has no final_output (run_finished event missing)"
        assert substring in str(output), f"final_output {output!r} does not contain {substring!r}"
        return self

    def _tool_names(self) -> list[str]:
        return [c.tool for c in self.trace.tool_calls]


def assert_trajectory(trace: AgentTrace) -> TrajectoryAssertion:
    return TrajectoryAssertion(trace)
