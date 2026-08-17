"""Google ADK 2 graph entrypoint using the same governed JARVIS request path."""

from __future__ import annotations

import os
from typing import Any

from google.adk import Event, Workflow

from .orchestrator import Jarvis


_JARVIS = Jarvis(os.getenv("JARVIS_STATE_DIR", "state"))


def governed_reasoning(node_input: str):
    """Run the canonical deterministic graph; no ADK tool receives effectful authority."""
    result = _JARVIS.chat(str(node_input))
    yield Event(output=result)


def emit_verified_response(node_input: dict[str, Any]):
    """Expose only the semantically checked response from the canonical graph."""
    yield Event(
        message=str(node_input["answer"]),
        output={
            "semanticFruit": bool(node_input["semanticFruit"]),
            "learningHash": str(node_input["learningHash"]),
            "providerMode": str(node_input["providerMode"]),
        },
    )


root_agent = Workflow(
    name="jarvis_ultimate_governed_workflow",
    edges=[("START", governed_reasoning, emit_verified_response)],
)
