"""Chaos scenario library — fault injection for tool calls.

The question nobody asks until an agent falls over in production: "what
happens when a tool returns garbage?" A `ChaosScenario` describes *what*
should go wrong and *at which call(s)* (1-indexed, per tool) it should
happen; the actual injection is framework-specific (see
`adapters.langgraph.inject_tool_chaos`) — this module only knows about
faults, never about LangGraph.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

StepSpec = int | Iterable[int]


def _normalize_steps(at_step: StepSpec) -> list[int]:
    return [at_step] if isinstance(at_step, int) else list(at_step)


class ToolRateLimitedError(RuntimeError):
    """Simulates a tool's backing API responding with HTTP 429."""


@dataclass
class ChaosScenario:
    """A named set of `{call_number: action}` faults for one tool.

    `apply(call_number)` returns `(True, action)` if this call should be
    faulted — the caller invokes `action()` to produce the result (which may
    raise, for fault kinds that simulate an exception) — or `(False, None)`
    to let the call through to the real tool.
    """

    name: str
    _faults: dict[int, Callable[[], Any]] = field(default_factory=dict)

    def apply(self, call_number: int) -> tuple[bool, Callable[[], Any] | None]:
        action = self._faults.get(call_number)
        return (action is not None), action

    @classmethod
    def timeout(cls, at_step: StepSpec, message: str = "tool timed out") -> ChaosScenario:
        def _raise() -> Any:
            raise TimeoutError(message)

        steps = _normalize_steps(at_step)
        return cls(name=f"timeout@{steps}", _faults=dict.fromkeys(steps, _raise))

    @classmethod
    def rate_limited(
        cls, at_step: StepSpec, message: str = "rate limit exceeded (429)"
    ) -> ChaosScenario:
        def _raise() -> Any:
            raise ToolRateLimitedError(message)

        steps = _normalize_steps(at_step)
        return cls(name=f"rate_limited@{steps}", _faults=dict.fromkeys(steps, _raise))

    @classmethod
    def corrupt_json(cls, at_step: StepSpec, raw: str = '{"temp": 18,') -> ChaosScenario:
        """Returns a truncated/malformed JSON string, as if the tool's
        backing API returned a cut-off or corrupted response body."""

        def _return() -> Any:
            return raw

        steps = _normalize_steps(at_step)
        return cls(name=f"corrupt_json@{steps}", _faults=dict.fromkeys(steps, _return))

    @classmethod
    def empty_result(cls, at_step: StepSpec) -> ChaosScenario:
        def _return() -> Any:
            return None

        steps = _normalize_steps(at_step)
        return cls(name=f"empty_result@{steps}", _faults=dict.fromkeys(steps, _return))

    @classmethod
    def contradictory_results(
        cls, step_a: int, value_a: Any, step_b: int, value_b: Any
    ) -> ChaosScenario:
        """Two calls to the *same* tool return conflicting values — e.g. two
        temperature readings for the same city that disagree."""
        return cls(
            name=f"contradictory@{step_a}v{step_b}",
            _faults={step_a: lambda: value_a, step_b: lambda: value_b},
        )
