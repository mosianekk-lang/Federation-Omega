from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Iterable, Mapping


@dataclass(frozen=True)
class Control:
    control_id: str
    domain: str
    objective: str
    evidence: tuple[str, ...]
    owner: str
    test: str
    residual_risk: str


@dataclass(frozen=True)
class Risk:
    risk_id: str
    scenario: str
    likelihood: int
    impact: int
    controls: tuple[str, ...]
    treatment: str

    @property
    def score(self) -> int:
        return self.likelihood * self.impact


class HigherEdITGRCLab:
    """Synthetic higher-education IT governance, risk, audit and cyber-assurance lab.

    The lab is intentionally provider-neutral and evidence-bound. It demonstrates
    governance design and deterministic control/risk evaluation only; it does not
    claim a real university audit, certification, compliance opinion or Kim's past
    personal responsibility for institution-wide GRC.
    """

    required_domains = (
        "strategy_and_governance",
        "identity_and_access",
        "cybersecurity_and_privacy",
        "service_management",
        "change_and_release",
        "data_and_ai_governance",
        "third_party_and_cloud",
        "continuity_and_recovery",
        "audit_and_evidence",
    )

    def __init__(self, controls: Iterable[Control] | None = None, risks: Iterable[Risk] | None = None):
        self.controls = tuple(controls or self.reference_controls())
        self.risks = tuple(risks or self.reference_risks())
        self._validate()

    @staticmethod
    def reference_controls() -> tuple[Control, ...]:
        return (
            Control("GOV-01", "strategy_and_governance", "Technology roadmap, decision rights and accountable ownership are explicit.", ("approved roadmap", "RACI", "portfolio register"), "CIO/ICT Director", "Trace sampled initiatives to owner, outcome and decision right.", "LOW"),
            Control("IAM-01", "identity_and_access", "Access is least-privilege, role-bound and periodically reviewed.", ("role matrix", "access review receipt", "joiner-mover-leaver evidence"), "IAM Lead", "Test privileged account sample for role, approval and review age.", "MEDIUM"),
            Control("SEC-01", "cybersecurity_and_privacy", "Security and privacy threats are identified, treated and tested.", ("risk register", "negative security tests", "incident records"), "Security Lead", "Run authz/privacy/tamper negative tests on synthetic service.", "MEDIUM"),
            Control("ITSM-01", "service_management", "Critical services have owners, SLAs/SLOs, support paths and measurable health.", ("service catalogue", "SLO report", "incident/problem records"), "Service Management Lead", "Verify sampled critical service has owner, SLO and current health evidence.", "LOW"),
            Control("CHG-01", "change_and_release", "Material changes are authorised, tested, reversible and independently read back.", ("change record", "test receipt", "rollback plan", "readback receipt"), "Change Manager", "Inspect sampled release for test, rollback and post-change verification.", "LOW"),
            Control("DATA-AI-01", "data_and_ai_governance", "Institutional data and AI use have lineage, quality, privacy and human-oversight controls.", ("data lineage", "quality metrics", "AI use-case register", "evaluation receipt"), "Data/AI Governance Lead", "Trace one KPI and one AI use case from source to decision and oversight.", "MEDIUM"),
            Control("TPR-01", "third_party_and_cloud", "Vendors and cloud services have due diligence, SLA, security and exit controls.", ("vendor assessment", "SLA/KPI", "security review", "exit plan"), "Vendor Manager", "Sample critical supplier for current risk, performance and exit evidence.", "MEDIUM"),
            Control("BCP-01", "continuity_and_recovery", "Critical services have tested recovery objectives, backups and rollback routes.", ("BIA", "RTO/RPO", "restore test", "DR exercise"), "Continuity Lead", "Run deterministic restore/restart test and compare to target RTO/RPO.", "MEDIUM"),
            Control("AUD-01", "audit_and_evidence", "Material control claims are supported by current, attributable evidence and tracked remediation.", ("control evidence index", "audit findings", "remediation ledger", "closure receipt"), "IT Governance Lead", "Reperform a control sample and verify evidence freshness plus remediation closure.", "LOW"),
        )

    @staticmethod
    def reference_risks() -> tuple[Risk, ...]:
        return (
            Risk("R-01", "Privileged access exceeds current role need.", 3, 5, ("IAM-01", "AUD-01"), "Quarterly privileged access review and rapid deprovisioning."),
            Risk("R-02", "Student-facing systems fail during registration or assessment peaks.", 3, 5, ("ITSM-01", "BCP-01", "CHG-01"), "Capacity, SLO, recovery and freeze-window controls."),
            Risk("R-03", "Institutional data produces inconsistent executive decisions.", 4, 4, ("DATA-AI-01", "AUD-01"), "Canonical definitions, lineage and data-quality thresholds."),
            Risk("R-04", "AI use creates privacy, bias or unsupported decision risk.", 3, 5, ("DATA-AI-01", "SEC-01"), "Use-case risk tiering, evaluation and human oversight."),
            Risk("R-05", "Critical vendor dependency creates lock-in or service interruption.", 3, 4, ("TPR-01", "BCP-01"), "Exit plans, portability, SLA evidence and recovery alternatives."),
            Risk("R-06", "Uncontrolled changes disrupt teaching, learning or research services.", 3, 4, ("CHG-01", "ITSM-01"), "Tested releases, rollback and semantic post-change readback."),
        )

    def _validate(self) -> None:
        ids = [c.control_id for c in self.controls]
        if len(ids) != len(set(ids)):
            raise ValueError("control IDs must be unique")
        present = {c.domain for c in self.controls}
        missing = set(self.required_domains) - present
        if missing:
            raise ValueError(f"missing required domains: {sorted(missing)}")
        control_ids = set(ids)
        for control in self.controls:
            if not control.evidence or not control.test or not control.owner:
                raise ValueError(f"control incomplete: {control.control_id}")
        for risk in self.risks:
            if not 1 <= risk.likelihood <= 5 or not 1 <= risk.impact <= 5:
                raise ValueError(f"invalid risk score: {risk.risk_id}")
            unknown = set(risk.controls) - control_ids
            if unknown:
                raise ValueError(f"risk {risk.risk_id} references unknown controls: {sorted(unknown)}")

    def assurance_report(self, evidence_state: Mapping[str, bool]) -> dict[str, object]:
        results = []
        for control in self.controls:
            missing = [item for item in control.evidence if not evidence_state.get(f"{control.control_id}:{item}", False)]
            results.append({
                "control_id": control.control_id,
                "domain": control.domain,
                "status": "PASS" if not missing else "EVIDENCE_GAP",
                "missing_evidence": missing,
                "test": control.test,
                "residual_risk": control.residual_risk,
            })
        pass_count = sum(item["status"] == "PASS" for item in results)
        return {
            "schema": "BUBBLES-HIGHER-ED-IT-GRC-ASSURANCE-V1",
            "control_count": len(results),
            "pass_count": pass_count,
            "gap_count": len(results) - pass_count,
            "controls": results,
            "risks": [dict(asdict(risk), score=risk.score) for risk in sorted(self.risks, key=lambda r: (-r.score, r.risk_id))],
            "maturity": "DETERMINISTIC_TESTED" if pass_count == len(results) else "IMPLEMENTED_WITH_EVIDENCE_GAPS",
            "truth_boundary": "Synthetic control design/evaluation only; not a real audit, certification, compliance opinion, provider security assessment or evidence of Kim's past institution-wide GRC responsibility.",
        }

    def complete_synthetic_evidence(self) -> dict[str, bool]:
        return {
            f"{control.control_id}:{item}": True
            for control in self.controls
            for item in control.evidence
        }

    def receipt(self) -> dict[str, object]:
        report = self.assurance_report(self.complete_synthetic_evidence())
        canonical = json.dumps(report, sort_keys=True, separators=(",", ":"))
        return {
            "schema": "BUBBLES-HIGHER-ED-IT-GRC-RECEIPT-V1",
            "state": report["maturity"],
            "sha256": sha256(canonical.encode("utf-8")).hexdigest(),
            "control_count": report["control_count"],
            "risk_count": len(self.risks),
            "safe_claim": "Designed and deterministically tested a synthetic higher-education IT governance, risk, audit and cyber-assurance control model with evidence requirements, risk-to-control mapping and fail-closed assurance reporting.",
            "forbidden_claims": [
                "performed a real university IT audit",
                "certified an institution against COBIT, NIST, ISO 27001 or ITIL",
                "proved provider security or regulatory compliance",
                "personally held institution-wide IT governance authority",
            ],
            "truth_boundary": report["truth_boundary"],
        }
