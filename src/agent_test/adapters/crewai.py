"""CrewAI adapter — placeholder.

Not implemented yet. Once built, this file (and only this file) should know
about CrewAI's own objects, mirroring `adapters/langgraph.py`'s shape:
a `CrewAIRecorder` that hooks into a Crew's execution and writes the same
`core.events` cassette format, so `core/` and the assertion API stay
completely framework-agnostic.

TODO: implement `CrewAIRecorder` once the LangGraph adapter's replay engine
has proven the event schema is sufficient across frameworks.
"""

from __future__ import annotations
