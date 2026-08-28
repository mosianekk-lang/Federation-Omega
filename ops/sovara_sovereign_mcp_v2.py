#!/usr/bin/env python3
"""Chat-facing MCP adapter for SOVARA Sovereign Intelligence Court v2.

This adapter exposes one user-facing tool: `sovara_external_model_review`.
The entire review transaction executes inside SOVARA so a client does not need
to sequence multiple tools correctly.

The implementation uses the Python MCP SDK when installed. Import is deferred so
repository source/test environments without the SDK can still validate the core
court independently.
"""

from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
from typing import Any

from sovara_sovereign_intelligence_court_v2 import MissionStore, SovereignIntelligenceCourt

TOOL_NAME = "sovara_external_model_review"
DEFAULT_STATE_DIR = Path(os.environ.get("SOVARA_STATE_DIR", ".sovara/sovereign-intelligence-court"))


def run_review(
    code: str,
    *,
    language: str = "text",
    objective: str | None = None,
    mode: str = "AUTO",
    max_models: int = 4,
) -> dict[str, Any]:
    court = SovereignIntelligenceCourt(mission_store=MissionStore(DEFAULT_STATE_DIR))
    result = court.evaluate(
        code,
        language=language,
        objective=objective or "Find defects and propose materially better architectures without changing intended behavior.",
        mode=mode,
        max_models=max_models,
    )
    return asdict(result)


def _build_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception as exc:  # pragma: no cover - deployment dependency boundary
        raise RuntimeError(
            "Python MCP SDK is required for chat-native service deployment. "
            "Install the repository's MCP runtime dependencies before serving."
        ) from exc

    server = FastMCP(
        "SOVARA Sovereign Intelligence Court",
        instructions=(
            "Use sovara_external_model_review when the user asks SOVARA to review, red-team, "
            "benchmark, creatively redesign, security-review, performance-review, or zero-dilution "
            "review a supplied code block. External model outputs are proposal-only; return the "
            "SOVARA adjudicated result and never claim canonical source was modified."
        ),
    )

    @server.tool(
        name=TOOL_NAME,
        description=(
            "Use this when the user asks for a SOVARA external model review of supplied code. "
            "Runs one durable, resumable SOVARA evaluation transaction and returns the adjudicated "
            "proposal-only result. The tool does not modify canonical code."
        ),
    )
    def sovara_external_model_review(
        code: str,
        language: str = "text",
        objective: str = "Find defects and propose materially better architectures without changing intended behavior.",
        mode: str = "AUTO",
        max_models: int = 4,
    ) -> str:
        result = run_review(
            code,
            language=language,
            objective=objective,
            mode=mode,
            max_models=max_models,
        )
        return json.dumps(result, ensure_ascii=False, sort_keys=True)

    return server


def main() -> int:
    server = _build_server()
    # Streamable HTTP is the deployment target for ChatGPT connections.
    # The MCP SDK owns protocol framing; SOVARA owns mission state.
    server.run(transport="streamable-http")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
