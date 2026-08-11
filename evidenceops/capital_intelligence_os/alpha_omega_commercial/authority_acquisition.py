from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OPERATIONAL_STATES = {"FRESH_VERIFIED", "FRESH_VERIFIED_READBACK", "FRESH_AUTHORITY_VERIFIED"}
STAGE_PATTERN = re.compile(r"^C(0[1-9]|1[0-5])$")
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    re.compile(r"(?i)\b(?:client_secret|access_token|refresh_token|password)\b\s*[:=]\s*['\"][^'\"]+['\"]"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def valid_sha256(value: str) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def contains_secret_material(value: Any) -> bool:
    if isinstance(value, dict):
        return any(contains_secret_material(key) or contains_secret_material(item) for key, item in value.items())
    if isinstance(value, (list, tuple, set)):
        return any(contains_secret_material(item) for item in value)
    if not isinstance(value, str):
        return False
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)


@dataclass(frozen=True)
class AuthorityRequirement:
    domain: str
    stage: str
    provider: str
    purpose: str
    required_scopes: tuple[str, ...]
    required_proofs: tuple[str, ...]
    max_age_seconds: int
    owner_reserved_actions: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class AuthorityEvidence:
    evidence_id: str
    domain: str
    provider: str
    provider_native: bool
    state: str
    locator: str
    observed_at: str
    captured_at: str
    scopes: tuple[str, ...]
    proofs: dict[str, bool]
    content_sha256: str
    owner_confirmations: tuple[str, ...] = ()
    evidence: dict[str, Any] = field(default_factory=dict)


class AuthorityAcquisitionFabric:
    """Fail-closed provider-authority acquisition and handoff controller.

    The fabric packages exact authority requirements, verifies provider-native
    evidence, preserves owner-reserved decisions, and never treats alternate
    provider conformance as authority for a blocked provider domain.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.handoff_root = self.root / "handoffs"
        self.handoff_root.mkdir(parents=True, exist_ok=True)
        self.ledger_file = self.root / "provider-authority-acquisition-ledger.jsonl"
        self.state_file = self.root / "provider-authority-acquisition-state.json"
        self.requirements: dict[str, AuthorityRequirement] = {}
        self.decisions: dict[str, dict[str, Any]] = {}
        self.authority_by_domain: dict[str, list[str]] = {}
        self.conformance: dict[str, list[dict[str, Any]]] = {}
        self.handoffs: dict[str, dict[str, Any]] = {}
        self._replay()

    def register_requirement(self, requirement: AuthorityRequirement) -> dict[str, Any]:
        if not requirement.domain.strip() or not requirement.provider.strip():
            raise ValueError("domain and provider are required")
        if not STAGE_PATTERN.fullmatch(requirement.stage):
            raise ValueError("invalid commercial stage")
        if requirement.max_age_seconds < 1:
            raise ValueError("max_age_seconds must be positive")
        if not requirement.required_scopes or not requirement.required_proofs:
            raise ValueError("scope and proof contracts are required")
        if contains_secret_material(asdict(requirement)):
            raise ValueError("secret material is forbidden")
        missing_dependencies = sorted(set(requirement.depends_on) - set(self.requirements))
        if missing_dependencies:
            raise ValueError("unregistered dependencies:" + ",".join(missing_dependencies))
        existing = self.requirements.get(requirement.domain)
        if existing and existing != requirement:
            raise ValueError("requirement conflict")
        self.requirements[requirement.domain] = requirement
        self.authority_by_domain.setdefault(requirement.domain, [])
        self.conformance.setdefault(requirement.domain, [])
        return asdict(requirement)

    def build_handoff(self, domain: str, base_state: str) -> dict[str, Any]:
        requirement = self.requirements[domain]
        handoff = {
            "domain": requirement.domain,
            "stage": requirement.stage,
            "provider": requirement.provider,
            "purpose": requirement.purpose,
            "depends_on": list(requirement.depends_on),
            "required_scopes": sorted(requirement.required_scopes),
            "required_proofs": sorted(requirement.required_proofs),
            "freshness_max_age_seconds": requirement.max_age_seconds,
            "owner_reserved_actions": sorted(requirement.owner_reserved_actions),
            "base_state": base_state,
            "secret_material_allowed": False,
            "admission_rule": (
                "Provider-native evidence must prove identity, exact scope, execution, target readback, health, "
                "persistence and rollback as required by this contract. Owner-reserved actions require explicit confirmation."
            ),
            "authority_granted": False,
        }
        handoff["handoff_sha256"] = digest(handoff)
        path = self.handoff_root / f"{domain}.json"
        path.write_text(json.dumps(handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.handoffs[domain] = handoff
        self._append("AUTHORITY_HANDOFF_PACKAGED", handoff)
        return handoff

    def record_conformance(
        self,
        domain: str,
        *,
        provider: str,
        provider_native: bool,
        scopes: tuple[str, ...],
        proofs: dict[str, bool],
    ) -> dict[str, Any]:
        requirement = self.requirements[domain]
        missing_scopes = sorted(set(requirement.required_scopes) - set(scopes))
        missing_proofs = sorted(name for name in requirement.required_proofs if not proofs.get(name))
        passed = provider_native and not missing_scopes and not missing_proofs
        result = {
            "domain": domain,
            "provider": provider,
            "provider_native": provider_native,
            "status": "CONFORMANCE_VERIFIED_NOT_AUTHORITY_GRANTED" if passed else "CONFORMANCE_FAILED",
            "contract_pass": passed,
            "missing_scopes": missing_scopes,
            "missing_proofs": missing_proofs,
            "authority_granted": False,
        }
        result["conformance_sha256"] = digest(result)
        self.conformance.setdefault(domain, []).append(result)
        self._append("ALTERNATE_PROVIDER_CONFORMANCE_EVALUATED", result)
        return result

    def admit_authority(self, evidence: AuthorityEvidence, *, now: str | None = None) -> dict[str, Any]:
        evidence_hash = digest(asdict(evidence))
        existing = self.decisions.get(evidence.evidence_id)
        if existing:
            if existing["evidence_hash"] == evidence_hash:
                return existing
            conflict = {
                "evidence_id": evidence.evidence_id,
                "domain": evidence.domain,
                "status": "REJECTED",
                "admitted": False,
                "reasons": ["EVIDENCE_ID_CONFLICT"],
                "evidence_hash": evidence_hash,
            }
            self._append("AUTHORITY_EVIDENCE_CONFLICT", conflict)
            return conflict

        reasons: list[str] = []
        requirement = self.requirements.get(evidence.domain)
        if requirement is None:
            reasons.append("UNKNOWN_AUTHORITY_DOMAIN")
        if not evidence.evidence_id.strip() or not evidence.locator.strip():
            reasons.append("MISSING_EVIDENCE_ID_OR_LOCATOR")
        if not evidence.provider_native:
            reasons.append("NON_PROVIDER_NATIVE_EVIDENCE")
        if evidence.state not in {"FRESH_VERIFIED", "FRESH_VERIFIED_READBACK", "FRESH_AUTHORITY_VERIFIED"}:
            reasons.append("INVALID_AUTHORITY_STATE")
        if not valid_sha256(evidence.content_sha256):
            reasons.append("INVALID_CONTENT_SHA256")
        if contains_secret_material(asdict(evidence)):
            reasons.append("SECRET_MATERIAL_FORBIDDEN")

        if requirement is not None:
            if evidence.provider != requirement.provider:
                reasons.append("PROVIDER_MISMATCH")
            missing_scopes = sorted(set(requirement.required_scopes) - set(evidence.scopes))
            if missing_scopes:
                reasons.append("MISSING_REQUIRED_SCOPE:" + ",".join(missing_scopes))
            missing_proofs = sorted(name for name in requirement.required_proofs if not evidence.proofs.get(name))
            if missing_proofs:
                reasons.append("MISSING_REQUIRED_PROOF:" + ",".join(missing_proofs))
            missing_owner = sorted(set(requirement.owner_reserved_actions) - set(evidence.owner_confirmations))
            if missing_owner:
                reasons.append("OWNER_CONFIRMATION_REQUIRED:" + ",".join(missing_owner))
            try:
                observed = parse_utc(evidence.observed_at)
                captured = parse_utc(evidence.captured_at)
                current = parse_utc(now or utc_now())
                if observed > captured:
                    reasons.append("OBSERVED_AFTER_CAPTURE")
                if captured > current:
                    reasons.append("CAPTURE_FROM_FUTURE")
                age_seconds = (current - observed).total_seconds()
                if age_seconds < 0:
                    reasons.append("OBSERVATION_FROM_FUTURE")
                if age_seconds > requirement.max_age_seconds:
                    reasons.append("AUTHORITY_EVIDENCE_STALE")
            except (TypeError, ValueError):
                reasons.append("INVALID_TIMESTAMP")

        admitted = not reasons
        decision = {
            "evidence_id": evidence.evidence_id,
            "domain": evidence.domain,
            "provider": evidence.provider,
            "state": evidence.state,
            "status": "ADMITTED" if admitted else "REJECTED",
            "admitted": admitted,
            "reasons": sorted(set(reasons)),
            "evidence_hash": evidence_hash,
            "locator": evidence.locator,
            "observed_at": evidence.observed_at,
            "captured_at": evidence.captured_at,
            "scopes": sorted(evidence.scopes),
            "proofs": evidence.proofs,
            "content_sha256": evidence.content_sha256,
            "owner_confirmations": sorted(evidence.owner_confirmations),
            "evidence": evidence.evidence,
        }
        self._append("AUTHORITY_EVIDENCE_EVALUATED", decision)
        return decision

    def project(self, base_authority: dict[str, str], *, now: str) -> dict[str, Any]:
        current = parse_utc(now)
        states = dict(base_authority)
        evidence: dict[str, dict[str, Any]] = {}
        for domain, requirement in self.requirements.items():
            states.setdefault(domain, "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY")
            candidates = [self.decisions[evidence_id] for evidence_id in self.authority_by_domain.get(domain, [])]
            if not candidates:
                continue
            latest = max(candidates, key=lambda row: parse_utc(row["observed_at"]))
            age_seconds = (current - parse_utc(latest["observed_at"])).total_seconds()
            fresh = 0 <= age_seconds <= requirement.max_age_seconds
            states[domain] = latest["state"] if fresh else "STALE_REVALIDATION_REQUIRED"
            evidence[domain] = {
                "evidence_id": latest["evidence_id"],
                "provider": latest["provider"],
                "locator": latest["locator"],
                "observed_at": latest["observed_at"],
                "age_seconds": age_seconds,
                "fresh": fresh,
                "content_sha256": latest["content_sha256"],
                "proofs": latest["proofs"],
            }

        owner_queue = [
            {
                "domain": domain,
                "stage": requirement.stage,
                "actions": sorted(requirement.owner_reserved_actions),
            }
            for domain, requirement in self.requirements.items()
            if requirement.owner_reserved_actions and states.get(domain) not in OPERATIONAL_STATES
        ]
        result = {
            "status": "PROVIDER_AUTHORITY_ACQUISITION_PACKAGE_VERIFIED_BLOCKED_DOMAINS_UNCHANGED",
            "states": states,
            "evidence": evidence,
            "operational_domains": sorted(domain for domain, state in states.items() if state in OPERATIONAL_STATES),
            "blocked_or_unverified_domains": sorted(
                domain for domain, state in states.items() if state not in OPERATIONAL_STATES
            ),
            "owner_decision_queue": owner_queue,
            "handoff_domains": sorted(self.handoffs),
            "alternate_provider_conformance_domains": sorted(
                domain for domain, rows in self.conformance.items() if any(row["contract_pass"] for row in rows)
            ),
            "external_gate_effect": "UNCHANGED",
            "owner_authority_effect": "UNCHANGED",
            "ledger_integrity": self.verify_ledger(),
            "projected_at": now,
        }
        result["projection_sha256"] = digest(result)
        return result

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
            "event_id": f"authority-acquisition-{len(events) + 1:08d}",
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
        return [json.loads(line) for line in self.ledger_file.read_text(encoding="utf-8").splitlines() if line]

    def _apply(self, event: dict[str, Any]) -> None:
        kind = event["event_type"]
        payload = event["payload"]
        if kind == "AUTHORITY_HANDOFF_PACKAGED":
            self.handoffs[payload["domain"]] = payload
        elif kind == "ALTERNATE_PROVIDER_CONFORMANCE_EVALUATED":
            rows = self.conformance.setdefault(payload["domain"], [])
            if payload not in rows:
                rows.append(payload)
        elif kind == "AUTHORITY_EVIDENCE_EVALUATED":
            self.decisions[payload["evidence_id"]] = payload
            if payload.get("admitted"):
                ids = self.authority_by_domain.setdefault(payload["domain"], [])
                if payload["evidence_id"] not in ids:
                    ids.append(payload["evidence_id"])

    def _replay(self) -> None:
        for event in self._events():
            self._apply(event)
        self._persist()

    def _persist(self) -> None:
        events = self._events()
        state = {
            "decisions": self.decisions,
            "authority_by_domain": self.authority_by_domain,
            "conformance": self.conformance,
            "handoffs": self.handoffs,
            "ledger_head": events[-1]["event_hash"] if events else "GENESIS",
        }
        self.state_file.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
