"""A genuinely reactive demo agent, used for chaos-engineering tests.

`weather_agent.py`'s `FakeMessagesListChatModel` plays back a fixed script
regardless of what actually happened — fine for recorder/replay/diff tests,
but useless for chaos: a chaos-injected tool failure can't reveal anything
about resilience if the "model" was never going to look at the tool result
in the first place. This model actually inspects the conversation: if the
last tool result looks broken, it retries once, then gives up and escalates
to a human. Deterministic and free (no real API) but reactive.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolCall, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition


@tool
def get_weather(city: str) -> dict:
    """Return the current weather for a city."""
    return {"temp": 18}


def _tool_result_looks_broken(message: ToolMessage) -> bool:
    if getattr(message, "status", None) == "error":
        return True
    content = message.content
    if not content:
        return True
    if isinstance(content, str):
        try:
            json.loads(content)
        except json.JSONDecodeError:
            return True
    return False


class ReactiveChatModel(BaseChatModel):
    """Retries a failed tool call once, then escalates to a human."""

    tool_name: str = "get_weather"
    city: str = "Warszawa"
    max_retries: int = 1

    @property
    def _llm_type(self) -> str:
        return "reactive-weather"

    def _generate(
        self, messages: list, stop: list[str] | None = None, run_manager: Any = None, **kwargs: Any
    ) -> ChatResult:
        tool_messages = [m for m in messages if isinstance(m, ToolMessage)]

        if not tool_messages:
            ai_message = AIMessage(
                content="",
                tool_calls=[ToolCall(name=self.tool_name, args={"city": self.city}, id="call_1")],
            )
        elif (
            _tool_result_looks_broken(tool_messages[-1]) and len(tool_messages) <= self.max_retries
        ):
            ai_message = AIMessage(
                content="",
                tool_calls=[
                    ToolCall(
                        name=self.tool_name,
                        args={"city": self.city},
                        id=f"call_{len(tool_messages) + 1}",
                    )
                ],
            )
        elif _tool_result_looks_broken(tool_messages[-1]):
            ai_message = AIMessage(
                content="Nie udało się pobrać pogody — potrzebna pomoc człowieka"
            )
        else:
            ai_message = AIMessage(content=f"W {self.city} jest {tool_messages[-1].content}")

        return ChatResult(generations=[ChatGeneration(message=ai_message)])


class _State(TypedDict):
    messages: Annotated[list, add_messages]


@dataclass
class ResilientWeatherAgent:
    graph: Any
    model: Any
    tool: Any


def build_resilient_weather_agent(tool: Any = None, max_retries: int = 1) -> ResilientWeatherAgent:
    if tool is None:
        tool = get_weather
    tool_name = getattr(tool, "name", "get_weather")
    model = ReactiveChatModel(tool_name=tool_name, max_retries=max_retries)

    def call_model(state: _State) -> dict:
        return {"messages": [model.invoke(state["messages"])]}

    builder = StateGraph(_State)
    builder.add_node("agent", call_model)
    builder.add_node("tools", ToolNode([tool], handle_tool_errors=True))
    builder.set_entry_point("agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    return ResilientWeatherAgent(graph=builder.compile(), model=model, tool=tool)
