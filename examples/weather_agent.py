"""Minimal LangGraph agent used as the recorder demo/fixture.

Deterministic on purpose: it's driven by `FakeMessagesListChatModel` so the
whole pipeline (recorder -> cassette -> assertions) can be exercised without
hitting a real LLM API, exactly like the recorder's own tests need.
"""

from __future__ import annotations

from typing import Annotated, TypedDict

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


def build_weather_agent():
    """Fresh graph + fresh fake model each call — the fake model consumes its
    response list in order, so a shared instance would break repeated runs.
    """
    responses = [
        AIMessage(
            content="",
            tool_calls=[ToolCall(name="get_weather", args={"city": "Warszawa"}, id="call_1")],
        ),
        AIMessage(content="W Warszawie jest 18 stopni"),
    ]
    model = FakeMessagesListChatModel(responses=responses)

    def call_model(state: _State) -> dict:
        return {"messages": [model.invoke(state["messages"])]}

    builder = StateGraph(_State)
    builder.add_node("agent", call_model)
    builder.add_node("tools", ToolNode([get_weather]))
    builder.set_entry_point("agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    return builder.compile()
