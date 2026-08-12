from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Iterable, Mapping, Sequence


REQUIRED_DOMAINS = (
    "teaching_learning",
    "research_innovation",
    "student_lifecycle",
    "corporate_services",
    "data_decision_intelligence",
    "cyber_privacy",
    "ai_automation",
    "it_service_management",
)

REQUIRED_ARCHITECTURE_LAYERS = (
    "business_capability",
    "application",
    "data",
    "integration",
    "technology",
    "risk_control",
)

STUDENT_LIFECYCLE_STAGES = (
    "prospect",
    "application",
    "admission",
    "registration",
    "learning",
    "assessment",
    "progression",
    "graduation",
    "alumni",
)


@dataclass(frozen=True)
class CapabilityNode:
    capability_id: str
    domain: str
    outcome: str
    applications: tuple[str, ...]
    data_products: tuple[str, ...]
    integrations: tuple[str, ...]
    controls: tuple[str, ...]
    lifecycle_stages: tuple[str, ...] = ()


@dataclass(frozen=True)
class TransitionWave:
    wave: int
    name: str
    capabilities: tuple[str, ...]
    success_metrics: tuple[str, ...]
    rollback_trigger: str


@dataclass(frozen=True)
class ArchitectureReceipt:
    schema: str
    state: str
    domain_coverage: tuple[str, ...]
    architecture_layer_coverage: tuple[str, ...]
    lifecycle_coverage: tuple[str, ...]
    traceability_pass: bool
    transition_pass: bool
    risk_control_pass: bool
    missing_domains: tuple[str, ...]
    missing_lifecycle_stages: tuple[str, ...]
    violations: tuple[str, ...]
    external_effect: bool
    provider_verified: bool
    receipt_sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class HigherEdDigitalStrategyLab:
    """Synthetic higher-education digital strategy + enterprise architecture proof lab.

    The lab proves deterministic architecture reasoning, traceability and transition
    controls over a synthetic institution. It does not claim that the owner held a
    university-wide CIO/DVC mandate, deployed these systems at a provider, or
    achieved real student outcomes.
    """

    schema = "BUBBLES-HIGHER-ED-DIGITAL-STRATEGY-LAB-V1"

    def __init__(
        self,
        capabilities: Sequence[CapabilityNode],
        waves: Sequence[TransitionWave],
    ) -> None:
        self.capabilities = tuple(capabilities)
        self.waves = tuple(sorted(waves, key=lambda item: item.wave))
        ids = [item.capability_id for item in self.capabilities]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("Capability IDs must be present and unique")
        if not self.waves:
            raise ValueError("At least one transition wave is required")
        wave_numbers = [item.wave for item in self.waves]
        if wave_numbers != list(range(1, len(wave_numbers) + 1)):
            raise ValueError("Transition waves must be contiguous starting at 1")

    @staticmethod
    def reference() -> "HigherEdDigitalStrategyLab":
        capabilities = (
            CapabilityNode(
                "CAP-DIG-TEACH",
                "teaching_learning",
                "Reliable blended learning and digitally enabled academic delivery",
                ("LMS", "virtual_classroom"),
                ("learning_activity", "course_engagement"),
                ("LMS_SIS_enrolment_sync",),
                ("access_control", "academic_content_governance"),
                ("learning", "assessment"),
            ),
            CapabilityNode(
                "CAP-DIG-RESEARCH",
                "research_innovation",
                "Improve research administration, collaboration and evidence visibility",
                ("research_information_system",),
                ("research_outputs", "grant_pipeline"),
                ("research_finance_bridge",),
                ("research_data_governance", "ethics_traceability"),
            ),
            CapabilityNode(
                "CAP-DIG-STUDENT",
                "student_lifecycle",
                "Create a coherent digital student journey from prospect to alumni",
                ("CRM", "SIS", "student_portal"),
                ("student_master", "progression_metrics"),
                ("CRM_SIS_bridge", "SIS_LMS_bridge", "SIS_ERP_bridge"),
                ("identity_governance", "privacy_minimisation", "student_record_integrity"),
                STUDENT_LIFECYCLE_STAGES,
            ),
            CapabilityNode(
                "CAP-DIG-CORP",
                "corporate_services",
                "Reduce administrative friction and improve institutional efficiency",
                ("ERP", "HRIS", "service_management"),
                ("finance_operational", "workforce_operational"),
                ("ERP_HRIS_bridge", "ERP_service_catalogue_bridge"),
                ("segregation_of_duties", "financial_control", "records_management"),
            ),
            CapabilityNode(
                "CAP-DIG-DATA",
                "data_decision_intelligence",
                "Provide trusted executive intelligence for recruitment, retention, throughput and service quality",
                ("data_platform", "BI_dashboard"),
                ("institutional_kpi_model", "data_quality_scorecard"),
                ("source_to_kpi_lineage",),
                ("data_quality_gate", "metric_definition_control", "lineage_evidence"),
            ),
            CapabilityNode(
                "CAP-DIG-CYBER",
                "cyber_privacy",
                "Protect identities, services and sensitive institutional information",
                ("IAM", "security_monitoring"),
                ("identity_risk", "security_events"),
                ("IAM_application_federation",),
                ("least_privilege", "incident_response", "privacy_control", "recovery_test"),
            ),
            CapabilityNode(
                "CAP-DIG-AI",
                "ai_automation",
                "Introduce governed AI and automation where measurable institutional value exists",
                ("ai_gateway", "workflow_automation"),
                ("ai_use_case_register", "evaluation_metrics"),
                ("AI_business_process_bridge",),
                ("human_oversight", "model_evaluation", "privacy_gate", "release_gate"),
            ),
            CapabilityNode(
                "CAP-DIG-ITSM",
                "it_service_management",
                "Operate digital services with measurable reliability and user experience",
                ("ITSM", "observability_platform"),
                ("service_health", "SLA_metrics", "experience_metrics"),
                ("monitoring_incident_bridge",),
                ("change_control", "service_ownership", "rollback", "problem_management"),
            ),
        )
        waves = (
            TransitionWave(
                1,
                "Foundation and trust",
                ("CAP-DIG-CYBER", "CAP-DIG-ITSM", "CAP-DIG-STUDENT"),
                ("identity_control_coverage", "service_health_baseline", "student_master_quality"),
                "critical identity, service-health or student-record regression",
            ),
            TransitionWave(
                2,
                "Integration and intelligence",
                ("CAP-DIG-CORP", "CAP-DIG-DATA", "CAP-DIG-TEACH"),
                ("integration_success_rate", "data_quality", "digital_learning_availability"),
                "material integration corruption or KPI lineage failure",
            ),
            TransitionWave(
                3,
                "AI-enabled optimisation",
                ("CAP-DIG-AI", "CAP-DIG-RESEARCH"),
                ("validated_automation_value", "ai_eval_pass_rate", "research_process_cycle_time"),
                "AI evaluation, privacy, human-oversight or research-governance gate fails",
            ),
        )
        return HigherEdDigitalStrategyLab(capabilities, waves)

    def _layer_coverage(self) -> tuple[str, ...]:
        layers = set()
        for item in self.capabilities:
            if item.outcome:
                layers.add("business_capability")
            if item.applications:
                layers.add("application")
            if item.data_products:
                layers.add("data")
            if item.integrations:
                layers.add("integration")
            if item.applications or item.integrations:
                layers.add("technology")
            if item.controls:
                layers.add("risk_control")
        return tuple(sorted(layers))

    def validate(self) -> ArchitectureReceipt:
        violations: list[str] = []
        by_id = {item.capability_id: item for item in self.capabilities}
        domain_coverage = tuple(sorted({item.domain for item in self.capabilities}))
        missing_domains = tuple(sorted(set(REQUIRED_DOMAINS).difference(domain_coverage)))

        lifecycle = tuple(sorted({stage for item in self.capabilities for stage in item.lifecycle_stages}))
        missing_lifecycle = tuple(sorted(set(STUDENT_LIFECYCLE_STAGES).difference(lifecycle)))

        traceability_pass = True
        risk_control_pass = True
        for item in self.capabilities:
            if not item.outcome or not item.applications or not item.data_products or not item.integrations:
                traceability_pass = False
                violations.append(f"TRACEABILITY_INCOMPLETE:{item.capability_id}")
            if not item.controls:
                risk_control_pass = False
                violations.append(f"CONTROL_MISSING:{item.capability_id}")

        transition_pass = True
        seen: set[str] = set()
        for wave in self.waves:
            if not wave.success_metrics or not wave.rollback_trigger.strip():
                transition_pass = False
                violations.append(f"WAVE_CONTROL_INCOMPLETE:{wave.wave}")
            for capability_id in wave.capabilities:
                if capability_id not in by_id:
                    transition_pass = False
                    violations.append(f"UNKNOWN_WAVE_CAPABILITY:{capability_id}")
                if capability_id in seen:
                    transition_pass = False
                    violations.append(f"DUPLICATE_WAVE_CAPABILITY:{capability_id}")
                seen.add(capability_id)
        unsequenced = sorted(set(by_id).difference(seen))
        for capability_id in unsequenced:
            transition_pass = False
            violations.append(f"UNSEQUENCED_CAPABILITY:{capability_id}")

        layer_coverage = self._layer_coverage()
        missing_layers = sorted(set(REQUIRED_ARCHITECTURE_LAYERS).difference(layer_coverage))
        violations.extend(f"ARCHITECTURE_LAYER_MISSING:{layer}" for layer in missing_layers)
        if missing_domains:
            violations.extend(f"DOMAIN_MISSING:{domain}" for domain in missing_domains)
        if missing_lifecycle:
            violations.extend(f"LIFECYCLE_STAGE_MISSING:{stage}" for stage in missing_lifecycle)

        state = "DETERMINISTIC_TESTED_REFERENCE_MODEL" if not violations else "HOLD"
        payload: Mapping[str, object] = {
            "schema": self.schema,
            "state": state,
            "domain_coverage": domain_coverage,
            "architecture_layer_coverage": layer_coverage,
            "lifecycle_coverage": lifecycle,
            "traceability_pass": traceability_pass,
            "transition_pass": transition_pass,
            "risk_control_pass": risk_control_pass,
            "missing_domains": missing_domains,
            "missing_lifecycle_stages": missing_lifecycle,
            "violations": tuple(sorted(violations)),
            "external_effect": False,
            "provider_verified": False,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return ArchitectureReceipt(receipt_sha256=digest, **payload)  # type: ignore[arg-type]

    def executive_case(self) -> dict[str, object]:
        receipt = self.validate()
        return {
            "schema": "BUBBLES-HIGHER-ED-EXECUTIVE-CASE-V1",
            "mission": "Transform a synthetic multi-campus institution into a secure, integrated, data-informed and AI-ready digital university without claiming real institutional deployment.",
            "architecture_receipt": receipt.to_dict(),
            "strategic_outcomes": [item.outcome for item in self.capabilities],
            "transition_waves": [asdict(item) for item in self.waves],
            "safe_claim": (
                "Designed and deterministically validated a synthetic higher-education digital operating model "
                "with business-to-technology traceability, student-lifecycle coverage, architecture layers, "
                "risk controls and phased rollback-aware transition planning."
            ),
            "forbidden_claims": [
                "Led an institution-wide university digital transformation using this model",
                "Deployed this architecture at a university",
                "Achieved real student retention or throughput gains from this model",
                "This reference model is provider verified or production proven",
            ],
            "next_proof": "Build the LMS/SIS/ERP integration vertical slice and executive KPI dashboard over synthetic institutional data, then run a recruiter-facing demonstration.",
        }


def validate_reference_model() -> ArchitectureReceipt:
    return HigherEdDigitalStrategyLab.reference().validate()
