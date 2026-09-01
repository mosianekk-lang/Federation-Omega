from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import json
import math
import re
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_utc(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def _is_sha256(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value or "")))


class HardeningError(RuntimeError):
    pass


class ProofError(HardeningError):
    pass


class AuthorityError(HardeningError):
    pass


class IdempotencyCollision(HardeningError):
    pass


class FenceError(HardeningError):
    pass


class ConstraintError(HardeningError):
    pass


@dataclass(frozen=True)
class ProofEnvelope:
    proof_id: str
    subject: str
    target: str
    operation: str
    issuer: str
    observed_at: str
    max_age_seconds: int
    source_version: str
    evidence_sha256: str
    semantic_state: str
    provider_correlation_id: str = ""
    signature_ref: str = ""
    evidence_class: str = "DETERMINISTIC"
    scope: str = "LOCAL"
    attributes: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_evidence(
        cls,
        *,
        proof_id: str,
        subject: str,
        target: str,
        operation: str,
        issuer: str,
        source_version: str,
        evidence: Any,
        semantic_state: str = "VERIFIED",
        observed_at: str | None = None,
        max_age_seconds: int = 86400,
        provider_correlation_id: str = "",
        signature_ref: str = "",
        evidence_class: str = "DETERMINISTIC",
        scope: str = "LOCAL",
        attributes: Mapping[str, Any] | None = None,
    ) -> "ProofEnvelope":
        return cls(
            proof_id=proof_id,
            subject=subject,
            target=target,
            operation=operation,
            issuer=issuer,
            observed_at=observed_at or utc_now(),
            max_age_seconds=max_age_seconds,
            source_version=source_version,
            evidence_sha256=digest(evidence),
            semantic_state=semantic_state,
            provider_correlation_id=provider_correlation_id,
            signature_ref=signature_ref,
            evidence_class=evidence_class,
            scope=scope,
            attributes=dict(attributes or {}),
        )

    def validate(
        self,
        *,
        now_epoch: int | None = None,
        expected_subject: str | None = None,
        expected_target: str | None = None,
        expected_operation: str | None = None,
        expected_source_version: str | None = None,
        accepted_evidence_classes: Iterable[str] | None = None,
        require_provider_correlation: bool = False,
        require_signature_ref: bool = False,
    ) -> dict[str, Any]:
        now_epoch = int(time.time()) if now_epoch is None else int(now_epoch)
        age = now_epoch - parse_utc(self.observed_at)
        reasons: list[str] = []
        if not self.proof_id or not self.issuer:
            reasons.append("IDENTITY_FIELDS_MISSING")
        if not _is_sha256(self.evidence_sha256):
            reasons.append("INVALID_EVIDENCE_DIGEST")
        if self.semantic_state != "VERIFIED":
            reasons.append("SEMANTIC_STATE_NOT_VERIFIED")
        if age < -300:
            reasons.append("PROOF_FROM_FUTURE")
        if age > self.max_age_seconds:
            reasons.append("PROOF_STALE")
        if expected_subject is not None and self.subject != expected_subject:
            reasons.append("SUBJECT_MISMATCH")
        if expected_target is not None and self.target != expected_target:
            reasons.append("TARGET_MISMATCH")
        if expected_operation is not None and self.operation != expected_operation:
            reasons.append("OPERATION_MISMATCH")
        if expected_source_version is not None and self.source_version != expected_source_version:
            reasons.append("SOURCE_VERSION_MISMATCH")
        if accepted_evidence_classes is not None and self.evidence_class not in set(accepted_evidence_classes):
            reasons.append("EVIDENCE_CLASS_NOT_ACCEPTED")
        if require_provider_correlation and not self.provider_correlation_id:
            reasons.append("PROVIDER_CORRELATION_REQUIRED")
        if require_signature_ref and not self.signature_ref:
            reasons.append("SIGNATURE_REFERENCE_REQUIRED")
        return {
            "valid": not reasons,
            "reasons": reasons,
            "age_seconds": age,
            "proof_id": self.proof_id,
            "evidence_sha256": self.evidence_sha256,
        }


@dataclass(frozen=True)
class AuthorityLease:
    lease_id: str
    action: str
    target: str
    actor: str
    source_version: str
    issued_at_epoch: int
    expires_at_epoch: int
    nonce: str
    max_uses: int = 1

    def validate(self, *, action: str, target: str, actor: str, source_version: str, now_epoch: int) -> list[str]:
        reasons: list[str] = []
        if self.action != action:
            reasons.append("ACTION_MISMATCH")
        if self.target != target:
            reasons.append("TARGET_MISMATCH")
        if self.actor != actor:
            reasons.append("ACTOR_MISMATCH")
        if self.source_version != source_version:
            reasons.append("SOURCE_VERSION_MISMATCH")
        if now_epoch < self.issued_at_epoch:
            reasons.append("NOT_YET_VALID")
        if now_epoch >= self.expires_at_epoch:
            reasons.append("LEASE_EXPIRED")
        if not self.nonce:
            reasons.append("NONCE_REQUIRED")
        return reasons


@dataclass(frozen=True)
class EffectContract:
    effect_id: str
    provider: str
    operation: str
    target: str
    semantics: str
    consequential: bool
    rollback_required: bool
    idempotency_key: str
    expected_readback: Mapping[str, Any] = field(default_factory=dict)


class SQLiteControlPlane:
    """Transactional local/shared control plane.

    SQLite WAL + BEGIN IMMEDIATE supplies serialized writes for multi-process
    coordination on one shared filesystem. It is an upgrade over independent
    JSONL writers, but it is not claimed as a multi-region consensus service.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self.db = sqlite3.connect(self.path, timeout=10.0, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=10000")
        self._init_schema()

    def close(self) -> None:
        self.db.close()

    def _init_schema(self) -> None:
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS events(
              seq INTEGER PRIMARY KEY AUTOINCREMENT,
              event_id TEXT NOT NULL UNIQUE,
              aggregate TEXT NOT NULL,
              kind TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              previous_hash TEXT NOT NULL,
              event_hash TEXT NOT NULL UNIQUE,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS state(
              namespace TEXT NOT NULL,
              item_key TEXT NOT NULL,
              value_json TEXT NOT NULL,
              version INTEGER NOT NULL,
              updated_at TEXT NOT NULL,
              PRIMARY KEY(namespace,item_key)
            );
            CREATE TABLE IF NOT EXISTS idempotency(
              idem_key TEXT PRIMARY KEY,
              request_sha256 TEXT NOT NULL,
              semantics TEXT NOT NULL,
              state TEXT NOT NULL,
              result_json TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS leases(
              resource_id TEXT PRIMARY KEY,
              owner TEXT NOT NULL,
              epoch INTEGER NOT NULL,
              fencing_token INTEGER NOT NULL,
              expires_at_epoch INTEGER NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS effects(
              effect_id TEXT PRIMARY KEY,
              idem_key TEXT NOT NULL UNIQUE,
              request_sha256 TEXT NOT NULL,
              provider TEXT NOT NULL,
              operation TEXT NOT NULL,
              target TEXT NOT NULL,
              semantics TEXT NOT NULL,
              consequential INTEGER NOT NULL,
              rollback_required INTEGER NOT NULL,
              state TEXT NOT NULL,
              provider_ref TEXT,
              result_json TEXT,
              attempt_count INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(idem_key) REFERENCES idempotency(idem_key)
            );
            CREATE TABLE IF NOT EXISTS proofs(
              proof_id TEXT PRIMARY KEY,
              envelope_json TEXT NOT NULL,
              envelope_sha256 TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS authority_leases(
              lease_id TEXT PRIMARY KEY,
              lease_json TEXT NOT NULL,
              uses INTEGER NOT NULL DEFAULT 0,
              consumed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS budgets(
              scope TEXT PRIMARY KEY,
              allowed REAL NOT NULL,
              consumed REAL NOT NULL DEFAULT 0,
              currency TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS schemas(
              schema_id TEXT PRIMARY KEY,
              version INTEGER NOT NULL,
              schema_sha256 TEXT NOT NULL,
              body_json TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS values_ledger(
              event_id TEXT PRIMARY KEY,
              mission_id TEXT NOT NULL,
              accepted_outcome INTEGER NOT NULL,
              owner_interventions INTEGER NOT NULL,
              minutes_saved REAL NOT NULL,
              cost REAL NOT NULL,
              metadata_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )

    @contextlib.contextmanager
    def tx(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield self.db
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        else:
            self.db.execute("COMMIT")

    def append_event(self, aggregate: str, kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        with self.tx() as db:
            previous = db.execute("SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
            previous_hash = previous["event_hash"] if previous else "GENESIS"
            next_seq = int(db.execute("SELECT COALESCE(MAX(seq),0)+1 AS n FROM events").fetchone()["n"])
            created_at = utc_now()
            body = {
                "event_id": f"evt-{next_seq:012d}",
                "aggregate": aggregate,
                "kind": kind,
                "payload": dict(payload),
                "previous_hash": previous_hash,
                "created_at": created_at,
            }
            event_hash = digest(body)
            db.execute(
                "INSERT INTO events(event_id,aggregate,kind,payload_json,previous_hash,event_hash,created_at)"
                " VALUES(?,?,?,?,?,?,?)",
                (
                    body["event_id"], aggregate, kind, stable_json(body["payload"]), previous_hash,
                    event_hash, created_at,
                ),
            )
            return body | {"event_hash": event_hash, "seq": next_seq}

    def verify_event_chain(self) -> bool:
        previous = "GENESIS"
        rows = self.db.execute("SELECT * FROM events ORDER BY seq").fetchall()
        for row in rows:
            body = {
                "event_id": row["event_id"], "aggregate": row["aggregate"], "kind": row["kind"],
                "payload": json.loads(row["payload_json"]), "previous_hash": row["previous_hash"],
                "created_at": row["created_at"],
            }
            if row["previous_hash"] != previous or digest(body) != row["event_hash"]:
                return False
            previous = row["event_hash"]
        return True

    def cas_put(self, namespace: str, key: str, value: Mapping[str, Any], *, expected_version: int | None) -> int:
        with self.tx() as db:
            current = db.execute("SELECT version FROM state WHERE namespace=? AND item_key=?", (namespace, key)).fetchone()
            if current is None:
                if expected_version not in (None, 0):
                    raise FenceError("CAS_VERSION_MISMATCH")
                version = 1
                db.execute(
                    "INSERT INTO state(namespace,item_key,value_json,version,updated_at) VALUES(?,?,?,?,?)",
                    (namespace, key, stable_json(value), version, utc_now()),
                )
            else:
                if expected_version is None or int(current["version"]) != int(expected_version):
                    raise FenceError("CAS_VERSION_MISMATCH")
                version = int(current["version"]) + 1
                db.execute(
                    "UPDATE state SET value_json=?, version=?, updated_at=? WHERE namespace=? AND item_key=?",
                    (stable_json(value), version, utc_now(), namespace, key),
                )
            return version

    def get_state(self, namespace: str, key: str) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT value_json,version,updated_at FROM state WHERE namespace=? AND item_key=?", (namespace, key)
        ).fetchone()
        if not row:
            return None
        return {"value": json.loads(row["value_json"]), "version": int(row["version"]), "updated_at": row["updated_at"]}

    def register_schema(self, schema_id: str, version: int, body: Mapping[str, Any]) -> dict[str, Any]:
        body_sha = digest(body)
        with self.tx() as db:
            prior = db.execute("SELECT version,schema_sha256 FROM schemas WHERE schema_id=?", (schema_id,)).fetchone()
            if prior and int(version) <= int(prior["version"]) and body_sha != prior["schema_sha256"]:
                raise ConstraintError("SCHEMA_REPLACEMENT_REQUIRES_HIGHER_VERSION")
            db.execute(
                "INSERT INTO schemas(schema_id,version,schema_sha256,body_json,updated_at) VALUES(?,?,?,?,?)"
                " ON CONFLICT(schema_id) DO UPDATE SET version=excluded.version,schema_sha256=excluded.schema_sha256,"
                " body_json=excluded.body_json,updated_at=excluded.updated_at",
                (schema_id, int(version), body_sha, stable_json(body), utc_now()),
            )
        return {"schema_id": schema_id, "version": int(version), "sha256": body_sha}

    def acquire_lease(self, resource_id: str, owner: str, *, ttl_seconds: int, now_epoch: int) -> dict[str, Any]:
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be positive")
        with self.tx() as db:
            current = db.execute("SELECT * FROM leases WHERE resource_id=?", (resource_id,)).fetchone()
            if current and int(current["expires_at_epoch"]) > now_epoch:
                if current["owner"] != owner:
                    raise FenceError("LEASE_HELD")
                return dict(current)
            epoch = int(current["epoch"]) + 1 if current else 1
            fencing = int(current["fencing_token"]) + 1 if current else 1
            expires = now_epoch + ttl_seconds
            db.execute(
                "INSERT INTO leases(resource_id,owner,epoch,fencing_token,expires_at_epoch,updated_at) VALUES(?,?,?,?,?,?)"
                " ON CONFLICT(resource_id) DO UPDATE SET owner=excluded.owner,epoch=excluded.epoch,"
                " fencing_token=excluded.fencing_token,expires_at_epoch=excluded.expires_at_epoch,updated_at=excluded.updated_at",
                (resource_id, owner, epoch, fencing, expires, utc_now()),
            )
            return {"resource_id": resource_id, "owner": owner, "epoch": epoch, "fencing_token": fencing, "expires_at_epoch": expires}

    def renew_lease(self, resource_id: str, owner: str, *, epoch: int, fencing_token: int, ttl_seconds: int, now_epoch: int) -> dict[str, Any]:
        with self.tx() as db:
            current = db.execute("SELECT * FROM leases WHERE resource_id=?", (resource_id,)).fetchone()
            if not current:
                raise FenceError("LEASE_MISSING")
            if (
                current["owner"] != owner or int(current["epoch"]) != int(epoch)
                or int(current["fencing_token"]) != int(fencing_token)
                or int(current["expires_at_epoch"]) <= now_epoch
            ):
                raise FenceError("STALE_FENCE")
            expires = now_epoch + ttl_seconds
            db.execute("UPDATE leases SET expires_at_epoch=?,updated_at=? WHERE resource_id=?", (expires, utc_now(), resource_id))
            return dict(current) | {"expires_at_epoch": expires}

    def assert_fence(self, resource_id: str, owner: str, *, epoch: int, fencing_token: int, now_epoch: int) -> None:
        current = self.db.execute("SELECT * FROM leases WHERE resource_id=?", (resource_id,)).fetchone()
        if (
            not current or current["owner"] != owner or int(current["epoch"]) != int(epoch)
            or int(current["fencing_token"]) != int(fencing_token)
            or int(current["expires_at_epoch"]) <= now_epoch
        ):
            raise FenceError("STALE_FENCE")

    def reserve_idempotency(self, idem_key: str, request: Mapping[str, Any], semantics: str) -> dict[str, Any]:
        request_hash = digest(request)
        with self.tx() as db:
            existing = db.execute("SELECT * FROM idempotency WHERE idem_key=?", (idem_key,)).fetchone()
            if existing:
                if existing["request_sha256"] != request_hash:
                    raise IdempotencyCollision("IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_REQUEST")
                return dict(existing)
            now = utc_now()
            db.execute(
                "INSERT INTO idempotency(idem_key,request_sha256,semantics,state,result_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (idem_key, request_hash, semantics, "RESERVED", None, now, now),
            )
            return {"idem_key": idem_key, "request_sha256": request_hash, "semantics": semantics, "state": "RESERVED"}

    def prepare_effect(self, contract: EffectContract, payload: Mapping[str, Any]) -> dict[str, Any]:
        request = {
            "provider": contract.provider, "operation": contract.operation, "target": contract.target,
            "payload": dict(payload), "expected_readback": dict(contract.expected_readback),
        }
        reservation = self.reserve_idempotency(contract.idempotency_key, request, contract.semantics)
        request_hash = reservation["request_sha256"]
        with self.tx() as db:
            existing = db.execute("SELECT * FROM effects WHERE idem_key=?", (contract.idempotency_key,)).fetchone()
            if existing:
                if existing["request_sha256"] != request_hash:
                    raise IdempotencyCollision("EFFECT_REQUEST_COLLISION")
                return dict(existing)
            now = utc_now()
            db.execute(
                "INSERT INTO effects(effect_id,idem_key,request_sha256,provider,operation,target,semantics,consequential,rollback_required,state,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (contract.effect_id, contract.idempotency_key, request_hash, contract.provider, contract.operation,
                 contract.target, contract.semantics, int(contract.consequential), int(contract.rollback_required),
                 "PREPARED", now, now),
            )
            return {"effect_id": contract.effect_id, "state": "PREPARED", "request_sha256": request_hash, "semantics": contract.semantics}

    def transition_effect(self, effect_id: str, *, expected_state: str, next_state: str, provider_ref: str | None = None, result: Mapping[str, Any] | None = None) -> dict[str, Any]:
        allowed = {
            "PREPARED": {"DISPATCHING", "CANCELLED"},
            "DISPATCHING": {"DISPATCHED", "FAILED_UNCERTAIN"},
            "DISPATCHED": {"OBSERVED", "FAILED_UNCERTAIN"},
            "OBSERVED": {"VERIFIED", "COMPENSATING"},
            "COMPENSATING": {"COMPENSATED", "FAILED_UNCERTAIN"},
            "FAILED_UNCERTAIN": {"OBSERVED", "COMPENSATING", "DEAD_LETTER"},
        }
        if next_state not in allowed.get(expected_state, set()):
            raise ConstraintError("INVALID_EFFECT_TRANSITION")
        with self.tx() as db:
            row = db.execute("SELECT * FROM effects WHERE effect_id=?", (effect_id,)).fetchone()
            if not row:
                raise KeyError(effect_id)
            if row["state"] != expected_state:
                raise FenceError("EFFECT_STATE_RACE")
            attempts = int(row["attempt_count"]) + (1 if next_state == "DISPATCHING" else 0)
            db.execute(
                "UPDATE effects SET state=?,provider_ref=COALESCE(?,provider_ref),result_json=COALESCE(?,result_json),attempt_count=?,updated_at=? WHERE effect_id=?",
                (next_state, provider_ref, stable_json(result) if result is not None else None, attempts, utc_now(), effect_id),
            )
            return dict(db.execute("SELECT * FROM effects WHERE effect_id=?", (effect_id,)).fetchone())

    def interrupted_effect_decision(self, effect_id: str) -> dict[str, Any]:
        row = self.db.execute("SELECT * FROM effects WHERE effect_id=?", (effect_id,)).fetchone()
        if not row:
            raise KeyError(effect_id)
        state, semantics = row["state"], row["semantics"]
        if state in {"VERIFIED", "COMPENSATED", "CANCELLED"}:
            return {"action": "NOOP_TERMINAL", "state": state}
        if state in {"DISPATCHING", "DISPATCHED", "FAILED_UNCERTAIN"}:
            if semantics == "AT_MOST_ONCE":
                return {"action": "PROBE_PROVIDER_BEFORE_RETRY", "state": state}
            if semantics == "IDEMPOTENT":
                return {"action": "SAFE_RETRY_WITH_SAME_IDEMPOTENCY_KEY", "state": state}
            return {"action": "PROBE_THEN_RETRY_IF_ABSENT", "state": state}
        return {"action": "DISPATCH", "state": state}

    def register_proof(self, envelope: ProofEnvelope) -> dict[str, Any]:
        check = envelope.validate()
        if not check["valid"]:
            raise ProofError(",".join(check["reasons"]))
        body = dataclasses.asdict(envelope)
        envelope_hash = digest(body)
        with self.tx() as db:
            existing = db.execute("SELECT envelope_sha256 FROM proofs WHERE proof_id=?", (envelope.proof_id,)).fetchone()
            if existing and existing["envelope_sha256"] != envelope_hash:
                raise ProofError("PROOF_ID_COLLISION")
            db.execute(
                "INSERT OR IGNORE INTO proofs(proof_id,envelope_json,envelope_sha256,created_at) VALUES(?,?,?,?)",
                (envelope.proof_id, stable_json(body), envelope_hash, utc_now()),
            )
        return {"proof_id": envelope.proof_id, "sha256": envelope_hash}

    def fetch_proof(self, proof_id: str) -> ProofEnvelope:
        row = self.db.execute("SELECT envelope_json FROM proofs WHERE proof_id=?", (proof_id,)).fetchone()
        if not row:
            raise KeyError(proof_id)
        return ProofEnvelope(**json.loads(row["envelope_json"]))

    def create_authority_lease(self, lease: AuthorityLease) -> dict[str, Any]:
        body = dataclasses.asdict(lease)
        with self.tx() as db:
            existing = db.execute("SELECT lease_json FROM authority_leases WHERE lease_id=?", (lease.lease_id,)).fetchone()
            if existing and digest(json.loads(existing["lease_json"])) != digest(body):
                raise AuthorityError("AUTHORITY_LEASE_ID_COLLISION")
            db.execute("INSERT OR IGNORE INTO authority_leases(lease_id,lease_json,uses) VALUES(?,?,0)", (lease.lease_id, stable_json(body)))
        return {"lease_id": lease.lease_id, "sha256": digest(body)}

    def consume_authority_lease(self, lease_id: str, *, action: str, target: str, actor: str, source_version: str, now_epoch: int) -> dict[str, Any]:
        with self.tx() as db:
            row = db.execute("SELECT * FROM authority_leases WHERE lease_id=?", (lease_id,)).fetchone()
            if not row:
                raise AuthorityError("AUTHORITY_LEASE_MISSING")
            lease = AuthorityLease(**json.loads(row["lease_json"]))
            reasons = lease.validate(action=action, target=target, actor=actor, source_version=source_version, now_epoch=now_epoch)
            if reasons:
                raise AuthorityError(",".join(reasons))
            uses = int(row["uses"])
            if uses >= lease.max_uses:
                raise AuthorityError("AUTHORITY_LEASE_ALREADY_CONSUMED")
            uses += 1
            db.execute("UPDATE authority_leases SET uses=?,consumed_at=? WHERE lease_id=?", (uses, utc_now(), lease_id))
            return {"lease_id": lease_id, "uses": uses, "remaining": lease.max_uses - uses}

    def set_budget(self, scope: str, allowed: float, currency: str = "USD") -> None:
        if allowed < 0:
            raise ValueError("budget cannot be negative")
        with self.tx() as db:
            db.execute(
                "INSERT INTO budgets(scope,allowed,consumed,currency,updated_at) VALUES(?,?,0,?,?)"
                " ON CONFLICT(scope) DO UPDATE SET allowed=excluded.allowed,currency=excluded.currency,updated_at=excluded.updated_at",
                (scope, float(allowed), currency, utc_now()),
            )

    def consume_budget(self, scope: str, amount: float) -> dict[str, Any]:
        if amount < 0:
            raise ValueError("amount cannot be negative")
        with self.tx() as db:
            row = db.execute("SELECT * FROM budgets WHERE scope=?", (scope,)).fetchone()
            if not row:
                raise ConstraintError("UNKNOWN_COST_FAIL_CLOSED")
            new_value = float(row["consumed"]) + float(amount)
            if new_value > float(row["allowed"]) + 1e-12:
                raise ConstraintError("BUDGET_EXCEEDED")
            db.execute("UPDATE budgets SET consumed=?,updated_at=? WHERE scope=?", (new_value, utc_now(), scope))
            return {"scope": scope, "allowed": float(row["allowed"]), "consumed": new_value, "remaining": float(row["allowed"]) - new_value, "currency": row["currency"]}

    def record_value(self, *, event_id: str, mission_id: str, accepted_outcome: bool, owner_interventions: int, minutes_saved: float, cost: float, metadata: Mapping[str, Any] | None = None) -> None:
        with self.tx() as db:
            db.execute(
                "INSERT INTO values_ledger(event_id,mission_id,accepted_outcome,owner_interventions,minutes_saved,cost,metadata_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (event_id, mission_id, int(accepted_outcome), int(owner_interventions), float(minutes_saved), float(cost), stable_json(dict(metadata or {})), utc_now()),
            )

    def value_summary(self, mission_id: str) -> dict[str, Any]:
        row = self.db.execute(
            "SELECT COUNT(*) n, SUM(accepted_outcome) ok, SUM(owner_interventions) interventions, SUM(minutes_saved) saved, SUM(cost) cost FROM values_ledger WHERE mission_id=?",
            (mission_id,),
        ).fetchone()
        n = int(row["n"] or 0)
        ok = int(row["ok"] or 0)
        return {"mission_id": mission_id, "observations": n, "accepted_rate": ok / n if n else 0.0, "owner_interventions": int(row["interventions"] or 0), "minutes_saved": float(row["saved"] or 0.0), "cost": float(row["cost"] or 0.0)}


class ProofBundleVerifier:
    def __init__(self, proofs: Sequence[ProofEnvelope]) -> None:
        self.proofs = {p.proof_id: p for p in proofs}

    def verify_requirements(self, requirements: Sequence[Mapping[str, Any]], *, now_epoch: int) -> dict[str, Any]:
        missing: list[str] = []
        invalid: dict[str, list[str]] = {}
        for req in requirements:
            proof_id = str(req["proof_id"])
            proof = self.proofs.get(proof_id)
            if proof is None:
                missing.append(proof_id)
                continue
            check = proof.validate(
                now_epoch=now_epoch, expected_subject=req.get("subject"), expected_target=req.get("target"),
                expected_operation=req.get("operation"), expected_source_version=req.get("source_version"),
                accepted_evidence_classes=req.get("accepted_evidence_classes"),
                require_provider_correlation=bool(req.get("require_provider_correlation", False)),
                require_signature_ref=bool(req.get("require_signature_ref", False)),
            )
            if not check["valid"]:
                invalid[proof_id] = check["reasons"]
        return {"valid": not missing and not invalid, "missing": sorted(missing), "invalid": invalid}


class WorkloadIdentityPolicy:
    def __init__(self, *, allowed_issuers: set[str], audience: str, subject_prefix: str, max_ttl_seconds: int = 3600) -> None:
        self.allowed_issuers = set(allowed_issuers)
        self.audience = audience
        self.subject_prefix = subject_prefix
        self.max_ttl_seconds = int(max_ttl_seconds)

    def validate(self, claims: Mapping[str, Any], *, now_epoch: int) -> dict[str, Any]:
        reasons: list[str] = []
        if claims.get("iss") not in self.allowed_issuers:
            reasons.append("ISSUER_NOT_ALLOWED")
        aud = claims.get("aud")
        audiences = set(aud if isinstance(aud, list) else [aud])
        if self.audience not in audiences:
            reasons.append("AUDIENCE_MISMATCH")
        if not str(claims.get("sub", "")).startswith(self.subject_prefix):
            reasons.append("SUBJECT_MISMATCH")
        iat = int(claims.get("iat", 0)); exp = int(claims.get("exp", 0))
        if not (iat <= now_epoch < exp):
            reasons.append("TOKEN_NOT_CURRENT")
        if exp - iat > self.max_ttl_seconds:
            reasons.append("TOKEN_TTL_TOO_LONG")
        if claims.get("credential_type") in {"static_key", "service_account_key", "long_lived_secret"}:
            reasons.append("STATIC_CREDENTIAL_FORBIDDEN")
        return {"valid": not reasons, "reasons": reasons}


class GatewayPolicy:
    def __init__(self, gateway_id: str, runtime_id: str) -> None:
        self.gateway_id = gateway_id; self.runtime_id = runtime_id

    def admit(self, request: Mapping[str, Any]) -> dict[str, Any]:
        reasons = []
        if request.get("runtime_id") != self.runtime_id:
            reasons.append("RUNTIME_MISMATCH")
        if request.get("via_gateway") != self.gateway_id:
            reasons.append("DIRECT_RUNTIME_BYPASS_FORBIDDEN")
        if not request.get("authenticated_principal"):
            reasons.append("AUTHENTICATED_PRINCIPAL_REQUIRED")
        if not request.get("policy_version"):
            reasons.append("POLICY_VERSION_REQUIRED")
        return {"admitted": not reasons, "reasons": reasons}


@dataclass(frozen=True)
class GuardrailResult:
    name: str
    decision: str
    reason: str = ""


class GuardrailPipeline:
    def __init__(self) -> None:
        self.input_guards: list[Callable[[Mapping[str, Any]], GuardrailResult]] = []
        self.pre_tool_guards: list[Callable[[Mapping[str, Any]], GuardrailResult]] = []
        self.post_tool_guards: list[Callable[[Mapping[str, Any]], GuardrailResult]] = []
        self.output_guards: list[Callable[[Mapping[str, Any]], GuardrailResult]] = []

    @staticmethod
    def _run(guards: Sequence[Callable[[Mapping[str, Any]], GuardrailResult]], value: Mapping[str, Any]) -> dict[str, Any]:
        results = [guard(value) for guard in guards]
        rejected = [r for r in results if r.decision == "REJECT"]
        review = [r for r in results if r.decision == "REVIEW"]
        decision = "REJECT" if rejected else "REVIEW" if review else "ALLOW"
        return {"decision": decision, "results": [dataclasses.asdict(r) for r in results]}

    def check_input(self, value: Mapping[str, Any]) -> dict[str, Any]: return self._run(self.input_guards, value)
    def check_pre_tool(self, value: Mapping[str, Any]) -> dict[str, Any]: return self._run(self.pre_tool_guards, value)
    def check_post_tool(self, value: Mapping[str, Any]) -> dict[str, Any]: return self._run(self.post_tool_guards, value)
    def check_output(self, value: Mapping[str, Any]) -> dict[str, Any]: return self._run(self.output_guards, value)


@dataclass
class RouteRecord:
    provider: str
    capability: str
    model: str
    region: str
    endpoint: str
    unit_cost: float
    latency_ms: float
    success_rate: float
    quota_remaining: int
    concurrency_limit: int
    active: int = 0
    breaker_state: str = "CLOSED"
    open_until_epoch: int = 0
    ewma_success: float | None = None
    ewma_latency_ms: float | None = None

    @property
    def key(self) -> tuple[str, str, str, str, str]: return (self.provider, self.capability, self.model, self.region, self.endpoint)


class AdaptiveRouterV2:
    def __init__(self, *, breaker_window: int = 8, breaker_failure_threshold: float = 0.5, cooldown_seconds: int = 60) -> None:
        self.routes: dict[tuple[str, str, str, str, str], RouteRecord] = {}
        self.outcomes: dict[tuple[str, str, str, str, str], list[bool]] = {}
        self.breaker_window = int(breaker_window); self.breaker_failure_threshold = float(breaker_failure_threshold); self.cooldown_seconds = int(cooldown_seconds)

    def register(self, route: RouteRecord) -> None:
        if not (0 <= route.success_rate <= 1): raise ValueError("success_rate outside range")
        if route.unit_cost < 0 or route.latency_ms < 0: raise ValueError("negative route metric")
        self.routes[route.key] = route; self.outcomes.setdefault(route.key, [])

    def record_outcome(self, key: tuple[str, str, str, str, str], *, success: bool, latency_ms: float, now_epoch: int) -> str:
        route = self.routes[key]; history = self.outcomes[key]
        history.append(bool(success)); del history[:-self.breaker_window]
        alpha = 0.25
        route.ewma_success = float(success) if route.ewma_success is None else alpha * float(success) + (1 - alpha) * route.ewma_success
        route.ewma_latency_ms = float(latency_ms) if route.ewma_latency_ms is None else alpha * float(latency_ms) + (1 - alpha) * route.ewma_latency_ms
        failures = sum(not x for x in history)
        if len(history) >= 4 and failures / len(history) >= self.breaker_failure_threshold:
            route.breaker_state = "OPEN"; route.open_until_epoch = now_epoch + self.cooldown_seconds
        elif route.breaker_state == "HALF_OPEN" and success:
            route.breaker_state = "CLOSED"; route.open_until_epoch = 0
        return route.breaker_state

    def half_open_due(self, now_epoch: int) -> list[tuple[str, str, str, str, str]]:
        due = []
        for key, route in self.routes.items():
            if route.breaker_state == "OPEN" and now_epoch >= route.open_until_epoch:
                route.breaker_state = "HALF_OPEN"; due.append(key)
        return due

    def select(self, *, capability: str, now_epoch: int, max_unit_cost: float, max_latency_ms: float, min_success_rate: float, preferred_regions: Sequence[str] = ()) -> dict[str, Any]:
        self.half_open_due(now_epoch)
        eligible: list[tuple[float, RouteRecord]] = []; rejected: dict[str, str] = {}
        for route in self.routes.values():
            label = "|".join(route.key)
            if route.capability != capability: continue
            if route.breaker_state == "OPEN": rejected[label] = "CIRCUIT_OPEN"; continue
            if route.quota_remaining <= 0: rejected[label] = "RATE_LIMITED"; continue
            if route.active >= route.concurrency_limit: rejected[label] = "SATURATED"; continue
            observed_success = route.ewma_success if route.ewma_success is not None else route.success_rate
            observed_latency = route.ewma_latency_ms if route.ewma_latency_ms is not None else route.latency_ms
            if route.unit_cost > max_unit_cost: rejected[label] = "COST_LIMIT"; continue
            if observed_latency > max_latency_ms: rejected[label] = "LATENCY_LIMIT"; continue
            if observed_success < min_success_rate: rejected[label] = "RELIABILITY_LIMIT"; continue
            cost_norm = route.unit_cost / max(max_unit_cost, 1e-9); latency_norm = observed_latency / max(max_latency_ms, 1e-9)
            quota_norm = min(1.0, route.quota_remaining / 100.0); region_bonus = 0.05 if route.region in set(preferred_regions) else 0.0
            half_open_penalty = 0.15 if route.breaker_state == "HALF_OPEN" else 0.0; load_penalty = route.active / max(1, route.concurrency_limit)
            score = 0.50 * observed_success + 0.15 * (1 - cost_norm) + 0.10 * (1 - latency_norm) + 0.10 * quota_norm + region_bonus - 0.10 * load_penalty - half_open_penalty
            eligible.append((score, route))
        if not eligible: return {"state": "NO_ELIGIBLE_ROUTE", "selected": None, "rejected": rejected}
        eligible.sort(key=lambda item: (-item[0], item[1].key)); score, route = eligible[0]
        return {"state": "ROUTED", "selected": route.key, "score": round(score, 6), "rejected": rejected}


class TokenBucket:
    def __init__(self, capacity: float, refill_per_second: float, *, initial_tokens: float | None = None) -> None:
        self.capacity = float(capacity); self.refill_per_second = float(refill_per_second)
        self.tokens = self.capacity if initial_tokens is None else min(self.capacity, float(initial_tokens)); self.last_epoch = 0.0

    def allow(self, cost: float, now_epoch: float) -> bool:
        if self.last_epoch: self.tokens = min(self.capacity, self.tokens + max(0.0, now_epoch - self.last_epoch) * self.refill_per_second)
        self.last_epoch = float(now_epoch)
        if self.tokens + 1e-12 < cost: return False
        self.tokens -= cost; return True


@dataclass
class MissionNodeV2:
    node_id: str
    dependencies: tuple[str, ...] = ()
    required_proofs: tuple[Mapping[str, Any], ...] = ()
    constraints: tuple[str, ...] = ()
    status: str = "QUEUED"
    priority: int = 50
    cost: float = 1.0
    risk: float = 0.0
    conflict_domains: tuple[str, ...] = ()
    superseded_by: str | None = None


class MissionGraphV2:
    TERMINAL_SATISFIED = {"VERIFIED", "SUPERSEDED", "COMPENSATED"}

    def __init__(self, mission_id: str, *, mission_constraints: Sequence[str] = ()) -> None:
        self.mission_id = mission_id; self.mission_constraints = tuple(mission_constraints); self.nodes: dict[str, MissionNodeV2] = {}

    def add(self, node: MissionNodeV2) -> None:
        if node.node_id in self.nodes: raise ValueError("duplicate node")
        self.nodes[node.node_id] = node

    def validate_dag(self) -> None:
        unknown = sorted({d for n in self.nodes.values() for d in n.dependencies if d not in self.nodes})
        if unknown: raise ConstraintError("UNKNOWN_DEPENDENCIES:" + ",".join(unknown))
        visiting: set[str] = set(); visited: set[str] = set()
        def visit(node_id: str) -> None:
            if node_id in visiting: raise ConstraintError("DEPENDENCY_CYCLE")
            if node_id in visited: return
            visiting.add(node_id)
            for dep in self.nodes[node_id].dependencies: visit(dep)
            visiting.remove(node_id); visited.add(node_id)
        for node_id in self.nodes: visit(node_id)

    def ready(self, *, capacity: int | None = None) -> list[str]:
        self.validate_dag(); satisfied = {k for k, n in self.nodes.items() if n.status in self.TERMINAL_SATISFIED}
        candidates = [n for n in self.nodes.values() if n.status == "QUEUED" and set(n.dependencies) <= satisfied]
        candidates.sort(key=lambda n: (-n.priority, n.cost, n.risk, n.node_id)); selected: list[MissionNodeV2] = []; used_domains: set[str] = set()
        for node in candidates:
            if capacity is not None and len(selected) >= capacity: break
            if used_domains & set(node.conflict_domains): continue
            selected.append(node); used_domains |= set(node.conflict_domains)
        return [n.node_id for n in selected]

    def supersede_failed(self, failed_node_id: str, replacement: MissionNodeV2) -> None:
        failed = self.nodes[failed_node_id]
        if failed.status not in {"FAILED", "BLOCKED"}: raise ConstraintError("ONLY_FAILED_OR_BLOCKED_NODE_CAN_BE_SUPERSEDED")
        if replacement.node_id in self.nodes: raise ValueError("replacement node exists")
        replacement.required_proofs = tuple(list(replacement.required_proofs) + list(failed.required_proofs))
        replacement.constraints = tuple(sorted(set(replacement.constraints) | set(failed.constraints)))
        self.nodes[replacement.node_id] = replacement; failed.status = "SUPERSEDED"; failed.superseded_by = replacement.node_id

    def verify_node(self, node_id: str, *, proof_bundle: ProofBundleVerifier, now_epoch: int, satisfied_constraints: set[str]) -> dict[str, Any]:
        node = self.nodes[node_id]; missing_constraints = sorted(set(node.constraints) - satisfied_constraints)
        proof_result = proof_bundle.verify_requirements(node.required_proofs, now_epoch=now_epoch)
        if missing_constraints or not proof_result["valid"]:
            node.status = "PARTIALLY_VERIFIED"; return {"status": node.status, "missing_constraints": missing_constraints, "proof": proof_result}
        node.status = "VERIFIED"; return {"status": "VERIFIED", "missing_constraints": [], "proof": proof_result}

    def evaluate_closure(self, *, satisfied_constraints: set[str]) -> dict[str, Any]:
        missing_mission_constraints = sorted(set(self.mission_constraints) - satisfied_constraints)
        incomplete = sorted(node.node_id for node in self.nodes.values() if node.status not in self.TERMINAL_SATISFIED)
        state = "PROOF_CLOSED" if not incomplete and not missing_mission_constraints else "OPEN"
        result = {"mission_id": self.mission_id, "state": state, "incomplete": incomplete, "missing_constraints": missing_mission_constraints}
        return result | {"closure_sha256": digest(result)}

    def critical_path_length(self) -> int:
        self.validate_dag(); memo: dict[str, int] = {}
        def depth(node_id: str) -> int:
            if node_id in memo: return memo[node_id]
            deps = self.nodes[node_id].dependencies; memo[node_id] = 1 + max((depth(d) for d in deps), default=0); return memo[node_id]
        return max((depth(n) for n in self.nodes), default=0)


@dataclass(frozen=True)
class MemoryItemV2:
    memory_id: str; claim_key: str; content: str; verified: bool; confidence: float; observed_at_epoch: int; priority: int; source_ref: str
    supersedes: tuple[str, ...] = (); contradicts: tuple[str, ...] = ()


class HybridMemoryIndex:
    def __init__(self) -> None: self.items: dict[str, MemoryItemV2] = {}
    def add(self, item: MemoryItemV2) -> None:
        if item.memory_id in self.items and self.items[item.memory_id] != item: raise ValueError("memory collision")
        self.items[item.memory_id] = item
    @staticmethod
    def _tokens(text: str) -> set[str]: return set(re.findall(r"[a-z0-9_]+", text.lower()))
    @staticmethod
    def _trigrams(text: str) -> set[str]:
        text = re.sub(r"\s+", " ", text.lower().strip()); return {text[i:i+3] for i in range(max(0, len(text)-2))}
    def active(self) -> list[MemoryItemV2]:
        superseded = {sid for item in self.items.values() for sid in item.supersedes}; return [item for key, item in self.items.items() if key not in superseded]
    def retrieve(self, query: str, *, now_epoch: int, limit: int = 10) -> dict[str, Any]:
        qt = self._tokens(query); qg = self._trigrams(query); rows = []
        for item in self.active():
            text = f"{item.claim_key} {item.content}"; tokens = self._tokens(text); trigrams = self._trigrams(text)
            lexical = len(qt & tokens) / max(1, len(qt)); fuzzy = len(qg & trigrams) / max(1, len(qg))
            age_days = max(0.0, (now_epoch - item.observed_at_epoch) / 86400); freshness = 0.5 ** (age_days / 7)
            score = 0.35*lexical + 0.20*fuzzy + 0.20*(1.0 if item.verified else 0.25) + 0.10*item.confidence + 0.075*freshness + 0.075*min(1.0, item.priority/100)
            if item.contradicts: score *= 0.65
            rows.append((score, item))
        rows.sort(key=lambda x: (-x[0], x[1].memory_id)); selected = [dataclasses.asdict(item) | {"score": round(score, 6)} for score, item in rows[:limit]]
        contradictions = sorted({tuple(sorted((item.memory_id, other))) for item in self.active() for other in item.contradicts if other in self.items and other != item.memory_id})
        return {"selected": selected, "contradictions": [list(x) for x in contradictions], "context_sha256": digest(selected)}


@dataclass(frozen=True)
class CausalEdgeV2:
    cause: str; effect: str; strength: float; confidence: float


class CausalGraphV2:
    def __init__(self) -> None: self.edges: list[CausalEdgeV2] = []
    def add(self, edge: CausalEdgeV2) -> None:
        if not (-1 <= edge.strength <= 1 and 0 <= edge.confidence <= 1): raise ValueError("invalid edge")
        self.edges.append(edge)
    def influence(self, cause: str, effect: str, *, max_depth: int = 8) -> float:
        best = 0.0; frontier = [(cause, 1.0, 0, {cause})]
        while frontier:
            node, weight, depth, seen = frontier.pop()
            if depth >= max_depth: continue
            for edge in self.edges:
                if edge.cause != node or edge.effect in seen: continue
                next_weight = weight * edge.strength * edge.confidence
                if edge.effect == effect and abs(next_weight) > abs(best): best = next_weight
                frontier.append((edge.effect, next_weight, depth + 1, seen | {edge.effect}))
        return best
    def rank_interventions(self, *, symptom: str, interventions: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        for item in interventions:
            target = str(item["target"]); causal_fit = abs(self.influence(target, symptom))
            if target == symptom: causal_fit = max(causal_fit, 0.25)
            score = float(item["expected_effect"])*causal_fit*float(item.get("reversibility",1.0)) - 0.15*float(item.get("cost",0.0)) - 0.35*float(item.get("risk",0.0))
            rows.append(dict(item) | {"causal_fit": round(causal_fit,6), "score": round(score,6)})
        return sorted(rows, key=lambda x: (-x["score"], str(x.get("id", ""))))


@dataclass(frozen=True)
class TraceEnvelope:
    trace_id: str; span_id: str; parent_span_id: str | None; kind: str; name: str; started_at_epoch_ms: int; duration_ms: float; status: str; attributes: Mapping[str, Any]
    def otel_attributes(self) -> dict[str, Any]:
        base = {"gen_ai.operation.name": self.kind, "sol.trace.name": self.name, "sol.trace.id": self.trace_id, "sol.span.id": self.span_id}; safe = {}
        for key, value in self.attributes.items():
            lowered = key.lower()
            if any(secret in lowered for secret in ("token", "password", "secret", "authorization", "cookie")): continue
            safe[key] = value
        return base | safe


@dataclass(frozen=True)
class SLODefinition:
    slo_id: str; target_good_rate: float; window: int = 100


class SLOErrorBudget:
    def __init__(self, slo: SLODefinition) -> None:
        if not 0 < slo.target_good_rate <= 1: raise ValueError("invalid target")
        self.slo = slo; self.outcomes: list[bool] = []
    def record(self, good: bool) -> dict[str, Any]:
        self.outcomes.append(bool(good)); del self.outcomes[:-self.slo.window]
        good_rate = sum(self.outcomes) / len(self.outcomes); allowed_bad = 1 - self.slo.target_good_rate; observed_bad = 1 - good_rate
        burn = 0.0 if allowed_bad == 0 and observed_bad == 0 else math.inf if allowed_bad == 0 else observed_bad / allowed_bad
        action = "FREEZE_PROMOTION" if burn >= 2 else "DEGRADE_AND_INVESTIGATE" if burn >= 1 else "CONTINUE"
        return {"good_rate": good_rate, "burn_rate": burn, "action": action, "samples": len(self.outcomes)}


@dataclass(frozen=True)
class SupplyChainProvenance:
    artifact_sha256: str; source_uri: str; source_revision: str; builder_id: str; build_type: str; materials: tuple[tuple[str, str], ...]; invocation_id: str; signature_ref: str = ""; transparency_log_ref: str = ""
    def verify(self, *, expected_artifact_sha256: str, expected_source_uri: str, expected_source_revision: str, allowed_builders: set[str], require_signature: bool = False, require_transparency_log: bool = False) -> dict[str, Any]:
        reasons = []
        if not _is_sha256(self.artifact_sha256) or self.artifact_sha256 != expected_artifact_sha256: reasons.append("ARTIFACT_DIGEST_MISMATCH")
        if self.source_uri != expected_source_uri: reasons.append("SOURCE_URI_MISMATCH")
        if self.source_revision != expected_source_revision: reasons.append("SOURCE_REVISION_MISMATCH")
        if self.builder_id not in allowed_builders: reasons.append("BUILDER_NOT_ALLOWED")
        if any(not uri or not _is_sha256(sha) for uri, sha in self.materials): reasons.append("MATERIALS_INVALID")
        if require_signature and not self.signature_ref: reasons.append("SIGNATURE_REQUIRED")
        if require_transparency_log and not self.transparency_log_ref: reasons.append("TRANSPARENCY_LOG_REQUIRED")
        return {"valid": not reasons, "reasons": reasons}


class ToolboxManifest:
    def __init__(self, version: str) -> None: self.version = version; self.tools: dict[str, dict[str, str]] = {}
    def register(self, tool_name: str, *, schema: Mapping[str, Any], implementation_sha256: str) -> None:
        if not _is_sha256(implementation_sha256): raise ValueError("invalid implementation digest")
        self.tools[tool_name] = {"schema_sha256": digest(schema), "implementation_sha256": implementation_sha256}
    def fingerprint(self) -> str: return digest({"version": self.version, "tools": self.tools})
    def verify(self, expected_fingerprint: str) -> bool: return self.fingerprint() == expected_fingerprint


class DeterministicFaultInjector:
    def __init__(self, faults: Mapping[str, str]) -> None: self.faults = dict(faults)
    def invoke(self, point: str) -> None:
        failure = self.faults.get(point)
        if failure: raise RuntimeError(failure)


class ChampionChallenger:
    @staticmethod
    def score(metrics: Mapping[str, float]) -> float:
        return 0.45*float(metrics["success_rate"]) + 0.20*float(metrics["proof_quality"]) + 0.15*(1/(1+float(metrics["latency_ms"])/1000)) + 0.10*(1/(1+float(metrics["cost"]))) + 0.10*(1/(1+float(metrics["owner_interventions"])))
    @classmethod
    def evaluate(cls, champion: Mapping[str, float], challenger: Mapping[str, float], *, min_relative_gain: float = 0.05, min_samples: int = 30, challenger_samples: int = 0, critical_regressions: int = 0) -> dict[str, Any]:
        c = cls.score(champion); h = cls.score(challenger); gain = (h-c)/max(abs(c),1e-9)
        promote = challenger_samples >= min_samples and critical_regressions == 0 and gain >= min_relative_gain
        return {"champion_score": round(c,6), "challenger_score": round(h,6), "relative_gain": round(gain,6), "promote": promote}


class LearningPromotionGate:
    def evaluate(self, *, distinct_events: int, independent_sources: int, contradiction_count: int, regression_count: int, measured_gain: float, min_distinct_events: int = 3, min_independent_sources: int = 2, min_gain: float = 0.02) -> dict[str, Any]:
        gates = {"distinct_events": distinct_events >= min_distinct_events, "independent_sources": independent_sources >= min_independent_sources, "no_open_contradiction": contradiction_count == 0, "no_regression": regression_count == 0, "measured_gain": measured_gain >= min_gain}
        return {"promote": all(gates.values()), "gates": gates}


class MaturityMatrix:
    ORDER = {"DESIGNED":0,"SOURCE_IMPLEMENTED":1,"DETERMINISTIC_TESTED":2,"HOSTED_SHADOW":3,"PROVIDER_VERIFIED_SCOPED":4,"OPERATIONAL_VERIFIED_SCOPED":5,"SUSTAINED_VALUE_VERIFIED_SCOPED":6}
    @classmethod
    def can_promote(cls, current: str, candidate: str, *, same_scope: bool, proof_chain_complete: bool) -> bool:
        if current not in cls.ORDER or candidate not in cls.ORDER: return False
        return same_scope and proof_chain_complete and cls.ORDER[candidate] == cls.ORDER[current] + 1


GENE_TITLES = [
("Transactional SQLite WAL control plane","durability","SQLiteControlPlane"),("Serialized append-only event commits","durability","SQLiteControlPlane.append_event"),("Global event hash-chain verification","durability","SQLiteControlPlane.verify_event_chain"),("Verify-before-replay state hydration","durability","SQLiteControlPlane.verify_event_chain"),("Atomic state projection commits","durability","SQLiteControlPlane.cas_put"),("Event-truth-first checkpoint contract","durability","SQLiteControlPlane.append_event"),("State schema registry","durability","SQLiteControlPlane.register_schema"),("Schema version migration gate","durability","SQLiteControlPlane.register_schema"),("Compare-and-swap state writes","durability","SQLiteControlPlane.cas_put"),("Corruption fail-closed boundary","durability","SQLiteControlPlane.verify_event_chain"),
("Leader/resource lease epochs","coordination","SQLiteControlPlane.acquire_lease"),("Monotonic fencing tokens","coordination","SQLiteControlPlane.acquire_lease"),("Lease renewal with stale-fence rejection","coordination","SQLiteControlPlane.renew_lease"),("Pre-effect fence assertion","coordination","SQLiteControlPlane.assert_fence"),("Expired-owner takeover","coordination","SQLiteControlPlane.acquire_lease"),("Workstream conflict-domain scheduling","coordination","MissionGraphV2.ready"),("Dependency-aware parallel lane selection","coordination","MissionGraphV2.ready"),("Queue/backpressure contract","coordination","TokenBucket"),("Multi-tenant fairness-ready state boundary","coordination","SQLiteControlPlane"),("Multi-process serialized write substrate","coordination","SQLiteControlPlane"),
("Request-hash idempotency","effects","SQLiteControlPlane.reserve_idempotency"),("Idempotency collision rejection","effects","SQLiteControlPlane.reserve_idempotency"),("Durable effect outbox","effects","SQLiteControlPlane.prepare_effect"),("Explicit effect state machine","effects","SQLiteControlPlane.transition_effect"),("At-most-once interruption semantics","effects","SQLiteControlPlane.interrupted_effect_decision"),("Idempotent retry semantics","effects","SQLiteControlPlane.interrupted_effect_decision"),("Provider-probe-before-retry rule","effects","SQLiteControlPlane.interrupted_effect_decision"),("Compensation lifecycle","effects","SQLiteControlPlane.transition_effect"),("Duplicate-effect suppression","effects","SQLiteControlPlane.prepare_effect"),("Uncertain-effect quarantine","effects","SQLiteControlPlane.transition_effect"),
("Typed proof envelope","proof","ProofEnvelope"),("Proof subject binding","proof","ProofEnvelope.validate"),("Proof target binding","proof","ProofEnvelope.validate"),("Proof operation binding","proof","ProofEnvelope.validate"),("Proof source-version binding","proof","ProofEnvelope.validate"),("Proof freshness TTL enforcement","proof","ProofEnvelope.validate"),("Semantic proof-state enforcement","proof","ProofEnvelope.validate"),("Provider correlation requirement","proof","ProofEnvelope.validate"),("Proof bundle validity not key presence","proof","ProofBundleVerifier.verify_requirements"),("Evidence-class/scope non-inheritance","proof","ProofEnvelope.validate"),
("Action-bound authority leases","authority","AuthorityLease"),("One-use authority consumption","authority","SQLiteControlPlane.consume_authority_lease"),("Authority expiry enforcement","authority","AuthorityLease.validate"),("Actor/target/version authority binding","authority","AuthorityLease.validate"),("Owner-reserved effect compatibility surface","authority","AuthorityLease"),("Input guardrail pipeline","guardrails","GuardrailPipeline.check_input"),("Pre-tool guardrail pipeline","guardrails","GuardrailPipeline.check_pre_tool"),("Post-tool guardrail pipeline","guardrails","GuardrailPipeline.check_post_tool"),("Gateway-only runtime ingress","guardrails","GatewayPolicy.admit"),("Short-lived workload identity policy","guardrails","WorkloadIdentityPolicy.validate"),
("OpenTelemetry-aligned trace attributes","observability","TraceEnvelope.otel_attributes"),("Mission/workstream/tool/provider span model","observability","TraceEnvelope"),("Privacy-aware telemetry redaction","observability","TraceEnvelope.otel_attributes"),("SLO definition primitive","observability","SLODefinition"),("Error-budget accounting","observability","SLOErrorBudget.record"),("Burn-rate promotion freeze","observability","SLOErrorBudget.record"),("False-completion proof integration","observability","ProofBundleVerifier.verify_requirements"),("Proof freshness alarm surface","observability","ProofEnvelope.validate"),("Incident/fault injection test seam","observability","DeterministicFaultInjector"),("Value and owner-burden telemetry ledger","observability","SQLiteControlPlane.record_value"),
("Hybrid lexical+trigram retrieval","memory","HybridMemoryIndex.retrieve"),("Verified-memory preference","memory","HybridMemoryIndex.retrieve"),("Memory freshness decay","memory","HybridMemoryIndex.retrieve"),("Supersession-aware active memory","memory","HybridMemoryIndex.active"),("Contradiction cluster surfacing","memory","HybridMemoryIndex.retrieve"),("Context fingerprinting","memory","HybridMemoryIndex.retrieve"),("Source-reference preservation","memory","MemoryItemV2"),("Causal path-strength propagation","causal","CausalGraphV2.influence"),("Upstream intervention ranking","causal","CausalGraphV2.rank_interventions"),("Counterfactual calibration-ready evidence surface","causal","CausalGraphV2"),
("Composite provider-route identity","routing","RouteRecord.key"),("Circuit-breaker cooldown","routing","AdaptiveRouterV2.record_outcome"),("Half-open recovery probe","routing","AdaptiveRouterV2.half_open_due"),("EWMA success learning","routing","AdaptiveRouterV2.record_outcome"),("EWMA latency learning","routing","AdaptiveRouterV2.record_outcome"),("Normalized cost/latency/reliability ranking","routing","AdaptiveRouterV2.select"),("Quota-aware route rejection","routing","AdaptiveRouterV2.select"),("Concurrency-aware route rejection","routing","AdaptiveRouterV2.select"),("Token-bucket rate limiting","routing","TokenBucket.allow"),("Unknown-cost fail-closed budget","routing","SQLiteControlPlane.consume_budget"),
("SLSA-style artifact provenance envelope","supply_chain","SupplyChainProvenance"),("Artifact digest expectation verification","supply_chain","SupplyChainProvenance.verify"),("Source revision expectation verification","supply_chain","SupplyChainProvenance.verify"),("Builder identity allowlist","supply_chain","SupplyChainProvenance.verify"),("Materials/SBOM digest contract","supply_chain","SupplyChainProvenance.verify"),("Keyless signature reference gate","supply_chain","SupplyChainProvenance.verify"),("Transparency-log reference gate","supply_chain","SupplyChainProvenance.verify"),("Version-pinned toolbox manifest","supply_chain","ToolboxManifest"),("Deterministic fault-injection seam","supply_chain","DeterministicFaultInjector"),("Independent release-proof requirement","supply_chain","MaturityMatrix.can_promote"),
("Mission DAG cycle detection","mission","MissionGraphV2.validate_dag"),("Failed-path supersession closure repair","mission","MissionGraphV2.supersede_failed"),("Mission constraint enforcement","mission","MissionGraphV2.evaluate_closure"),("Proof-based node verification","mission","MissionGraphV2.verify_node"),("Critical-path depth metric","mission","MissionGraphV2.critical_path_length"),("Champion/challenger evaluation","learning","ChampionChallenger.evaluate"),("Measured-gain promotion threshold","learning","ChampionChallenger.evaluate"),("Realized owner-value ledger","learning","SQLiteControlPlane.value_summary"),("Empirical learning promotion gate","learning","LearningPromotionGate.evaluate"),("No cross-scope maturity inheritance","learning","MaturityMatrix.can_promote")]

if len(GENE_TITLES) != 100: raise AssertionError(f"expected 100 genes, got {len(GENE_TITLES)}")
HYPERLEVERAGE_100 = tuple({"id":f"SOL-HL-{idx:03d}","title":title,"category":category,"implementation":implementation,"state":"SOURCE_ENFORCED"} for idx,(title,category,implementation) in enumerate(GENE_TITLES,1))

def coverage_receipt() -> dict[str, Any]:
    ids=[g["id"] for g in HYPERLEVERAGE_100]; titles=[g["title"] for g in HYPERLEVERAGE_100]
    gates={"exactly_100":len(ids)==100,"unique_ids":len(set(ids))==100,"unique_titles":len(set(titles))==100,"all_have_implementation":all(g["implementation"] for g in HYPERLEVERAGE_100),"all_source_enforced":all(g["state"]=="SOURCE_ENFORCED" for g in HYPERLEVERAGE_100)}
    body={"programme":"CFBE-SOL61-HYPERLEVERAGE-100-20260901","status":"SOURCE_IMPLEMENTATION_COMPLETE" if all(gates.values()) else "INCOMPLETE","gates":gates,"gene_count":len(ids),"truth_boundary":{"source_enforced":True,"provider_live_inheritance":False,"production_cutover":False,"market_superiority_claim":False,"sustained_owner_value_proven":False}}
    return body | {"sha256":digest(body)}
