"""Provider-neutral, fail-closed Redis replay qualification state machine."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from . import __version__

TARGET_FINGERPRINT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_DENIALS = frozenset(
    {
        "ACL",
        "CONFIG",
        "DEBUG",
        "DEL",
        "EVAL",
        "EVALSHA",
        "EXPIRE",
        "FAILOVER",
        "FLUSHALL",
        "FLUSHDB",
        "GET",
        "INFO",
        "KEYS",
        "MIGRATE",
        "MODULE",
        "PERSIST",
        "REPLICAOF",
        "RESTORE",
        "SCAN",
        "SHUTDOWN",
        "TTL",
        "UNLINK",
    }
)


class QualificationError(RuntimeError):
    """A typed, sanitized qualification failure."""


class RunMode(StrEnum):
    PLAN = "plan"
    LIVE_PREFLIGHT = "live_preflight"
    LIVE_FAILOVER = "live_failover"


class EvidenceClass(StrEnum):
    SYNTHETIC = "SYNTHETIC"
    LIVE = "LIVE"


class GateState(StrEnum):
    NOT_RUN = "NOT_RUN"
    PASS = "PASS"  # noqa: S105 - proof state, not a credential
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    UNCERTAIN = "UNCERTAIN"


class OverallState(StrEnum):
    PLAN_ONLY = "PLAN_ONLY"
    READY_FOR_AUTHORIZED_LIVE_QUALIFICATION = "READY_FOR_AUTHORIZED_LIVE_QUALIFICATION"
    LIVE_QUALIFICATION_FAILED = "LIVE_QUALIFICATION_FAILED"
    LIVE_REDIS_QUALIFIED = "LIVE_REDIS_QUALIFIED"


@dataclass(frozen=True)
class AuthorizationProof:
    """Caller-supplied authorization fact; never a credential or permit token."""

    allowed: bool
    scope: str
    expires_at: int
    evidence_sha256: str


@dataclass(frozen=True)
class PolicySnapshot:
    target_fingerprint: str
    topology_epoch: str
    role: str
    maxmemory_policy: str
    aof_enabled: bool
    aof_last_write_status: str
    appendfsync: str
    loading: bool
    connected_replicas: int
    sync_in_progress: bool
    evicted_keys: int
    writer_identity_id: str
    observer_identity_id: str
    writer_tls_verified: bool
    observer_tls_verified: bool
    acl_set_prefix_allowed: bool
    acl_denied_commands: frozenset[str]
    observer_write_denied: bool


class WriterSession(Protocol):
    client_id: str
    instance_id: str
    target_fingerprint: str
    topology_epoch: str

    def set_once(self, *, key: str, ttl_seconds: int) -> bool | None: ...

    def wait_replicas(self, *, replicas: int, timeout_ms: int) -> int: ...

    def close(self) -> None: ...


class WriterFactory(Protocol):
    def open(self, *, expected_topology_epoch: str) -> WriterSession: ...


class Observer(Protocol):
    def snapshot(self) -> PolicySnapshot: ...


class FailoverController(Protocol):
    def trigger(self, *, expected_topology_epoch: str) -> str: ...

    def wait_complete(self, *, operation_ref: str, timeout_seconds: int) -> bool: ...


class AuthorizationVerifier(Protocol):
    """Trusted verifier for a target-bound, single-use authority receipt."""

    def verify(self, proof: AuthorizationProof, config: RunnerConfig) -> bool: ...


class LiveEvidenceVerifier(Protocol):
    """Trusted attestor; public configuration cannot mint live provenance."""

    def verify(self, *, config: RunnerConfig, snapshot: PolicySnapshot) -> bool: ...


@dataclass(frozen=True)
class RunnerConfig:
    mode: RunMode = RunMode.PLAN
    evidence_class: EvidenceClass = EvidenceClass.SYNTHETIC
    target_fingerprint: str = "UNBOUND"
    key_prefix: str = "modisa:webhook:nonce:v1:"
    ttl_seconds: int = 601
    required_replicas: int = 1
    wait_timeout_ms: int = 5000
    max_failover_seconds: int = 120
    failover_safety_seconds: int = 30
    source_hashes: Mapping[str, str] | None = None


@dataclass(frozen=True)
class GateResult:
    state: GateState
    observed_at: str
    code: str
    evidence_digest: str


def _normalize(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted((_normalize(item) for item in value), key=str)
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def canonical_json(value: object) -> bytes:
    return json.dumps(_normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def seal_receipt(payload: Mapping[str, object]) -> dict[str, object]:
    normalized = dict(payload)
    return {
        "schema_version": "1.0",
        "receipt_type": "MODISA_REDIS_QUALIFICATION",
        "payload": normalized,
        "payload_sha256": hashlib.sha256(canonical_json(normalized)).hexdigest(),
    }


def verify_receipt(envelope: Mapping[str, object]) -> bool:
    if set(envelope) != {"schema_version", "receipt_type", "payload", "payload_sha256"}:
        return False
    if envelope.get("schema_version") != "1.0":
        return False
    if envelope.get("receipt_type") != "MODISA_REDIS_QUALIFICATION":
        return False
    payload = envelope.get("payload")
    digest = envelope.get("payload_sha256")
    return isinstance(payload, dict) and isinstance(digest, str) and hashlib.sha256(
        canonical_json(payload)
    ).hexdigest() == digest


def write_receipt(path: Path, envelope: Mapping[str, object]) -> None:
    """Atomically create a mode-0600 receipt without following symlinks or overwriting."""
    if not verify_receipt(envelope):
        raise QualificationError("RECEIPT_INVALID")
    parent = path.parent.resolve(strict=True)
    if path.exists() or path.is_symlink():
        raise QualificationError("RECEIPT_TARGET_EXISTS")
    temporary = parent / f".{path.name}.{os.getpid()}.{secrets.token_hex(6)}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(temporary, flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(canonical_json(envelope) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        if stat.S_IMODE(temporary.stat().st_mode) != 0o600:
            raise QualificationError("RECEIPT_MODE_UNSAFE")
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError as exc:
            raise QualificationError("RECEIPT_TARGET_EXISTS") from exc
        directory_fd = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


class RedisQualificationRunner:
    """Runs only the phases explicitly authorized by ``RunnerConfig.mode``."""

    def __init__(
        self,
        config: RunnerConfig,
        *,
        writer_factory: WriterFactory | None = None,
        observer: Observer | None = None,
        controller: FailoverController | None = None,
        clock: Callable[[], int] = lambda: int(time.time()),
        run_id_factory: Callable[[], str] = lambda: secrets.token_hex(16),
        nonce_factory: Callable[[], str] = lambda: secrets.token_hex(32),
        authorization_verifier: AuthorizationVerifier | None = None,
        live_evidence_verifier: LiveEvidenceVerifier | None = None,
    ) -> None:
        self.config = config
        self.writer_factory = writer_factory
        self.observer = observer
        self.controller = controller
        self.clock = clock
        self.run_id_factory = run_id_factory
        self.nonce_factory = nonce_factory
        self.authorization_verifier = authorization_verifier
        self.live_evidence_verifier = live_evidence_verifier
        self.gates: dict[str, GateResult] = {}
        self.external_effects = 0

    def _timestamp(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.clock()))

    def _gate(self, name: str, state: GateState, code: str, evidence: object) -> None:
        self.gates[name] = GateResult(state, self._timestamp(), code, _digest(evidence))

    def _effect_attempt(self) -> None:
        if self.config.evidence_class is EvidenceClass.LIVE:
            self.external_effects += 1

    def _base_payload(
        self, *, run_id: str, started_at: str, overall: OverallState, blockers: list[str]
    ) -> dict[str, object]:
        return {
            "run_id": run_id,
            "started_at": started_at,
            "ended_at": self._timestamp(),
            "mode": self.config.mode.value,
            "evidence_class": self.config.evidence_class.value,
            "package_version": __version__,
            "deployment_state": "NOT_DEPLOYED",
            "target_fingerprint": self.config.target_fingerprint,
            "identity_roles": ["restricted_nonce_writer", "read_only_observer", "external_controller"],
            "source_hashes": dict(sorted((self.config.source_hashes or {}).items())),
            "gates": {name: asdict(result) for name, result in sorted(self.gates.items())},
            "overall_state": overall.value,
            "provider_proven": overall is OverallState.LIVE_REDIS_QUALIFIED,
            "blockers": blockers,
            "external_effects_count": self.external_effects,
        }

    def _finish(
        self, *, run_id: str, started_at: str, overall: OverallState, blockers: list[str]
    ) -> dict[str, object]:
        return seal_receipt(
            self._base_payload(
                run_id=run_id, started_at=started_at, overall=overall, blockers=blockers
            )
        )

    def _static_validate(self) -> list[str]:
        blockers: list[str] = []
        if self.config.mode is not RunMode.PLAN and TARGET_FINGERPRINT.fullmatch(
            self.config.target_fingerprint
        ) is None:
            blockers.append("TARGET_FINGERPRINT_INVALID")
        if self.config.key_prefix != "modisa:webhook:nonce:v1:":
            blockers.append("KEY_PREFIX_INVALID")
        if type(self.config.ttl_seconds) is not int or self.config.ttl_seconds < 1:
            blockers.append("TTL_INVALID")
        if self.config.required_replicas < 1:
            blockers.append("REPLICA_REQUIREMENT_INVALID")
        if self.config.wait_timeout_ms < 1:
            blockers.append("WAIT_TIMEOUT_INVALID")
        hashes = self.config.source_hashes or {}
        if not hashes or any(SHA256.fullmatch(value) is None for value in hashes.values()):
            blockers.append("SOURCE_HASHES_INVALID")
        return blockers

    def _authorize(self, authorization: AuthorizationProof | None) -> str | None:
        expected = (
            "redis_live_preflight"
            if self.config.mode is RunMode.LIVE_PREFLIGHT
            else "redis_live_failover"
        )
        if authorization is None or not authorization.allowed:
            return "AUTHORITY_REQUIRED"
        if authorization.scope != expected or authorization.expires_at <= self.clock():
            return "AUTHORITY_SCOPE_OR_EXPIRY_INVALID"
        if SHA256.fullmatch(authorization.evidence_sha256) is None:
            return "AUTHORITY_EVIDENCE_INVALID"
        if self.authorization_verifier is None:
            return "AUTHORITY_VERIFIER_REQUIRED"
        try:
            if not self.authorization_verifier.verify(authorization, self.config):
                return "AUTHORITY_PROOF_UNTRUSTED"
        except Exception:
            return "AUTHORITY_VERIFICATION_UNAVAILABLE"
        return None

    def _policy_blockers(self, snapshot: PolicySnapshot) -> list[str]:
        blockers: list[str] = []
        if snapshot.target_fingerprint != self.config.target_fingerprint:
            blockers.append("TARGET_BINDING_MISMATCH")
        if not snapshot.writer_tls_verified or not snapshot.observer_tls_verified:
            blockers.append("TLS_VALIDATION_UNPROVEN")
        if (
            not snapshot.writer_identity_id
            or not snapshot.observer_identity_id
            or snapshot.writer_identity_id == snapshot.observer_identity_id
        ):
            blockers.append("IDENTITY_SEPARATION_UNPROVEN")
        if snapshot.maxmemory_policy != "noeviction":
            blockers.append("NOEVICTION_REQUIRED")
        if not snapshot.aof_enabled or snapshot.aof_last_write_status != "ok":
            blockers.append("AOF_UNHEALTHY")
        if snapshot.appendfsync not in {"always", "everysec"} or snapshot.loading:
            blockers.append("PERSISTENCE_POLICY_UNSAFE")
        if snapshot.role != "master" or snapshot.sync_in_progress:
            blockers.append("PRIMARY_TOPOLOGY_UNHEALTHY")
        if snapshot.connected_replicas < self.config.required_replicas:
            blockers.append("REPLICA_COUNT_INSUFFICIENT")
        if not snapshot.acl_set_prefix_allowed:
            blockers.append("WRITER_SET_PREFIX_UNPROVEN")
        if not snapshot.observer_write_denied:
            blockers.append("OBSERVER_WRITE_DENIAL_UNPROVEN")
        missing_denials = REQUIRED_DENIALS - snapshot.acl_denied_commands
        if missing_denials:
            blockers.append("WRITER_DENIAL_MATRIX_INCOMPLETE")
        return blockers

    def _open_writer(self, epoch: str) -> WriterSession:
        if self.writer_factory is None:
            raise QualificationError("WRITER_FACTORY_REQUIRED")
        writer = self.writer_factory.open(expected_topology_epoch=epoch)
        if (
            writer.target_fingerprint != self.config.target_fingerprint
            or writer.topology_epoch != epoch
        ):
            writer.close()
            raise QualificationError("WRITER_BINDING_MISMATCH")
        return writer

    def _canary_key(self) -> str:
        material = self.nonce_factory()
        return self.config.key_prefix + hashlib.sha256(material.encode("utf-8")).hexdigest()

    def run(self, authorization: AuthorizationProof | None = None) -> dict[str, object]:
        run_id = self.run_id_factory()
        started_at = self._timestamp()
        blockers = self._static_validate()
        if blockers:
            self._gate("static_validation", GateState.FAIL, "STATIC_INVALID", blockers)
            return self._finish(
                run_id=run_id,
                started_at=started_at,
                overall=OverallState.LIVE_QUALIFICATION_FAILED,
                blockers=blockers,
            )
        self._gate("static_validation", GateState.PASS, "STATIC_VALID", {"version": __version__})
        if self.config.mode is RunMode.PLAN:
            for name in (
                "authorization",
                "baseline_policy",
                "two_instance_replay",
                "replication_ack",
                "authorized_failover",
                "topology_rebind",
                "post_failover_replay",
            ):
                self._gate(name, GateState.NOT_RUN, "PLAN_ONLY", name)
            return self._finish(
                run_id=run_id,
                started_at=started_at,
                overall=OverallState.PLAN_ONLY,
                blockers=["LIVE_AUTHORITY_AND_RUNTIME_REQUIRED"],
            )

        authorization_blocker = self._authorize(authorization)
        if authorization_blocker:
            self._gate("authorization", GateState.BLOCKED, authorization_blocker, "blocked")
            return self._finish(
                run_id=run_id,
                started_at=started_at,
                overall=OverallState.LIVE_QUALIFICATION_FAILED,
                blockers=[authorization_blocker],
            )
        assert authorization is not None
        self._gate("authorization", GateState.PASS, "AUTHORITY_BOUND", authorization.scope)
        if self.observer is None or self.writer_factory is None:
            self._gate("baseline_policy", GateState.BLOCKED, "RUNTIME_ADAPTER_REQUIRED", "missing")
            return self._finish(
                run_id=run_id,
                started_at=started_at,
                overall=OverallState.LIVE_QUALIFICATION_FAILED,
                blockers=["RUNTIME_ADAPTER_REQUIRED"],
            )

        try:
            baseline = self.observer.snapshot()
        except Exception:
            self._gate("baseline_policy", GateState.UNCERTAIN, "OBSERVER_UNAVAILABLE", "sanitized")
            return self._finish(
                run_id=run_id,
                started_at=started_at,
                overall=OverallState.LIVE_QUALIFICATION_FAILED,
                blockers=["OBSERVER_UNAVAILABLE"],
            )
        policy_blockers = self._policy_blockers(baseline)
        if policy_blockers:
            self._gate("baseline_policy", GateState.FAIL, "POLICY_FAILED", policy_blockers)
            return self._finish(
                run_id=run_id,
                started_at=started_at,
                overall=OverallState.LIVE_QUALIFICATION_FAILED,
                blockers=policy_blockers,
            )
        self._gate("baseline_policy", GateState.PASS, "POLICY_PASSED", asdict(baseline))

        first: WriterSession | None = None
        second: WriterSession | None = None
        try:
            first = self._open_writer(baseline.topology_epoch)
            second = self._open_writer(baseline.topology_epoch)
            if first.client_id == second.client_id or first.instance_id == second.instance_id:
                raise QualificationError("DISTINCT_INSTANCES_REQUIRED")
            key = self._canary_key()
            self._effect_attempt()
            accepted = first.set_once(key=key, ttl_seconds=self.config.ttl_seconds)
            if accepted is not True:
                raise QualificationError("FIRST_CANARY_NOT_ACCEPTED")
            self._effect_attempt()
            replay = second.set_once(key=key, ttl_seconds=self.config.ttl_seconds)
            if replay is not None:
                raise QualificationError("CROSS_CLIENT_REPLAY_NOT_REJECTED")
            self._gate("two_instance_replay", GateState.PASS, "DISTINCT_INSTANCE_REPLAY_PASSED", {"clients": True, "instances": True})
        except QualificationError as error:
            if first is not None:
                first.close()
            self._gate("two_instance_replay", GateState.FAIL, str(error), "sanitized")
            return self._finish(run_id=run_id, started_at=started_at, overall=OverallState.LIVE_QUALIFICATION_FAILED, blockers=[str(error)])
        except Exception:
            if first is not None:
                first.close()
            self._gate("two_instance_replay", GateState.UNCERTAIN, "CANARY_RESULT_UNCERTAIN", "sanitized")
            return self._finish(run_id=run_id, started_at=started_at, overall=OverallState.LIVE_QUALIFICATION_FAILED, blockers=["CANARY_RESULT_UNCERTAIN"])
        finally:
            if second is not None:
                second.close()

        if self.config.mode is RunMode.LIVE_PREFLIGHT:
            if first is not None:
                first.close()
            return self._finish(
                run_id=run_id,
                started_at=started_at,
                overall=OverallState.READY_FOR_AUTHORIZED_LIVE_QUALIFICATION,
                blockers=["AUTHORIZED_FAILOVER_NOT_RUN"],
            )

        required_ttl = self.config.max_failover_seconds + self.config.failover_safety_seconds + 1
        if self.config.ttl_seconds < required_ttl:
            if first is not None:
                first.close()
            self._gate("authorized_failover", GateState.BLOCKED, "FAILOVER_TTL_MARGIN_INSUFFICIENT", required_ttl)
            return self._finish(run_id=run_id, started_at=started_at, overall=OverallState.LIVE_QUALIFICATION_FAILED, blockers=["FAILOVER_TTL_MARGIN_INSUFFICIENT"])
        if self.controller is None:
            if first is not None:
                first.close()
            self._gate("authorized_failover", GateState.BLOCKED, "FAILOVER_CONTROLLER_REQUIRED", "missing")
            return self._finish(run_id=run_id, started_at=started_at, overall=OverallState.LIVE_QUALIFICATION_FAILED, blockers=["FAILOVER_CONTROLLER_REQUIRED"])

        failover_key = self._canary_key()
        try:
            assert first is not None
            self._effect_attempt()
            pre_result = first.set_once(key=failover_key, ttl_seconds=self.config.ttl_seconds)
            if pre_result is not True:
                raise QualificationError("PRE_FAILOVER_CANARY_NOT_ACCEPTED")
            acknowledgements = first.wait_replicas(
                replicas=self.config.required_replicas, timeout_ms=self.config.wait_timeout_ms
            )
            if acknowledgements < self.config.required_replicas:
                self._gate("replication_ack", GateState.FAIL, "REPLICATION_ACK_INSUFFICIENT", acknowledgements)
                raise QualificationError("REPLICATION_ACK_INSUFFICIENT")
            self._gate("replication_ack", GateState.PASS, "REPLICATION_ACK_PASSED", acknowledgements)
            self._effect_attempt()
            operation_ref = self.controller.trigger(expected_topology_epoch=baseline.topology_epoch)
            completed = self.controller.wait_complete(
                operation_ref=operation_ref, timeout_seconds=self.config.max_failover_seconds
            )
            if not completed:
                self._gate("authorized_failover", GateState.UNCERTAIN, "FAILOVER_RESULT_UNCERTAIN", "sanitized")
                raise QualificationError("FAILOVER_RESULT_UNCERTAIN")
            self._gate("authorized_failover", GateState.PASS, "FAILOVER_COMPLETED", "controller")
        except QualificationError as error:
            return self._finish(run_id=run_id, started_at=started_at, overall=OverallState.LIVE_QUALIFICATION_FAILED, blockers=[str(error)])
        except Exception:
            self._gate("authorized_failover", GateState.UNCERTAIN, "FAILOVER_RESULT_UNCERTAIN", "sanitized")
            return self._finish(run_id=run_id, started_at=started_at, overall=OverallState.LIVE_QUALIFICATION_FAILED, blockers=["FAILOVER_RESULT_UNCERTAIN"])
        finally:
            if first is not None:
                first.close()

        try:
            after = self.observer.snapshot()
            post_blockers = self._policy_blockers(after)
            if after.topology_epoch == baseline.topology_epoch:
                post_blockers.append("TOPOLOGY_EPOCH_UNCHANGED")
            if after.evicted_keys > baseline.evicted_keys:
                post_blockers.append("EVICTION_OCCURRED_DURING_CANARY")
            if post_blockers:
                self._gate("topology_rebind", GateState.FAIL, "POST_FAILOVER_POLICY_FAILED", post_blockers)
                return self._finish(run_id=run_id, started_at=started_at, overall=OverallState.LIVE_QUALIFICATION_FAILED, blockers=post_blockers)
            self._gate("topology_rebind", GateState.PASS, "NEW_PRIMARY_BOUND", after.topology_epoch)
            post = self._open_writer(after.topology_epoch)
            try:
                self._effect_attempt()
                replay = post.set_once(key=failover_key, ttl_seconds=self.config.ttl_seconds)
                if replay is True:
                    self._gate("post_failover_replay", GateState.FAIL, "NONCE_LOST_ACROSS_FAILOVER", "lost")
                    return self._finish(run_id=run_id, started_at=started_at, overall=OverallState.LIVE_QUALIFICATION_FAILED, blockers=["NONCE_LOST_ACROSS_FAILOVER"])
                if replay is not None:
                    raise QualificationError("POST_FAILOVER_RESULT_UNCERTAIN")
                self._effect_attempt()
                fresh = post.set_once(key=self._canary_key(), ttl_seconds=self.config.ttl_seconds)
                if fresh is not True:
                    raise QualificationError("POST_FAILOVER_FRESH_WRITE_FAILED")
            finally:
                post.close()
            self._gate("post_failover_replay", GateState.PASS, "NONCE_PRESERVED_ACROSS_FAILOVER", "preserved")
        except QualificationError as error:
            self._gate("post_failover_replay", GateState.UNCERTAIN, str(error), "sanitized")
            return self._finish(run_id=run_id, started_at=started_at, overall=OverallState.LIVE_QUALIFICATION_FAILED, blockers=[str(error)])
        except Exception:
            self._gate("post_failover_replay", GateState.UNCERTAIN, "POST_FAILOVER_RESULT_UNCERTAIN", "sanitized")
            return self._finish(run_id=run_id, started_at=started_at, overall=OverallState.LIVE_QUALIFICATION_FAILED, blockers=["POST_FAILOVER_RESULT_UNCERTAIN"])

        trusted_live = False
        if self.config.evidence_class is EvidenceClass.LIVE and self.live_evidence_verifier:
            try:
                trusted_live = self.live_evidence_verifier.verify(config=self.config, snapshot=after)
            except Exception:
                trusted_live = False
        overall = (
            OverallState.LIVE_REDIS_QUALIFIED
            if trusted_live
            else OverallState.READY_FOR_AUTHORIZED_LIVE_QUALIFICATION
        )
        if trusted_live:
            remaining: list[str] = []
        elif self.config.evidence_class is EvidenceClass.LIVE:
            remaining = ["TRUSTED_LIVE_EVIDENCE_VERIFIER_REQUIRED"]
        else:
            remaining = ["SYNTHETIC_EVIDENCE_ONLY"]
        return self._finish(run_id=run_id, started_at=started_at, overall=overall, blockers=remaining)
