from __future__ import annotations

"""FUSE Formation Cyber-Investigative Intelligence Engine v1.

Permanent additive investigation capability for authorised/owned/public software,
devices, networks and artifacts. Reuses Formation, Hypercube/CFBE, existing FUSE
mission/checkpoint/proof systems and Formation Network Intelligence.

This module does NOT create a scanner/exploit plane, credential bypass, DRM
circumvention, proprietary-source reconstruction service, or external-effect root.
"""

from dataclasses import dataclass, asdict
from enum import StrEnum
from hashlib import sha256
import json
from typing import Iterable, Sequence

from federation.formation_network_intelligence_v1 import FormationNetworkIntelligence


SCHEMA = "FUSE_FORMATION_CYBER_INVESTIGATIVE_ENGINE_V1"
VERSION = "1.0.0"
CONTRACT_ID = "FUSE-FORMATION-CYBER-INVESTIGATIVE-001"


class RightsScope(StrEnum):
    OWNER_CONTROLLED = "OWNER_CONTROLLED"
    EXPLICITLY_AUTHORISED = "EXPLICITLY_AUTHORISED"
    OPEN_SOURCE = "OPEN_SOURCE"
    PUBLIC_DOCUMENTATION = "PUBLIC_DOCUMENTATION"
    LICENSED_ANALYSIS = "LICENSED_ANALYSIS"
    UNKNOWN = "UNKNOWN"


class InvestigationKind(StrEnum):
    NETWORK_DEVICE = "NETWORK_DEVICE"
    SOURCE_CODE = "SOURCE_CODE"
    SOFTWARE_PACKAGE = "SOFTWARE_PACKAGE"
    BINARY_METADATA = "BINARY_METADATA"
    FILE_FORMAT = "FILE_FORMAT"
    API_SURFACE = "API_SURFACE"
    PROTOCOL = "PROTOCOL"
    CONFIGURATION = "CONFIGURATION"
    LOG_TELEMETRY = "LOG_TELEMETRY"
    CONTAINER_IMAGE = "CONTAINER_IMAGE"
    DEPENDENCY_SBOM = "DEPENDENCY_SBOM"
    BEHAVIOUR_TRACE = "BEHAVIOUR_TRACE"
    DIGITAL_TWIN = "DIGITAL_TWIN"


class AnalysisDisposition(StrEnum):
    DIRECT_SOURCE_ANALYSIS = "DIRECT_SOURCE_ANALYSIS"
    PUBLIC_MECHANISM_HARVEST = "PUBLIC_MECHANISM_HARVEST"
    CLEAN_ROOM_BEHAVIOURAL_SPEC = "CLEAN_ROOM_BEHAVIOURAL_SPEC"
    METADATA_ONLY = "METADATA_ONLY"
    HOLD_RIGHTS_OR_AUTHORITY = "HOLD_RIGHTS_OR_AUTHORITY"
    REJECT = "REJECT"


@dataclass(frozen=True, slots=True)
class InvestigationTarget:
    target_id: str
    objective: str
    kinds: frozenset[InvestigationKind]
    rights_scope: RightsScope
    source_available: bool = False
    binaries_available: bool = False
    logs_available: bool = False
    packet_or_protocol_evidence_available: bool = False
    public_docs_available: bool = False
    external_effect_required: bool = False
    consequential: bool = False
    secrets_present: bool = False
    protected_content: bool = False


@dataclass(frozen=True, slots=True)
class InvestigativeCapability:
    capability_id: str
    mechanism: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    authority: str
    evidence_class: str
    fallback: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class InvestigationPlan:
    schema: str
    version: str
    contract_id: str
    plan_id: str
    target_id: str
    disposition: str
    stages: tuple[str, ...]
    capabilities: tuple[InvestigativeCapability, ...]
    workaround_ladder: tuple[str, ...]
    persistence_receivers: tuple[str, ...]
    proof_requirements: tuple[str, ...]
    prohibited_actions: tuple[str, ...]
    external_effect_authorized: bool
    truth_boundary: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _digest(value: object) -> str:
    raw=json.dumps(value,sort_keys=True,separators=(",",":"),default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


class FormationCyberInvestigativeEngine:
    """Compile evidence-bound deep investigations without widening authority."""

    TRUTH_BOUNDARY = (
        "INVESTIGATION_PLAN_COMPILED!=SOURCE_UNDERSTOOD!=RUNTIME_BEHAVIOUR_VERIFIED"
        "!=PROPRIETARY_IMPLEMENTATION_KNOWN!=SECURITY_DEFECT_PROVEN!=OWNER_VALUE!=COMPLETE"
    )

    PROHIBITED = (
        "AUTHENTICATION_BYPASS",
        "CREDENTIAL_EXTRACTION_OR_REPLAY",
        "DRM_OR_ACCESS_CONTROL_CIRCUMVENTION",
        "PROPRIETARY_SOURCE_EXFILTRATION",
        "PRIVATE_MODEL_WEIGHT_EXTRACTION",
        "STEALTH_OR_EVASION_MECHANISMS",
        "EXPLOITATION_WITHOUT_SEPARATE_EXACT_AUTHORITY",
        "CLAIM_SOURCE_EQUIVALENCE_FROM_BLACK_BOX_BEHAVIOUR",
    )

    PERSISTENCE_RECEIVERS = (
        "EXISTING_MISSION_CHECKPOINT",
        "FUSE_WORK_PLANE",
        "FAILURE_MEMORY",
        "ROUTE_MEMORY",
        "FEDERATION_LEARNING",
        "ARTIFACT_PROVENANCE",
        "PROOFOS_JUDGE",
    )

    WORKAROUND_LADDER = (
        "REUSE_EXISTING_FUSE_ANALYSER_OR_RECEIPT",
        "REBIND_TO_CURRENT_CALLABLE_LOCAL_OR_PROVIDER_TOOL",
        "REPAIR_FAILED_PARSER_OR_ADAPTER",
        "EXTEND_WITH_FORMAT_OR_PROTOCOL_DECODER",
        "COMPOSE_MULTIPLE_INDEPENDENT_EVIDENCE_SOURCES",
        "HARVEST_PUBLIC_DOCUMENTED_MECHANISM_CLEAN_ROOM",
        "BUILD_MINIMUM_RESIDUAL_ANALYSER",
        "HOLD_IF_RIGHTS_AUTHORITY_OR_PROTECTED_BOUNDARY_REMAINS",
    )

    def __init__(self) -> None:
        self.network = FormationNetworkIntelligence()

    @staticmethod
    def _disposition(target: InvestigationTarget) -> AnalysisDisposition:
        if target.rights_scope is RightsScope.UNKNOWN:
            return AnalysisDisposition.HOLD_RIGHTS_OR_AUTHORITY
        if target.protected_content and not target.source_available:
            return AnalysisDisposition.METADATA_ONLY
        if target.source_available and target.rights_scope in {
            RightsScope.OWNER_CONTROLLED,
            RightsScope.EXPLICITLY_AUTHORISED,
            RightsScope.OPEN_SOURCE,
            RightsScope.LICENSED_ANALYSIS,
        }:
            return AnalysisDisposition.DIRECT_SOURCE_ANALYSIS
        if target.public_docs_available:
            return AnalysisDisposition.PUBLIC_MECHANISM_HARVEST
        if target.binaries_available or target.logs_available or target.packet_or_protocol_evidence_available:
            return AnalysisDisposition.CLEAN_ROOM_BEHAVIOURAL_SPEC
        return AnalysisDisposition.METADATA_ONLY

    @staticmethod
    def _capabilities(target: InvestigationTarget) -> tuple[InvestigativeCapability, ...]:
        caps: list[InvestigativeCapability] = []

        def add(cid: str, mechanism: str, inputs: Sequence[str], outputs: Sequence[str], evidence: str, fallback: Sequence[str]=()) -> None:
            caps.append(InvestigativeCapability(
                capability_id=cid,
                mechanism=mechanism,
                inputs=tuple(inputs),
                outputs=tuple(outputs),
                authority="A1_INTERNAL_READ_ANALYSIS_ONLY",
                evidence_class=evidence,
                fallback=tuple(fallback),
            ))

        if InvestigationKind.SOURCE_CODE in target.kinds:
            add(
                "FCIE-SOURCE-GRAPH",
                "AST/import/call/config/test graph over authorised source",
                ("source tree","manifests","tests"),
                ("module graph","entrypoints","capability map","dependency edges"),
                "SOURCE",
                ("text/symbol graph","documentation cross-reference"),
            )
        if InvestigationKind.SOFTWARE_PACKAGE in target.kinds or InvestigationKind.DEPENDENCY_SBOM in target.kinds:
            add(
                "FCIE-PACKAGE-SBOM",
                "manifest/package/archive/SBOM dependency inventory",
                ("packages","lockfiles","archives","signatures"),
                ("component inventory","versions","licenses","dependency graph"),
                "ARTIFACT",
                ("file tree","hash inventory"),
            )
        if InvestigationKind.BINARY_METADATA in target.kinds:
            add(
                "FCIE-BINARY-METADATA",
                "headers/imports/exports/symbols/strings/signatures/sections metadata",
                ("authorised binaries",),
                ("binary profile","library dependencies","observable capability clues"),
                "BINARY_METADATA",
                ("OS-native metadata tools","strings-only"),
            )
        if InvestigationKind.FILE_FORMAT in target.kinds:
            add(
                "FCIE-FORMAT-INFERENCE",
                "magic/header/schema/field-differential clean-room format inference",
                ("owned samples","public format docs"),
                ("field map","version markers","parser contract"),
                "CLEAN_ROOM",
                ("sample differencing","public specification"),
            )
        if InvestigationKind.API_SURFACE in target.kinds:
            add(
                "FCIE-API-MAP",
                "documented/local introspection of routes, schemas and semantic readbacks",
                ("OpenAPI","local route tables","docs","logs"),
                ("endpoint map","input/output schema","authority requirements"),
                "API",
                ("log-derived route map","source route extraction"),
            )
        if InvestigationKind.PROTOCOL in target.kinds:
            add(
                "FCIE-PROTOCOL-MECHANISM",
                "public/authorised message-shape and state-machine inference",
                ("pcap/logs","public docs","owned endpoints"),
                ("message grammar","state transitions","semantic contract"),
                "CLEAN_ROOM",
                ("passive capture","application logs","public standards"),
            )
        if InvestigationKind.CONFIGURATION in target.kinds:
            add(
                "FCIE-CONFIG-SCHEMA",
                "config-key/default/constraint/dependency inference",
                ("config files","schemas","source/docs"),
                ("config schema","safe defaults","feature gates"),
                "CONFIG",
                ("sample comparison","runtime readback"),
            )
        if InvestigationKind.LOG_TELEMETRY in target.kinds:
            add(
                "FCIE-LOG-MINER",
                "timeline/fingerprint/state-transition extraction with source timestamps",
                ("logs","event records","receipts"),
                ("timeline","failure fingerprints","identity transitions"),
                "OBSERVATION",
                ("native event viewer","bounded text search"),
            )
        if InvestigationKind.CONTAINER_IMAGE in target.kinds:
            add(
                "FCIE-CONTAINER-INTROSPECTION",
                "manifest/layer/package/entrypoint/environment inspection",
                ("authorised image","image manifest"),
                ("layer inventory","entrypoint","packages","runtime contract"),
                "ARTIFACT",
                ("exported manifest","SBOM"),
            )
        if InvestigationKind.BEHAVIOUR_TRACE in target.kinds:
            add(
                "FCIE-BEHAVIOUR-DIFFERENTIAL",
                "controlled input/output/state differential in isolated owner-authorised environment",
                ("test harness","snapshots","semantic readback"),
                ("behavioural contract","state machine","side-effect map"),
                "BEHAVIOUR",
                ("logs-only differential","synthetic fixture"),
            )
        if InvestigationKind.NETWORK_DEVICE in target.kinds:
            add(
                "FCIE-NETWORK-IDENTITY",
                "temporal IP/MAC/DHCP/DNS/mDNS/SSDP/SMB/RPC/TLS evidence fusion",
                ("passive/current LAN evidence","security-product history"),
                ("identity graph","device class","contradictions","next evidence"),
                "NETWORK_OBSERVATION",
                ("router lease readback","local logs","passive reappearance"),
            )
        if InvestigationKind.DIGITAL_TWIN in target.kinds:
            add(
                "FCIE-DIGITAL-TWIN",
                "source/behaviour/config/protocol evidence compiled into a falsifiable model",
                ("capability maps","state machines","test receipts"),
                ("digital twin","counterexamples","unknowns"),
                "MODEL",
                ("partial twin with explicit UNKNOWN",),
            )
        return tuple(caps)

    def compile(self, target: InvestigationTarget) -> InvestigationPlan:
        if not target.target_id.strip() or not target.objective.strip():
            raise ValueError("FCIE_TARGET_AND_OBJECTIVE_REQUIRED")
        disposition = self._disposition(target)
        capabilities = self._capabilities(target)

        stages = [
            "RIGHTS_AUTHORITY_AND_SCOPE_PREFLIGHT",
            "HISTORICAL_HYPERCUBE_CFBE_REUSE_CENSUS",
            "EVIDENCE_AND_ARTIFACT_INVENTORY",
            "CURRENTNESS_AND_IDENTITY_NORMALIZATION",
            "STATIC_METADATA_AND_DEPENDENCY_ANALYSIS",
            "BEHAVIOURAL_OR_PROTOCOL_DIFFERENTIAL_WHEN_AUTHORISED",
            "MECHANISM_EXTRACTION_AND_VENDOR_NOISE_REMOVAL",
            "CROSS_SOURCE_CONTRADICTION_FUSION",
            "DIGITAL_TWIN_OR_CAPABILITY_GRAPH",
            "FAILURE_FINGERPRINT_AND_WORKAROUND_COMPILATION",
            "INDEPENDENT_FALSIFICATION",
            "PERSIST_TO_EXISTING_FUSE_RECEIVERS",
        ]
        if disposition is AnalysisDisposition.HOLD_RIGHTS_OR_AUTHORITY:
            stages = stages[:1] + ["HOLD_WITH_EXACT_RIGHTS_OR_AUTHORITY_GAP"]
        elif disposition is AnalysisDisposition.METADATA_ONLY:
            stages = [x for x in stages if "BEHAVIOURAL_OR_PROTOCOL" not in x]

        proof = (
            "EXACT_TARGET_IDENTITY",
            "SOURCE_OR_ARTIFACT_HASH_WHEN_AVAILABLE",
            "PROVENANCE_AND_RIGHTS_SCOPE",
            "OBSERVATION_TIMESTAMP_AND_CURRENTNESS",
            "FACT_INFERENCE_UNKNOWN_SEPARATION",
            "CONTRADICTION_PRESERVATION",
            "NO_PROPRIETARY_SOURCE_EQUIVALENCE_FROM_BLACK_BOX",
            "INDEPENDENT_FALSIFIER_FOR_MATERIAL_CLAIMS",
            "ROLLBACK_OR_NO_EFFECT_CONFIRMATION_FOR_TESTS",
        )

        stable = {
            "target_id": target.target_id,
            "objective": target.objective,
            "kinds": sorted(k.value for k in target.kinds),
            "rights": target.rights_scope.value,
            "disposition": disposition.value,
            "caps": [c.capability_id for c in capabilities],
        }

        return InvestigationPlan(
            schema=SCHEMA,
            version=VERSION,
            contract_id=CONTRACT_ID,
            plan_id=f"FCIE-{_digest(stable)[:24].upper()}",
            target_id=target.target_id,
            disposition=disposition.value,
            stages=tuple(stages),
            capabilities=capabilities,
            workaround_ladder=self.WORKAROUND_LADDER,
            persistence_receivers=self.PERSISTENCE_RECEIVERS,
            proof_requirements=proof,
            prohibited_actions=self.PROHIBITED,
            external_effect_authorized=False,
            truth_boundary=self.TRUTH_BOUNDARY,
        )


__all__ = [
    "AnalysisDisposition",
    "FormationCyberInvestigativeEngine",
    "InvestigationKind",
    "InvestigationPlan",
    "InvestigationTarget",
    "InvestigativeCapability",
    "RightsScope",
]
