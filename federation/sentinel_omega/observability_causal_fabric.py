from __future__ import annotations

"""Sentinel Ω Observability & Causal Intelligence Fabric.

A deterministic, provider-neutral composition layer over Federation Living State.
It normalizes heterogeneous observations, detects robust metric anomalies, clusters
incident signals, ranks probable origins using topology/change evidence, evaluates
multi-window SLO burn, and emits A1-internal remediation candidates for the
existing Autonomic Mission Fabric.

It does not ingest live provider telemetry by itself, execute repairs, confer
authority, or turn probable-origin rankings into verified causal claims.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
import json
import math
import statistics
from typing import Any, Iterable, Mapping, Sequence

from federation.living_state.evolution_intelligence import FederationEvolutionIntelligence
from federation.living_state.model import LivingWorldModel
from formation_omega.autonomic_fabric import ActionCandidate, AuthorityCeiling

SCHEMA = "SENTINEL-OMEGA-OBSERVABILITY-CAUSAL-FABRIC-V1"
AUTHORITY_CEILING = "A1_INTERNAL"
EXTERNAL_EFFECTS = False


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


class SignalKind(StrEnum):
    METRIC = "METRIC"
    LOG = "LOG"
    TRACE = "TRACE"
    EVENT = "EVENT"
    CHANGE = "CHANGE"
    HEALTH = "HEALTH"
    QUEUE = "QUEUE"
    PROOF = "PROOF"
    OWNER_BURDEN = "OWNER_BURDEN"


@dataclass(frozen=True)
class NormalizedObservation:
    observation_id: str
    source: str
    signal_kind: SignalKind
    target_id: str
    observed_at: str
    fingerprint: str
    severity: float
    proof_refs: tuple[str, ...]
    attributes: Mapping[str, Any] = field(default_factory=dict)
    change_ref: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    external_effect: bool = False

    def validate(self) -> "NormalizedObservation":
        if not self.observation_id.strip() or not self.source.strip() or not self.target_id.strip():
            raise ValueError("observation identity/source/target are required")
        if not self.fingerprint.strip():
            raise ValueError("observation fingerprint is required")
        _time(self.observed_at)
        if not 0 <= float(self.severity) <= 1:
            raise ValueError("severity must be in [0,1]")
        if not self.proof_refs:
            raise ValueError("observation requires proof_refs")
        if self.external_effect:
            raise ValueError("observations cannot execute external effects")
        return self


class SemanticObservationNormalizer:
    """Normalizes provider-specific records into a stable Sentinel semantic shape."""

    _KIND_ALIASES = {
        "metric": SignalKind.METRIC,
        "metrics": SignalKind.METRIC,
        "log": SignalKind.LOG,
        "logs": SignalKind.LOG,
        "trace": SignalKind.TRACE,
        "span": SignalKind.TRACE,
        "event": SignalKind.EVENT,
        "change": SignalKind.CHANGE,
        "deployment": SignalKind.CHANGE,
        "health": SignalKind.HEALTH,
        "queue": SignalKind.QUEUE,
        "proof": SignalKind.PROOF,
        "owner_burden": SignalKind.OWNER_BURDEN,
    }

    @staticmethod
    def _first(record: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
        for key in keys:
            if key in record and record[key] not in (None, ""):
                return record[key]
        return default

    def normalize(self, record: Mapping[str, Any]) -> NormalizedObservation:
        raw_kind = str(self._first(record, "signal_kind", "kind", "type", default="event")).casefold()
        kind = self._KIND_ALIASES.get(raw_kind)
        if kind is None:
            raise ValueError(f"unsupported signal kind: {raw_kind}")
        source = str(self._first(record, "source", "provider", "instrumentation_scope", default="UNKNOWN"))
        target = str(
            self._first(
                record,
                "target_id",
                "service.name",
                "service_name",
                "resource.service.name",
                "component",
                default="",
            )
        )
        observed_at = str(self._first(record, "observed_at", "timestamp", "time", default=""))
        fingerprint = str(
            self._first(
                record,
                "fingerprint",
                "error.type",
                "event_name",
                "name",
                default=f"{kind.value}:{target}",
            )
        )
        severity = float(self._first(record, "severity", "severity_score", "risk", default=0.5))
        proof = self._first(record, "proof_refs", default=None)
        if proof is None:
            single = self._first(record, "proof_ref", "receipt", "source_ref", default="")
            proof_refs = (str(single),) if str(single) else ()
        elif isinstance(proof, str):
            proof_refs = (proof,)
        else:
            proof_refs = tuple(str(x) for x in proof if str(x))
        trace_id = self._first(record, "trace_id", "trace.id", default=None)
        span_id = self._first(record, "span_id", "span.id", default=None)
        change_ref = self._first(record, "change_ref", "deployment_id", "commit_sha", default=None)
        attributes = {
            str(k): v
            for k, v in record.items()
            if k
            not in {
                "observation_id", "source", "provider", "instrumentation_scope", "signal_kind", "kind", "type",
                "target_id", "service.name", "service_name", "resource.service.name", "component",
                "observed_at", "timestamp", "time", "fingerprint", "error.type", "event_name", "name",
                "severity", "severity_score", "risk", "proof_refs", "proof_ref", "receipt", "source_ref",
                "trace_id", "trace.id", "span_id", "span.id", "change_ref", "deployment_id", "commit_sha",
            }
        }
        observation_id = str(self._first(record, "observation_id", default=""))
        if not observation_id:
            observation_id = "OBS-" + _digest(
                {
                    "source": source,
                    "kind": kind.value,
                    "target": target,
                    "observed_at": observed_at,
                    "fingerprint": fingerprint,
                    "trace_id": trace_id,
                    "span_id": span_id,
                }
            )[:20].upper()
        return NormalizedObservation(
            observation_id=observation_id,
            source=source,
            signal_kind=kind,
            target_id=target,
            observed_at=observed_at,
            fingerprint=fingerprint,
            severity=_clip(severity),
            proof_refs=tuple(sorted(set(proof_refs))),
            attributes=attributes,
            change_ref=str(change_ref) if change_ref else None,
            trace_id=str(trace_id) if trace_id else None,
            span_id=str(span_id) if span_id else None,
        ).validate()


@dataclass(frozen=True)
class BaselineAssessment:
    sample_count: int
    median: float
    mad: float
    value: float
    robust_z: float
    anomalous: bool
    threshold: float
    external_effect: bool = False


class AdaptiveBaselineDetector:
    """Robust median/MAD detector suitable for bounded deterministic canaries."""

    def __init__(self, *, minimum_samples: int = 5, z_threshold: float = 3.5) -> None:
        if minimum_samples < 3 or z_threshold <= 0:
            raise ValueError("invalid baseline detector configuration")
        self.minimum_samples = int(minimum_samples)
        self.z_threshold = float(z_threshold)

    def assess(self, history: Sequence[float], value: float) -> BaselineAssessment:
        clean = [float(x) for x in history if math.isfinite(float(x))]
        if len(clean) < self.minimum_samples:
            raise ValueError("insufficient baseline samples")
        median = statistics.median(clean)
        deviations = [abs(x - median) for x in clean]
        mad = statistics.median(deviations)
        if mad <= 1e-12:
            robust_z = 0.0 if abs(float(value) - median) <= 1e-12 else float("inf")
        else:
            robust_z = 0.6745 * abs(float(value) - median) / mad
        return BaselineAssessment(
            sample_count=len(clean),
            median=round(median, 8),
            mad=round(mad, 8),
            value=float(value),
            robust_z=robust_z if math.isinf(robust_z) else round(robust_z, 8),
            anomalous=robust_z >= self.z_threshold,
            threshold=self.z_threshold,
        )


@dataclass(frozen=True)
class IncidentCluster:
    incident_id: str
    observation_ids: tuple[str, ...]
    target_ids: tuple[str, ...]
    fingerprints: tuple[str, ...]
    first_seen: str
    last_seen: str
    severity: float
    change_refs: tuple[str, ...]
    proof_refs: tuple[str, ...]
    external_effect: bool = False


class IncidentCorrelator:
    """Deduplicates repeated observations and groups contextually related signals."""

    def __init__(self, *, window_seconds: int = 300) -> None:
        if window_seconds < 1:
            raise ValueError("window_seconds must be positive")
        self.window_seconds = int(window_seconds)

    @staticmethod
    def _related(left: NormalizedObservation, right: NormalizedObservation, window_seconds: int) -> bool:
        dt = abs((_time(left.observed_at) - _time(right.observed_at)).total_seconds())
        if dt > window_seconds:
            return False
        if left.fingerprint == right.fingerprint:
            return True
        if left.target_id == right.target_id:
            return True
        if left.trace_id and left.trace_id == right.trace_id:
            return True
        if left.change_ref and left.change_ref == right.change_ref:
            return True
        return False

    def cluster(self, observations: Iterable[NormalizedObservation]) -> tuple[IncidentCluster, ...]:
        dedup: dict[str, NormalizedObservation] = {}
        for item in observations:
            item.validate()
            existing = dedup.get(item.observation_id)
            if existing and existing != item:
                raise ValueError(f"conflicting observation replay: {item.observation_id}")
            dedup[item.observation_id] = item
        remaining = sorted(dedup.values(), key=lambda x: (_time(x.observed_at), x.observation_id))
        clusters: list[list[NormalizedObservation]] = []
        while remaining:
            seed = remaining.pop(0)
            group = [seed]
            changed = True
            while changed:
                changed = False
                keep: list[NormalizedObservation] = []
                for candidate in remaining:
                    if any(self._related(candidate, member, self.window_seconds) for member in group):
                        group.append(candidate)
                        changed = True
                    else:
                        keep.append(candidate)
                remaining = keep
            clusters.append(sorted(group, key=lambda x: (_time(x.observed_at), x.observation_id)))
        out = []
        for group in clusters:
            body = {
                "observations": [x.observation_id for x in group],
                "targets": sorted({x.target_id for x in group}),
                "fingerprints": sorted({x.fingerprint for x in group}),
            }
            out.append(
                IncidentCluster(
                    incident_id="INC-" + _digest(body)[:20].upper(),
                    observation_ids=tuple(x.observation_id for x in group),
                    target_ids=tuple(body["targets"]),
                    fingerprints=tuple(body["fingerprints"]),
                    first_seen=group[0].observed_at,
                    last_seen=group[-1].observed_at,
                    severity=round(max(x.severity for x in group), 8),
                    change_refs=tuple(sorted({x.change_ref for x in group if x.change_ref})),
                    proof_refs=tuple(sorted({r for x in group for r in x.proof_refs})),
                )
            )
        return tuple(sorted(out, key=lambda x: (-x.severity, x.first_seen, x.incident_id)))


@dataclass(frozen=True)
class OriginCandidate:
    target_id: str
    score: float
    topology_coverage: float
    direct_signal: float
    change_correlation: float
    proof_density: float
    blast_radius: int
    reasons: tuple[str, ...]
    proof_refs: tuple[str, ...]
    causal_claim: bool = False
    external_effect: bool = False


class CausalOriginRanker:
    """Ranks probable origins without promoting correlation to verified causality."""

    def __init__(self, model: LivingWorldModel) -> None:
        self.model = model
        self.intelligence = FederationEvolutionIntelligence(model)

    def rank(
        self,
        cluster: IncidentCluster,
        observations: Sequence[NormalizedObservation],
    ) -> tuple[OriginCandidate, ...]:
        by_id = {x.observation_id: x for x in observations}
        members = [by_id[x] for x in cluster.observation_ids if x in by_id]
        if not members:
            raise ValueError("cluster observations unavailable")
        nodes = self.model.current_nodes()
        cluster_targets = set(cluster.target_ids)
        candidates: set[str] = {x for x in cluster_targets if x in nodes}
        for nid in nodes:
            try:
                impact = self.intelligence.dependency_impact((nid,))
            except Exception:
                continue
            if cluster_targets.intersection(set(impact.impacted_nodes) | {nid}):
                candidates.add(nid)
        out = []
        for candidate in sorted(candidates):
            try:
                impact = self.intelligence.dependency_impact((candidate,))
                reachable = set(impact.impacted_nodes) | {candidate}
                blast = impact.blast_radius
            except Exception:
                reachable = {candidate}
                blast = 0
            covered = cluster_targets.intersection(reachable)
            topology_coverage = len(covered) / max(1, len(cluster_targets))
            direct_members = [x for x in members if x.target_id == candidate]
            direct_signal = max((x.severity for x in direct_members), default=0.0)
            change_members = [x for x in direct_members if x.signal_kind == SignalKind.CHANGE or x.change_ref]
            if not change_members and cluster.change_refs:
                change_members = [x for x in members if x.change_ref in cluster.change_refs and x.target_id == candidate]
            change_correlation = min(1.0, 0.5 * len(change_members))
            evidence = {r for x in direct_members for r in x.proof_refs}
            proof_density = min(1.0, len(evidence) / 3.0)
            score = (
                0.36 * direct_signal
                + 0.30 * topology_coverage
                + 0.22 * change_correlation
                + 0.12 * proof_density
            )
            reasons = []
            if direct_signal:
                reasons.append("DIRECT_SIGNAL")
            if topology_coverage:
                reasons.append("TOPOLOGY_REACH")
            if change_correlation:
                reasons.append("CHANGE_CORRELATION")
            if proof_density:
                reasons.append("PROOF_DENSITY")
            out.append(
                OriginCandidate(
                    target_id=candidate,
                    score=round(score, 8),
                    topology_coverage=round(topology_coverage, 8),
                    direct_signal=round(direct_signal, 8),
                    change_correlation=round(change_correlation, 8),
                    proof_density=round(proof_density, 8),
                    blast_radius=blast,
                    reasons=tuple(reasons),
                    proof_refs=tuple(sorted(evidence or set(cluster.proof_refs))),
                )
            )
        return tuple(sorted(out, key=lambda x: (-x.score, -x.topology_coverage, x.target_id)))


@dataclass(frozen=True)
class SLOWindowSample:
    window_minutes: int
    total_events: int
    bad_events: int
    target_success_rate: float
    proof_ref: str

    def validate(self) -> "SLOWindowSample":
        if self.window_minutes <= 0 or self.total_events <= 0:
            raise ValueError("SLO window and total_events must be positive")
        if not 0 <= self.bad_events <= self.total_events:
            raise ValueError("bad_events outside total_events")
        if not 0 < self.target_success_rate < 1:
            raise ValueError("target_success_rate must be in (0,1)")
        if not self.proof_ref.strip():
            raise ValueError("SLO sample requires proof_ref")
        return self

    @property
    def burn_rate(self) -> float:
        self.validate()
        observed_error = self.bad_events / self.total_events
        allowed_error = 1.0 - self.target_success_rate
        return observed_error / allowed_error


@dataclass(frozen=True)
class SLOBurnState:
    service_id: str
    windows: tuple[tuple[int, float], ...]
    disposition: str
    max_burn_rate: float
    proof_refs: tuple[str, ...]
    external_effect: bool = False


class MultiWindowSLOGuard:
    """Fail-closed multi-window error-budget burn evaluator."""

    def evaluate(
        self,
        service_id: str,
        samples: Sequence[SLOWindowSample],
        *,
        watch_threshold: float = 1.0,
        fast_burn_threshold: float = 6.0,
    ) -> SLOBurnState:
        if not service_id.strip() or not samples:
            raise ValueError("service_id and samples are required")
        if not 0 < watch_threshold < fast_burn_threshold:
            raise ValueError("invalid SLO thresholds")
        clean = tuple(sorted((x.validate() for x in samples), key=lambda x: x.window_minutes))
        windows = tuple((x.window_minutes, round(x.burn_rate, 8)) for x in clean)
        burns = [x[1] for x in windows]
        burning = sum(1 for x in burns if x >= watch_threshold)
        fast = any(x >= fast_burn_threshold for x in burns)
        if fast and burning >= 2:
            disposition = "FAST_BURN_HOLD_RELEASE"
        elif burning >= 2:
            disposition = "MULTI_WINDOW_BURN"
        elif burning == 1:
            disposition = "WATCH"
        else:
            disposition = "HEALTHY"
        return SLOBurnState(
            service_id=service_id,
            windows=windows,
            disposition=disposition,
            max_burn_rate=max(burns),
            proof_refs=tuple(sorted({x.proof_ref for x in clean})),
        )


class RemediationBridge:
    """Converts probable-origin evidence into A1-internal Autonomic Mission actions."""

    def to_actions(
        self,
        cluster: IncidentCluster,
        origins: Sequence[OriginCandidate],
        *,
        limit: int = 3,
    ) -> tuple[ActionCandidate, ...]:
        if limit < 1:
            raise ValueError("limit must be positive")
        actions = []
        for origin in origins[:limit]:
            info_gain = _clip(0.45 + 0.35 * (1.0 - origin.proof_density))
            risk = _clip(0.10 + 0.15 * origin.change_correlation)
            actions.append(
                ActionCandidate(
                    action_id=f"SENTINEL-{cluster.incident_id}-{origin.target_id}".replace(":", "-"),
                    objective=(
                        f"Falsify probable origin {origin.target_id} for {cluster.incident_id}; "
                        "prepare the smallest reversible repair/canary if supported."
                    ),
                    closure_leverage=_clip(0.45 + 0.45 * origin.score),
                    information_gain=info_gain,
                    success_probability=_clip(0.50 + 0.35 * origin.score),
                    reversibility=0.95,
                    cost=0.05,
                    risk=risk,
                    latency=0.10,
                    unlock_count=max(0, origin.blast_radius),
                    shared_state_key=origin.target_id,
                    authority_ceiling=AuthorityCeiling.A1_INTERNAL,
                    external_effect=False,
                    required_capabilities=(
                        "sentinel-observability-causal-fabric",
                        "proofos",
                        "failure-win",
                    ),
                    evidence_refs=tuple(sorted(set(cluster.proof_refs) | set(origin.proof_refs))),
                )
            )
        return tuple(actions)


@dataclass(frozen=True)
class SentinelAssessment:
    clusters: tuple[IncidentCluster, ...]
    origin_rankings: Mapping[str, tuple[OriginCandidate, ...]]
    slo_states: tuple[SLOBurnState, ...]
    remediation_actions: tuple[ActionCandidate, ...]
    receipt_sha256: str
    truth_boundary: str
    external_effect: bool = False


class SentinelObservabilityCausalFabric:
    """Facade that composes normalization, incident intelligence, topology and SLOs."""

    def __init__(self, model: LivingWorldModel) -> None:
        self.model = model
        self.normalizer = SemanticObservationNormalizer()
        self.correlator = IncidentCorrelator()
        self.ranker = CausalOriginRanker(model)
        self.slo_guard = MultiWindowSLOGuard()
        self.bridge = RemediationBridge()

    def assess(
        self,
        observations: Sequence[NormalizedObservation | Mapping[str, Any]],
        *,
        slo_samples: Mapping[str, Sequence[SLOWindowSample]] | None = None,
    ) -> SentinelAssessment:
        normalized = tuple(
            x.validate() if isinstance(x, NormalizedObservation) else self.normalizer.normalize(x)
            for x in observations
        )
        clusters = self.correlator.cluster(normalized)
        rankings = {cluster.incident_id: self.ranker.rank(cluster, normalized) for cluster in clusters}
        actions = tuple(
            action
            for cluster in clusters
            for action in self.bridge.to_actions(cluster, rankings[cluster.incident_id])
        )
        slo_states = tuple(
            self.slo_guard.evaluate(service_id, samples)
            for service_id, samples in sorted((slo_samples or {}).items())
        )
        body = {
            "schema": SCHEMA,
            "clusters": [x.incident_id for x in clusters],
            "origins": {
                incident_id: [(x.target_id, x.score) for x in rows]
                for incident_id, rows in sorted(rankings.items())
            },
            "slo": [(x.service_id, x.disposition, x.windows) for x in slo_states],
            "actions": [x.action_id for x in actions],
        }
        return SentinelAssessment(
            clusters=clusters,
            origin_rankings=rankings,
            slo_states=slo_states,
            remediation_actions=actions,
            receipt_sha256=_digest(body),
            truth_boundary=(
                "Deterministic internal diagnosis only. Incident grouping and probable-origin rankings are "
                "correlation/topology evidence, not verified causality. Remediation actions are A1-internal "
                "planning candidates and do not execute provider effects or grant authority."
            ),
        )
