"""Trajectory diff engine — baseline vs new-run regression detection.

Changes in *what tools were actually called and with what args* are
`significant` — that's the part of a trajectory that actually defines
behavior, so it fails a `--agent-diff-baseline` run. Changes in the LLM's
response text or the final answer's wording are `informational` — shown in
the report so nothing is hidden, but they don't fail the test on their own,
because that text is expected to vary even when nothing meaningfully broke
(temperature > 0, minor prompt rewording, a model bump). A tool being
added/removed/reordered, or called with different arguments, is never "just
wording" — so those stay strict with no fuzzy opt-out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from agent_test.core.trace import AgentTrace

Severity = Literal["significant", "informational"]

# Below this, a latency/token-count difference is normal run-to-run jitter,
# not something worth a report line. Deliberately not a CLI flag: richness
# here follows from whatever the cassette actually recorded, not from a
# runtime mode - so this only ever adds informational entries, never a
# reason to fail a build.
_NOTABLE_RELATIVE_CHANGE = 0.5


def _notably_changed(before: int | None, after: int | None) -> bool:
    if before is None or after is None:
        return False
    if before == 0:
        return after != 0
    return abs(after - before) / before >= _NOTABLE_RELATIVE_CHANGE


@dataclass
class DiffEntry:
    severity: Severity
    message: str


@dataclass
class TrajectoryDiff:
    entries: list[DiffEntry] = field(default_factory=list)

    @property
    def is_significant(self) -> bool:
        return any(e.severity == "significant" for e in self.entries)

    def __bool__(self) -> bool:
        return bool(self.entries)

    def render(self) -> str:
        if not self.entries:
            return "Trajectory matches baseline — no differences."
        header = (
            "Trajectory changed vs baseline:"
            if self.is_significant
            else "Trajectory notes vs baseline:"
        )
        lines = [header]
        for entry in self.entries:
            marker = "-" if entry.severity == "significant" else "~"
            lines.append(f"  {marker} {entry.message}")
        return "\n".join(lines)


def diff_trajectories(baseline: AgentTrace, current: AgentTrace) -> TrajectoryDiff:
    diff = TrajectoryDiff()

    baseline_tools = baseline.tool_calls
    current_tools = current.tool_calls
    for i in range(max(len(baseline_tools), len(current_tools))):
        before = baseline_tools[i] if i < len(baseline_tools) else None
        after = current_tools[i] if i < len(current_tools) else None
        step = i + 1
        if before is None:
            assert after is not None
            diff.entries.append(
                DiffEntry(
                    "significant", f'Step {step}: new tool call "{after.tool}" (not in baseline)'
                )
            )
            continue
        if after is None:
            diff.entries.append(
                DiffEntry(
                    "significant",
                    f'Step {step}: tool call "{before.tool}" is missing (was in baseline)',
                )
            )
            continue
        if before.tool != after.tool:
            diff.entries.append(
                DiffEntry("significant", f'Step {step}: tool "{before.tool}" → tool "{after.tool}"')
            )
            continue
        if before.args != after.args:
            diff.entries.append(
                DiffEntry(
                    "significant",
                    f'Step {step}: tool "{before.tool}" args changed: {before.args} → {after.args}',
                )
            )
        if _notably_changed(before.duration_ms, after.duration_ms):
            diff.entries.append(
                DiffEntry(
                    "informational",
                    f'Step {step}: tool "{before.tool}" latency changed: '
                    f"{before.duration_ms}ms → {after.duration_ms}ms",
                )
            )

    baseline_llm = baseline.llm_calls
    current_llm = current.llm_calls
    if len(baseline_llm) != len(current_llm):
        diff.entries.append(
            DiffEntry(
                "informational",
                f"LLM call count changed: {len(baseline_llm)} → {len(current_llm)}",
            )
        )
    else:
        for i, (before_llm, after_llm) in enumerate(zip(baseline_llm, current_llm, strict=True)):
            step = i + 1
            if before_llm.response != after_llm.response:
                diff.entries.append(
                    DiffEntry(
                        "informational",
                        f"Step {step}: LLM response text changed: "
                        f"{before_llm.response!r} → {after_llm.response!r}",
                    )
                )
            if _notably_changed(before_llm.duration_ms, after_llm.duration_ms):
                diff.entries.append(
                    DiffEntry(
                        "informational",
                        f"Step {step}: LLM call latency changed: "
                        f"{before_llm.duration_ms}ms → {after_llm.duration_ms}ms",
                    )
                )
            if _notably_changed(before_llm.total_tokens, after_llm.total_tokens):
                diff.entries.append(
                    DiffEntry(
                        "informational",
                        f"Step {step}: LLM call token usage changed: "
                        f"{before_llm.total_tokens} → {after_llm.total_tokens} total tokens",
                    )
                )

    if baseline.final_output != current.final_output:
        diff.entries.append(
            DiffEntry(
                "informational",
                f"final_output changed: {baseline.final_output!r} → {current.final_output!r}",
            )
        )

    return diff
