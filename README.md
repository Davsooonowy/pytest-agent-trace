# pytest-agent-trace

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/Davsooonowy/pytest-agent-trace/blob/master/LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue)](https://www.python.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://img.shields.io/badge/mypy-checked-blue)](https://mypy-lang.org/)

**pytest for AI agents.** Record, replay, diff, and stress-test what your LangGraph agent actually *does* — not just what it answers.

## The problem

`pytest` assumes `f(x)` returns the same `y` every time. An LLM agent breaks that assumption on purpose: the same input can produce a different tool call, a different order, a different number of steps, every single run. `assert result == expected` doesn't survive contact with an agent, and most evaluation tools respond by giving up on the process entirely and scoring only the final answer with another LLM.

That throws away the part that actually breaks in production. An agent that calls the right tool with the wrong arguments, calls a tool twice it should only call once, or silently skips a step your prompt promised — all of that can still produce a final answer that *sounds* fine. `pytest-agent-trace` tests the trajectory: which tools got called, in what order, with what arguments, and how the agent behaves when one of them fails.

## Quickstart

```python
from agent_test import assert_trajectory


def test_weather_agent(agent_cassette):
    from weather_agent import build_weather_agent

    agent = build_weather_agent()
    agent_cassette.load("cassettes/weather.jsonl")

    if agent_cassette.record:
        agent_cassette.record_langgraph(
            agent.graph, {"messages": [("user", "What's the weather in Warsaw?")]}
        )

    (
        assert_trajectory(agent_cassette.trace)
        .tool_called("get_weather", times=1)
        .tool_called_with("get_weather", city="Warsaw")
        .tool_not_called("send_email")
        .final_output_contains("18")
    )
```

```bash
pytest --record-mode=once   # cassette missing: runs the real agent, writes cassettes/weather.jsonl
pytest --record-mode=once   # cassette exists: replays it instead, no API calls, no cost
```

## Install

```bash
pip install "pytest-agent-trace[langgraph]"
```

The distribution is `pytest-agent-trace`; the package you import is `agent_test`. The pytest plugin registers itself automatically via the `pytest11` entry point — no `conftest.py` wiring needed.

## How it works

```
pytest plugin (agent_cassette fixture, --record-mode / --agent-diff-baseline)
        │
assertion library (assert_trajectory, assert_resilience)
        │
diff engine (baseline vs. new run)
        │
recorder / replay (adapters/langgraph.py)
        │
cassette — an append-only JSONL event log
```

A cassette is not a nested blob of JSON — it's one event per line:

```jsonl
{"seq": 1, "type": "run_started", "run_id": "r1", "input": {"query": "weather in Warsaw?"}}
{"seq": 2, "type": "llm_call", "run_id": "r1", "parent_seq": 1, "response": "Let me check the weather"}
{"seq": 3, "type": "tool_call", "run_id": "r1", "parent_seq": 2, "tool": "get_weather", "args": {"city": "Warsaw"}, "result": {"temp": 18}}
{"seq": 4, "type": "llm_call", "run_id": "r1", "parent_seq": 3, "response": "It's 18°C in Warsaw"}
{"seq": 5, "type": "run_finished", "run_id": "r1", "final_output": "It's 18°C in Warsaw"}
```

That's deliberate: a new event type is a new variant, not a migration of every cassette you've already recorded; `git diff` on two cassettes reads line by line instead of re-indenting a whole tree; and replaying from a checkpoint is a fold over a prefix of events instead of a full-tree parse.

Recording hooks into LangGraph's own `astream_events` stream rather than subclassing `BaseCallbackHandler`, since callback internals get restructured between LangGraph minor versions and `astream_events` doesn't. Replay works by swapping out the model's and tools' leaf methods (`_generate`/`_run`) for ones that answer from the cassette in order — the outer tracing and message-wrapping machinery stays untouched, so a replayed run is indistinguishable from a live one to everything downstream, including this project's own diff and chaos tooling. The core (`core/trace.py`, `core/assertions.py`, `core/diff.py`, `core/chaos.py`, `core/resilience.py`) never imports a LangGraph object directly — everything framework-specific lives in `adapters/langgraph.py`.

## Trajectory assertions

```python
(
    assert_trajectory(trace)
    .tool_called("get_weather", times=1)
    .tool_called_with("get_weather", city="Warsaw")
    .tool_not_called("send_email")
    .order(["get_weather", "format_response"])
    .max_llm_calls(3)
    .final_output_contains("18")
)
```

## Regression detection

Record a known-good trajectory once as a baseline. Later — after a prompt edit, a model bump, a refactor — diff the new run against it:

```bash
pytest --agent-diff-baseline
```

```
Trajectory changed vs baseline:
  - Step 2: tool "get_weather" → tool "get_weather_v2"
  ~ Step 3: LLM response text changed: 'Checking now' → 'Let me look that up'
```

Tool-call structure — a tool added, removed, renamed, or called with different arguments — is *significant* and fails the run. Wording differences in the model's own text or the final answer are *informational*: shown so nothing is hidden, but never failing the build on their own, because that text is expected to drift run to run even when nothing actually broke.

## Chaos engineering

Everyone finds out how their agent handles a broken tool call in production. `pytest-agent-trace` lets you find out first:

```python
from agent_test import ChaosScenario, assert_resilience
from agent_test.adapters.langgraph import LangGraphRecorder, inject_tool_chaos


def test_agent_recovers_from_a_timeout(tmp_path):
    agent = build_resilient_weather_agent()
    cassette = tmp_path / "chaos.jsonl"

    with inject_tool_chaos(agent.tool, ChaosScenario.timeout(at_step=1)):
        run_id = LangGraphRecorder(agent.graph, str(cassette)).record(
            {"messages": [("user", "weather in Warsaw?")]}
        )

    trace = AgentTrace.from_cassette(cassette, run_id=run_id)
    assert_resilience(trace).eventually_recovers_or_escalates("get_weather")
```

The scenario library covers the failures that actually happen to a tool call: `timeout`, `rate_limited`, `corrupt_json`, `empty_result`, `contradictory_results`. `assert_resilience` is an assertion class deliberately separate from `assert_trajectory` — it asks *how did the agent behave when something broke*, not *what did it do*: `eventually_retries`, `does_not_repeat_failed_call_infinitely`, `escalates_to_human`, `eventually_recovers_or_escalates`, `does_not_hallucinate_result`.

Fault injection wraps the real tool, on purpose — it does not go through the cassette. Replaying a script can't tell you whether your agent is resilient; only a live (or genuinely reactive) model reacting to a fault can.

## CLI

```bash
agent-trace show cassettes/weather.jsonl        # print a cassette's event timeline
agent-trace diff baseline.jsonl current.jsonl   # diff two cassettes outside pytest
```

## Development

```bash
git clone https://github.com/Davsooonowy/pytest-agent-trace.git
cd pytest-agent-trace
uv sync --extra langgraph --extra dev

uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

## License

MIT — see [LICENSE](https://github.com/Davsooonowy/pytest-agent-trace/blob/master/LICENSE).
