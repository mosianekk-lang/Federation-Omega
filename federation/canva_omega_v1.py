from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping, Sequence


CAPABILITY_ID = "CANVA-OMEGA-MAX-V1"
SCHEMA = "FEDERATION-CANVA-VISUAL-INTELLIGENCE-V1"
VERSION = "1.0.0"


class ProofState(str, Enum):
    D0 = "D0_DOCTRINE"
    I1 = "I1_IMPLEMENTED"
    R2 = "R2_RUNTIME_READBACK"
    B3 = "B3_BEHAVIOR"
    V4 = "V4_LONGITUDINAL_VALUE"


class PrivacyClass(str, Enum):
    P0_PUBLIC = "P0_PUBLIC"
    P1_INTERNAL = "P1_INTERNAL"
    P2_CONFIDENTIAL = "P2_CONFIDENTIAL"
    P3_PRIVILEGED = "P3_PRIVILEGED"
    P4_SECRET = "P4_SECRET"


class AuthorityClass(str, Enum):
    A0_ANALYSIS = "A0_ANALYSIS"
    A1_INTERNAL = "A1_INTERNAL"
    A2_CONSEQUENTIAL = "A2_CONSEQUENTIAL"


class VisualSurface(str, Enum):
    PRESENTATION = "presentation"
    REPORT = "report"
    INFOGRAPHIC = "infographic"
    POSTER = "poster"
    DOC = "doc"
    WHITEBOARD = "whiteboard"
    SOCIAL = "social"
    VISUAL_ATLAS = "visual_atlas"
    DESIGN_SYSTEM = "design_system"


@dataclass(frozen=True)
class VisualProjectionPacket:
    system_id: str
    source_refs: tuple[str, ...]
    claims: tuple[str, ...]
    proof_state: ProofState
    authority: AuthorityClass = AuthorityClass.A1_INTERNAL
    privacy: PrivacyClass = PrivacyClass.P1_INTERNAL
    freshness: str = "CURRENT_READ_REQUIRED"
    owner_gate: bool = False
    registered_system: bool = True
    canonical_source: bool = False
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class VisualMission:
    objective: str
    audience: str
    packets: tuple[VisualProjectionPacket, ...]
    requested_surfaces: tuple[VisualSurface, ...] = ()
    require_expert_depth: bool = True
    require_reusable_patterns: bool = True
    allow_external_release: bool = False


@dataclass(frozen=True)
class VisualPlan:
    capability_id: str
    surfaces: tuple[VisualSurface, ...]
    visual_primitives: tuple[str, ...]
    proof_legend: tuple[str, ...]
    source_systems: tuple[str, ...]
    warnings: tuple[str, ...]
    release_blocked: bool
    release_reasons: tuple[str, ...]
    reuse_contract: tuple[str, ...]


class CanvaOmegaVisualIntelligence:
    """Proof-bounded visual compiler for Federation outputs.

    The compiler is deliberately provider-neutral and effect-free. It converts
    typed Federation projection packets into a visual-production plan. Canva is
    a presentation/design surface, never the canonical truth store.
    """

    CORE_SYSTEM_FAMILIES = (
        "FUSE",
        "OF50",
        "OMEGA-SCIENTIA",
        "AO-HARMONIC",
        "FAILURE-TO-OPERATIONAL-WIN",
        "EVIDENCEOPS",
        "FORMATION",
        "ALPHA-OMEGA",
        "OMEGA-MAX",
        "KIM-DATAVERSE",
        "CHATBRIDGE",
        "LOCAL-BIBLE",
        "HUMAN-FIRST",
        "SOVARA",
        "BUBBLES",
        "MODISA",
        "JARVIS",
        "FUSE-MOBILE",
    )

    PROVIDER_SURFACES = (
        "GOOGLE-DRIVE",
        "GOOGLE-DOCS",
        "GOOGLE-SHEETS",
        "GITHUB",
        "GOOGLE-CLOUD",
        "APPS-SCRIPT",
        "GOOGLE-AI-STUDIO",
        "GEMINI",
        "OPENAI",
        "GMAIL",
        "OUTLOOK",
        "MICROSOFT-365",
        "CANVA",
        "ADOBE",
    )

    PROOF_ORDER = {
        ProofState.D0: 0,
        ProofState.I1: 1,
        ProofState.R2: 2,
        ProofState.B3: 3,
        ProofState.V4: 4,
    }

    @staticmethod
    def _validate_packet(packet: VisualProjectionPacket) -> None:
        if not packet.registered_system:
            raise ValueError("UNREGISTERED_SYSTEM_PACKET")
        if not packet.system_id.strip():
            raise ValueError("MISSING_SYSTEM_ID")
        if not packet.source_refs:
            raise ValueError("MISSING_SOURCE_PROVENANCE")
        if not packet.claims:
            raise ValueError("MISSING_VISUAL_CLAIMS")
        if packet.canonical_source and packet.system_id.upper() == "CANVA":
            raise ValueError("CANVA_CANNOT_BE_CANONICAL_TRUTH_STORE")

    @staticmethod
    def _visual_primitives(objective: str) -> tuple[str, ...]:
        text = objective.lower()
        primitives: list[str] = []
        rules = (
            (("architecture", "system", "platform", "federation"), "layered_architecture"),
            (("process", "workflow", "pipeline", "lifecycle"), "process_flow"),
            (("cause", "hypothesis", "falsif", "science"), "causal_hypothesis_map"),
            (("evidence", "proof", "claim", "forensic"), "evidence_proof_graph"),
            (("timeline", "chronology", "history"), "timeline"),
            (("maturity", "progress", "state", "promotion"), "maturity_ladder"),
            (("compare", "option", "alternative", "benchmark"), "comparison_matrix"),
            (("risk", "control", "gate", "authority"), "control_gate_map"),
            (("knowledge", "bible", "corpus", "chapter"), "knowledge_atlas"),
            (("value", "outcome", "owner burden"), "human_value_scorecard"),
        )
        for needles, primitive in rules:
            if any(needle in text for needle in needles):
                primitives.append(primitive)
        if not primitives:
            primitives.extend(("concept_map", "executive_summary"))
        return tuple(dict.fromkeys(primitives))

    @staticmethod
    def _route_surfaces(mission: VisualMission) -> tuple[VisualSurface, ...]:
        if mission.requested_surfaces:
            return tuple(dict.fromkeys(mission.requested_surfaces))
        text = mission.objective.lower()
        if any(k in text for k in ("bible", "corpus", "knowledge base", "atlas")):
            return (
                VisualSurface.VISUAL_ATLAS,
                VisualSurface.PRESENTATION,
                VisualSurface.INFOGRAPHIC,
                VisualSurface.POSTER,
                VisualSurface.DOC,
                VisualSurface.DESIGN_SYSTEM,
            )
        if any(k in text for k in ("executive", "brief", "present", "pitch")):
            return (VisualSurface.PRESENTATION, VisualSurface.INFOGRAPHIC)
        if any(k in text for k in ("evidence", "analysis", "report", "audit")):
            return (VisualSurface.REPORT, VisualSurface.INFOGRAPHIC)
        return (VisualSurface.PRESENTATION, VisualSurface.INFOGRAPHIC, VisualSurface.DOC)

    @classmethod
    def compile(cls, mission: VisualMission) -> VisualPlan:
        if not mission.packets:
            raise ValueError("NO_VISUAL_PROJECTION_PACKETS")
        for packet in mission.packets:
            cls._validate_packet(packet)

        source_systems = tuple(dict.fromkeys(packet.system_id for packet in mission.packets))
        surfaces = cls._route_surfaces(mission)
        primitives = cls._visual_primitives(mission.objective)

        warnings: list[str] = [
            "CANVA_IS_PRESENTATION_LAYER_NOT_SOURCE_OF_TRUTH",
            "VISUAL_POLISH_MUST_NOT_STRENGTHEN_EPISTEMIC_STATE",
            "CURRENT_PROVIDER_STATE_REQUIRES_FRESH_READ_WHEN_MATERIAL",
        ]
        release_reasons: list[str] = []

        for packet in mission.packets:
            if packet.privacy in (PrivacyClass.P3_PRIVILEGED, PrivacyClass.P4_SECRET):
                warnings.append(f"RESTRICTED_PRIVACY:{packet.system_id}:{packet.privacy.value}")
                if mission.allow_external_release:
                    release_reasons.append(f"PRIVACY_BLOCK:{packet.system_id}")
            if packet.authority == AuthorityClass.A2_CONSEQUENTIAL or packet.owner_gate:
                warnings.append(f"OWNER_GATE:{packet.system_id}")
                if mission.allow_external_release:
                    release_reasons.append(f"OWNER_APPROVAL_REQUIRED:{packet.system_id}")
            if packet.freshness != "CURRENT":
                warnings.append(f"FRESHNESS_QUALIFIER:{packet.system_id}:{packet.freshness}")

        proof_legend = tuple(
            f"{state.value}:{cls.PROOF_ORDER[state]}" for state in ProofState
        )
        reuse_contract = (
            "REUSE_VISUAL_REFERENCE_BEFORE_REBUILD",
            "PRESERVE_HIGH_PERFORMING_COMPONENT_PATTERNS",
            "COMPARE_NEW_PATTERN_AGAINST_INCUMBENT",
            "STORE_DURABLE_LESSONS_ONLY_ON_AUTHORISED_USER_CONTROLLED_SURFACES",
            "NO_INVISIBLE_LEARNING_CLAIMS",
        )

        return VisualPlan(
            capability_id=CAPABILITY_ID,
            surfaces=surfaces,
            visual_primitives=primitives,
            proof_legend=proof_legend,
            source_systems=source_systems,
            warnings=tuple(dict.fromkeys(warnings)),
            release_blocked=bool(release_reasons),
            release_reasons=tuple(dict.fromkeys(release_reasons)),
            reuse_contract=reuse_contract,
        )


def compile_visual_mission(
    objective: str,
    audience: str,
    packets: Sequence[VisualProjectionPacket],
    requested_surfaces: Iterable[VisualSurface] = (),
    *,
    allow_external_release: bool = False,
) -> VisualPlan:
    return CanvaOmegaVisualIntelligence.compile(
        VisualMission(
            objective=objective,
            audience=audience,
            packets=tuple(packets),
            requested_surfaces=tuple(requested_surfaces),
            allow_external_release=allow_external_release,
        )
    )
