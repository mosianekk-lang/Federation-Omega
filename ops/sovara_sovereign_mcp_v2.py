#!/usr/bin/env python3
"""Single-command MCP ingress for SOVARA Sovereign Intelligence Court v2."""

from __future__ import annotations

from dataclasses import asdict
import os
from pathlib import Path
import sys
from typing import Any, Callable, Literal

OPS_DIR = Path(__file__).resolve().parent
REPO_ROOT = OPS_DIR.parent
for _path in (OPS_DIR, REPO_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from sovara_sovereign_intelligence_court_v2 import (  # noqa: E402
    DEFAULT_OBJECTIVE,
    FileMissionStore,
    LaneReceipt,
    LaneStatus,
    SovereignIntelligenceCourt,
    deterministic_source_reviewer,
)

TOOL_NAME = "sovara_external_model_review"
ReviewMode = Literal[
    "AUTO",
    "CREATIVE",
    "RED_TEAM",
    "ARCHITECTURE",
    "ZERO_DILUTION",
    "PERFORMANCE",
    "SECURITY",
    "10X",
]


def build_store(*, state_dir: Path | None = None):
    backend = os.environ.get("SOVARA_STATE_BACKEND", "file").strip().lower()
    if backend == "file":
        root = state_dir or Path(os.environ.get("SOVARA_STATE_DIR", ".sovara/sovereign-intelligence-court"))
        return FileMissionStore(root)
    if backend == "gcs":
        bucket = os.environ.get("SOVARA_STATE_BUCKET", "").strip()
        if not bucket:
            raise RuntimeError("SOVARA_STATE_BUCKET_REQUIRED_FOR_GCS_BACKEND")
        from sovara_gcs_mission_store_v1 import GCSMissionStore

        return GCSMissionStore(
            bucket_name=bucket,
            prefix=os.environ.get("SOVARA_STATE_PREFIX", "sovara/sic-v2"),
        )
    raise RuntimeError(f"UNSUPPORTED_SOVARA_STATE_BACKEND:{backend}")


def _failing_local_reviewer(error: Exception) -> Callable[[str, str, str], LaneReceipt]:
    """Represent bad local-lane configuration as an isolated lane failure.

    The deterministic lane still runs and the court records this reviewer failure;
    a local configuration mistake must not terminate the whole mission.
    """

    def reviewer(code: str, language: str, objective: str) -> LaneReceipt:
        del code, language, objective
        return LaneReceipt(
            lane_id="local-model-config",
            lane_type="LOCAL_MODEL",
            status=LaneStatus.FAILED.value,
            provider="SOVARA_LOOPBACK",
            error_class=type(error).__name__,
            error_message=str(error)[:1000],
            metadata={"credential_value_recorded": False, "code_executed": False},
        )

    return reviewer


def build_reviewers() -> tuple[Callable[[str, str, str], LaneReceipt], ...]:
    reviewers: list[Callable[[str, str, str], LaneReceipt]] = [deterministic_source_reviewer]
    if os.environ.get("SOVARA_LOCAL_MODEL_URL", "").strip():
        try:
            from sovara_local_model_lane_v1 import reviewer_from_env

            local = reviewer_from_env()
            if local is not None:
                reviewers.append(local)
        except Exception as exc:
            reviewers.append(_failing_local_reviewer(exc))
    return tuple(reviewers)


def run_review(
    code: str,
    *,
    language: str = "text",
    objective: str = DEFAULT_OBJECTIVE,
    mode: ReviewMode = "AUTO",
    max_models: int = 4,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    court = SovereignIntelligenceCourt(
        store=build_store(state_dir=state_dir),
        sovereign_reviewers=build_reviewers(),
    )
    return asdict(
        court.evaluate(
            code,
            language=language,
            objective=objective,
            mode=mode,
            max_models=max_models,
        )
    )


def build_server():
    """Build the MCP server lazily so source-only modules remain independently testable."""
    try:
        from mcp.server.mcpserver import MCPServer
        from mcp.types import ToolAnnotations
    except Exception as exc:  # pragma: no cover - deployment dependency boundary
        raise RuntimeError("MCP_RUNTIME_DEPENDENCY_NOT_INSTALLED") from exc

    server = MCPServer(
        "sovara-sovereign-intelligence-court",
        title="SOVARA Sovereign Intelligence Court",
        version="2.0.0",
        instructions=(
            "Use sovara_external_model_review when the user asks SOVARA to review, red-team, "
            "benchmark, creatively redesign, security-review, performance-review, or zero-dilution "
            "review supplied code. It runs one durable SOVARA transaction. External model outputs "
            "are proposal-only and canonical source is never modified by this tool."
        ),
    )

    @server.tool(
        name=TOOL_NAME,
        title="SOVARA external model review",
        description=(
            "Use this when the user asks for a SOVARA external or multi-model review of supplied code. "
            "The tool checkpoints the mission, may contact authorized external model providers, performs "
            "bounded adversarial/adjudication steps, and returns a sealed proposal-only review receipt. "
            "It never directly modifies or promotes canonical source."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=True,
        ),
    )
    def sovara_external_model_review(
        code: str,
        language: str = "text",
        objective: str = DEFAULT_OBJECTIVE,
        mode: ReviewMode = "AUTO",
        max_models: int = 4,
    ) -> dict[str, Any]:
        return run_review(
            code,
            language=language,
            objective=objective,
            mode=mode,
            max_models=max_models,
        )

    return server


def main() -> int:
    server = build_server()
    server.run(
        transport="streamable-http",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        streamable_http_path="/mcp",
        json_response=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
