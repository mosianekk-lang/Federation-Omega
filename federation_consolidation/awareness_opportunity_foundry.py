from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .ao_cra import BoundaryEvent, create_build_trigger

SCHEMA = "FEDOMEGA-AWARENESS-OPPORTUNITY-FOUNDRY-1"
PRIVATE_SCHEMA = "FEDOMEGA-PRIVATE-SURFACE-AWARENESS-1"
PUBLIC_SCHEMA = "FEDOMEGA-SURFACE-AWARENESS-V1"
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
)


class FoundryError(RuntimeError):
    """Fail-closed awareness, credential or opportunity error."""


class OpportunityClass(StrEnum):
    INTERNAL_BUILD = "INTERNAL_BUILD"
    INTERNAL_HARDENING = "INTERNAL_HARDENING"
    PROVIDER_PROBE = "PROVIDER_PROBE"
    PROVIDER_ADAPTER = "PROVIDER_ADAPTER"
    CONTINUITY_FILTER = "CONTINUITY_FILTER"
    DRIFT_REPAIR = "DRIFT_REPAIR"
    MONITOR = "MONITOR"


@dataclass(frozen=True)
class SurfaceRecord:
    surface_id: str
    name: str
    surface_class: str
    alias: str
    provider: str
    current_state: str
    capability: str
    authority_ceiling: str
    freshness_rule: str
    runtime_readback: str
    pointer_class: str
    notes: str


@dataclass(frozen=True)
class CredentialHandle:
    handle_id: str
    surface: str
    reference_name: str
    storage_class: str
    current_state: str
    scope: str
    raw_value_stored: bool
    runtime_validation: str
    rotation_or_expiry: str
    notes: str


@dataclass(frozen=True)
class Opportunity:
    opportunity_id: str
    opportunity_class: str
    source_alias: str
    title: str
    owning_engine: str
    desired_capability: str
    current_state: str
    buildable_now: bool
    external_effect: bool
    priority: int
    reason: str
    build_trigger: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def reject_secret_material(value: Any, path: str = "payload") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in {
                "token",
                "secret",
                "password",
                "api_key",
                "credential_value",
                "private_key",
            }:
                raise FoundryError(f"secret-bearing field prohibited: {path}.{key}")
            reject_secret_material(item, f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for index, item in enumerate(value):
            reject_secret_material(item, f"{path}[{index}]")
    elif isinstance(value, str) and any(
        pattern.search(value) for pattern in SECRET_PATTERNS
    ):
        raise FoundryError(f"secret-shaped value prohibited at {path}")


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def _row_dicts(table: Sequence[Sequence[Any]]) -> list[dict[str, Any]]:
    if not table:
        return []
    headers = [str(item) for item in table[0]]
    return [
        dict(zip(headers, row, strict=False))
        for row in table[1:]
        if any(str(item).strip() for item in row)
    ]


def parse_surfaces(table: Sequence[Sequence[Any]]) -> list[SurfaceRecord]:
    records: list[SurfaceRecord] = []
    for row in _row_dicts(table):
        records.append(
            SurfaceRecord(
                surface_id=str(row.get("Surface_ID", "")),
                name=str(row.get("Name", "")),
                surface_class=str(row.get("Class", "")),
                alias=str(row.get("Canonical_Alias", "")),
                provider=str(row.get("Provider_or_Connector", "")),
                current_state=str(row.get("Current_State", "")),
                capability=str(row.get("Proven_Capability", "")),
                authority_ceiling=str(row.get("Authority_Ceiling", "")),
                freshness_rule=str(row.get("Freshness_Rule", "")),
                runtime_readback=str(row.get("Runtime_Readback", "")),
                pointer_class=str(row.get("Private_Pointer_Class", "")),
                notes=str(row.get("Notes", "")),
            )
        )
    return records


def parse_credentials(table: Sequence[Sequence[Any]]) -> list[CredentialHandle]:
    records: list[CredentialHandle] = []
    for row in _row_dicts(table):
        records.append(
            CredentialHandle(
                handle_id=str(row.get("Handle_ID", "")),
                surface=str(row.get("Surface", "")),
                reference_name=str(row.get("Reference_Name", "")),
                storage_class=str(row.get("Storage_Location_Class", "")),
                current_state=str(row.get("Current_State", "")),
                scope=str(row.get("Scope", "")),
                raw_value_stored=_bool(row.get("Raw_Value_Stored", False)),
                runtime_validation=str(row.get("Runtime_Validation", "")),
                rotation_or_expiry=str(row.get("Rotation_or_Expiry", "")),
                notes=str(row.get("Notes", "")),
            )
        )
    return records


def verify_public_private_binding(
    public: Mapping[str, Any], private: Mapping[str, Any]
) -> dict[str, Any]:
    reject_secret_material(public, "public")
    reject_secret_material(private, "private")
    if public.get("schema") != PUBLIC_SCHEMA:
        raise FoundryError("public awareness schema mismatch")
    if private.get("schema") != PRIVATE_SCHEMA:
        raise FoundryError("private awareness schema mismatch")
    expected = public.get("private_manifest", {}).get("logical_sha256")
    observed = private.get("logical_sha256")
    checks = {
        "owner": public.get("owner") == private.get("owner"),
        "version": public.get("private_manifest", {}).get("version")
        == private.get("version"),
        "logical_sha256": isinstance(expected, str) and expected == observed,
        "credential_value_recorded": private.get("credential_value_recorded")
        is False,
    }
    failed = sorted(key for key, value in checks.items() if not value)
    return {
        "status": "VERIFIED" if not failed else "BLOCKED",
        "checks": checks,
        "failed_checks": failed,
    }


def detect_drift(
    surfaces: Iterable[SurfaceRecord],
    automation_rows: Sequence[Sequence[Any]],
    observed_main: str,
) -> list[dict[str, Any]]:
    drifts: list[dict[str, Any]] = []
    for surface in surfaces:
        if surface.alias == "FEDERATION_OMEGA_CONTROL_PLANE":
            match = re.search(r"\b[0-9a-f]{40}\b", surface.notes.lower())
            if match and match.group(0) != observed_main.lower():
                drifts.append(
                    {
                        "kind": "STALE_GITHUB_SURFACE_POINTER",
                        "alias": surface.alias,
                        "stored": match.group(0),
                        "observed": observed_main.lower(),
                    }
                )
    for row in _row_dicts(automation_rows):
        if str(row.get("Alias")) == "FEDERATION_OMEGA_CONTROL_PLANE":
            stored = str(row.get("Exact_Private_Pointer", "")).lower()
            if re.fullmatch(r"[0-9a-f]{40}", stored) and stored != observed_main.lower():
                drifts.append(
                    {
                        "kind": "STALE_GITHUB_AUTOMATION_POINTER",
                        "alias": str(row.get("Alias")),
                        "stored": stored,
                        "observed": observed_main.lower(),
                    }
                )
    return drifts


def credential_preflight(
    handles: Iterable[CredentialHandle],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for handle in handles:
        if handle.raw_value_stored:
            raise FoundryError(
                f"raw credential value recorded for {handle.handle_id}"
            )
        state = handle.current_state.upper()
        ready = state.startswith("LIVE_") or state == "WRITE_AND_READBACK_VERIFIED"
        results.append(
            {
                "handle_id": handle.handle_id,
                "reference_name": handle.reference_name,
                "status": "READY_READ_SCOPED" if ready else "REVALIDATION_REQUIRED",
                "effectful_use_allowed": False,
                "runtime_validation": handle.runtime_validation,
                "credential_value_recorded": False,
            }
        )
    return results


def classify_gmail_subject(subject: str, sender: str = "") -> str:
    text = f"{subject} {sender}".lower()
    if "notifications@github.com" in text or (
        "federation omega airlock" in text and "run failed" in text
    ):
        return "CI_TELEMETRY"
    if any(
        token in text
        for token in (
            "formation engine",
            "kim dataverse",
            "continuation",
            "restore",
            "respawn",
            "active sovereign translator",
            "next frontier ai bible",
        )
    ):
        return "CONTINUITY_SOURCE"
    if any(token in text for token in ("approval", "authorise", "authorize")):
        return "AUTHORITY_SOURCE_REVIEW_REQUIRED"
    return "MISSION_RELEVANCE_REVIEW"


def _surface_score(surface: SurfaceRecord, mission: str) -> int:
    text = (
        f"{surface.name} {surface.surface_class} {surface.alias} "
        f"{surface.capability}"
    ).lower()
    mission_tokens = set(re.findall(r"[a-z0-9]+", mission.lower()))
    score = sum(
        6 for token in mission_tokens if len(token) > 2 and token in text
    )
    state = surface.current_state.upper()
    if (
        "LIVE_VERIFIED" in state
        or "WRITE_AND_READBACK_VERIFIED" in state
        or "VERIFIED_LIVE" in state
    ):
        score += 30
    elif "CONNECTOR_AVAILABLE" in state:
        score += 15
    elif "UNVERIFIED" in state or "PARTIAL" in state:
        score -= 10
    if surface.runtime_readback == "REQUIRED":
        score += 4
    if "OWNER_RESERVED" in surface.authority_ceiling:
        score -= 8
    return score


def route_mission(
    surfaces: Iterable[SurfaceRecord], mission: str, limit: int = 5
) -> list[dict[str, Any]]:
    ranked = sorted(
        surfaces, key=lambda item: (-_surface_score(item, mission), item.alias)
    )
    return [
        {
            "alias": item.alias,
            "provider": item.provider,
            "state": item.current_state,
            "score": _surface_score(item, mission),
            "runtime_readback": item.runtime_readback,
        }
        for item in ranked[:limit]
    ]


def _state_needs_build(state: str) -> bool:
    upper = state.upper()
    return any(
        token in upper
        for token in (
            "UNVERIFIED",
            "REVALIDATE",
            "PARTIAL",
            "SOURCE_PRESENT",
            "UNPROBED",
            "NOT_PRESENT",
            "PENDING",
        )
    )


def _opportunity_for_surface(surface: SurfaceRecord) -> Opportunity | None:
    if not _state_needs_build(surface.current_state):
        return None
    external_provider = surface.provider in {
        "Google Cloud",
        "Apps Script",
        "Google AI Studio",
        "Microsoft Dataverse",
        "OpenAI Platform",
        "Microsoft Outlook",
        "Canva",
        "Adobe",
        "Booking.com",
        "Google Calendar",
        "Google Contacts",
    }
    if "DATAVERSE" in surface.alias:
        opportunity_class = OpportunityClass.PROVIDER_ADAPTER
        engine = "FORMATION_INNOVATION_ENGINE"
        capability = (
            "A least-privilege provider-native Dataverse schema/read/write adapter "
            "with semantic readback"
        )
    elif "GMAIL" in surface.alias:
        opportunity_class = OpportunityClass.CONTINUITY_FILTER
        engine = "SECONDARY_BRAIN"
        capability = (
            "A mission-scoped Gmail signal classifier that separates continuity "
            "sources from CI telemetry"
        )
    elif external_provider:
        opportunity_class = OpportunityClass.PROVIDER_PROBE
        engine = "FORMATION_INNOVATION_ENGINE"
        capability = (
            "A harmless provider-native authority and semantic readback probe for "
            f"{surface.alias}"
        )
    else:
        opportunity_class = OpportunityClass.INTERNAL_HARDENING
        engine = "FEDERATION_OMEGA_CORE"
        capability = (
            "A deterministic runtime verifier and freshness repair for "
            f"{surface.alias}"
        )
    event = BoundaryEvent(
        statement=f"{surface.alias} is {surface.current_state}",
        desired_capability=capability,
        owning_engine=engine,
        workaround=surface.capability
        if surface.capability
        else "Use current verified canonical routes",
        dependency=surface.provider if external_provider else "",
        source_trigger=f"surface-awareness:{surface.surface_id}",
    )
    trigger = create_build_trigger(
        event,
        existing_capabilities=(
            "FEDERATION_SURFACE_AWARENESS",
            "AO_CRA",
            "FORMATION_ENGINE",
            "ALPHA_TO_OMEGA_FOUNDRY",
        ),
    )
    priority = (
        100
        if surface.alias
        in {
            "FEDERATION_OMEGA_CONTROL_PLANE",
            "KIM_DATAVERSE_PRIVATE_CANONICAL_BRIDGE_V2",
        }
        else 70
        if external_provider
        else 80
    )
    return Opportunity(
        opportunity_id=(
            f"OPP-{trigger.build_id.removeprefix('BUILD-AO-FED-')}"
        ),
        opportunity_class=opportunity_class.value,
        source_alias=surface.alias,
        title=f"Resolve {surface.alias}",
        owning_engine=engine,
        desired_capability=capability,
        current_state=surface.current_state,
        buildable_now=not external_provider,
        external_effect=external_provider,
        priority=priority,
        reason=(
            "Current state requires fresh proof or implementation: "
            f"{surface.current_state}"
        ),
        build_trigger=trigger.to_dict(),
    )


def discover_opportunities(
    surfaces: Iterable[SurfaceRecord], drifts: Sequence[Mapping[str, Any]]
) -> list[Opportunity]:
    opportunities = [
        item
        for surface in surfaces
        if (item := _opportunity_for_surface(surface)) is not None
    ]
    for drift in drifts:
        event = BoundaryEvent(
            statement=(
                f"{drift['kind']} stored {drift['stored']} "
                f"observed {drift['observed']}"
            ),
            desired_capability=(
                "Automatic observed-main drift reconciliation with provenance "
                "preservation"
            ),
            owning_engine="FEDERATION_OMEGA_CORE",
            workaround="Read the live GitHub head before every invocation",
            source_trigger="awareness-drift-detector",
        )
        trigger = create_build_trigger(
            event,
            existing_capabilities=(
                "FEDERATION_SURFACE_AWARENESS",
                "GITHUB_CONNECTOR",
            ),
        )
        opportunities.append(
            Opportunity(
                opportunity_id=(
                    f"OPP-{trigger.build_id.removeprefix('BUILD-AO-FED-')}"
                ),
                opportunity_class=OpportunityClass.DRIFT_REPAIR.value,
                source_alias=str(drift["alias"]),
                title="Repair stale GitHub awareness pointer",
                owning_engine="FEDERATION_OMEGA_CORE",
                desired_capability=(
                    "Automatic observed-main drift reconciliation with provenance "
                    "preservation"
                ),
                current_state="STALE_POINTER_DETECTED",
                buildable_now=True,
                external_effect=False,
                priority=110,
                reason=str(drift["kind"]),
                build_trigger=trigger.to_dict(),
            )
        )
    deduplicated = {item.opportunity_id: item for item in opportunities}
    return sorted(
        deduplicated.values(),
        key=lambda item: (-item.priority, item.opportunity_id),
    )


def build_node_packet(
    public: Mapping[str, Any],
    private: Mapping[str, Any],
    observed_main: str,
    routes: Sequence[Mapping[str, Any]],
    opportunities: Sequence[Opportunity],
) -> dict[str, Any]:
    packet = {
        "schema": "FEDOMEGA-NODE-AWARENESS-PACKET-1",
        "startup_block": public.get("startup_block"),
        "observed_main": observed_main.lower(),
        "private_manifest_sha256": private.get("logical_sha256"),
        "required_contracts": [
            "governance/federation_surface_awareness_v1.json",
            "governance/federation_awareness_bootstrap_v1.json",
            "governance/federation_node_bootstrap_v2.json",
            "governance/federation_n_directive_v2.yaml",
            "governance/ao_cra_federation_inheritance_v1.json",
            "governance/federation_awareness_opportunity_foundry_v1.json",
        ],
        "formation_engine": "REQUIRED",
        "alpha_to_omega_foundry": "REQUIRED",
        "ao_cra": "REQUIRED_ON_BOUNDARY",
        "selected_routes": list(routes),
        "open_build_ids": [
            item.build_trigger["build_id"] for item in opportunities
        ],
        "credential_value_recorded": False,
        "external_effect": False,
    }
    packet["packet_sha256"] = canonical_sha256(packet)
    return packet


def run_foundry(
    *,
    public: Mapping[str, Any],
    private: Mapping[str, Any],
    surfaces_table: Sequence[Sequence[Any]],
    credentials_table: Sequence[Sequence[Any]],
    automation_table: Sequence[Sequence[Any]],
    observed_main: str,
    mission: str,
    gmail_messages: Sequence[Mapping[str, str]] = (),
) -> dict[str, Any]:
    binding = verify_public_private_binding(public, private)
    surfaces = parse_surfaces(surfaces_table)
    credentials = parse_credentials(credentials_table)
    drifts = detect_drift(surfaces, automation_table, observed_main)
    credential_results = credential_preflight(credentials)
    routes = route_mission(surfaces, mission)
    opportunities = discover_opportunities(surfaces, drifts)
    gmail = [
        {
            **dict(message),
            "classification": classify_gmail_subject(
                message.get("subject", ""), message.get("sender", "")
            ),
        }
        for message in gmail_messages
    ]
    node_packet = build_node_packet(
        public, private, observed_main, routes, opportunities
    )
    result = {
        "schema": SCHEMA,
        "status": "VERIFIED_LOCAL_BUILD_SET"
        if binding["status"] == "VERIFIED"
        else "BLOCKED_PRIVATE_BINDING",
        "observed_main": observed_main.lower(),
        "mission": mission,
        "binding": binding,
        "drifts": drifts,
        "routes": routes,
        "credential_preflight": credential_results,
        "gmail_signal_map": gmail,
        "opportunities": [item.to_dict() for item in opportunities],
        "internal_build_ids": [
            item.build_trigger["build_id"]
            for item in opportunities
            if item.buildable_now
        ],
        "provider_gated_build_ids": [
            item.build_trigger["build_id"]
            for item in opportunities
            if not item.buildable_now
        ],
        "node_packet": node_packet,
        "credential_value_recorded": False,
        "provider_mutation_performed": False,
    }
    result["receipt_sha256"] = canonical_sha256(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--surfaces", type=Path, required=True)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--automation", type=Path, required=True)
    parser.add_argument("--observed-main", required=True)
    parser.add_argument("--mission", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_foundry(
        public=json.loads(args.public.read_text(encoding="utf-8")),
        private=json.loads(args.private.read_text(encoding="utf-8")),
        surfaces_table=json.loads(args.surfaces.read_text(encoding="utf-8")),
        credentials_table=json.loads(
            args.credentials.read_text(encoding="utf-8")
        ),
        automation_table=json.loads(args.automation.read_text(encoding="utf-8")),
        observed_main=args.observed_main,
        mission=args.mission,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"].startswith("VERIFIED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
