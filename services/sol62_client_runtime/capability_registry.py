from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Iterable


REGISTRY_SCHEMA = "SOL62_CAPABILITY_REGISTRY_V1"


@dataclass(frozen=True)
class CapabilityBinding:
    capability_id: str
    family: str
    transport: str
    maturity: str
    callable: bool
    runtime_native: bool
    authority: str
    operations: tuple[str, ...] = ("*",)
    failure_domain: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["operations"] = list(self.operations)
        return row


def _binding(
    capability_id: str,
    family: str,
    transport: str,
    maturity: str,
    *,
    callable: bool,
    runtime_native: bool,
    authority: str = "ACTION_SPECIFIC",
    operations: Iterable[str] = ("*",),
    failure_domain: str = "",
    notes: str = "",
) -> CapabilityBinding:
    return CapabilityBinding(
        capability_id=capability_id,
        family=family,
        transport=transport,
        maturity=maturity,
        callable=callable,
        runtime_native=runtime_native,
        authority=authority,
        operations=tuple(operations),
        failure_domain=failure_domain or family,
        notes=notes,
    )


def built_in_bindings(*, gateway_execution_ready: bool) -> tuple[CapabilityBinding, ...]:
    """Truthful SOL 6.2 capability census.

    runtime_native=True means the server runtime has a concrete adapter in this
    repository/runtime. CHAT_SESSION_TOOL means the current authorized client
    may expose the capability through its tool plane; that never promotes the
    standalone SOL server to provider-callable without a bridge/readback.
    """
    rows = [
        _binding(
            "FUSE-GATEWAY",
            "FUSE",
            "FUSE_GATEWAY",
            "RUNTIME_BOUND" if gateway_execution_ready else "CONFIGURED_UNBOUND",
            callable=gateway_execution_ready,
            runtime_native=True,
            authority="OWNER_SESSION_PLUS_ROUTE_POLICY",
            failure_domain="FUSE_GATEWAY",
        ),
        _binding(
            "GOOGLE-VERTEX-GEMINI",
            "GOOGLE_AI",
            "FUSE_GATEWAY:VertexGeminiClient",
            "RUNTIME_BOUND" if gateway_execution_ready else "CONFIGURED_UNBOUND",
            callable=gateway_execution_ready,
            runtime_native=True,
            authority="ADC_SERVER_SIDE",
            failure_domain="GOOGLE_VERTEX",
        ),
        _binding(
            "KDV-GOOGLE-SHEETS",
            "GOOGLE_WORKSPACE",
            "FUSE_GATEWAY:KDVSheetsReader",
            "RUNTIME_BOUND" if gateway_execution_ready else "CONFIGURED_UNBOUND",
            callable=gateway_execution_ready,
            runtime_native=True,
            authority="ADC_SERVER_SIDE_READ",
            operations=("read", "currentness"),
            failure_domain="GOOGLE_SHEETS",
        ),
        _binding(
            "FUSE-GENESIS-RESIDENT-EXECUTOR-V2",
            "FUSE",
            "GENESIS_WAKE",
            "SOURCE_BOUND",
            callable=True,
            runtime_native=True,
            authority="EXISTING_FDOF_EFFECT_BOUNDARY",
            operations=("wake", "resume", "build_handoff"),
            failure_domain="GENESIS",
        ),
    ]

    chat_bound = [
        ("CHATGPT-GPT-5.6-SOL", "OPENAI", ("reason", "orchestrate")),
        ("WEB-INTELLIGENCE", "WEB", ("search", "open", "research")),
        ("IMAGE-SEARCH", "WEB", ("image_search",)),
        ("IMAGE-GENERATION-EDITING", "OPENAI", ("image_generate", "image_edit")),
        ("PYTHON-PRIVATE", "LOCAL_COMPUTE", ("compute", "analyze")),
        ("PYTHON-USER-VISIBLE", "LOCAL_COMPUTE", ("compute", "artifact")),
        ("LINUX-CONTAINER", "LOCAL_COMPUTE", ("filesystem", "shell", "build", "test")),
        ("FILES-LIBRARY", "OPENAI_FILES", ("search", "read", "materialize", "manage", "share")),
        ("GOOGLE-DRIVE", "GOOGLE_WORKSPACE", ("read", "write", "docs", "sheets", "slides")),
        ("GMAIL", "GOOGLE_WORKSPACE", ("search", "read", "draft", "send", "organize")),
        ("GOOGLE-CALENDAR", "GOOGLE_WORKSPACE", ("read", "availability", "create", "update")),
        ("GOOGLE-CONTACTS", "GOOGLE_WORKSPACE", ("search", "read")),
        ("GITHUB", "GITHUB", ("repo", "source", "pr", "issues", "actions", "artifacts")),
        ("OUTLOOK-EMAIL", "MICROSOFT_365", ("search", "read", "draft", "send")),
        ("OUTLOOK-CALENDAR", "MICROSOFT_365", ("read", "availability", "create", "update")),
        ("CANVA", "CREATIVE", ("design", "edit", "export")),
        ("ADOBE-CREATIVE-CLOUD", "CREATIVE", ("create", "edit")),
        ("ADOBE-ACROBAT", "DOCUMENTS", ("pdf", "edit", "organize", "extract")),
        ("ADOBE-EXPRESS", "CREATIVE", ("design", "edit")),
        ("REMOTE-DESKTOP-COMMANDER", "WINDOWS", ("filesystem", "terminal", "desktop")),
        ("OPENAI-PLATFORM", "OPENAI", ("api_platform",)),
        ("AUTOMATION-SCHEDULER", "OPENAI_AUTOMATION", ("schedule", "condition_watch")),
        ("PLUGIN-MANAGEMENT", "OPENAI_PLUGIN", ("discover", "connect", "permissions")),
        ("PERSONAL-CONTEXT", "OPENAI_CONTEXT", ("retrieve",)),
        ("MEMORY", "OPENAI_CONTEXT", ("persist",)),
        ("SUMMARY-RECOVERY", "OPENAI_CONTEXT", ("recover",)),
        ("GENUI", "OPENAI_UI", ("map", "utility_widget")),
        ("BOOKING-COM", "TRAVEL", ("search", "stays", "cars", "attractions")),
        ("LONA-TRADING-ASSISTANT", "TRADING", ("research", "backtest")),
    ]
    for capability_id, family, operations in chat_bound:
        rows.append(
            _binding(
                capability_id,
                family,
                "CHAT_SESSION_TOOL",
                "CHAT_BOUND_RUNTIME_UNPROVEN",
                callable=False,
                runtime_native=False,
                authority="CURRENT_CLIENT_ACTION_SPECIFIC",
                operations=operations,
                failure_domain=f"CHAT_TOOL:{family}",
                notes=(
                    "Bound into SOL 6.2 capability truth as a detachable current-client route. "
                    "Standalone server callability requires an explicit provider/bridge adapter."
                ),
            )
        )

    estate_known = [
        ("GOOGLE-APPS-SCRIPT", "GOOGLE"),
        ("GOOGLE-CLOUD", "GOOGLE"),
        ("GOOGLE-AI-STUDIO", "GOOGLE_AI"),
        ("GEMINI-DEVELOPER-API", "GOOGLE_AI"),
        ("MICROSOFT-GRAPH", "MICROSOFT_365"),
        ("MICROSOFT-TEAMS", "MICROSOFT_365"),
        ("SHAREPOINT", "MICROSOFT_365"),
        ("POWER-AUTOMATE", "MICROSOFT_365"),
        ("POWER-APPS", "MICROSOFT_365"),
        ("POWER-BI", "MICROSOFT_365"),
        ("DATAVERSE", "MICROSOFT_365"),
        ("MICROSOFT-COPILOT", "MICROSOFT_365"),
        ("GITHUB-COPILOT", "GITHUB"),
        ("OLLAMA", "LOCAL_AI"),
        ("LM-STUDIO", "LOCAL_AI"),
        ("OPENROUTER", "MODEL_ROUTER"),
        ("X", "SOCIAL"),
    ]
    for capability_id, family in estate_known:
        rows.append(
            _binding(
                capability_id,
                family,
                "ESTATE_ROUTE_DISCOVERY",
                "ESTATE_KNOWN_CHAT_UNBOUND",
                callable=False,
                runtime_native=False,
                authority="UNPROVEN_CURRENT_SESSION",
                notes="UNKNOWN is not ABSENT. Re-resolve through capability discovery before use.",
            )
        )
    return tuple(rows)


def _snapshot_bindings() -> tuple[CapabilityBinding, ...]:
    raw = os.getenv("SOL62_EXTERNAL_CAPABILITY_SNAPSHOT_JSON", "").strip()
    if not raw:
        return ()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return ()
    if not isinstance(payload, list):
        return ()
    rows: list[CapabilityBinding] = []
    for item in payload:
        if not isinstance(item, dict) or not str(item.get("capability_id") or "").strip():
            continue
        rows.append(
            _binding(
                str(item["capability_id"]).strip(),
                str(item.get("family") or "EXTERNAL"),
                str(item.get("transport") or "EXTERNAL_SNAPSHOT"),
                str(item.get("maturity") or "UNKNOWN"),
                callable=bool(item.get("callable", False)),
                runtime_native=bool(item.get("runtime_native", False)),
                authority=str(item.get("authority") or "ACTION_SPECIFIC_UNPROVEN"),
                operations=tuple(str(x) for x in item.get("operations") or ("*",)),
                failure_domain=str(item.get("failure_domain") or "EXTERNAL_SNAPSHOT"),
                notes=str(item.get("notes") or ""),
            )
        )
    return tuple(rows)


def compile_registry(*, gateway_execution_ready: bool) -> dict[str, Any]:
    merged: dict[str, CapabilityBinding] = {
        row.capability_id: row for row in built_in_bindings(gateway_execution_ready=gateway_execution_ready)
    }
    # Fresh client/provider snapshot may strengthen or downgrade a binding, but
    # it never grants source/effect authority by itself.
    for row in _snapshot_bindings():
        merged[row.capability_id] = row
    rows = tuple(sorted(merged.values(), key=lambda row: row.capability_id))
    return {
        "schema": REGISTRY_SCHEMA,
        "runtime": "FUSE_SOL_6_2",
        "bindings": [row.to_dict() for row in rows],
        "counts": {
            "total": len(rows),
            "runtime_native": sum(1 for row in rows if row.runtime_native),
            "callable_now": sum(1 for row in rows if row.callable),
            "chat_bound_runtime_unproven": sum(1 for row in rows if row.maturity == "CHAT_BOUND_RUNTIME_UNPROVEN"),
            "estate_known_chat_unbound": sum(1 for row in rows if row.maturity == "ESTATE_KNOWN_CHAT_UNBOUND"),
        },
        "truth_boundary": (
            "REGISTERED_NE_CALLABLE; CHAT_BOUND_NE_SERVER_BOUND; "
            "SOURCE_BOUND_NE_PROVIDER_RUNTIME_VERIFIED; AUTHORITY_REQUIRES_ACTION_SPECIFIC_READBACK"
        ),
    }
