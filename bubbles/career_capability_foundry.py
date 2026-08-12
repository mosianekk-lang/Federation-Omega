from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence


class GapClass(str, Enum):
    USER_EVIDENCE_GAP = "USER_EVIDENCE_GAP"
    BUBBLES_CAPABILITY_GAP = "BUBBLES_CAPABILITY_GAP"
    BOTH = "BOTH"
    COVERED = "COVERED"


class GrowthState(str, Enum):
    WATCH = "WATCH"
    BUILD = "BUILD"
    IMPLEMENTED = "IMPLEMENTED"
    TESTED = "TESTED"
    RUNTIME_VERIFIED = "RUNTIME_VERIFIED"
    PROVIDER_VERIFIED = "PROVIDER_VERIFIED"
    PILOT_VERIFIED = "PILOT_VERIFIED"


@dataclass(frozen=True)
class CapabilityRequirement:
    capability_id: str
    name: str
    domain: str
    required_disciplines: tuple[str, ...]
    evidence_terms: tuple[str, ...] = ()
    strategic_weight: int = 1


@dataclass(frozen=True)
class RoleSignal:
    role_id: str
    employer: str
    title: str
    sector: str
    source_ref: str
    requirements: tuple[str, ...]
    strategic_target: bool = False
    signal_type: str = "VACANCY"


@dataclass(frozen=True)
class CapabilityAssessment:
    capability_id: str
    name: str
    occurrence_count: int
    strategic_occurrence: bool
    gap_class: GapClass
    growth_state: GrowthState
    squad: tuple[str, ...]
    proof_project: str
    proof_gates: tuple[str, ...]
    role_ids: tuple[str, ...]
    truth_boundary: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["gap_class"] = self.gap_class.value
        payload["growth_state"] = self.growth_state.value
        return payload


DEFAULT_CAPABILITIES: tuple[CapabilityRequirement, ...] = (
    CapabilityRequirement("CAP-EA", "Enterprise and Business Architecture", "architecture", ("architecture", "proof-prioritisation"), ("enterprise architecture", "business architecture", "capability mapping", "roadmap", "togaf", "archimate"), 3),
    CapabilityRequirement("CAP-HE-DIGITAL", "Higher-Education Digital Strategy", "education", ("architecture", "product", "integration"), ("higher education", "digital transformation", "institutional strategy", "student experience"), 3),
    CapabilityRequirement("CAP-ACADEMIC-GOV", "Academic Operations and Governance", "education", ("product", "evidence", "research"), ("academic governance", "curriculum", "assessment", "examinations", "accreditation", "quality assurance"), 3),
    CapabilityRequirement("CAP-LMS-SIS-ERP", "LMS, SIS and ERP Ecosystem Architecture", "education", ("integration", "api", "architecture", "persistence"), ("lms", "sis", "student information", "erp", "institutional software", "learning platform"), 3),
    CapabilityRequirement("CAP-EDTECH", "Educational Technology and Learning Analytics", "education", ("product", "integration", "evaluation", "ux"), ("educational technology", "digital learning", "learning analytics", "technology-enhanced learning"), 3),
    CapabilityRequirement("CAP-API", "API and Integration Engineering", "engineering", ("api", "integration", "software", "testing"), ("api", "integration", "data bridge", "middleware", "script"), 3),
    CapabilityRequirement("CAP-DATA-BI", "Data, BI and Decision Intelligence", "data", ("persistence", "integration", "evaluation", "metrics"), ("power bi", "looker", "business intelligence", "dashboard", "analytics", "data quality"), 3),
    CapabilityRequirement("CAP-CLOUD", "Cloud Platform and Deployment Engineering", "engineering", ("cloud", "deployment", "ci-cd", "identity", "observability"), ("cloud", "cloud run", "azure", "deployment", "ci/cd", "container"), 3),
    CapabilityRequirement("CAP-IT-GRC", "IT Governance, Risk and Audit", "governance", ("security", "evidence", "claims", "architecture"), ("it governance", "risk", "audit", "cobit", "nist", "iso 27001", "itil"), 3),
    CapabilityRequirement("CAP-CYBER", "Cybersecurity and Privacy Architecture", "security", ("security", "privacy", "trust", "reliability"), ("cybersecurity", "privacy", "identity access", "zero trust", "security architecture"), 3),
    CapabilityRequirement("CAP-AI-GOV", "AI Governance and Responsible AI", "ai", ("security", "evaluation", "evidence", "architecture"), ("ai governance", "responsible ai", "model risk", "ai policy", "ai assurance"), 3),
    CapabilityRequirement("CAP-CHANGE", "Digital Change and Adoption Leadership", "leadership", ("product", "ux", "communication", "pilot"), ("change management", "adoption", "training", "stakeholder influence", "human-centric"), 2),
    CapabilityRequirement("CAP-IT-FIN", "IT Financial, Budget and ROI Management", "leadership", ("product", "metrics", "commercialisation", "proof-prioritisation"), ("budget", "roi", "cost optimization", "funding model", "business case"), 2),
    CapabilityRequirement("CAP-VENDOR", "Vendor and Technology Partner Management", "leadership", ("product", "commercialisation", "evidence"), ("vendor", "partner management", "supplier", "procurement", "service provider"), 2),
    CapabilityRequirement("CAP-PPM", "Programme, Portfolio and OKR Management", "leadership", ("orchestration", "product", "metrics"), ("programme management", "portfolio", "project management", "okr", "roadmap"), 2),
    CapabilityRequirement("CAP-DIGITAL-CAMPUS", "Digital Campus and Student Experience Architecture", "education", ("architecture", "integration", "ux", "product"), ("digital campus", "student experience", "campus technology", "student services"), 2),
)


ROLE_TO_DISCIPLINE: Mapping[str, str] = {
    "architecture": "Bubbles",
    "proof-prioritisation": "Bubbles",
    "software": "Forge",
    "api": "Forge",
    "testing": "Forge",
    "persistence": "Forge",
    "cloud": "Sparks",
    "deployment": "Sparks",
    "ci-cd": "Sparks",
    "identity": "Sparks",
    "evaluation": "Pulse",
    "reliability": "Patch",
    "observability": "Patch",
    "evidence": "Ledger",
    "claims": "Ledger",
    "security": "Sentinel",
    "privacy": "Sentinel",
    "trust": "Sentinel",
    "integration": "Bridge",
    "research": "Scout",
    "ux": "Prism",
    "product": "Beacon",
    "pilot": "Beacon",
    "metrics": "Beacon",
    "commercialisation": "Beacon",
    "communication": "Showcase",
    "orchestration": "Bubbles",
}


PROOF_PROJECTS: Mapping[str, str] = {
    "CAP-EA": "Model one flagship as as-is/to-be capabilities, applications, data, integrations, risks and three-year transition roadmap; validate traceability from business outcome to technical component.",
    "CAP-HE-DIGITAL": "Create a university digital-transformation reference operating model covering teaching, research, administration, student experience, data, cyber, AI and service management, then apply it to a synthetic institution case.",
    "CAP-ACADEMIC-GOV": "Build a synthetic School-of-Technology operations control plane covering programme lifecycle, scheduling, assessment integrity, faculty allocation, student support and academic-governance evidence gates.",
    "CAP-LMS-SIS-ERP": "Build a synthetic LMS-SIS-ERP integration reference using event/API contracts, canonical identities, retry/idempotency, data-quality checks and semantic readback.",
    "CAP-EDTECH": "Build a safe learning-analytics prototype with synthetic learner data, intervention logic, privacy controls, dashboard and measurable learning-support outcomes.",
    "CAP-API": "Expose one flagship through a versioned authenticated API, integration tests, OpenAPI contract, idempotency, error semantics and independent readback.",
    "CAP-DATA-BI": "Produce an executive decision dashboard from synthetic operational data with defined KPIs, lineage, quality checks and reproducible metrics.",
    "CAP-CLOUD": "Deploy one bounded flagship canary with identity, immutable artifact digest, health, persistence, logs, rollback and provider-native readback.",
    "CAP-IT-GRC": "Create a control crosswalk and executable evidence pack mapping a synthetic university IT service to governance, risk, audit and remediation controls.",
    "CAP-CYBER": "Threat-model one education platform and implement negative security tests for authentication, authorization, privacy, replay, tamper and recovery.",
    "CAP-AI-GOV": "Create an education-AI assurance gate with model inventory, use-case risk, evaluation, human oversight, provenance, privacy and release controls.",
    "CAP-CHANGE": "Create an adoption plan for a synthetic multi-campus rollout with stakeholder map, training, communications, adoption telemetry and rollback criteria.",
    "CAP-IT-FIN": "Build a three-year technology investment portfolio with TCO, ROI hypotheses, cost/risk scenarios and evidence-linked prioritisation using synthetic figures.",
    "CAP-VENDOR": "Create a vendor-selection and performance scorecard with requirements traceability, SLA/KPI evidence, risk, cost and exit/continuity controls.",
    "CAP-PPM": "Run a multi-workstream digital portfolio with OKRs, dependency graph, benefits tracking, risk register and proof-based stage gates.",
    "CAP-DIGITAL-CAMPUS": "Design a synthetic student digital journey spanning identity, registration, learning, support and service analytics, with accessibility/privacy/reliability gates.",
}


class CareerCapabilityFoundry:
    """Turn recurring market requirements into proof-bound Bubbles capability growth.

    Organisational capability and the human owner's personal experience are separate
    proof dimensions. This foundry may develop the former; only owner evidence plus
    Ledger approval may support personal CV or interview claims.
    """

    def __init__(self, capabilities: Sequence[CapabilityRequirement] = DEFAULT_CAPABILITIES) -> None:
        self.capabilities = tuple(capabilities)
        self.by_id = {item.capability_id: item for item in self.capabilities}
        if len(self.by_id) != len(self.capabilities):
            raise ValueError("Capability IDs must be unique")

    @staticmethod
    def _normalise(text: str) -> str:
        return " ".join(text.casefold().replace("/", " ").replace("-", " ").split())

    @classmethod
    def load_role_signals(cls, path: str | Path) -> tuple[RoleSignal, ...]:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        records = payload.get("signals", payload if isinstance(payload, list) else [])
        signals = []
        for item in records:
            signals.append(
                RoleSignal(
                    role_id=str(item["role_id"]),
                    employer=str(item["employer"]),
                    title=str(item["title"]),
                    sector=str(item["sector"]),
                    source_ref=str(item["source_ref"]),
                    requirements=tuple(str(value) for value in item.get("requirements", [])),
                    strategic_target=bool(item.get("strategic_target", False)),
                    signal_type=str(item.get("signal_type", "VACANCY")),
                )
            )
        return tuple(signals)

    def match_role(self, role: RoleSignal) -> tuple[str, ...]:
        blob = self._normalise(" ".join((role.title, role.sector, *role.requirements)))
        hits: list[str] = []
        for capability in self.capabilities:
            if any(self._normalise(term) in blob for term in capability.evidence_terms):
                hits.append(capability.capability_id)
        return tuple(sorted(set(hits)))

    def minimum_squad(self, capability_id: str) -> tuple[str, ...]:
        capability = self.by_id[capability_id]
        members = ["Bubbles"]
        for discipline in capability.required_disciplines:
            member = ROLE_TO_DISCIPLINE.get(discipline, "Bubbles")
            if member not in members:
                members.append(member)
        if "Ledger" not in members:
            members.append("Ledger")
        return tuple(members)

    @staticmethod
    def _proof_gates(capability: CapabilityRequirement) -> tuple[str, ...]:
        gates = ["IMPLEMENTED", "TESTED"]
        if capability.domain in {"engineering", "data", "education", "security", "ai"}:
            gates.append("RUNTIME_OR_DEMONSTRATION_VERIFIED")
        if "cloud" in capability.required_disciplines or "deployment" in capability.required_disciplines:
            gates.append("PROVIDER_READBACK")
        if "pilot" in capability.required_disciplines or capability.domain in {"education", "leadership"}:
            gates.append("MEASURED_OUTCOME_OR_PILOT_EVIDENCE")
        gates.append("LEDGER_APPROVED_CLAIM")
        return tuple(gates)

    def assess(
        self,
        roles: Iterable[RoleSignal],
        *,
        user_evidence: Iterable[str] = (),
        bubbles_verified: Iterable[str] = (),
    ) -> tuple[CapabilityAssessment, ...]:
        role_list = tuple(roles)
        user = set(user_evidence)
        bubbles = set(bubbles_verified)
        occurrences: dict[str, list[RoleSignal]] = {c.capability_id: [] for c in self.capabilities}
        for role in role_list:
            for capability_id in self.match_role(role):
                occurrences[capability_id].append(role)

        assessments: list[CapabilityAssessment] = []
        for capability in self.capabilities:
            matched = occurrences[capability.capability_id]
            if not matched:
                continue
            user_has = capability.capability_id in user
            bubbles_has = capability.capability_id in bubbles
            if user_has and bubbles_has:
                gap = GapClass.COVERED
            elif user_has and not bubbles_has:
                gap = GapClass.BUBBLES_CAPABILITY_GAP
            elif not user_has and bubbles_has:
                gap = GapClass.USER_EVIDENCE_GAP
            else:
                gap = GapClass.BOTH

            strategic = any(role.strategic_target for role in matched)
            should_build = len(matched) >= 2 or strategic or capability.strategic_weight >= 3
            state = GrowthState.TESTED if gap == GapClass.COVERED else (GrowthState.BUILD if should_build else GrowthState.WATCH)
            assessments.append(
                CapabilityAssessment(
                    capability_id=capability.capability_id,
                    name=capability.name,
                    occurrence_count=len(matched),
                    strategic_occurrence=strategic,
                    gap_class=gap,
                    growth_state=state,
                    squad=self.minimum_squad(capability.capability_id),
                    proof_project=PROOF_PROJECTS[capability.capability_id],
                    proof_gates=self._proof_gates(capability),
                    role_ids=tuple(sorted(role.role_id for role in matched)),
                    truth_boundary=(
                        "This grows Bubbles organisational capability only. It is not evidence that the human owner "
                        "personally has the role experience; CV/interview claims require separate owner evidence and Ledger approval."
                    ),
                )
            )
        return tuple(sorted(assessments, key=lambda item: (-item.occurrence_count, item.capability_id)))

    def backlog(self, assessments: Iterable[CapabilityAssessment]) -> dict[str, object]:
        records = [item.to_dict() for item in assessments]
        payload = {
            "schema": "BUBBLES-CAREER-CAPABILITY-GROWTH-V1",
            "capability_count": len(records),
            "build_count": sum(1 for item in records if item["growth_state"] == GrowthState.BUILD.value),
            "items": records,
            "truth_boundary": (
                "Market requirements are learning signals. Bubbles capability growth and human-owner evidence "
                "remain separate proof dimensions and cannot be inferred from one another."
            ),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload["digest"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return payload

    def write_backlog(self, path: str | Path, assessments: Iterable[CapabilityAssessment]) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.backlog(assessments), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return target
