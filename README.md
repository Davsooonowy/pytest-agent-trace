# pytest-agent-trace

pytest dla agentów AI (LangGraph/LangChain): nagrywa i replayuje pełną
trajektorię agenta (wywołania LLM + narzędzi jako event log), a nie tylko
finalny output, i pozwala asercjonować *jak* agent doszedł do wyniku.

```python
from agent_test import AgentTrace, assert_trajectory

def test_weather_agent():
    trace = AgentTrace.from_cassette("weather_query.cassette.jsonl")

    assert_trajectory(trace) \
        .tool_called("get_weather", times=1) \
        .tool_called_with("get_weather", city="Warszawa") \
        .tool_not_called("send_email") \
        .max_llm_calls(3) \
        .final_output_contains("18")
```

Status: wczesny szkielet (rdzeń + pytest plugin). Recorder/replay dla
LangGraph, diff engine i chaos engineering są w budowie — patrz
[description.md](description.md) po pełną architekturę i roadmapę.
