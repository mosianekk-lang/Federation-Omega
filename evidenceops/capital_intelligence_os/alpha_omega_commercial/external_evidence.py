from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from owner_authority import OwnerAuthorityValidator, OwnerDecisionReceipt


EXTERNAL_GATE_KEYS = (
    "customer_demand",
    "signed_customer_contract",
    "payment_provider_revenue",
    "live_cloud_provider",
    "enterprise_attestation",
    "partner_adoption",
    "external_case_study",
    "production_scale",
)

OWNER_RESERVED_GATES = {
    "signed_customer_contract",
    "payment_provider_revenue",
    "partner_adoption",
    "external_case_study",
}

GATE_POLICIES: dict[str, dict[str, Any]] = {
    "customer_demand": {
        "authority_domain": "customer_market",
        "required_claims": ("customer_identity_verified", "price_accepted"),
        "max_age_days": 180,
    },
    "signed_customer_contract": {
        "authority_domain": "customer_market",
        "required_claims": ("signed", "parties_verified", "commercial_terms_present"),
        "max_age_days": 365,
    },
    "payment_provider_revenue": {
        "authority_domain": "payment_provider",
        "required_claims": ("settled", "currency", "amount"),
        "max_age_days": 90,
    },
    "live_cloud_provider": {
        "authority_domain": "cloud_run",
        "required_claims": ("deployment_id", "readback", "health", "persistence", "rollback"),
        "max_age_days": 30,
    },
    "enterprise_attestation": {
        "authority_domain": "external_attestation",
        "required_claims": ("independent_issuer", "attestation_valid", "scope_matches"),
        "max_age_days": 365,
    },
    "partner_adoption": {
        "authority_domain": "partner_market",
        "required_claims": ("partner_identity_verified", "adopted", "entitlement_active"),
        "max_age_days": 365,
    },
    "external_case_study": {
        "authority_domain": "customer_market",
        "required_claims": ("customer_consent", "externally_observed", "outcome_evidence_complete"),
        "max_age_days": 365,
    },
    "production_scale": {
        "authority_domain": "live_cloud_operations",
        "required_claims": ("provider_metrics", "load_target_met", "recovery_verified", "duration_met"),
        "max_age_days": 30,
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class EvidenceEnvelope:
    evidence_id: str
    gate: str
    provider: str
    locator: str
    observed_at: str
    content_sha256: str
    evidence_class: str
    claims: dict[str, Any] = field(default_factory=dict)
    owner_confirmed: bool = False
    owner_decision_receipt_id: str | None = None


class ExternalEvidenceAdmissionController:
    """Fail-closed admission and persistence for external commercial proof.

    Evidence may advance a maturity gate only when it is external provider-native,
    current, complete for the relevant gate and backed by fresh provider authority.
    Owner-reserved gates require a provider-backed, hash-valid, evidence-bound owner
    decision receipt. A caller-set boolean is retained only for compatibility and is
    never accepted as owner authority.
    """

    def __init__(
        self,
        root: str | Path,
        authority: dict[str, dict[str, Any]],
        *,
        owner_receipts: dict[str, OwnerDecisionReceipt] | None = None,
        expected_owner_id: str = "Kim Kagiso Mosiane",
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger_file = self.root / "external-evidence-ledger.jsonl"
        self.state_file = self.root / "external-evidence-state.json"
        self.authority = authority
        self.owner_validator = OwnerAuthorityValidator(
            owner_receipts,
            expected_owner_id=expected_owner_id,
        )
        self.decisions: dict[str, dict[str, Any]] = {}
        self.admitted_by_gate: dict[str, list[str]] = {key: [] for key in EXTERNAL_GATE_KEYS}
        self.consumed_owner_receipts: dict[str, str] = {}
        self._replay()

    def admit(self, evidence: EvidenceEnvelope, *, now: str | None = None) -> dict[str, Any]:
        current_time = now or utc_now()
        evidence_hash = digest(asdict(evidence))
        existing = self.decisions.get(evidence.evidence_id)
        if existing:
            if existing["evidence_hash"] == evidence_hash:
                return existing
            conflict = {
                "evidence_id": evidence.evidence_id,
                "gate": evidence.gate,
                "status": "REJECTED",
                "reasons": ["EVIDENCE_ID_CONFLICT"],
                "evidence_hash": evidence_hash,
                "admitted": False,
            }
            self._append("EVIDENCE_CONFLICT", conflict)
            return conflict

        reasons: list[str] = []
        owner_receipt_sha256: str | None = None
        policy = GATE_POLICIES.get(evidence.gate)
        if not policy:
            reasons.append("UNKNOWN_EXTERNAL_GATE")
        if not evidence.evidence_id.strip():
            reasons.append("MISSING_EVIDENCE_ID")
        if not evidence.provider.strip() or not evidence.locator.strip():
            reasons.append("MISSING_PROVIDER_LOCATOR")
        if evidence.evidence_class != "EXTERNAL_PROVIDER_NATIVE":
            reasons.append("NON_EXTERNAL_OR_SYNTHETIC_EVIDENCE")
        if len(evidence.content_sha256) != 64:
            reasons.append("INVALID_CONTENT_SHA256")
        else:
            try:
                int(evidence.content_sha256, 16)
            except ValueError:
                reasons.append("INVALID_CONTENT_SHA256")

        if policy:
            authority_domain = policy["authority_domain"]
            authority = self.authority.get(authority_domain, {})
            if authority.get("state") != "FRESH_VERIFIED":
                reasons.append(f"PROVIDER_AUTHORITY_NOT_VERIFIED:{authority_domain}")
            required = policy["required_claims"]
            missing = [name for name in required if evidence.claims.get(name) in (None, False, "")]
            if missing:
                reasons.append("MISSING_REQUIRED_CLAIMS:" + ",".join(sorted(missing)))
            if evidence.gate == "payment_provider_revenue":
                try:
                    amount = float(evidence.claims.get("amount", 0))
                except (TypeError, ValueError):
                    amount = 0
                if amount <= 0:
                    reasons.append("PAYMENT_AMOUNT_NOT_POSITIVE")
            if evidence.gate == "production_scale":
                try:
                    request_count = int(evidence.claims.get("request_count", 0))
                except (TypeError, ValueError):
                    request_count = 0
                if request_count < 1000:
                    reasons.append("PRODUCTION_SCALE_SAMPLE_TOO_SMALL")
            if evidence.gate in OWNER_RESERVED_GATES:
                if evidence.owner_confirmed:
                    reasons.append("BOOLEAN_OWNER_CONFIRMATION_NOT_ACCEPTED")
                validation = self.owner_validator.validate(
                    receipt_id=evidence.owner_decision_receipt_id,
                    gate=evidence.gate,
                    evidence_id=evidence.evidence_id,
                    evidence_content_sha256=evidence.content_sha256,
                    authority=self.authority,
                    now=current_time,
                    consumed_by=self.consumed_owner_receipts,
                )
                reasons.extend(validation.reasons)
                owner_receipt_sha256 = validation.receipt_sha256

            try:
                observed = parse_utc(evidence.observed_at)
                current = parse_utc(current_time)
                age_seconds = (current - observed).total_seconds()
                if age_seconds < 0:
                    reasons.append("EVIDENCE_FROM_FUTURE")
                if age_seconds > int(policy["max_age_days"]) * 86400:
                    reasons.append("EVIDENCE_STALE")
            except (TypeError, ValueError):
                reasons.append("INVALID_OBSERVED_AT")

        admitted = not reasons
        decision = {
            "evidence_id": evidence.evidence_id,
            "gate": evidence.gate,
            "status": "ADMITTED" if admitted else "REJECTED",
            "reasons": sorted(set(reasons)),
            "evidence_hash": evidence_hash,
            "admitted": admitted,
            "provider": evidence.provider,
            "locator": evidence.locator,
            "observed_at": evidence.observed_at,
            "owner_decision_receipt_id": evidence.owner_decision_receipt_id,
            "owner_decision_receipt_sha256": owner_receipt_sha256,
        }
        self._append("EVIDENCE_EVALUATED", decision)
        return decision

    def project_maturity(self, current_gates: dict[str, bool] | None = None) -> dict[str, Any]:
        gates = {key: bool((current_gates or {}).get(key, False)) for key in EXTERNAL_GATE_KEYS}
        evidence: dict[str, list[str]] = {key: [] for key in EXTERNAL_GATE_KEYS}
        for gate, ids in self.admitted_by_gate.items():
            if ids:
                gates[gate] = True
                evidence[gate] = sorted(ids)
        full = all(gates.values())
        result = {
            "external_gates": gates,
            "external_gate_evidence": evidence,
            "full_commercial_maturity": full,
            "canonical_status": (
                "FULL_COMMERCIAL_MATURITY_VERIFIED"
                if full
                else "COMMERCIAL_READINESS_VERIFIED_EXTERNAL_MATURITY_GATES_OPEN"
            ),
            "ledger_integrity": self.verify_ledger(),
            "consumed_owner_receipts": dict(sorted(self.consumed_owner_receipts.items())),
        }
        result["projection_sha256"] = digest(result)
        return result

    def authority_readback(self) -> dict[str, Any]:
        required_domains = sorted(
            {policy["authority_domain"] for policy in GATE_POLICIES.values()} | {"owner_decision"}
        )
        states = {domain: self.authority.get(domain, {}).get("state", "UNVERIFIED") for domain in required_domains}
        return {
            "required_domains": required_domains,
            "states": states,
            "fresh_verified_domains": sorted(domain for domain, state in states.items() if state == "FRESH_VERIFIED"),
            "blocked_or_unverified_domains": sorted(domain for domain, state in states.items() if state != "FRESH_VERIFIED"),
            "readback_sha256": digest(states),
        }

    def verify_ledger(self) -> bool:
        previous = "GENESIS"
        for event in self._events():
            if event.get("previous_hash") != previous:
                return False
            payload = {key: value for key, value in event.items() if key != "event_hash"}
            if digest(payload) != event.get("event_hash"):
                return False
            previous = event["event_hash"]
        return True

    def _append(self, event_type: str, payload: dict[str, Any]) -> None:
        events = self._events()
        event = {
            "event_id": f"commercial-evidence-{len(events) + 1:08d}",
            "event_type": event_type,
            "payload": payload,
            "recorded_at": utc_now(),
            "previous_hash": events[-1]["event_hash"] if events else "GENESIS",
        }
        event["event_hash"] = digest(event)
        with self.ledger_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        self._apply(event)
        self._persist()

    def _events(self) -> list[dict[str, Any]]:
        if not self.ledger_file.exists():
            return []
        return [
            json.loads(line)
            for line in self.ledger_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _apply(self, event: dict[str, Any]) -> None:
        if event["event_type"] != "EVIDENCE_EVALUATED":
            return
        decision = event["payload"]
        self.decisions[decision["evidence_id"]] = decision
        if decision.get("admitted"):
            ids = self.admitted_by_gate.setdefault(decision["gate"], [])
            if decision["evidence_id"] not in ids:
                ids.append(decision["evidence_id"])
            receipt_id = decision.get("owner_decision_receipt_id")
            if receipt_id:
                self.consumed_owner_receipts[receipt_id] = decision["evidence_id"]

    def _replay(self) -> None:
        for event in self._events():
            self._apply(event)
        self._persist()

    def _persist(self) -> None:
        state = {
            "decisions": self.decisions,
            "admitted_by_gate": self.admitted_by_gate,
            "consumed_owner_receipts": self.consumed_owner_receipts,
            "ledger_head": self._events()[-1]["event_hash"] if self._events() else "GENESIS",
        }
        self.state_file.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
