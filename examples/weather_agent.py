"""Minimal LangGraph agent used as the recorder demo/fixture.

Deterministic on purpose: it's driven by `FakeMessagesListChatModel` so the
whole pipeline (recorder -> cassette -> assertions) can be exercised without
hitting a real LLM API, exactly like the recorder's own tests need.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, ToolCall
from langchain_core.tools import tool
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition


@tool
def get_weather(city: str) -> dict:
    """Return the current weather for a city."""
    return {"temp": 18}


class _State(TypedDict):
    messages: Annotated[list, add_messages]


@dataclass
class WeatherAgent:
    graph: Any
    model: Any
    tool: Any


def build_weather_agent(model: Any = None, tool: Any = None) -> WeatherAgent:
    """Fresh graph each call. `model`/`tool` are injectable so replay tests
    can pass in stand-ins (e.g. ones that raise if genuinely invoked) and
    still get back the exact instances the graph will call — needed to patch
    them. Defaults to a deterministic fake model + `get_weather`, matching
    what the recorder tests expect.
    """
    if tool is None:
        tool = get_weather
    if model is None:
        tool_name = getattr(tool, "name", "get_weather")
        responses = [
            AIMessage(
                content="",
                tool_calls=[ToolCall(name=tool_name, args={"city": "Warszawa"}, id="call_1")],
            ),
            AIMessage(content="W Warszawie jest 18 stopni"),
        ]
        model = FakeMessagesListChatModel(responses=responses)

    def call_model(state: _State) -> dict:
        return {"messages": [model.invoke(state["messages"])]}

    builder = StateGraph(_State)
    builder.add_node("agent", call_model)
    builder.add_node("tools", ToolNode([tool]))
    builder.set_entry_point("agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    return WeatherAgent(graph=builder.compile(), model=model, tool=tool)
