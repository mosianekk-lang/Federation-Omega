from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


_SECRET_KEY_RE = re.compile(r"(secret|token|password|private[_-]?key|api[_-]?key)", re.IGNORECASE)
_ALLOWED_PRIVACY_REQUESTS = {"ACCESS", "RECTIFY", "DELETE", "RESTRICT"}
_ALLOWED_SERVICE_REQUESTS = {
    "workspace.provision",
    "workspace.rollback",
    "subscription.change",
    "tenant.suspend",
    "support.request",
}
_OWNER_RESERVED_SERVICE_REQUESTS = {"subscription.change", "tenant.suspend"}
_ALLOWED_LEAD_STAGES = {"NEW", "QUALIFIED", "DISCOVERY", "PROPOSAL", "NEGOTIATION", "CLOSED_WON", "CLOSED_LOST"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _reject_secret_material(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if _SECRET_KEY_RE.search(str(key)):
                raise ValueError(f"secret-shaped field rejected at {path}.{key}")
            _reject_secret_material(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_secret_material(item, f"{path}[{index}]")


@dataclass(frozen=True)
class EvidenceReference:
    reference_id: str
    provider: str
    locator: str
    sha256: str
    observed_at: str
    evidence_class: str = "REFERENCE_PROVIDER"

    def validate(self) -> None:
        if not self.reference_id or not self.provider or not self.locator:
            raise ValueError("evidence reference fields are required")
        if not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ValueError("evidence sha256 must be 64 lowercase hex characters")
        _reject_secret_material(asdict(self))


class CommercialAssuranceControlPlane:
    """Reference control plane implementing the safe C10-C15 commercial slice.

    It is intentionally effect-bounded. It provides assurance, service-request,
    evidence, revenue-operations, scale and succession contracts without sending
    communications, creating financial commitments, claiming external customers,
    or mutating external cloud/payment providers.
    """

    def __init__(self, state_dir: str | Path) -> None:
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / "commercial_assurance_state.json"
        self.ledger_file = self.state_dir / "commercial_assurance_ledger.jsonl"
        self.receipts_dir = self.state_dir / "receipts"
        self.receipts_dir.mkdir(exist_ok=True)
        if not self.state_file.exists():
            self._write_state(
                {
                    "controls": {},
                    "retention_policies": {},
                    "privacy_requests": {},
                    "dr_drills": {},
                    "service_requests": {},
                    "case_studies": {},
                    "leads": {},
                    "quotes": {},
                    "contracts": {},
                    "revenue_events": {},
                    "scale_runs": {},
                    "succession_exports": {},
                }
            )

    # C10 — Security, privacy and enterprise assurance
    def register_control(
        self,
        control_id: str,
        family: str,
        description: str,
        owner_role: str,
        evidence: list[EvidenceReference],
    ) -> dict[str, Any]:
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{2,63}", control_id):
            raise ValueError("invalid control_id")
        if not evidence:
            raise ValueError("at least one evidence reference is required")
        for item in evidence:
            item.validate()
        record = {
            "control_id": control_id,
            "family": family,
            "description": description,
            "owner_role": owner_role,
            "evidence": [asdict(item) for item in evidence],
            "status": "REFERENCE_EVIDENCE_ATTACHED",
            "registered_at": utc_now(),
        }
        _reject_secret_material(record)
        state = self._read_state()
        existing = state["controls"].get(control_id)
        if existing and self._stable(existing) != self._stable(record):
            raise ValueError("control_id already exists with different content")
        state["controls"][control_id] = record
        self._write_state(state)
        self._ledger("C10", "control.register", control_id, record)
        return record

    def set_retention_policy(
        self,
        policy_id: str,
        data_class: str,
        retention_days: int,
        deletion_mode: str,
        legal_hold_supported: bool = True,
    ) -> dict[str, Any]:
        if retention_days < 1:
            raise ValueError("retention_days must be positive")
        if deletion_mode not in {"DELETE", "ANONYMIZE", "ARCHIVE"}:
            raise ValueError("unsupported deletion_mode")
        record = {
            "policy_id": policy_id,
            "data_class": data_class,
            "retention_days": retention_days,
            "deletion_mode": deletion_mode,
            "legal_hold_supported": legal_hold_supported,
            "status": "REFERENCE_POLICY_ACTIVE",
            "updated_at": utc_now(),
        }
        state = self._read_state()
        state["retention_policies"][policy_id] = record
        self._write_state(state)
        self._ledger("C10", "retention.upsert", policy_id, record)
        return record

    def open_privacy_request(
        self,
        request_id: str,
        tenant_id: str,
        subject_reference: str,
        request_type: str,
    ) -> dict[str, Any]:
        if request_type not in _ALLOWED_PRIVACY_REQUESTS:
            raise ValueError("unsupported privacy request type")
        if _SECRET_KEY_RE.search(subject_reference):
            raise ValueError("subject_reference must be an opaque non-secret identifier")
        record = {
            "request_id": request_id,
            "tenant_id": tenant_id,
            "subject_reference": subject_reference,
            "request_type": request_type,
            "status": "OPEN",
            "opened_at": utc_now(),
        }
        state = self._read_state()
        if request_id in state["privacy_requests"]:
            raise ValueError("duplicate privacy request")
        state["privacy_requests"][request_id] = record
        self._write_state(state)
        self._ledger("C10", "privacy.open", request_id, record)
        return record

    def complete_privacy_request(
        self,
        request_id: str,
        evidence: list[EvidenceReference],
        disposition: str,
    ) -> dict[str, Any]:
        if disposition not in {"FULFILLED", "DENIED_WITH_LAWFUL_BASIS", "HELD_LEGAL_HOLD"}:
            raise ValueError("unsupported disposition")
        if not evidence:
            raise ValueError("completion evidence is required")
        for item in evidence:
            item.validate()
        state = self._read_state()
        record = state["privacy_requests"][request_id]
        if record["status"] != "OPEN":
            raise ValueError("privacy request is not open")
        record.update(
            {
                "status": disposition,
                "completed_at": utc_now(),
                "evidence": [asdict(item) for item in evidence],
            }
        )
        self._write_state(state)
        self._ledger("C10", "privacy.complete", request_id, record)
        return record

    def run_disaster_recovery_drill(
        self,
        drill_id: str,
        source_snapshot: dict[str, Any],
        restored_snapshot: dict[str, Any],
        recovery_seconds: float,
        rto_target_seconds: float,
    ) -> dict[str, Any]:
        if recovery_seconds < 0 or rto_target_seconds <= 0:
            raise ValueError("recovery and target values must be valid")
        source_sha = digest(source_snapshot)
        restored_sha = digest(restored_snapshot)
        record = {
            "drill_id": drill_id,
            "source_sha256": source_sha,
            "restored_sha256": restored_sha,
            "integrity_pass": source_sha == restored_sha,
            "recovery_seconds": recovery_seconds,
            "rto_target_seconds": rto_target_seconds,
            "rto_pass": recovery_seconds <= rto_target_seconds,
            "provider_boundary": "REFERENCE_PROVIDER_ONLY",
            "executed_at": utc_now(),
        }
        record["pass"] = bool(record["integrity_pass"] and record["rto_pass"])
        state = self._read_state()
        state["dr_drills"][drill_id] = record
        self._write_state(state)
        self._receipt("C10", drill_id, record)
        self._ledger("C10", "dr.drill", drill_id, record)
        return record

    def assurance_pack(self) -> dict[str, Any]:
        state = self._read_state()
        required_families = {"ACCESS", "AUDIT", "PRIVACY", "RETENTION", "RECOVERY"}
        observed = {item["family"] for item in state["controls"].values()}
        open_privacy = [key for key, item in state["privacy_requests"].items() if item["status"] == "OPEN"]
        passing_drills = [item for item in state["dr_drills"].values() if item["pass"]]
        result = {
            "stage": "C10",
            "required_control_families": sorted(required_families),
            "observed_control_families": sorted(observed),
            "control_coverage_pass": required_families.issubset(observed),
            "retention_policy_count": len(state["retention_policies"]),
            "open_privacy_requests": sorted(open_privacy),
            "passing_dr_drills": len(passing_drills),
            "truth_boundary": "Reference assurance evidence only; no certification, legal opinion, production security guarantee or enterprise audit attestation.",
        }
        result["status"] = (
            "REFERENCE_ASSURANCE_VERIFIED_ENTERPRISE_ATTESTATION_REQUIRED"
            if result["control_coverage_pass"] and result["retention_policy_count"] > 0 and not open_privacy and passing_drills
            else "REFERENCE_ASSURANCE_INCOMPLETE"
        )
        self._receipt("C10", "assurance-pack", result)
        return result

    # C11 — Service-enabled control plane before self-service SaaS
    def submit_service_request(
        self,
        request_id: str,
        tenant_id: str,
        request_type: str,
        payload: dict[str, Any],
        requested_by: str,
        owner_approved: bool = False,
    ) -> dict[str, Any]:
        if request_type not in _ALLOWED_SERVICE_REQUESTS:
            raise ValueError("unsupported service request")
        _reject_secret_material(payload)
        state = self._read_state()
        if request_id in state["service_requests"]:
            existing = state["service_requests"][request_id]
            if self._stable(existing["request"]) == self._stable(payload):
                return existing
            raise ValueError("request_id already used for different payload")
        reserved = request_type in _OWNER_RESERVED_SERVICE_REQUESTS
        status = "OWNER_APPROVAL_REQUIRED" if reserved and not owner_approved else "ACCEPTED_REFERENCE_EXECUTION_PENDING"
        record = {
            "request_id": request_id,
            "tenant_id": tenant_id,
            "request_type": request_type,
            "request": payload,
            "requested_by": requested_by,
            "owner_approved": owner_approved,
            "status": status,
            "submitted_at": utc_now(),
            "external_effects_allowed": False,
        }
        state["service_requests"][request_id] = record
        self._write_state(state)
        self._ledger("C11", "service.submit", request_id, record)
        return record

    def execute_reference_service_request(
        self,
        request_id: str,
        handler: Callable[[dict[str, Any]], dict[str, Any]],
        rollback: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        state = self._read_state()
        record = state["service_requests"][request_id]
        if record["status"] != "ACCEPTED_REFERENCE_EXECUTION_PENDING":
            raise PermissionError("service request is not eligible for reference execution")
        execution = handler(record["request"])
        _reject_secret_material(execution)
        if not execution.get("readback_pass") or not execution.get("health_pass"):
            rollback_result = rollback(execution)
            record.update({"status": "ROLLED_BACK_AFTER_FAILED_PROOF", "execution": execution, "rollback": rollback_result})
        else:
            rollback_result = rollback(execution)
            if not rollback_result.get("rollback_pass"):
                raise RuntimeError("rollback proof failed")
            record.update(
                {
                    "status": "REFERENCE_EXECUTION_VERIFIED_AND_ROLLED_BACK",
                    "execution": execution,
                    "rollback": rollback_result,
                    "provider_boundary": "REFERENCE_HANDLER_ONLY_EXTERNAL_PROVIDER_BLOCKED",
                }
            )
        record["completed_at"] = utc_now()
        self._write_state(state)
        self._receipt("C11", request_id, record)
        self._ledger("C11", "service.execute", request_id, record)
        return record

    # C12 — Case-study evidence framework
    def register_outcome_study(
        self,
        study_id: str,
        tenant_id: str,
        metric: str,
        baseline: float,
        outcome: float,
        unit: str,
        lower_is_better: bool,
        evidence: list[EvidenceReference],
        evidence_origin: str,
    ) -> dict[str, Any]:
        if baseline < 0 or outcome < 0:
            raise ValueError("baseline and outcome must be non-negative")
        if baseline == 0:
            raise ValueError("baseline must be non-zero")
        for item in evidence:
            item.validate()
        raw_change = baseline - outcome if lower_is_better else outcome - baseline
        improvement = raw_change / baseline
        external = evidence_origin == "EXTERNAL_CUSTOMER_VERIFIED" and all(
            item.evidence_class == "EXTERNAL_CUSTOMER_VERIFIED" for item in evidence
        )
        record = {
            "study_id": study_id,
            "tenant_id": tenant_id,
            "metric": metric,
            "baseline": baseline,
            "outcome": outcome,
            "unit": unit,
            "lower_is_better": lower_is_better,
            "improvement_ratio": round(improvement, 6),
            "evidence": [asdict(item) for item in evidence],
            "evidence_origin": evidence_origin,
            "status": "EXTERNAL_CASE_STUDY_VERIFIED" if external else "MARKET_PROOF_REQUIRED",
            "registered_at": utc_now(),
        }
        state = self._read_state()
        state["case_studies"][study_id] = record
        self._write_state(state)
        self._ledger("C12", "study.register", study_id, record)
        return record

    def case_study_report(self, study_id: str) -> dict[str, Any]:
        study = self._read_state()["case_studies"][study_id]
        return {
            "study_id": study_id,
            "metric": study["metric"],
            "result": {
                "baseline": study["baseline"],
                "outcome": study["outcome"],
                "unit": study["unit"],
                "improvement_ratio": study["improvement_ratio"],
            },
            "status": study["status"],
            "publication_allowed": study["status"] == "EXTERNAL_CASE_STUDY_VERIFIED",
            "truth_boundary": "Internal or synthetic evidence cannot establish customer outcomes or market demand.",
        }

    # C13 — Sales and revenue operations with owner-reserved commitments
    def create_lead(self, lead_id: str, organisation_reference: str, source: str, problem_statement: str) -> dict[str, Any]:
        record = {
            "lead_id": lead_id,
            "organisation_reference": organisation_reference,
            "source": source,
            "problem_statement": problem_statement,
            "stage": "NEW",
            "created_at": utc_now(),
        }
        _reject_secret_material(record)
        state = self._read_state()
        if lead_id in state["leads"]:
            raise ValueError("duplicate lead")
        state["leads"][lead_id] = record
        self._write_state(state)
        self._ledger("C13", "lead.create", lead_id, record)
        return record

    def advance_lead(self, lead_id: str, stage: str, evidence_reference: str) -> dict[str, Any]:
        if stage not in _ALLOWED_LEAD_STAGES:
            raise ValueError("invalid lead stage")
        state = self._read_state()
        lead = state["leads"][lead_id]
        lead.update({"stage": stage, "stage_evidence_reference": evidence_reference, "updated_at": utc_now()})
        self._write_state(state)
        self._ledger("C13", "lead.advance", lead_id, lead)
        return lead

    def create_quote_draft(
        self,
        quote_id: str,
        lead_id: str,
        offer_id: str,
        currency: str,
        amount: float,
        term_months: int,
    ) -> dict[str, Any]:
        if amount < 0 or term_months < 1:
            raise ValueError("invalid quote terms")
        state = self._read_state()
        if lead_id not in state["leads"]:
            raise KeyError("lead not found")
        record = {
            "quote_id": quote_id,
            "lead_id": lead_id,
            "offer_id": offer_id,
            "currency": currency,
            "amount": round(amount, 2),
            "term_months": term_months,
            "status": "DRAFT_OWNER_APPROVAL_REQUIRED",
            "financial_commitment": False,
            "created_at": utc_now(),
        }
        state["quotes"][quote_id] = record
        self._write_state(state)
        self._ledger("C13", "quote.draft", quote_id, record)
        return record

    def approve_quote(self, quote_id: str, owner_approval_reference: str) -> dict[str, Any]:
        state = self._read_state()
        quote = state["quotes"][quote_id]
        quote.update(
            {
                "status": "OWNER_APPROVED_FOR_EXTERNAL_PRESENTATION",
                "owner_approval_reference": owner_approval_reference,
                "approved_at": utc_now(),
                "financial_commitment": False,
            }
        )
        self._write_state(state)
        self._ledger("C13", "quote.approve", quote_id, quote)
        return quote

    def register_contract_draft(self, contract_id: str, quote_id: str, legal_review_status: str) -> dict[str, Any]:
        state = self._read_state()
        quote = state["quotes"][quote_id]
        if quote["status"] != "OWNER_APPROVED_FOR_EXTERNAL_PRESENTATION":
            raise PermissionError("quote requires owner approval before contract drafting")
        record = {
            "contract_id": contract_id,
            "quote_id": quote_id,
            "legal_review_status": legal_review_status,
            "status": "DRAFT_NOT_EXECUTED",
            "binding": False,
            "created_at": utc_now(),
        }
        state["contracts"][contract_id] = record
        self._write_state(state)
        self._ledger("C13", "contract.draft", contract_id, record)
        return record

    def register_verified_revenue_event(
        self,
        event_id: str,
        contract_id: str,
        amount: float,
        currency: str,
        provider_receipt: EvidenceReference,
        owner_confirmed: bool,
    ) -> dict[str, Any]:
        provider_receipt.validate()
        if not owner_confirmed:
            raise PermissionError("owner confirmation is required for revenue recognition")
        if provider_receipt.evidence_class != "PAYMENT_PROVIDER_VERIFIED":
            raise ValueError("payment-provider evidence is required")
        if amount <= 0:
            raise ValueError("revenue amount must be positive")
        state = self._read_state()
        if contract_id not in state["contracts"]:
            raise KeyError("contract not found")
        record = {
            "event_id": event_id,
            "contract_id": contract_id,
            "amount": round(amount, 2),
            "currency": currency,
            "provider_receipt": asdict(provider_receipt),
            "status": "PAYMENT_PROVIDER_VERIFIED_OWNER_CONFIRMED",
            "recognised_at": utc_now(),
        }
        state["revenue_events"][event_id] = record
        self._write_state(state)
        self._ledger("C13", "revenue.register", event_id, record)
        return record

    def revenue_operations_dashboard(self) -> dict[str, Any]:
        state = self._read_state()
        by_stage = {stage: 0 for stage in sorted(_ALLOWED_LEAD_STAGES)}
        for lead in state["leads"].values():
            by_stage[lead["stage"]] += 1
        revenue_by_currency: dict[str, float] = {}
        for event in state["revenue_events"].values():
            revenue_by_currency[event["currency"]] = round(
                revenue_by_currency.get(event["currency"], 0.0) + float(event["amount"]), 2
            )
        return {
            "lead_funnel": by_stage,
            "quotes": len(state["quotes"]),
            "draft_contracts": len(state["contracts"]),
            "verified_revenue_events": len(state["revenue_events"]),
            "verified_revenue_by_currency": revenue_by_currency,
            "truth_boundary": "Only payment-provider receipts with owner confirmation are counted as revenue.",
        }

    # C14 — Scale, reliability and unit-economics evidence
    def run_scale_evaluation(
        self,
        run_id: str,
        operation: str,
        latencies_ms: list[float],
        request_count: int,
        failure_count: int,
        concurrency: int,
        recovery_seconds: float,
        monthly_revenue_zar: float,
        monthly_delivery_cost_zar: float,
        support_hours: float,
        targets: dict[str, float],
    ) -> dict[str, Any]:
        if not latencies_ms or request_count < 1 or failure_count < 0 or failure_count > request_count:
            raise ValueError("invalid load-test sample")
        if concurrency < 1 or recovery_seconds < 0 or monthly_revenue_zar <= 0:
            raise ValueError("invalid scale inputs")
        ordered = sorted(float(item) for item in latencies_ms)
        p95_index = max(0, math.ceil(len(ordered) * 0.95) - 1)
        p95 = ordered[p95_index]
        error_rate = failure_count / request_count
        gross_margin = (monthly_revenue_zar - monthly_delivery_cost_zar) / monthly_revenue_zar
        gates = {
            "p95_latency": p95 <= targets["max_p95_latency_ms"],
            "error_rate": error_rate <= targets["max_error_rate"],
            "recovery": recovery_seconds <= targets["max_recovery_seconds"],
            "gross_margin": gross_margin >= targets["min_gross_margin"],
            "support_burden": support_hours <= targets["max_support_hours"],
        }
        record = {
            "run_id": run_id,
            "operation": operation,
            "sample": {
                "request_count": request_count,
                "failure_count": failure_count,
                "concurrency": concurrency,
                "latency_samples": len(ordered),
            },
            "metrics": {
                "p95_latency_ms": round(p95, 3),
                "error_rate": round(error_rate, 6),
                "recovery_seconds": recovery_seconds,
                "gross_margin": round(gross_margin, 6),
                "support_hours": support_hours,
            },
            "targets": targets,
            "gates": gates,
            "status": "REFERENCE_SCALE_VERIFIED_PRODUCTION_LOAD_REQUIRED" if all(gates.values()) else "REFERENCE_SCALE_TARGET_FAILED",
            "provider_boundary": "DETERMINISTIC_REFERENCE_LOAD_ONLY",
            "executed_at": utc_now(),
        }
        state = self._read_state()
        state["scale_runs"][run_id] = record
        self._write_state(state)
        self._receipt("C14", run_id, record)
        self._ledger("C14", "scale.evaluate", run_id, record)
        return record

    # C15 — Commercial succession and exact completion gate
    def export_succession_package(
        self,
        package_id: str,
        runbooks: dict[str, str],
        authority_boundaries: dict[str, str],
    ) -> dict[str, Any]:
        _reject_secret_material(runbooks)
        _reject_secret_material(authority_boundaries)
        state = self._read_state()
        payload = {
            "package_id": package_id,
            "created_at": utc_now(),
            "state_sha256": digest(state),
            "ledger_sha256": hashlib.sha256(self.ledger_file.read_bytes()).hexdigest() if self.ledger_file.exists() else digest([]),
            "runbooks": runbooks,
            "authority_boundaries": authority_boundaries,
            "maturity": self.maturity_snapshot(),
        }
        package_sha = digest(payload)
        payload["package_sha256"] = package_sha
        path = self.receipts_dir / f"succession-{package_id}.json"
        self._atomic_json(path, payload)
        readback = json.loads(path.read_text(encoding="utf-8"))
        verification = {
            "package_id": package_id,
            "path": str(path),
            "readback_pass": readback["package_sha256"] == package_sha,
            "package_sha256": package_sha,
            "status": "SUCCESSION_PACKAGE_VERIFIED",
        }
        state = self._read_state()
        state["succession_exports"][package_id] = verification
        self._write_state(state)
        self._ledger("C15", "succession.export", package_id, verification)
        return verification

    def maturity_snapshot(self) -> dict[str, Any]:
        state = self._read_state()
        assurance = self.assurance_pack()
        service_verified = any(
            item["status"] == "REFERENCE_EXECUTION_VERIFIED_AND_ROLLED_BACK"
            for item in state["service_requests"].values()
        )
        case_external = any(item["status"] == "EXTERNAL_CASE_STUDY_VERIFIED" for item in state["case_studies"].values())
        scale_verified = any(
            item["status"] == "REFERENCE_SCALE_VERIFIED_PRODUCTION_LOAD_REQUIRED"
            for item in state["scale_runs"].values()
        )
        external_gates = {
            "customer_demand": False,
            "signed_customer_contract": False,
            "payment_provider_revenue": bool(state["revenue_events"]),
            "live_cloud_provider": False,
            "enterprise_attestation": False,
            "partner_adoption": False,
            "external_case_study": case_external,
            "production_scale": False,
        }
        technical = {
            "C10_reference_assurance": assurance["status"] == "REFERENCE_ASSURANCE_VERIFIED_ENTERPRISE_ATTESTATION_REQUIRED",
            "C11_service_enabled_reference": service_verified,
            "C12_evidence_framework": bool(state["case_studies"]),
            "C13_revenue_operations": bool(state["leads"]) and bool(state["quotes"]),
            "C14_reference_scale": scale_verified,
            "C15_succession_ready": bool(state["succession_exports"]),
        }
        technical_ready = all(value for key, value in technical.items() if key != "C15_succession_ready")
        full_maturity = technical_ready and all(external_gates.values())
        return {
            "technical_gates": technical,
            "external_gates": external_gates,
            "technical_reference_ready": technical_ready,
            "full_commercial_maturity": full_maturity,
            "canonical_status": (
                "FULL_COMMERCIAL_MATURITY_VERIFIED" if full_maturity else "COMMERCIAL_READINESS_VERIFIED_EXTERNAL_MATURITY_GATES_OPEN"
                if technical_ready else "COMMERCIAL_REFERENCE_IMPLEMENTATION_INCOMPLETE"
            ),
        }

    # Persistence and proof helpers
    def verify_ledger(self) -> dict[str, Any]:
        rows = self._read_jsonl(self.ledger_file)
        previous = "GENESIS"
        for index, row in enumerate(rows):
            body = {key: value for key, value in row.items() if key != "entry_sha256"}
            if row.get("previous_sha256") != previous or digest(body) != row.get("entry_sha256"):
                return {"pass": False, "failed_index": index, "entries": len(rows)}
            previous = row["entry_sha256"]
        return {"pass": True, "entries": len(rows), "head_sha256": previous}

    def _ledger(self, stage: str, action: str, object_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._read_jsonl(self.ledger_file)
        previous = rows[-1]["entry_sha256"] if rows else "GENESIS"
        body = {
            "stage": stage,
            "action": action,
            "object_id": object_id,
            "payload_sha256": digest(payload),
            "previous_sha256": previous,
            "recorded_at": utc_now(),
        }
        row = {**body, "entry_sha256": digest(body)}
        with self.ledger_file.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(row) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return row

    def _receipt(self, stage: str, receipt_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = {
            "stage": stage,
            "receipt_id": receipt_id,
            "payload_sha256": digest(payload),
            "created_at": utc_now(),
        }
        body["receipt_sha256"] = digest(body)
        self._atomic_json(self.receipts_dir / f"{stage.lower()}-{receipt_id}.json", body)
        return body

    def _read_state(self) -> dict[str, Any]:
        return json.loads(self.state_file.read_text(encoding="utf-8"))

    def _write_state(self, value: dict[str, Any]) -> None:
        _reject_secret_material(value)
        self._atomic_json(self.state_file, value)

    @staticmethod
    def _stable(value: dict[str, Any]) -> dict[str, Any]:
        return {key: item for key, item in value.items() if key not in {"registered_at", "updated_at", "created_at"}}

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    @staticmethod
    def _atomic_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, path)
