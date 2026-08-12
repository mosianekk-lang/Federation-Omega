from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Iterable, Mapping


@dataclass(frozen=True)
class AcademicProcess:
    process_id: str
    domain: str
    objective: str
    owner_role: str
    required_evidence: tuple[str, ...]
    control_test: str


@dataclass(frozen=True)
class AcademicRisk:
    risk_id: str
    scenario: str
    processes: tuple[str, ...]
    treatment: str
    severity: str


class HigherEdAcademicOperationsLab:
    """Synthetic School-of-Technology academic operations/governance reference lab.

    This lab demonstrates process architecture, evidence gates and operating controls.
    It does not create academic authority, accreditation status, curriculum ownership,
    or evidence that Kim personally served as a dean, academic head or programme owner.
    """

    required_domains = (
        "programme_lifecycle",
        "curriculum_and_module_control",
        "faculty_allocation",
        "timetabling_and_resources",
        "assessment_and_examinations",
        "academic_integrity",
        "quality_assurance_and_accreditation",
        "student_support_and_progression",
        "academic_data_and_reporting",
    )

    def __init__(self, processes: Iterable[AcademicProcess] | None = None, risks: Iterable[AcademicRisk] | None = None):
        self.processes = tuple(processes or self.reference_processes())
        self.risks = tuple(risks or self.reference_risks())
        self._validate()

    @staticmethod
    def reference_processes() -> tuple[AcademicProcess, ...]:
        return (
            AcademicProcess("APL-01", "programme_lifecycle", "Every programme has an approved owner, current status, review cycle and evidence of authorised changes.", "Academic Head", ("programme register", "approval record", "review schedule", "change history"), "Trace one programme from approval through current version and next review."),
            AcademicProcess("CUR-01", "curriculum_and_module_control", "Curriculum and module outcomes are version-controlled and mapped to programme outcomes and delivery plans.", "Programme Lead", ("curriculum map", "module descriptors", "outcome mapping", "version approval"), "Select one module and verify outcomes, version, owner and approved programme mapping."),
            AcademicProcess("FAC-01", "faculty_allocation", "Teaching allocation matches qualification, workload, availability and programme need.", "Academic Head", ("faculty profile", "workload plan", "allocation schedule", "exception approval"), "Sample allocations and verify qualification/workload/exception evidence."),
            AcademicProcess("TIM-01", "timetabling_and_resources", "Schedules, classrooms, laboratories and technology resources are conflict-checked and fit for delivery.", "Operations Manager", ("master timetable", "room/lab allocation", "resource readiness check", "conflict report"), "Run a synthetic timetable conflict check and verify critical lab readiness."),
            AcademicProcess("ASM-01", "assessment_and_examinations", "Assessments and examinations have approved instruments, moderation, secure handling, scheduling and result controls.", "Assessment Lead", ("assessment plan", "moderation record", "exam schedule", "mark approval", "result release control"), "Trace one assessment from design through moderation, marking and controlled result release."),
            AcademicProcess("INT-01", "academic_integrity", "Potential misconduct is detected, recorded and routed through fair, evidence-based review with role separation.", "Academic Integrity Officer", ("integrity policy", "case register", "evidence record", "decision trail"), "Test one synthetic integrity case for evidence, decision rights, review and no automated guilt inference."),
            AcademicProcess("QA-01", "quality_assurance_and_accreditation", "Quality obligations, review findings, accreditation evidence and remediation are current and traceable.", "Quality Lead", ("quality calendar", "self-evaluation", "external review/accreditation record", "remediation ledger"), "Reperform one quality control and verify finding-to-remediation-to-closure traceability."),
            AcademicProcess("STU-01", "student_support_and_progression", "Student risk and progression are supported through transparent, non-discriminatory interventions with human oversight.", "Student Success Lead", ("progression rules", "support referral", "intervention record", "appeal/review route"), "Trace one synthetic at-risk student through support without automated high-consequence decision-making."),
            AcademicProcess("ADR-01", "academic_data_and_reporting", "Academic KPIs have agreed definitions, source lineage, quality checks and accountable owners.", "Academic Operations Lead", ("KPI dictionary", "source lineage", "quality report", "management dashboard"), "Trace one KPI from source to management report and verify definition and quality threshold."),
        )

    @staticmethod
    def reference_risks() -> tuple[AcademicRisk, ...]:
        return (
            AcademicRisk("AR-01", "Unapproved curriculum/version is delivered.", ("APL-01", "CUR-01"), "Version lock, approval checks and delivery-pack readback.", "HIGH"),
            AcademicRisk("AR-02", "Faculty allocation creates quality or workload failure.", ("FAC-01",), "Qualification/workload checks plus exception approval.", "MEDIUM"),
            AcademicRisk("AR-03", "Timetable/lab conflict disrupts teaching.", ("TIM-01",), "Automated conflict checks, readiness attestations and contingency planning.", "MEDIUM"),
            AcademicRisk("AR-04", "Assessment integrity or result-release controls fail.", ("ASM-01", "INT-01"), "Moderation, access separation, audit trails and controlled release.", "HIGH"),
            AcademicRisk("AR-05", "Quality/accreditation evidence is stale or remediation is not closed.", ("QA-01",), "Evidence freshness checks, accountable remediation and closure receipts.", "HIGH"),
            AcademicRisk("AR-06", "Student analytics cause unfair or unsupported decisions.", ("STU-01", "ADR-01"), "Human oversight, explainable criteria, review/appeal and data-quality controls.", "HIGH"),
        )

    def _validate(self) -> None:
        ids = [p.process_id for p in self.processes]
        if len(ids) != len(set(ids)):
            raise ValueError("process IDs must be unique")
        present = {p.domain for p in self.processes}
        missing = set(self.required_domains) - present
        if missing:
            raise ValueError(f"missing academic domains: {sorted(missing)}")
        for process in self.processes:
            if not process.owner_role or not process.required_evidence or not process.control_test:
                raise ValueError(f"incomplete process: {process.process_id}")
        known = set(ids)
        for risk in self.risks:
            unknown = set(risk.processes) - known
            if unknown:
                raise ValueError(f"risk {risk.risk_id} references unknown process: {sorted(unknown)}")

    def operating_report(self, evidence: Mapping[str, bool]) -> dict[str, object]:
        results = []
        for process in self.processes:
            missing = [item for item in process.required_evidence if not evidence.get(f"{process.process_id}:{item}", False)]
            results.append({
                "process_id": process.process_id,
                "domain": process.domain,
                "status": "PASS" if not missing else "EVIDENCE_GAP",
                "missing_evidence": missing,
                "control_test": process.control_test,
                "owner_role": process.owner_role,
            })
        pass_count = sum(item["status"] == "PASS" for item in results)
        return {
            "schema": "BUBBLES-HIGHER-ED-ACADEMIC-OPERATIONS-V1",
            "process_count": len(results),
            "pass_count": pass_count,
            "gap_count": len(results) - pass_count,
            "processes": results,
            "risks": [asdict(risk) for risk in self.risks],
            "maturity": "DETERMINISTIC_TESTED" if pass_count == len(results) else "IMPLEMENTED_WITH_EVIDENCE_GAPS",
            "truth_boundary": "Synthetic operating-model proof only; not accreditation, academic-authority, curriculum approval, real assessment administration, or evidence of Kim's past academic-management role.",
        }

    def complete_synthetic_evidence(self) -> dict[str, bool]:
        return {
            f"{process.process_id}:{item}": True
            for process in self.processes
            for item in process.required_evidence
        }

    def receipt(self) -> dict[str, object]:
        report = self.operating_report(self.complete_synthetic_evidence())
        canonical = json.dumps(report, sort_keys=True, separators=(",", ":"))
        return {
            "schema": "BUBBLES-HIGHER-ED-ACADEMIC-OPERATIONS-RECEIPT-V1",
            "state": report["maturity"],
            "sha256": sha256(canonical.encode("utf-8")).hexdigest(),
            "safe_claim": "Designed and deterministically tested a synthetic School-of-Technology academic operations model covering programme lifecycle, curriculum control, faculty allocation, timetabling/resources, assessment/examinations, academic integrity, quality/accreditation evidence, student progression and academic reporting.",
            "forbidden_claims": [
                "served as a dean or academic head",
                "owned real curriculum accreditation",
                "administered real university examinations",
                "made real academic-integrity findings",
                "proved compliance with a specific accreditation body",
            ],
            "truth_boundary": report["truth_boundary"],
        }
