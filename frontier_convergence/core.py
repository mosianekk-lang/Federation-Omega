"""Provider-neutral Frontier Convergence primitives.

This module complements Formation Omega MCE/FCI, SOVARA and CFBE. It does not
grant credentials, provider authority, deployment, canonical truth or spend.
All provider/effect promotion remains proof- and authority-gated.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import sqlite3
import threading
from typing import Any, Iterable, Mapping, Sequence


SECRET_KEYS = frozenset({
    "password", "passwd", "api_key", "apikey", "access_token", "refresh_token",
    "client_secret", "secret", "secret_value", "authorization", "cookie", "cookies",
    "private_key", "bearer_token",
})


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def digest(value: Any) -> str:
    payload = value if isinstance(value, str) else canonical_json(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(v).strip() for v in values if str(v).strip()}))


def assert_public_safe(value: Any, *, path: str = "payload") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).strip().casefold()
            if normalized in SECRET_KEYS:
                raise ValueError(f"SECRET_FIELD_PROHIBITED:{path}.{key}")
            assert_public_safe(item, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for idx, item in enumerate(value):
            assert_public_safe(item, path=f"{path}[{idx}]")


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


class ActionMode(str, Enum):
    READ = "READ"
    MUTATE = "MUTATE"


class ProofLevel(str, Enum):
    PLANNED = "PLANNED"
    SOURCE_ONLY = "SOURCE_ONLY"
    DETERMINISTIC = "DETERMINISTIC"
    SHADOW = "SHADOW"
    CANARY = "CANARY"
    PROVIDER_LIVE = "PROVIDER_LIVE"


class ConvergenceStage(str, Enum):
    CANDIDATE = "CANDIDATE"
    SHADOW = "SHADOW"
    CANARY = "CANARY"
    ADOPTED = "ADOPTED"
    HELD = "HELD"
    REJECTED = "REJECTED"


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"
    KILLED = "KILLED"


class AssetKind(str, Enum):
    AGENT = "AGENT"
    MODEL = "MODEL"
    TOOL = "TOOL"
    MCP_SERVER = "MCP_SERVER"
    RUNTIME = "RUNTIME"
    DATASET = "DATASET"
    CREDENTIAL_REFERENCE = "CREDENTIAL_REFERENCE"
    PROMPT = "PROMPT"
    APPLICATION = "APPLICATION"


@dataclass(frozen=True)
class FrontierSignal:
    signal_id: str
    source_organization: str
    capability_class: str
    mechanism: str
    evidence_refs: tuple[str, ...]
    observed_at: str
    public_evidence_only: bool = True
    source_freshness_days: int = 0

    @classmethod
    def create(
        cls,
        *,
        source_organization: str,
        capability_class: str,
        mechanism: str,
        evidence_refs: Iterable[str],
        observed_at: str | None = None,
        source_freshness_days: int = 0,
    ) -> "FrontierSignal":
        body = {
            "source_organization": " ".join(source_organization.split()),
            "capability_class": " ".join(capability_class.split()),
            "mechanism": " ".join(mechanism.split()),
            "evidence_refs": clean(evidence_refs),
            "observed_at": observed_at or utc_now(),
            "public_evidence_only": True,
            "source_freshness_days": max(0, int(source_freshness_days)),
        }
        if not body["source_organization"] or not body["capability_class"] or not body["mechanism"]:
            raise ValueError("FRONTIER_SIGNAL_FIELDS_REQUIRED")
        if not body["evidence_refs"]:
            raise ValueError("FRONTIER_SIGNAL_EVIDENCE_REQUIRED")
        assert_public_safe(body)
        return cls(signal_id=f"FC-SIG-{digest(body)[:24].upper()}", **body)


@dataclass(frozen=True)
class ConvergenceCandidate:
    candidate_id: str
    capability_class: str
    mechanism: str
    source_signal_ids: tuple[str, ...]
    incumbent_capability_id: str
    architecture: str
    provider_dependencies: tuple[str, ...] = ()
    expected_metric_names: tuple[str, ...] = ()
    authority_ceiling: str = "A1_INTERNAL"
    provider_neutral_core: bool = True
    rollback_required: bool = True

    @classmethod
    def form(
        cls,
        *,
        signals: Sequence[FrontierSignal],
        incumbent_capability_id: str,
        architecture: str,
        provider_dependencies: Iterable[str] = (),
        expected_metric_names: Iterable[str] = (),
        authority_ceiling: str = "A1_INTERNAL",
    ) -> "ConvergenceCandidate":
        if not signals:
            raise ValueError("AT_LEAST_ONE_FRONTIER_SIGNAL_REQUIRED")
        classes = {s.capability_class for s in signals}
        if len(classes) != 1:
            raise ValueError("CANDIDATE_CAPABILITY_CLASS_MISMATCH")
        mechanisms = tuple(sorted({s.mechanism for s in signals}))
        body = {
            "capability_class": next(iter(classes)),
            "mechanism": " + ".join(mechanisms),
            "source_signal_ids": tuple(sorted(s.signal_id for s in signals)),
            "incumbent_capability_id": incumbent_capability_id.strip(),
            "architecture": " ".join(architecture.split()),
            "provider_dependencies": clean(provider_dependencies),
            "expected_metric_names": clean(expected_metric_names),
            "authority_ceiling": authority_ceiling.strip() or "A1_INTERNAL",
            "provider_neutral_core": True,
            "rollback_required": True,
        }
        if not body["incumbent_capability_id"] or not body["architecture"]:
            raise ValueError("CANDIDATE_INCUMBENT_AND_ARCHITECTURE_REQUIRED")
        assert_public_safe(body)
        return cls(candidate_id=f"FC-CAND-{digest(body)[:24].upper()}", **body)


@dataclass(frozen=True)
class ExperimentIdentity:
    experiment_id: str
    fingerprint: str
    implementation_sha256: str
    source_sha256: str
    input_sha256: str
    environment_sha256: str
    observation_window: str
    parameters_sha256: str
    cost_latency_sha256: str
    controls_sha256: str
    authority_sha256: str


class ExperimentIdentityCompiler:
    """Deterministic comparability contract; different fingerprints are not peers."""

    @staticmethod
    def compile(
        *,
        implementation_sha256: str,
        source_sha256: str,
        inputs: Any,
        environment: Any,
        observation_window: str,
        parameters: Any,
        cost_latency_context: Any,
        controls: Any,
        authority: Any,
    ) -> ExperimentIdentity:
        body = {
            "implementation_sha256": implementation_sha256.strip(),
            "source_sha256": source_sha256.strip(),
            "input_sha256": digest(inputs),
            "environment_sha256": digest(environment),
            "observation_window": observation_window.strip(),
            "parameters_sha256": digest(parameters),
            "cost_latency_sha256": digest(cost_latency_context),
            "controls_sha256": digest(controls),
            "authority_sha256": digest(authority),
        }
        if not body["implementation_sha256"] or not body["source_sha256"] or not body["observation_window"]:
            raise ValueError("EXPERIMENT_IDENTITY_FIELDS_REQUIRED")
        fp = digest(body)
        return ExperimentIdentity(
            experiment_id=f"FC-EXP-{fp[:24].upper()}",
            fingerprint=fp,
            **body,
        )


@dataclass(frozen=True)
class CapabilityLease:
    lease_id: str
    capability_id: str
    receiver_id: str
    proof_level: ProofLevel
    proven_at: str
    expires_at: str
    evidence_refs: tuple[str, ...]
    cross_receiver_inheritance: bool = False
    revoked: bool = False

    @classmethod
    def issue(
        cls,
        *,
        capability_id: str,
        receiver_id: str,
        proof_level: ProofLevel,
        proven_at: str,
        expires_at: str,
        evidence_refs: Iterable[str],
    ) -> "CapabilityLease":
        if parse_time(expires_at) <= parse_time(proven_at):
            raise ValueError("CAPABILITY_LEASE_EXPIRY_INVALID")
        refs = clean(evidence_refs)
        if ProofLevel(proof_level) != ProofLevel.PLANNED and not refs:
            raise ValueError("CAPABILITY_LEASE_PROOF_REQUIRED")
        body = {
            "capability_id": capability_id.strip(),
            "receiver_id": receiver_id.strip(),
            "proof_level": ProofLevel(proof_level).value,
            "proven_at": proven_at,
            "expires_at": expires_at,
            "evidence_refs": refs,
            "cross_receiver_inheritance": False,
        }
        if not body["capability_id"] or not body["receiver_id"]:
            raise ValueError("CAPABILITY_LEASE_FIELDS_REQUIRED")
        return cls(
            lease_id=f"FC-LEASE-{digest(body)[:24].upper()}",
            proof_level=ProofLevel(proof_level),
            revoked=False,
            **{k: v for k, v in body.items() if k != "proof_level"},
        )

    def valid_at(self, at: str) -> bool:
        if self.revoked:
            return False
        instant = parse_time(at)
        return parse_time(self.proven_at) <= instant < parse_time(self.expires_at)


@dataclass(frozen=True)
class AgentIdentityContract:
    identity_id: str
    agent_id: str
    trust_domain: str
    provider: str
    subject_ref: str
    authority_ceiling: str
    allowed_actions: tuple[str, ...]
    allowed_resource_prefixes: tuple[str, ...]
    issued_at: str
    expires_at: str
    evidence_refs: tuple[str, ...]
    delegated_from: str | None = None
    revoked: bool = False

    @classmethod
    def issue(
        cls,
        *,
        agent_id: str,
        trust_domain: str,
        provider: str,
        subject_ref: str,
        authority_ceiling: str,
        allowed_actions: Iterable[str],
        allowed_resource_prefixes: Iterable[str],
        issued_at: str,
        expires_at: str,
        evidence_refs: Iterable[str],
        delegated_from: str | None = None,
    ) -> "AgentIdentityContract":
        if parse_time(expires_at) <= parse_time(issued_at):
            raise ValueError("AGENT_IDENTITY_EXPIRY_INVALID")
        refs = clean(evidence_refs)
        if not refs:
            raise ValueError("AGENT_IDENTITY_EVIDENCE_REQUIRED")
        body = {
            "agent_id": agent_id.strip(),
            "trust_domain": trust_domain.strip(),
            "provider": provider.strip(),
            "subject_ref": subject_ref.strip(),
            "authority_ceiling": authority_ceiling.strip(),
            "allowed_actions": clean(allowed_actions),
            "allowed_resource_prefixes": clean(allowed_resource_prefixes),
            "issued_at": issued_at,
            "expires_at": expires_at,
            "evidence_refs": refs,
            "delegated_from": delegated_from,
        }
        if any(not body[k] for k in ("agent_id", "trust_domain", "provider", "subject_ref", "authority_ceiling")):
            raise ValueError("AGENT_IDENTITY_FIELDS_REQUIRED")
        assert_public_safe(body)
        return cls(identity_id=f"FC-ID-{digest(body)[:24].upper()}", revoked=False, **body)

    def authorizes(self, *, action: str, resource: str, at: str) -> bool:
        if self.revoked or not (parse_time(self.issued_at) <= parse_time(at) < parse_time(self.expires_at)):
            return False
        action_ok = action in self.allowed_actions
        resource_ok = any(resource.startswith(prefix) for prefix in self.allowed_resource_prefixes)
        return action_ok and resource_ok


@dataclass(frozen=True)
class PrivacyEnvelope:
    envelope_id: str
    data_classification: str
    permitted_fields: tuple[str, ...]
    prohibited_fields: tuple[str, ...]
    retention_hours: int
    raw_evidence_allowed: bool
    provider_reuse_allowed: bool

    @classmethod
    def create(
        cls,
        *,
        data_classification: str,
        permitted_fields: Iterable[str],
        prohibited_fields: Iterable[str] = (),
        retention_hours: int = 24,
        raw_evidence_allowed: bool = False,
        provider_reuse_allowed: bool = False,
    ) -> "PrivacyEnvelope":
        body = {
            "data_classification": data_classification.strip(),
            "permitted_fields": clean(permitted_fields),
            "prohibited_fields": clean(prohibited_fields),
            "retention_hours": max(1, int(retention_hours)),
            "raw_evidence_allowed": bool(raw_evidence_allowed),
            "provider_reuse_allowed": bool(provider_reuse_allowed),
        }
        if not body["data_classification"]:
            raise ValueError("PRIVACY_CLASSIFICATION_REQUIRED")
        return cls(envelope_id=f"FC-PRIV-{digest(body)[:24].upper()}", **body)

    def filter_payload(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        result = {}
        for key, value in payload.items():
            if key in self.prohibited_fields:
                continue
            if self.permitted_fields and key not in self.permitted_fields:
                continue
            result[key] = value
        assert_public_safe(result)
        return result


@dataclass(frozen=True)
class BudgetLease:
    budget_id: str
    currency: str
    max_cost: float
    spent: float
    expires_at: str
    provider_allowlist: tuple[str, ...]
    owner_approved: bool

    @classmethod
    def create(
        cls,
        *,
        currency: str,
        max_cost: float,
        expires_at: str,
        provider_allowlist: Iterable[str] = (),
        owner_approved: bool = False,
    ) -> "BudgetLease":
        max_cost = float(max_cost)
        if max_cost < 0:
            raise ValueError("NEGATIVE_BUDGET_PROHIBITED")
        body = {
            "currency": currency.strip(),
            "max_cost": max_cost,
            "expires_at": expires_at,
            "provider_allowlist": clean(provider_allowlist),
            "owner_approved": bool(owner_approved),
        }
        if not body["currency"]:
            raise ValueError("BUDGET_CURRENCY_REQUIRED")
        return cls(budget_id=f"FC-BUDGET-{digest(body)[:24].upper()}", spent=0.0, **body)

    def can_spend(self, *, amount: float, provider: str, at: str) -> bool:
        amount = float(amount)
        if amount < 0 or parse_time(at) >= parse_time(self.expires_at):
            return False
        if self.provider_allowlist and provider not in self.provider_allowlist:
            return False
        if self.max_cost > 0 and not self.owner_approved:
            return False
        return self.spent + amount <= self.max_cost


@dataclass(frozen=True)
class SchemaCompatibilityHandshake:
    contract_name: str
    producer_version: str
    consumer_versions: tuple[str, ...]
    required_fields: tuple[str, ...]
    schema_hash: str

    @classmethod
    def create(
        cls,
        *,
        contract_name: str,
        producer_version: str,
        consumer_versions: Iterable[str],
        required_fields: Iterable[str],
    ) -> "SchemaCompatibilityHandshake":
        body = {
            "contract_name": contract_name.strip(),
            "producer_version": producer_version.strip(),
            "consumer_versions": clean(consumer_versions),
            "required_fields": clean(required_fields),
        }
        if not body["contract_name"] or not body["producer_version"] or not body["consumer_versions"]:
            raise ValueError("SCHEMA_HANDSHAKE_FIELDS_REQUIRED")
        return cls(schema_hash=digest(body), **body)

    def compatible(self, consumer_version: str, payload: Mapping[str, Any]) -> bool:
        return consumer_version in self.consumer_versions and all(field in payload for field in self.required_fields)


@dataclass(frozen=True)
class AuthorizationRequest:
    principal_id: str
    action: str
    resource: str
    context: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason: str
    decision_sha256: str


class PolicyDecisionPoint:
    """Default-deny PARC-style authorization decision point."""

    def decide(
        self,
        request: AuthorizationRequest,
        *,
        identity: AgentIdentityContract,
        at: str,
        effect_mode: ActionMode,
        owner_gate_satisfied: bool = False,
    ) -> AuthorizationDecision:
        reasons = []
        if request.principal_id != identity.identity_id:
            reasons.append("PRINCIPAL_IDENTITY_MISMATCH")
        if not identity.authorizes(action=request.action, resource=request.resource, at=at):
            reasons.append("IDENTITY_SCOPE_DENIED")
        if effect_mode == ActionMode.MUTATE and not owner_gate_satisfied and identity.authority_ceiling in {"A0_OBSERVE", "A1_INTERNAL", "A1"}:
            reasons.append("MUTATION_ABOVE_IDENTITY_CEILING")
        body = {
            "request": {
                "principal_id": request.principal_id,
                "action": request.action,
                "resource": request.resource,
                "context": dict(request.context),
            },
            "identity_id": identity.identity_id,
            "at": at,
            "effect_mode": ActionMode(effect_mode).value,
            "owner_gate_satisfied": bool(owner_gate_satisfied),
            "reasons": sorted(set(reasons)),
        }
        assert_public_safe(body)
        return AuthorizationDecision(
            allowed=not reasons,
            reason="ALLOW" if not reasons else "|".join(sorted(set(reasons))),
            decision_sha256=digest(body),
        )


@dataclass(frozen=True)
class EffectContract:
    effect_id: str
    mission_id: str
    target: str
    action: str
    parameters: Mapping[str, Any]
    mode: ActionMode
    authority_class: str
    idempotency_key: str
    expected_semantic_result: str
    readback_plan: tuple[str, ...]
    rollback_plan: tuple[str, ...]
    privacy_envelope_id: str | None = None

    @classmethod
    def create(
        cls,
        *,
        mission_id: str,
        target: str,
        action: str,
        parameters: Mapping[str, Any],
        mode: ActionMode,
        authority_class: str,
        expected_semantic_result: str,
        readback_plan: Iterable[str],
        rollback_plan: Iterable[str],
        privacy_envelope_id: str | None = None,
    ) -> "EffectContract":
        params = json.loads(canonical_json(dict(parameters)))
        assert_public_safe(params)
        body = {
            "mission_id": mission_id.strip(),
            "target": target.strip(),
            "action": action.strip(),
            "parameters": params,
            "mode": ActionMode(mode).value,
            "authority_class": authority_class.strip(),
            "expected_semantic_result": " ".join(expected_semantic_result.split()),
            "readback_plan": clean(readback_plan),
            "rollback_plan": clean(rollback_plan),
            "privacy_envelope_id": privacy_envelope_id,
        }
        if any(not body[k] for k in ("mission_id", "target", "action", "authority_class", "expected_semantic_result")):
            raise ValueError("EFFECT_CONTRACT_FIELDS_REQUIRED")
        if not body["readback_plan"]:
            raise ValueError("EFFECT_READBACK_PLAN_REQUIRED")
        if ActionMode(mode) == ActionMode.MUTATE and not body["rollback_plan"]:
            raise ValueError("MUTATION_ROLLBACK_PLAN_REQUIRED")
        stable = digest(body)
        return cls(
            effect_id=f"FC-EFF-{stable[:24].upper()}",
            idempotency_key=f"FC-IDEMP-{stable[:32].upper()}",
            mode=ActionMode(mode),
            **{k: v for k, v in body.items() if k != "mode"},
        )


@dataclass(frozen=True)
class ScenarioBranch:
    branch_id: str
    mission_id: str
    base_state_sha256: str
    base_state: Mapping[str, Any]
    delta: Mapping[str, Any]
    created_at: str

    @classmethod
    def create(cls, *, mission_id: str, base_state: Mapping[str, Any], delta: Mapping[str, Any]) -> "ScenarioBranch":
        base = json.loads(canonical_json(dict(base_state)))
        patch = json.loads(canonical_json(dict(delta)))
        assert_public_safe(base)
        assert_public_safe(patch)
        body = {
            "mission_id": mission_id.strip(),
            "base_state_sha256": digest(base),
            "base_state": base,
            "delta": patch,
            "created_at": utc_now(),
        }
        if not body["mission_id"]:
            raise ValueError("SCENARIO_MISSION_REQUIRED")
        return cls(branch_id=f"FC-SCEN-{digest(body)[:24].upper()}", **body)

    def materialized(self) -> dict[str, Any]:
        result = json.loads(canonical_json(dict(self.base_state)))
        for key, value in self.delta.items():
            if value is None:
                result.pop(key, None)
            else:
                result[key] = value
        return result

    def diff(self) -> dict[str, Any]:
        target = self.materialized()
        keys = sorted(set(self.base_state) | set(target))
        return {
            key: {"before": self.base_state.get(key), "after": target.get(key)}
            for key in keys
            if self.base_state.get(key) != target.get(key)
        }


@dataclass(frozen=True)
class TraceEvent:
    trace_id: str
    mission_id: str
    run_id: str
    event_type: str
    provider: str | None
    model: str | None
    tool: str | None
    effect_id: str | None
    latency_ms: float | None
    input_tokens: int | None
    output_tokens: int | None
    cost: float | None
    currency: str | None
    semantic_state: str
    readback_state: str
    proof_refs: tuple[str, ...]
    occurred_at: str
    event_hash: str

    @classmethod
    def create(
        cls,
        *,
        mission_id: str,
        run_id: str,
        event_type: str,
        semantic_state: str,
        readback_state: str,
        proof_refs: Iterable[str] = (),
        provider: str | None = None,
        model: str | None = None,
        tool: str | None = None,
        effect_id: str | None = None,
        latency_ms: float | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cost: float | None = None,
        currency: str | None = None,
        occurred_at: str | None = None,
    ) -> "TraceEvent":
        body = {
            "mission_id": mission_id.strip(),
            "run_id": run_id.strip(),
            "event_type": event_type.strip(),
            "provider": provider,
            "model": model,
            "tool": tool,
            "effect_id": effect_id,
            "latency_ms": None if latency_ms is None else float(latency_ms),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": None if cost is None else float(cost),
            "currency": currency,
            "semantic_state": semantic_state.strip(),
            "readback_state": readback_state.strip(),
            "proof_refs": clean(proof_refs),
            "occurred_at": occurred_at or utc_now(),
        }
        assert_public_safe(body)
        if not body["mission_id"] or not body["run_id"] or not body["event_type"]:
            raise ValueError("TRACE_IDENTITY_FIELDS_REQUIRED")
        event_hash = digest(body)
        return cls(trace_id=f"FC-TRACE-{event_hash[:24].upper()}", event_hash=event_hash, **body)


@dataclass(frozen=True)
class AIAssetRecord:
    asset_id: str
    kind: AssetKind
    name: str
    provider: str
    owner_ref: str
    purpose: str
    lifecycle_state: str
    authority_ceiling: str
    credential_reference: str | None
    proof_level: ProofLevel
    proof_refs: tuple[str, ...]
    observed_at: str
    expires_at: str | None = None
    dependencies: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        kind: AssetKind,
        name: str,
        provider: str,
        owner_ref: str,
        purpose: str,
        lifecycle_state: str,
        authority_ceiling: str,
        proof_level: ProofLevel,
        proof_refs: Iterable[str] = (),
        credential_reference: str | None = None,
        observed_at: str | None = None,
        expires_at: str | None = None,
        dependencies: Iterable[str] = (),
    ) -> "AIAssetRecord":
        body = {
            "kind": AssetKind(kind).value,
            "name": name.strip(),
            "provider": provider.strip(),
            "owner_ref": owner_ref.strip(),
            "purpose": " ".join(purpose.split()),
            "lifecycle_state": lifecycle_state.strip(),
            "authority_ceiling": authority_ceiling.strip(),
            "credential_reference": credential_reference,
            "proof_level": ProofLevel(proof_level).value,
            "proof_refs": clean(proof_refs),
            "observed_at": observed_at or utc_now(),
            "expires_at": expires_at,
            "dependencies": clean(dependencies),
        }
        if any(not body[k] for k in ("name", "provider", "owner_ref", "purpose", "lifecycle_state", "authority_ceiling")):
            raise ValueError("ASSET_FIELDS_REQUIRED")
        if ProofLevel(proof_level) != ProofLevel.PLANNED and not body["proof_refs"]:
            raise ValueError("ASSET_PROOF_REQUIRED")
        assert_public_safe(body)
        asset_id = f"FC-ASSET-{digest(body)[:24].upper()}"
        return cls(
            asset_id=asset_id,
            kind=AssetKind(kind),
            proof_level=ProofLevel(proof_level),
            **{k: v for k, v in body.items() if k not in {"kind", "proof_level"}},
        )

    def fresh_at(self, at: str) -> bool:
        return self.expires_at is None or parse_time(at) < parse_time(self.expires_at)


class SQLiteConvergenceStore:
    """Small durable convergence store. Mission truth remains in the canonical Federation planes."""

    def __init__(self, path: str = ":memory:") -> None:
        self.path = path
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS events(
                event_id TEXT PRIMARY KEY,
                object_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                previous_hash TEXT,
                event_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS idempotency(
                idempotency_key TEXT PRIMARY KEY,
                payload_hash TEXT NOT NULL,
                state TEXT NOT NULL,
                result_json TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS assets(
                asset_id TEXT PRIMARY KEY,
                record_json TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                expires_at TEXT
            );
            CREATE TABLE IF NOT EXISTS signals(
                signal_id TEXT PRIMARY KEY,
                record_json TEXT NOT NULL
            );
            """
        )

    def append_event(self, *, object_id: str, event_type: str, payload: Mapping[str, Any], idempotency_key: str = "") -> dict[str, Any]:
        normalized = json.loads(canonical_json(dict(payload)))
        assert_public_safe(normalized)
        event_id = f"FC-EVT-{digest({'object_id': object_id, 'event_type': event_type, 'payload': normalized, 'idempotency_key': idempotency_key})[:28].upper()}"
        with self._lock:
            row = self.conn.execute("SELECT payload_json,event_hash FROM events WHERE event_id=?", (event_id,)).fetchone()
            if row:
                return {"event_id": event_id, "event_hash": row[1], "replayed": True}
            prev = self.conn.execute("SELECT event_hash FROM events ORDER BY rowid DESC LIMIT 1").fetchone()
            previous_hash = prev[0] if prev else None
            created_at = utc_now()
            event_hash = digest({
                "event_id": event_id,
                "object_id": object_id,
                "event_type": event_type,
                "payload": normalized,
                "previous_hash": previous_hash,
                "created_at": created_at,
            })
            self.conn.execute(
                "INSERT INTO events VALUES(?,?,?,?,?,?,?)",
                (event_id, object_id, event_type, canonical_json(normalized), previous_hash, event_hash, created_at),
            )
            return {"event_id": event_id, "event_hash": event_hash, "replayed": False}

    def verify_event_chain(self) -> bool:
        rows = self.conn.execute(
            "SELECT event_id,object_id,event_type,payload_json,previous_hash,event_hash,created_at FROM events ORDER BY rowid"
        ).fetchall()
        previous = None
        for event_id, object_id, event_type, payload_json, previous_hash, event_hash, created_at in rows:
            if previous_hash != previous:
                return False
            expected = digest({
                "event_id": event_id,
                "object_id": object_id,
                "event_type": event_type,
                "payload": json.loads(payload_json),
                "previous_hash": previous_hash,
                "created_at": created_at,
            })
            if expected != event_hash:
                return False
            previous = event_hash
        return True

    def reserve_idempotency(self, *, key: str, payload: Any) -> str:
        payload_hash = digest(payload)
        with self._lock:
            row = self.conn.execute("SELECT payload_hash,state FROM idempotency WHERE idempotency_key=?", (key,)).fetchone()
            if row:
                if row[0] != payload_hash:
                    raise ValueError("IDEMPOTENCY_KEY_PAYLOAD_CONFLICT")
                return "REPLAY" if row[1] == "COMPLETED" else "EXISTS"
            self.conn.execute(
                "INSERT INTO idempotency(idempotency_key,payload_hash,state,result_json,created_at) VALUES(?,?,?,'',?)",
                (key, payload_hash, "RESERVED", utc_now()),
            )
            return "RESERVED"

    def complete_idempotency(self, *, key: str, result: Any) -> None:
        with self._lock:
            changed = self.conn.execute(
                "UPDATE idempotency SET state='COMPLETED',result_json=? WHERE idempotency_key=?",
                (canonical_json(result), key),
            ).rowcount
            if not changed:
                raise KeyError("IDEMPOTENCY_KEY_NOT_RESERVED")

    def upsert_asset(self, asset: AIAssetRecord) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO assets(asset_id,record_json,observed_at,expires_at) VALUES(?,?,?,?) "
                "ON CONFLICT(asset_id) DO UPDATE SET record_json=excluded.record_json,observed_at=excluded.observed_at,expires_at=excluded.expires_at",
                (asset.asset_id, canonical_json(asdict(asset)), asset.observed_at, asset.expires_at),
            )

    def list_assets(self) -> tuple[dict[str, Any], ...]:
        rows = self.conn.execute("SELECT record_json FROM assets ORDER BY asset_id").fetchall()
        return tuple(json.loads(row[0]) for row in rows)

    def add_signal(self, signal: FrontierSignal) -> bool:
        with self._lock:
            before = self.conn.total_changes
            self.conn.execute(
                "INSERT OR IGNORE INTO signals(signal_id,record_json) VALUES(?,?)",
                (signal.signal_id, canonical_json(asdict(signal))),
            )
            return self.conn.total_changes > before


class ConnectorIntentGuard:
    """Guards READ-vs-MUTATE mismatches and duplicate effect attempts."""

    def __init__(self, store: SQLiteConvergenceStore) -> None:
        self.store = store

    def preflight(
        self,
        *,
        declared_mode: ActionMode,
        callable_mode: ActionMode,
        idempotency_key: str,
        payload: Any,
    ) -> str:
        if ActionMode(declared_mode) != ActionMode(callable_mode):
            raise ValueError(f"CONNECTOR_INTENT_MISMATCH:{declared_mode.value}->{callable_mode.value}")
        return self.store.reserve_idempotency(key=idempotency_key, payload=payload)


class AIControlTower:
    def __init__(self, store: SQLiteConvergenceStore) -> None:
        self.store = store

    def register(self, asset: AIAssetRecord) -> str:
        self.store.upsert_asset(asset)
        return asset.asset_id

    def inventory(self, *, at: str | None = None) -> tuple[dict[str, Any], ...]:
        at = at or utc_now()
        records = []
        for item in self.store.list_assets():
            expires_at = item.get("expires_at")
            item["fresh"] = expires_at is None or parse_time(at) < parse_time(expires_at)
            records.append(item)
        return tuple(records)


@dataclass(frozen=True)
class ValueReceipt:
    receipt_id: str
    candidate_id: str
    quality: float
    reliability: float
    latency_ms: float
    cost: float
    owner_burden: float
    outcome_value: float
    evidence_refs: tuple[str, ...]
    measured: bool = True

    @classmethod
    def create(
        cls,
        *,
        candidate_id: str,
        quality: float,
        reliability: float,
        latency_ms: float,
        cost: float,
        owner_burden: float,
        outcome_value: float,
        evidence_refs: Iterable[str],
        measured: bool = True,
    ) -> "ValueReceipt":
        refs = clean(evidence_refs)
        if measured and not refs:
            raise ValueError("MEASURED_VALUE_REQUIRES_EVIDENCE")
        body = {
            "candidate_id": candidate_id.strip(),
            "quality": float(quality),
            "reliability": float(reliability),
            "latency_ms": float(latency_ms),
            "cost": float(cost),
            "owner_burden": float(owner_burden),
            "outcome_value": float(outcome_value),
            "evidence_refs": refs,
            "measured": bool(measured),
        }
        if not body["candidate_id"]:
            raise ValueError("VALUE_CANDIDATE_REQUIRED")
        return cls(receipt_id=f"FC-VALUE-{digest(body)[:24].upper()}", **body)


class FinOpsParetoRouter:
    """Retains non-dominated options; never trades below an explicit quality floor."""

    @staticmethod
    def pareto_front(receipts: Sequence[ValueReceipt], *, minimum_quality: float, minimum_reliability: float) -> tuple[ValueReceipt, ...]:
        eligible = [
            r for r in receipts
            if r.measured and r.quality >= minimum_quality and r.reliability >= minimum_reliability
        ]
        front = []
        for candidate in eligible:
            dominated = False
            for other in eligible:
                if other.receipt_id == candidate.receipt_id:
                    continue
                no_worse = (
                    other.quality >= candidate.quality
                    and other.reliability >= candidate.reliability
                    and other.latency_ms <= candidate.latency_ms
                    and other.cost <= candidate.cost
                    and other.owner_burden <= candidate.owner_burden
                    and other.outcome_value >= candidate.outcome_value
                )
                strictly = (
                    other.quality > candidate.quality
                    or other.reliability > candidate.reliability
                    or other.latency_ms < candidate.latency_ms
                    or other.cost < candidate.cost
                    or other.owner_burden < candidate.owner_burden
                    or other.outcome_value > candidate.outcome_value
                )
                if no_worse and strictly:
                    dominated = True
                    break
            if not dominated:
                front.append(candidate)
        return tuple(sorted(front, key=lambda r: (r.cost, r.latency_ms, -r.outcome_value, r.candidate_id)))


@dataclass(frozen=True)
class ProvenanceAttestation:
    attestation_id: str
    subject_name: str
    subject_sha256: str
    source_uri: str
    source_revision: str
    builder_id: str
    materials: tuple[tuple[str, str], ...]
    build_parameters_sha256: str
    environment_sha256: str
    generated_at: str

    @classmethod
    def create(
        cls,
        *,
        subject_name: str,
        subject_sha256: str,
        source_uri: str,
        source_revision: str,
        builder_id: str,
        materials: Mapping[str, str],
        build_parameters: Any,
        environment: Any,
        generated_at: str | None = None,
    ) -> "ProvenanceAttestation":
        body = {
            "subject_name": subject_name.strip(),
            "subject_sha256": subject_sha256.strip(),
            "source_uri": source_uri.strip(),
            "source_revision": source_revision.strip(),
            "builder_id": builder_id.strip(),
            "materials": tuple(sorted((str(k), str(v)) for k, v in materials.items())),
            "build_parameters_sha256": digest(build_parameters),
            "environment_sha256": digest(environment),
            "generated_at": generated_at or utc_now(),
        }
        if any(not body[k] for k in ("subject_name", "subject_sha256", "source_uri", "source_revision", "builder_id")):
            raise ValueError("PROVENANCE_FIELDS_REQUIRED")
        assert_public_safe(body)
        return cls(attestation_id=f"FC-PROV-{digest(body)[:24].upper()}", **body)


@dataclass(frozen=True)
class RobustnessObservation:
    gate: str
    passed: bool
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class RobustnessVerdict:
    passed: bool
    missing_gates: tuple[str, ...]
    failed_gates: tuple[str, ...]
    verdict_sha256: str


class RobustnessCourt:
    MANDATORY_GATES = frozenset({
        "HOLDOUT",
        "PARAMETER_PERTURBATION",
        "ADVERSE_COST_OR_LATENCY",
        "CROSS_REGIME_OR_ENVIRONMENT",
        "SIMPLE_BENCHMARK",
        "INPUT_PROVENANCE",
    })

    @classmethod
    def evaluate(cls, observations: Iterable[RobustnessObservation]) -> RobustnessVerdict:
        items = tuple(observations)
        by_gate = {item.gate: item for item in items}
        missing = tuple(sorted(cls.MANDATORY_GATES - set(by_gate)))
        failed = tuple(sorted(gate for gate, item in by_gate.items() if gate in cls.MANDATORY_GATES and not item.passed))
        for item in items:
            if item.passed and not item.evidence_refs:
                raise ValueError(f"ROBUSTNESS_PASS_REQUIRES_EVIDENCE:{item.gate}")
        body = {
            "observations": [asdict(item) for item in items],
            "missing": missing,
            "failed": failed,
        }
        return RobustnessVerdict(
            passed=not missing and not failed,
            missing_gates=missing,
            failed_gates=failed,
            verdict_sha256=digest(body),
        )


@dataclass(frozen=True)
class AdmissionReceipt:
    candidate_id: str
    decision: str
    stage: ConvergenceStage
    blockers: tuple[str, ...]
    receipt_sha256: str


class FrontierConvergenceEngine:
    """Mechanism-harvest -> comparable experiment -> proof-bound admission."""

    def __init__(self, store: SQLiteConvergenceStore | None = None) -> None:
        self.store = store or SQLiteConvergenceStore()

    def observe(self, signal: FrontierSignal) -> dict[str, Any]:
        self.store.add_signal(signal)
        return self.store.append_event(
            object_id=signal.signal_id,
            event_type="FRONTIER_SIGNAL_OBSERVED",
            payload={"signal_id": signal.signal_id, "capability_class": signal.capability_class},
            idempotency_key=signal.signal_id,
        )

    def form_candidate(
        self,
        *,
        signals: Sequence[FrontierSignal],
        incumbent_capability_id: str,
        architecture: str,
        provider_dependencies: Iterable[str] = (),
        expected_metric_names: Iterable[str] = (),
    ) -> ConvergenceCandidate:
        candidate = ConvergenceCandidate.form(
            signals=signals,
            incumbent_capability_id=incumbent_capability_id,
            architecture=architecture,
            provider_dependencies=provider_dependencies,
            expected_metric_names=expected_metric_names,
        )
        self.store.append_event(
            object_id=candidate.candidate_id,
            event_type="INNOVATION_CANDIDATE",
            payload={"candidate_id": candidate.candidate_id, "source_signal_ids": candidate.source_signal_ids},
            idempotency_key=candidate.candidate_id,
        )
        return candidate

    def admission(
        self,
        *,
        candidate: ConvergenceCandidate,
        stage: ConvergenceStage,
        robustness: RobustnessVerdict,
        independent_quorum_outcome: str,
        value_receipt: ValueReceipt | None,
        rollback_proof_ref: str | None,
        provider_readback_refs: Iterable[str] = (),
        experiment_identity: ExperimentIdentity | None = None,
    ) -> AdmissionReceipt:
        blockers = []
        stage = ConvergenceStage(stage)
        if stage in {ConvergenceStage.CANARY, ConvergenceStage.ADOPTED} and not robustness.passed:
            blockers.append("ROBUSTNESS_COURT_NOT_PASSED")
        if stage == ConvergenceStage.ADOPTED:
            if independent_quorum_outcome != "ADMIT":
                blockers.append("INDEPENDENT_EVIDENCE_QUORUM_REQUIRED")
            if value_receipt is None or not value_receipt.measured:
                blockers.append("MEASURED_VALUE_REQUIRED")
            if not rollback_proof_ref:
                blockers.append("ROLLBACK_PROOF_REQUIRED")
            if candidate.provider_dependencies and not clean(provider_readback_refs):
                blockers.append("PROVIDER_READBACK_REQUIRED")
            if experiment_identity is None:
                blockers.append("EXPERIMENT_IDENTITY_REQUIRED")
        decision = "ADMIT" if not blockers else "HOLD"
        body = {
            "candidate_id": candidate.candidate_id,
            "stage": stage.value,
            "robustness": robustness.verdict_sha256,
            "independent_quorum_outcome": independent_quorum_outcome,
            "value_receipt": value_receipt.receipt_id if value_receipt else None,
            "rollback_proof_ref": rollback_proof_ref,
            "provider_readback_refs": clean(provider_readback_refs),
            "experiment_identity": experiment_identity.fingerprint if experiment_identity else None,
            "blockers": tuple(sorted(set(blockers))),
            "decision": decision,
        }
        receipt = AdmissionReceipt(
            candidate_id=candidate.candidate_id,
            decision=decision,
            stage=stage,
            blockers=tuple(sorted(set(blockers))),
            receipt_sha256=digest(body),
        )
        self.store.append_event(
            object_id=candidate.candidate_id,
            event_type="EXPERIMENT_RESULT",
            payload={**body, "receipt_sha256": receipt.receipt_sha256},
            idempotency_key=f"{candidate.candidate_id}:{stage.value}:{receipt.receipt_sha256}",
        )
        return receipt
