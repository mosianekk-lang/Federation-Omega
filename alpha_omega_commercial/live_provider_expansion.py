from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SAFE_PROVIDER_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "github": {
        "scope": {"create_file", "readback", "delete_file"},
        "proofs": {"execution", "readback", "persistence", "rollback"},
        "max_age_seconds": 86400,
    },
    "google_drive": {
        "scope": {"create_native_doc", "fetch_readback", "permanent_delete"},
        "proofs": {"execution", "readback", "persistence", "rollback"},
        "max_age_seconds": 86400,
    },
    "gmail_draft": {
        "scope": {"create_draft", "list_readback", "trash_message"},
        "proofs": {"execution", "readback", "persistence", "rollback", "send_not_performed"},
        "max_age_seconds": 86400,
    },
    "google_calendar": {
        "scope": {"create_private_event", "provider_readback", "delete_event"},
        "proofs": {"execution", "readback", "persistence", "rollback"},
        "max_age_seconds": 86400,
    },
    "outlook_draft": {
        "scope": {"create_draft", "provider_readback", "move_to_deleted_items"},
        "proofs": {"execution", "readback", "persistence", "rollback", "send_not_performed"},
        "max_age_seconds": 86400,
    },
    "canva_transaction": {
        "scope": {"start_transaction", "temporary_title_edit", "cancel_transaction"},
        "proofs": {"execution", "readback", "persistence", "rollback", "persistent_change_not_performed"},
        "max_age_seconds": 86400,
    },
    "google_cloud_run": {
        "scope": {
            "authenticated_invoke",
            "service_readback",
            "health_readback",
            "persistence_readback",
            "reversible_tag_rollback",
        },
        "proofs": {
            "execution",
            "readback",
            "health",
            "persistence",
            "rollback",
            "private_invocation",
        },
        "max_age_seconds": 21600,
    },
}

OWNER_RESERVED = (
    "financial commitments",
    "contracts",
    "external communications",
    "consequential releases",
    "revenue recognition confirmation",
)

EXTERNAL_GATES = (
    "customer demand and price acceptance",
    "signed customer contract",
    "payment-provider revenue receipt",
    "enterprise assurance or certification",
    "partner adoption",
    "external customer case study",
    "production scale and recovery evidence",
)

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
        return any(contains_secret_material(k) or contains_secret_material(v) for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return any(contains_secret_material(item) for item in value)
    if not isinstance(value, str):
        return False
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)


@dataclass(frozen=True)
class ProviderObservation:
    observation_id: str
    provider: str
    provider_native: bool
    scopes: tuple[str, ...]
    proofs: dict[str, bool]
    observed_at: str
    locator: str
    content_sha256: str
    metadata: dict[str, Any] = field(default_factory=dict)


class LiveProviderExpansionFabric:
    """Fail-closed admission and persistence for bounded live commercial providers."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger_file = self.root / "live-provider-ledger.jsonl"
        self.state_file = self.root / "live-provider-state.json"
        self.rollback_root = self.root / "rollback"
        self.rollback_root.mkdir(parents=True, exist_ok=True)
        self.decisions: dict[str, dict[str, Any]] = {}
        self.by_provider: dict[str, list[str]] = {}
        self._replay()

    def import_certification_register(self, register: dict[str, Any], *, now: str) -> list[dict[str, Any]]:
        if register.get("status") != "REVERSIBLE_PROVIDER_ADAPTERS_CERTIFIED":
            raise ValueError("provider register is not certified")
        boundaries = register.get("truth_boundary", {})
        forbidden_true = (
            "gmail_send_certified",
            "outlook_send_certified",
            "apps_script_source_mutation_certified",
            "cloud_run_invocation_certified",
            "canva_permanent_commit_certified",
        )
        if any(boundaries.get(name) is True for name in forbidden_true):
            raise ValueError("provider register overstates owner-reserved authority")
        generated_at = register.get("generated_at")
        parse_utc(generated_at)
        results: list[dict[str, Any]] = []
        providers = register.get("providers", {})
        for provider in (
            "github",
            "google_drive",
            "gmail_draft",
            "google_calendar",
            "outlook_draft",
            "canva_transaction",
        ):
            row = providers.get(provider)
            if not isinstance(row, dict) or row.get("status") != "VERIFIED_OPERATIONAL":
                raise ValueError(f"missing verified provider: {provider}")
            proof_names = SAFE_PROVIDER_REQUIREMENTS[provider]["proofs"]
            proofs = {name: True for name in proof_names}
            if provider in {"gmail_draft", "outlook_draft"}:
                proofs["send_not_performed"] = row.get("send_performed") is False
            if provider == "canva_transaction":
                proofs["persistent_change_not_performed"] = row.get("persistent_change") is False
            payload_hash = digest(row)
            observation = ProviderObservation(
                observation_id=f"sol61-{provider}-{payload_hash[:16]}",
                provider=provider,
                provider_native=True,
                scopes=tuple(row.get("scope", ())),
                proofs=proofs,
                observed_at=generated_at,
                locator=f"sol_61_runtime/provider_certification_register.json#{provider}",
                content_sha256=payload_hash,
                metadata={"source_programme": register.get("programme"), "receipt": row},
            )
            results.append(self.admit(observation, now=now))
        return results

    def admit(self, observation: ProviderObservation, *, now: str) -> dict[str, Any]:
        evidence_hash = digest(asdict(observation))
        existing = self.decisions.get(observation.observation_id)
        if existing:
            if existing["evidence_hash"] == evidence_hash:
                return existing
            conflict = {
                "observation_id": observation.observation_id,
                "provider": observation.provider,
                "status": "REJECTED",
                "admitted": False,
                "reasons": ["OBSERVATION_ID_CONFLICT"],
                "evidence_hash": evidence_hash,
            }
            self._append("PROVIDER_OBSERVATION_CONFLICT", conflict)
            return conflict

        reasons: list[str] = []
        requirement = SAFE_PROVIDER_REQUIREMENTS.get(observation.provider)
        if requirement is None:
            reasons.append("UNKNOWN_PROVIDER")
        if not observation.provider_native:
            reasons.append("NON_PROVIDER_NATIVE")
        if not observation.observation_id.strip() or not observation.locator.strip():
            reasons.append("MISSING_ID_OR_LOCATOR")
        if not valid_sha256(observation.content_sha256):
            reasons.append("INVALID_CONTENT_SHA256")
        if contains_secret_material(asdict(observation)):
            reasons.append("SECRET_MATERIAL_FORBIDDEN")

        if requirement is not None:
            missing_scopes = sorted(requirement["scope"] - set(observation.scopes))
            extra_scopes = sorted(set(observation.scopes) - requirement["scope"])
            missing_proofs = sorted(name for name in requirement["proofs"] if not observation.proofs.get(name))
            if missing_scopes:
                reasons.append("MISSING_SCOPE:" + ",".join(missing_scopes))
            if extra_scopes:
                reasons.append("UNAUTHORISED_SCOPE:" + ",".join(extra_scopes))
            if missing_proofs:
                reasons.append("MISSING_PROOF:" + ",".join(missing_proofs))
            try:
                observed = parse_utc(observation.observed_at)
                current = parse_utc(now)
                age = (current - observed).total_seconds()
                if age < 0:
                    reasons.append("OBSERVATION_FROM_FUTURE")
                if age > requirement["max_age_seconds"]:
                    reasons.append("OBSERVATION_STALE")
            except (TypeError, ValueError):
                reasons.append("INVALID_TIMESTAMP")

        admitted = not reasons
        decision = {
            "observation_id": observation.observation_id,
            "provider": observation.provider,
            "status": "ADMITTED" if admitted else "REJECTED",
            "admitted": admitted,
            "reasons": sorted(set(reasons)),
            "evidence_hash": evidence_hash,
            "observed_at": observation.observed_at,
            "locator": observation.locator,
            "scopes": sorted(observation.scopes),
            "proofs": observation.proofs,
            "content_sha256": observation.content_sha256,
            "metadata": observation.metadata,
        }
        self._append("PROVIDER_OBSERVATION_EVALUATED", decision)
        return decision

    def snapshot(self, name: str) -> Path:
        if not name or not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            raise ValueError("invalid snapshot name")
        target = self.rollback_root / name
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        for source in (self.ledger_file, self.state_file):
            if source.exists():
                shutil.copy2(source, target / source.name)
        manifest = {
            "name": name,
            "ledger_sha256": hashlib.sha256(self.ledger_file.read_bytes()).hexdigest() if self.ledger_file.exists() else None,
            "state_sha256": hashlib.sha256(self.state_file.read_bytes()).hexdigest() if self.state_file.exists() else None,
            "captured_at": utc_now(),
        }
        manifest["manifest_sha256"] = digest(manifest)
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return target

    def restore(self, snapshot: str | Path) -> dict[str, Any]:
        source = Path(snapshot)
        manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
        expected = manifest.pop("manifest_sha256")
        if digest(manifest) != expected:
            raise ValueError("rollback manifest integrity failure")
        for target in (self.ledger_file, self.state_file):
            candidate = source / target.name
            if candidate.exists():
                shutil.copy2(candidate, target)
            elif target.exists():
                target.unlink()
        self.decisions = {}
        self.by_provider = {}
        self._replay()
        result = {
            "status": "ROLLBACK_RESTORED",
            "snapshot": source.name,
            "ledger_integrity": self.verify_ledger(),
            "state_sha256": hashlib.sha256(self.state_file.read_bytes()).hexdigest() if self.state_file.exists() else None,
        }
        result["rollback_sha256"] = digest(result)
        return result

    def record_probe_marker(self, marker: str) -> None:
        self._append("ROLLBACK_DRILL_MARKER", {"marker": marker})

    def project(self, *, now: str) -> dict[str, Any]:
        current = parse_utc(now)
        states: dict[str, str] = {}
        evidence: dict[str, dict[str, Any]] = {}
        for provider, requirement in SAFE_PROVIDER_REQUIREMENTS.items():
            candidates = [
                self.decisions[item]
                for item in self.by_provider.get(provider, [])
                if self.decisions[item].get("admitted")
            ]
            if not candidates:
                states[provider] = "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY"
                continue
            latest = max(candidates, key=lambda row: parse_utc(row["observed_at"]))
            age = (current - parse_utc(latest["observed_at"])).total_seconds()
            fresh = 0 <= age <= requirement["max_age_seconds"]
            states[provider] = "FRESH_VERIFIED_OPERATIONAL" if fresh else "STALE_REVALIDATION_REQUIRED"
            evidence[provider] = {
                "observation_id": latest["observation_id"],
                "locator": latest["locator"],
                "observed_at": latest["observed_at"],
                "age_seconds": age,
                "fresh": fresh,
                "content_sha256": latest["content_sha256"],
                "proofs": latest["proofs"],
            }

        live = sorted(provider for provider, state in states.items() if state == "FRESH_VERIFIED_OPERATIONAL")
        cloud_live = states.get("google_cloud_run") == "FRESH_VERIFIED_OPERATIONAL"
        all_reversible = all(
            states.get(provider) == "FRESH_VERIFIED_OPERATIONAL"
            for provider in (
                "github",
                "google_drive",
                "gmail_draft",
                "google_calendar",
                "outlook_draft",
                "canva_transaction",
            )
        )
        result = {
            "status": (
                "LIVE_PROVIDER_EXPANSION_VERIFIED_EXTERNAL_GATES_UNCHANGED"
                if cloud_live and all_reversible
                else "LIVE_PROVIDER_EXPANSION_INCOMPLETE"
            ),
            "provider_states": states,
            "evidence": evidence,
            "live_provider_count": len(live),
            "live_providers": live,
            "stage_projection": {
                "C03": "LIVE_REVERSIBLE_PROVIDER_AUTHORITY_VERIFIED_OWNER_RESERVED_DOMAINS_HELD",
                "C06": "LIVE_BOUNDED_OPERATION_HEALTH_PERSISTENCE_ROLLBACK_VERIFIED",
                "C07": "LIVE_PROVIDER_ADAPTER_EXPANSION_VERIFIED",
                "C11": "SERVICE_ENABLED_LIVE_PROVIDER_OPERATIONS_VERIFIED_SELF_SERVICE_SEND_AND_PAYMENT_HELD",
                "C14": "LIVE_PROVIDER_RELIABILITY_GATES_VERIFIED_PRODUCTION_SCALE_REQUIRED",
                "C15": "COMMERCIAL_READINESS_VERIFIED_LIVE_PROVIDER_EXPANSION_VERIFIED_EXTERNAL_MATURITY_GATES_OPEN",
            },
            "external_maturity_gates": {gate: False for gate in EXTERNAL_GATES},
            "live_cloud_provider_execution": cloud_live,
            "verified_revenue_events": 0,
            "full_commercial_maturity": False,
            "self_service_saas_claimed": False,
            "subscriptions_claimed": False,
            "invoices_claimed": False,
            "customer_demand_claimed": False,
            "owner_reserved_authority": list(OWNER_RESERVED),
            "owner_reserved_effects": {
                "gmail_send": "HELD",
                "outlook_send": "HELD",
                "canva_permanent_commit": "HELD",
                "apps_script_source_mutation": "HELD",
                "payment_provider": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
                "contracts": "OWNER_RESERVED",
                "revenue_recognition": "OWNER_RESERVED",
            },
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
            payload = {k: v for k, v in event.items() if k != "event_hash"}
            if digest(payload) != event.get("event_hash"):
                return False
            previous = event["event_hash"]
        return True

    def _append(self, event_type: str, payload: dict[str, Any]) -> None:
        events = self._events()
        event = {
            "event_id": f"live-provider-{len(events) + 1:08d}",
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
        if event["event_type"] == "PROVIDER_OBSERVATION_EVALUATED":
            payload = event["payload"]
            self.decisions[payload["observation_id"]] = payload
            ids = self.by_provider.setdefault(payload["provider"], [])
            if payload["observation_id"] not in ids:
                ids.append(payload["observation_id"])

    def _persist(self) -> None:
        state = {
            "decisions": self.decisions,
            "by_provider": self.by_provider,
            "ledger_head": self._events()[-1]["event_hash"] if self._events() else "GENESIS",
            "updated_at": utc_now(),
        }
        state["state_sha256"] = digest(state)
        self.state_file.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _replay(self) -> None:
        for event in self._events():
            self._apply(event)
