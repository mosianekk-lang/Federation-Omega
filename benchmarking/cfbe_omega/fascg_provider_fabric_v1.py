from __future__ import annotations

"""Provider-passport registry for FASCG.

The registry describes existing Federation provider bridges without calling them.
It keeps provider/native authority with the admitted workflow owners and lets FASCG
select a proof-capable route without becoming another provider executor.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable, Mapping, Sequence

from benchmarking.cfbe_omega.fascg_production_runtime_v1 import ProviderPassport, ProviderSurface

SCHEMA = "FASCG-PROVIDER-FABRIC-V1"
EXTERNAL_EFFECTS = False
AUTHORITY_MINTING = False


def _hash(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ProviderBridgeDescriptor:
    bridge_id: str
    surface: ProviderSurface
    workflow_path: str
    capabilities: tuple[str, ...]
    maturity: str
    effect_class: str
    provider_native_readback: bool
    proof_refs: tuple[str, ...]

    def validate(self) -> "ProviderBridgeDescriptor":
        if not self.bridge_id.strip() or not self.workflow_path.strip() or not self.capabilities or not self.proof_refs:
            raise ValueError("FASCG_PROVIDER_BRIDGE_FIELDS_REQUIRED")
        if self.effect_class != "NONE":
            raise ValueError("FASCG_PROVIDER_BRIDGE_EFFECT_MUST_BE_NONE")
        return self

    def passport(self) -> ProviderPassport:
        self.validate()
        identity = _hash({"bridge": self.bridge_id, "workflow": self.workflow_path, "proof": sorted(self.proof_refs)})
        return ProviderPassport(
            passport_id=f"PASS-{self.bridge_id}", surface=self.surface,
            capability_set=self.capabilities, source_workflow=self.workflow_path,
            identity_fingerprint=identity, authority_ceiling="A1_READ_ONLY_OR_INTERNAL",
            proof_refs=self.proof_refs, provider_readback_required=True,
            provider_effect_authorized=False, mutation_capable=False,
        )


CURRENT_PROVIDER_BRIDGES = (
    ProviderBridgeDescriptor(
        "GITHUB-HOSTED-SHADOW-REUSE", ProviderSurface.GITHUB_HOSTED,
        ".github/workflows/frontier-runtime-qualification.yml",
        ("hosted_shadow", "deterministic_eval", "artifact_proof", "durable_runtime"), "CURRENT_MAIN_HOST_WORKFLOW_REUSE_CANDIDATE", "NONE", False,
        ("repo:workflow:frontier-runtime-qualification", "local:fascg-full-court-286"),
    ),
    ProviderBridgeDescriptor(
        "GOOGLE-CLOUD-CURRENTNESS", ProviderSurface.GOOGLE_CLOUD,
        ".github/workflows/fuse-mobile-provider-currentness-v1.yml",
        ("google_cloud_readback", "cloud_run_state", "iap_state", "iam_readback"), "SOURCE_ADMITTED_PROVIDER_READBACK", "NONE", True,
        ("github:PR1355", "provider:run34396212620"),
    ),
    ProviderBridgeDescriptor(
        "GOOGLE-AI-STUDIO-SEMANTIC", ProviderSurface.GOOGLE_AI_STUDIO,
        ".github/workflows/sovara-ai-studio-semantic-canary.yml",
        ("ai_studio_semantic_canary", "model_surface_readback"), "CURRENT_MAIN_SOURCE", "NONE", True,
        ("repo:workflow:sovara-ai-studio-semantic-canary",),
    ),
    ProviderBridgeDescriptor(
        "GOOGLE-APPS-SCRIPT-READ", ProviderSurface.GOOGLE_APPS_SCRIPT,
        ".github/workflows/strategic-fuse-appsscript-read-zero-traffic.yml",
        ("apps_script_read", "zero_traffic_probe", "provider_readback"), "CURRENT_MAIN_SOURCE", "NONE", True,
        ("repo:workflow:strategic-fuse-appsscript-read-zero-traffic",),
    ),
    ProviderBridgeDescriptor(
        "SOL62-GOOGLE-SURFACE", ProviderSurface.GOOGLE_CLOUD,
        ".github/workflows/sol62-google-surface-probe.yml",
        ("google_surface_probe", "runtime_currentness", "provider_readback"), "CURRENT_MAIN_SOURCE", "NONE", True,
        ("repo:workflow:sol62-google-surface-probe",),
    ),
)


class ProviderRouteSelector:
    def choose(self, required_capabilities: Iterable[str], *, preferred_surfaces: Sequence[ProviderSurface] = ()) -> tuple[ProviderBridgeDescriptor, ...]:
        required = set(str(x).strip() for x in required_capabilities if str(x).strip())
        if not required:
            return ()
        surfaces = set(preferred_surfaces)
        candidates = [b.validate() for b in CURRENT_PROVIDER_BRIDGES if not surfaces or b.surface in surfaces]
        chosen: list[ProviderBridgeDescriptor] = []
        uncovered = set(required)
        while uncovered:
            ranked = sorted(candidates, key=lambda b: (len(set(b.capabilities) & uncovered), b.provider_native_readback, b.bridge_id), reverse=True)
            if not ranked or not (set(ranked[0].capabilities) & uncovered):
                break
            best = ranked[0]
            chosen.append(best)
            uncovered -= set(best.capabilities)
            candidates = [b for b in candidates if b.bridge_id != best.bridge_id]
        return tuple(chosen)


@dataclass(frozen=True, slots=True)
class NegotiationAdvertisement:
    advertisement_id: str
    provider_id: str
    protocols: tuple[str, ...]
    capabilities: tuple[str, ...]
    modalities: tuple[str, ...]
    endpoint_fingerprint: str
    authority_ceiling: str
    proof_refs: tuple[str, ...]
    advertisement_signature_verified: bool = False

    def validate(self) -> "NegotiationAdvertisement":
        if not self.advertisement_id.strip() or not self.provider_id.strip():
            raise ValueError("FASCG_NEGOTIATION_ADVERTISEMENT_ID_REQUIRED")
        if not self.protocols or not self.capabilities or not self.endpoint_fingerprint.strip():
            raise ValueError("FASCG_NEGOTIATION_PROTOCOL_CAPABILITY_ENDPOINT_REQUIRED")
        if not self.authority_ceiling.strip() or not self.proof_refs:
            raise ValueError("FASCG_NEGOTIATION_AUTHORITY_PROOF_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class CapabilityNegotiationResult:
    provider_id: str | None
    protocol: str | None
    covered_capabilities: tuple[str, ...]
    missing_capabilities: tuple[str, ...]
    modalities_satisfied: bool
    advertisement_proof_refs: tuple[str, ...]
    provider_execution_proven: bool = False
    external_effect_authorized: bool = False

    @property
    def complete(self) -> bool:
        return self.provider_id is not None and not self.missing_capabilities and self.modalities_satisfied


class CapabilityNegotiator:
    def negotiate(
        self,
        required_capabilities: Iterable[str],
        advertisements: Sequence[NegotiationAdvertisement],
        *,
        allowed_protocols: Sequence[str],
        required_modalities: Iterable[str] = (),
    ) -> CapabilityNegotiationResult:
        required = set(str(x).strip() for x in required_capabilities if str(x).strip())
        modalities = set(str(x).strip() for x in required_modalities if str(x).strip())
        protocols = tuple(str(x).strip() for x in allowed_protocols if str(x).strip())
        if not required:
            raise ValueError("FASCG_NEGOTIATION_REQUIRED_CAPABILITIES_EMPTY")
        if not protocols:
            raise ValueError("FASCG_NEGOTIATION_ALLOWED_PROTOCOLS_EMPTY")
        protocol_rank = {name: len(protocols) - i for i, name in enumerate(protocols)}
        candidates: list[tuple[tuple[int, int, int, int, str], NegotiationAdvertisement, str, set[str], bool]] = []
        for advertisement in advertisements:
            ad = advertisement.validate()
            if not ad.advertisement_signature_verified:
                continue
            compatible_protocols = [p for p in ad.protocols if p in protocol_rank]
            if not compatible_protocols:
                continue
            selected_protocol = max(compatible_protocols, key=lambda p: (protocol_rank[p], p))
            covered = required & set(ad.capabilities)
            modalities_ok = modalities.issubset(set(ad.modalities))
            score = (
                int(covered == required),
                len(covered),
                int(modalities_ok),
                protocol_rank[selected_protocol],
                ad.provider_id,
            )
            candidates.append((score, ad, selected_protocol, covered, modalities_ok))
        if not candidates:
            return CapabilityNegotiationResult(None, None, (), tuple(sorted(required)), False, ())
        _, ad, protocol, covered, modalities_ok = max(candidates, key=lambda item: item[0])
        return CapabilityNegotiationResult(
            provider_id=ad.provider_id,
            protocol=protocol,
            covered_capabilities=tuple(sorted(covered)),
            missing_capabilities=tuple(sorted(required - covered)),
            modalities_satisfied=modalities_ok,
            advertisement_proof_refs=tuple(sorted(set(ad.proof_refs))),
            provider_execution_proven=False,
            external_effect_authorized=False,
        )


def provider_fabric_manifest() -> Mapping[str, object]:
    body = {
        "schema": SCHEMA,
        "external_effects": False,
        "authority_minting": False,
        "capability_negotiation": {
            "stateless": True,
            "advertisement_proof_required": True,
            "supported_contract_families": ("MCP_STYLE", "A2A_STYLE", "FEDERATION_NATIVE"),
            "live_mcp_or_a2a_endpoint_claimed": False,
            "provider_execution_inherited_from_advertisement": False,
        },
        "bridges": [
            {"bridge_id": b.bridge_id, "surface": b.surface.value, "workflow": b.workflow_path,
             "capabilities": b.capabilities, "maturity": b.maturity,
             "provider_native_readback": b.provider_native_readback}
            for b in CURRENT_PROVIDER_BRIDGES
        ],
    }
    return {**body, "sha256": _hash(body)}


__all__ = [
    "SCHEMA", "EXTERNAL_EFFECTS", "AUTHORITY_MINTING", "ProviderBridgeDescriptor",
    "CURRENT_PROVIDER_BRIDGES", "ProviderRouteSelector", "NegotiationAdvertisement",
    "CapabilityNegotiationResult", "CapabilityNegotiator", "provider_fabric_manifest",
]
