"""A genuinely reasoning demo agent — asks a local Ollama model an F1
question and lets it decide, for real, whether to call the tool.

Unlike `weather_agent.py`'s `FakeMessagesListChatModel` (a scripted response
list) or `resilient_weather_agent.py`'s hand-rolled reactive stand-in, this
one is a real LLM making a real decision. Requires Ollama running locally
with the model pulled:

    ollama pull llama3.2:3b
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

_STANDINGS = {
    2023: [
        {"position": 1, "driver": "Max Verstappen", "points": 575},
        {"position": 2, "driver": "Sergio Perez", "points": 285},
        {"position": 3, "driver": "Lewis Hamilton", "points": 234},
    ],
    2024: [
        {"position": 1, "driver": "Max Verstappen", "points": 437},
        {"position": 2, "driver": "Lando Norris", "points": 374},
        {"position": 3, "driver": "Charles Leclerc", "points": 356},
    ],
}


@tool
def get_f1_standings(season: int) -> dict:
    """Return the final F1 drivers' championship standings for a given season."""
    return {"season": season, "standings": _STANDINGS.get(season, [])}


class _State(TypedDict):
    messages: Annotated[list, add_messages]


@dataclass
class F1Agent:
    graph: Any
    model: Any
    tool: Any


def build_f1_agent(model_name: str = "llama3.2:3b") -> F1Agent:
    tool_fn = get_f1_standings
    model = ChatOllama(model=model_name, temperature=0)
    bound_model = model.bind_tools([tool_fn])

    def call_model(state: _State) -> dict:
        return {"messages": [bound_model.invoke(state["messages"])]}

    builder = StateGraph(_State)
    builder.add_node("agent", call_model)
    builder.add_node("tools", ToolNode([tool_fn], handle_tool_errors=True))
    builder.set_entry_point("agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    # `model` is the raw ChatOllama instance (not the tools-bound wrapper) so
    # LangGraphReplayer.patch_model can find and patch its _generate/_agenerate
    # directly — bind_tools() returns a RunnableBinding around this same
    # instance, so patching the raw model still takes effect through it.
    return F1Agent(graph=builder.compile(), model=model, tool=tool_fn)
