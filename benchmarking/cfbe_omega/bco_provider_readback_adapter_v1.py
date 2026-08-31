from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import IntEnum
from hashlib import sha256
import argparse
import json
from pathlib import Path
from typing import Any, Mapping, TYPE_CHECKING

if TYPE_CHECKING:
    from formation_omega.durable_mission_runtime_v1 import DurableMissionRuntimeV1

_SCHEMA = "BCO-PROVIDER-READBACK-EVIDENCE-V1"
_FLOOR_SCHEMA = "BCO-PROVIDER-READBACK-FLOOR-V1"
_BINDING_SCHEMA = "BCO-PROVIDER-READBACK-BINDING-V1"
_EXPECTED_RECEIPT_SCHEMA = "BUBBLES-PROVIDER-SURFACE-PROBE-V1"


class ProviderReadbackLevel(IntEnum):
    UNVERIFIED = 0
    PUBLIC_REACHABILITY = 1
    AUTHENTICATED_SURFACE_READ = 2
    ACTION_SPECIFIC_AUTHENTICATED_READ = 3


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _http_seen(value: Any) -> bool:
    return isinstance(value, Mapping) and isinstance(value.get("http_status"), int)


def _body_ok(value: Any) -> bool:
    return (
        isinstance(value, Mapping)
        and value.get("http_status") == 200
        and isinstance(value.get("body"), Mapping)
        and value["body"].get("ok") is True
    )


@dataclass(frozen=True, slots=True)
class ProviderReadbackEvidence:
    schema: str
    level: str
    level_rank: int
    receipt_sha256: str
    public_surfaces: tuple[str, ...]
    authenticated_surfaces: tuple[str, ...]
    action_specific_surfaces: tuple[str, ...]
    classifications: tuple[tuple[str, str], ...]
    mutation_attempted: bool
    secret_values_recorded: bool
    proof_refs: tuple[str, ...]
    truth_boundary: tuple[str, ...]

    @property
    def enum_level(self) -> ProviderReadbackLevel:
        return ProviderReadbackLevel[self.level]

    def canonical_mapping(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ProviderProofFloorReceipt:
    schema: str
    state: str
    required_level: str
    observed_level: str
    required_rank: int
    observed_rank: int
    receipt_sha256: str
    provider_effect_authorized: bool = False
    financial_effect_authorized: bool = False
    publication_authorized: bool = False


@dataclass(frozen=True, slots=True)
class ProviderReadbackBindingReceipt:
    schema: str
    state: str
    mission_id: str
    request_id: str
    required_level: str
    observed_level: str
    receipt_sha256: str
    request_resolved: bool
    provider_effect_authorized: bool = False
    financial_effect_authorized: bool = False
    publication_authorized: bool = False


def compile_provider_readback_evidence(
    receipt: Mapping[str, Any],
    *,
    proof_ref: str = "",
) -> ProviderReadbackEvidence:
    payload = json.loads(_canonical(dict(receipt)))
    if payload.get("schema") != _EXPECTED_RECEIPT_SCHEMA:
        raise ValueError("BCO_PROVIDER_RECEIPT_SCHEMA_MISMATCH")
    if payload.get("mutation_attempted") is not False:
        raise ValueError("BCO_PROVIDER_RECEIPT_MUTATION_BOUNDARY_VIOLATED")
    if payload.get("secret_values_recorded") is not False:
        raise ValueError("BCO_PROVIDER_RECEIPT_SECRET_BOUNDARY_VIOLATED")

    surfaces = payload.get("surfaces")
    if not isinstance(surfaces, Mapping):
        raise ValueError("BCO_PROVIDER_RECEIPT_SURFACES_REQUIRED")

    public: set[str] = set()
    authenticated: set[str] = set()
    action_specific: set[str] = set()
    classifications: list[tuple[str, str]] = []

    for name, raw in sorted(surfaces.items()):
        if not isinstance(raw, Mapping):
            continue
        classification = str(raw.get("classification") or "UNCLASSIFIED")
        classifications.append((str(name), classification))
        for key in (
            "public_health",
            "public_contract",
            "public_root",
            "public_openapi",
            "public_probe",
        ):
            if _http_seen(raw.get(key)):
                public.add(str(name))
                break

        if classification in {
            "AUTHENTICATED_READBACK_VERIFIED",
            "AUTHENTICATED_CAPABILITY_AUDIT_REACHABLE",
            "IDENTITY_TOKEN_READ_VERIFIED",
        }:
            authenticated.add(str(name))

        if (
            classification == "AUTHENTICATED_READBACK_VERIFIED"
            and _body_ok(raw.get("authenticated_status"))
            and _body_ok(raw.get("authenticated_cloud_read"))
        ):
            action_specific.add(str(name))

    if action_specific:
        level = ProviderReadbackLevel.ACTION_SPECIFIC_AUTHENTICATED_READ
    elif authenticated:
        level = ProviderReadbackLevel.AUTHENTICATED_SURFACE_READ
    elif public:
        level = ProviderReadbackLevel.PUBLIC_REACHABILITY
    else:
        level = ProviderReadbackLevel.UNVERIFIED

    proof_refs = tuple(sorted({str(proof_ref).strip()} - {""}))
    return ProviderReadbackEvidence(
        schema=_SCHEMA,
        level=level.name,
        level_rank=int(level),
        receipt_sha256=_digest(payload),
        public_surfaces=tuple(sorted(public)),
        authenticated_surfaces=tuple(sorted(authenticated)),
        action_specific_surfaces=tuple(sorted(action_specific)),
        classifications=tuple(classifications),
        mutation_attempted=False,
        secret_values_recorded=False,
        proof_refs=proof_refs,
        truth_boundary=(
            "workflow_success_is_not_authenticated_provider_readback",
            "public_reachability_is_not_authenticated_semantic_readback",
            "authenticated_surface_read_is_not_provider_mutation_proof",
            "action_specific_authenticated_read_is_still_read_only_and_grants_no_effect_authority",
        ),
    )


def evaluate_provider_readback_floor(
    evidence: ProviderReadbackEvidence,
    required_level: ProviderReadbackLevel | str,
) -> ProviderProofFloorReceipt:
    required = (
        required_level
        if isinstance(required_level, ProviderReadbackLevel)
        else ProviderReadbackLevel[str(required_level).strip().upper()]
    )
    met = evidence.enum_level >= required
    return ProviderProofFloorReceipt(
        schema=_FLOOR_SCHEMA,
        state="PROOF_FLOOR_MET" if met else "HOLD_PROVIDER_READBACK_FLOOR_UNMET",
        required_level=required.name,
        observed_level=evidence.level,
        required_rank=int(required),
        observed_rank=evidence.level_rank,
        receipt_sha256=evidence.receipt_sha256,
    )


def bind_provider_readback_request(
    runtime: "DurableMissionRuntimeV1",
    mission_id: str,
    request_id: str,
    receipt: Mapping[str, Any],
    *,
    receipt_ref: str,
    required_level: ProviderReadbackLevel | str,
    resolved_at: str | None = None,
) -> ProviderReadbackBindingReceipt:
    evidence = compile_provider_readback_evidence(receipt, proof_ref=receipt_ref)
    floor = evaluate_provider_readback_floor(evidence, required_level)
    if floor.state != "PROOF_FLOOR_MET":
        return ProviderReadbackBindingReceipt(
            schema=_BINDING_SCHEMA,
            state=floor.state,
            mission_id=mission_id,
            request_id=request_id,
            required_level=floor.required_level,
            observed_level=floor.observed_level,
            receipt_sha256=evidence.receipt_sha256,
            request_resolved=False,
        )

    runtime.resolve_request(
        mission_id,
        request_id,
        response_ref=str(receipt_ref).strip(),
        response_sha256=evidence.receipt_sha256,
        proof_refs=tuple(sorted({*evidence.proof_refs, f"provider-readback-level:{evidence.level}"})),
        resolved_at=resolved_at,
    )
    return ProviderReadbackBindingReceipt(
        schema=_BINDING_SCHEMA,
        state="PROVIDER_READBACK_BOUND",
        mission_id=mission_id,
        request_id=request_id,
        required_level=floor.required_level,
        observed_level=floor.observed_level,
        receipt_sha256=evidence.receipt_sha256,
        request_resolved=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify a Bubbles provider receipt for BCΩ proof floors.")
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--required-level",
        default=ProviderReadbackLevel.ACTION_SPECIFIC_AUTHENTICATED_READ.name,
        choices=[item.name for item in ProviderReadbackLevel],
    )
    parser.add_argument("--proof-ref", default="")
    args = parser.parse_args()

    receipt = json.loads(Path(args.receipt).read_text(encoding="utf-8"))
    evidence = compile_provider_readback_evidence(receipt, proof_ref=args.proof_ref)
    floor = evaluate_provider_readback_floor(evidence, args.required_level)
    payload = {
        "evidence": evidence.canonical_mapping(),
        "floor": asdict(floor),
        "truth_boundary": "Classification is read-only evidence grading; it grants no provider or effect authority.",
    }
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
