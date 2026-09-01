from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Iterable, Mapping, Sequence

from .creative_graph import CreativeGraph
from .genome import RightsState
from .producer import ProductionPlan


_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_RELEASE_DETECTORS = (
    "IDENTITY",
    "RIGHTS",
    "CONSENT",
    "QA",
    "PROVENANCE",
    "POLICY",
)


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _clean(value: str, *, field: str) -> str:
    item = str(value).strip()
    if not item:
        raise ValueError(f"{field} is required")
    return item


def _clean_tuple(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(item).strip() for item in values if str(item).strip()}))


class ConsentState(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class ReleaseSignalState(str, Enum):
    PASS = "PASS"
    HOLD = "HOLD"
    FAIL = "FAIL"


class PreReleaseState(str, Enum):
    HOLD_MISSING_DETECTOR = "HOLD_MISSING_DETECTOR"
    HOLD_SIGNAL = "HOLD_SIGNAL"
    HOLD_OWNER_RELEASE = "HOLD_OWNER_RELEASE"
    QUARANTINED_TRUSTED_SIGNAL = "QUARANTINED_TRUSTED_SIGNAL"
    PACKAGE_ELIGIBLE = "PACKAGE_ELIGIBLE"


class DuplicateState(str, Enum):
    UNIQUE = "UNIQUE"
    EXACT_MATCH = "EXACT_MATCH"
    PERCEPTUAL_MATCH = "PERCEPTUAL_MATCH"


@dataclass(frozen=True, slots=True)
class AssetFingerprint:
    schema: str
    asset_id: str
    mission_id: str
    graph_node_id: str
    version_id: str
    content_sha256: str
    perceptual_fingerprint: str
    source_ref: str
    provider_id: str
    parent_asset_ids: tuple[str, ...]
    fingerprint_sha256: str
    external_effect_performed: bool = False


@dataclass(frozen=True, slots=True)
class DuplicateDecision:
    state: DuplicateState
    candidate_asset_id: str
    matched_asset_ids: tuple[str, ...]
    exact_content_match: bool
    perceptual_match: bool
    external_effect_performed: bool = False


def build_asset_fingerprint(
    *,
    asset_id: str,
    mission_id: str,
    graph_node_id: str,
    version_id: str,
    content: bytes,
    source_ref: str,
    provider_id: str = "",
    perceptual_fingerprint: str = "",
    parent_asset_ids: Iterable[str] = (),
) -> AssetFingerprint:
    """Build a deterministic lineage fingerprint for one creative asset.

    The exact content hash is computed locally. A perceptual fingerprint is optional
    and must be supplied by a suitable media fingerprinting implementation; this
    stdlib kernel does not pretend a byte hash is a perceptual hash.
    """

    aid = _clean(asset_id, field="asset_id")
    mission = _clean(mission_id, field="mission_id")
    node = _clean(graph_node_id, field="graph_node_id")
    version = _clean(version_id, field="version_id")
    source = _clean(source_ref, field="source_ref")
    if not isinstance(content, (bytes, bytearray)) or not content:
        raise ValueError("content must be non-empty bytes")
    perceptual = str(perceptual_fingerprint).strip().lower()
    if perceptual and len(perceptual) < 8:
        raise ValueError("perceptual_fingerprint is too short")
    base = {
        "schema": "SOVARA_SC_ASSET_FINGERPRINT_V1",
        "asset_id": aid,
        "mission_id": mission,
        "graph_node_id": node,
        "version_id": version,
        "content_sha256": sha256(bytes(content)).hexdigest(),
        "perceptual_fingerprint": perceptual,
        "source_ref": source,
        "provider_id": str(provider_id).strip(),
        "parent_asset_ids": list(_clean_tuple(parent_asset_ids)),
        "external_effect_performed": False,
    }
    return AssetFingerprint(
        schema=base["schema"],
        asset_id=aid,
        mission_id=mission,
        graph_node_id=node,
        version_id=version,
        content_sha256=base["content_sha256"],
        perceptual_fingerprint=perceptual,
        source_ref=source,
        provider_id=base["provider_id"],
        parent_asset_ids=tuple(base["parent_asset_ids"]),
        fingerprint_sha256=_digest(base),
        external_effect_performed=False,
    )


def detect_duplicate(
    candidate: AssetFingerprint,
    known_assets: Iterable[AssetFingerprint],
) -> DuplicateDecision:
    exact: list[str] = []
    perceptual: list[str] = []
    for known in known_assets:
        if known.asset_id == candidate.asset_id:
            continue
        if known.content_sha256 == candidate.content_sha256:
            exact.append(known.asset_id)
        elif (
            candidate.perceptual_fingerprint
            and known.perceptual_fingerprint
            and known.perceptual_fingerprint == candidate.perceptual_fingerprint
        ):
            perceptual.append(known.asset_id)
    if exact:
        return DuplicateDecision(
            DuplicateState.EXACT_MATCH,
            candidate.asset_id,
            tuple(sorted(exact)),
            True,
            bool(perceptual),
        )
    if perceptual:
        return DuplicateDecision(
            DuplicateState.PERCEPTUAL_MATCH,
            candidate.asset_id,
            tuple(sorted(perceptual)),
            False,
            True,
        )
    return DuplicateDecision(
        DuplicateState.UNIQUE,
        candidate.asset_id,
        (),
        False,
        False,
    )


@dataclass(frozen=True, slots=True)
class RightsGrant:
    grant_id: str
    subject_id: str
    graph_node_id: str
    rights_state: RightsState
    consent_state: ConsentState
    identity_verified: bool
    allowed_channels: tuple[str, ...]
    allowed_uses: tuple[str, ...]
    evidence_ref: str


@dataclass(frozen=True, slots=True)
class RightsDecision:
    eligible: bool
    graph_node_id: str
    channel: str
    use: str
    grant_ids: tuple[str, ...]
    blocking_grant_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    external_effect_performed: bool = False


@dataclass(frozen=True, slots=True)
class RightsImpactReceipt:
    subject_id: str
    direct_node_ids: tuple[str, ...]
    invalidated_node_ids: tuple[str, ...]
    blocked_locked_node_ids: tuple[str, ...]
    authority_inherited: bool = False
    external_effect_performed: bool = False


class RightsConsentGraph:
    """Identity/rights/consent bindings attached to SOVARA creative graph nodes."""

    def __init__(self) -> None:
        self._grants: dict[str, RightsGrant] = {}

    def bind(self, grant: RightsGrant) -> None:
        gid = _clean(grant.grant_id, field="grant_id")
        if gid in self._grants:
            raise ValueError(f"duplicate grant_id: {gid}")
        if not grant.evidence_ref.strip():
            raise ValueError("evidence_ref is required")
        if not grant.subject_id.strip() or not grant.graph_node_id.strip():
            raise ValueError("subject_id and graph_node_id are required")
        self._grants[gid] = RightsGrant(
            grant_id=gid,
            subject_id=grant.subject_id.strip(),
            graph_node_id=grant.graph_node_id.strip(),
            rights_state=grant.rights_state,
            consent_state=grant.consent_state,
            identity_verified=bool(grant.identity_verified),
            allowed_channels=_clean_tuple(grant.allowed_channels),
            allowed_uses=_clean_tuple(grant.allowed_uses),
            evidence_ref=grant.evidence_ref.strip(),
        )

    def grants(self) -> tuple[RightsGrant, ...]:
        return tuple(self._grants[key] for key in sorted(self._grants))

    def update_consent(
        self,
        grant_id: str,
        *,
        consent_state: ConsentState,
        evidence_ref: str,
    ) -> None:
        gid = _clean(grant_id, field="grant_id")
        old = self._grants.get(gid)
        if old is None:
            raise ValueError(f"unknown grant_id: {gid}")
        evidence = _clean(evidence_ref, field="evidence_ref")
        self._grants[gid] = RightsGrant(
            grant_id=old.grant_id,
            subject_id=old.subject_id,
            graph_node_id=old.graph_node_id,
            rights_state=old.rights_state,
            consent_state=consent_state,
            identity_verified=old.identity_verified,
            allowed_channels=old.allowed_channels,
            allowed_uses=old.allowed_uses,
            evidence_ref=evidence,
        )

    def evaluate(self, graph_node_id: str, *, channel: str, use: str) -> RightsDecision:
        node = _clean(graph_node_id, field="graph_node_id")
        ch = _clean(channel, field="channel").lower()
        use_name = _clean(use, field="use").lower()
        grants = tuple(item for item in self.grants() if item.graph_node_id == node)
        if not grants:
            return RightsDecision(True, node, ch, use_name, (), (), ("NO_SUBJECT_BINDINGS",))

        blockers: list[str] = []
        reasons: list[str] = []
        for grant in grants:
            if not grant.identity_verified:
                blockers.append(grant.grant_id)
                reasons.append(f"IDENTITY_UNVERIFIED:{grant.grant_id}")
            if grant.rights_state not in {RightsState.VERIFIED, RightsState.NOT_APPLICABLE}:
                blockers.append(grant.grant_id)
                reasons.append(f"RIGHTS_{grant.rights_state.value}:{grant.grant_id}")
            if grant.consent_state not in {ConsentState.VERIFIED, ConsentState.NOT_REQUIRED}:
                blockers.append(grant.grant_id)
                reasons.append(f"CONSENT_{grant.consent_state.value}:{grant.grant_id}")
            if grant.allowed_channels and ch not in grant.allowed_channels:
                blockers.append(grant.grant_id)
                reasons.append(f"CHANNEL_NOT_ALLOWED:{grant.grant_id}")
            if grant.allowed_uses and use_name not in grant.allowed_uses:
                blockers.append(grant.grant_id)
                reasons.append(f"USE_NOT_ALLOWED:{grant.grant_id}")
        unique_blockers = tuple(sorted(set(blockers)))
        return RightsDecision(
            eligible=not unique_blockers,
            graph_node_id=node,
            channel=ch,
            use=use_name,
            grant_ids=tuple(item.grant_id for item in grants),
            blocking_grant_ids=unique_blockers,
            reasons=tuple(sorted(set(reasons))) if reasons else ("RIGHTS_AND_CONSENT_VERIFIED",),
        )

    def impact_for_subject(self, graph: CreativeGraph, subject_id: str) -> RightsImpactReceipt:
        subject = _clean(subject_id, field="subject_id")
        direct = tuple(sorted({item.graph_node_id for item in self.grants() if item.subject_id == subject}))
        if not direct:
            return RightsImpactReceipt(subject, (), (), ())
        impact = graph.impact(direct)
        return RightsImpactReceipt(
            subject_id=subject,
            direct_node_ids=direct,
            invalidated_node_ids=impact.invalidated_node_ids,
            blocked_locked_node_ids=impact.blocked_locked_node_ids,
        )


@dataclass(frozen=True, slots=True)
class ReleaseSignal:
    detector: str
    state: ReleaseSignalState
    evidence_ref: str
    trusted: bool = False
    critical: bool = False


@dataclass(frozen=True, slots=True)
class PreReleaseDecision:
    state: PreReleaseState
    asset_id: str
    missing_detectors: tuple[str, ...]
    blocking_detectors: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    owner_release_observed: bool
    package_eligible: bool
    publication_authorized: bool = False
    provider_effect_authorized: bool = False
    external_effect_performed: bool = False


def evaluate_pre_release(
    *,
    asset: AssetFingerprint,
    signals: Sequence[ReleaseSignal],
    owner_release_observed: bool,
    required_detectors: Sequence[str] = _REQUIRED_RELEASE_DETECTORS,
) -> PreReleaseDecision:
    by_detector: dict[str, ReleaseSignal] = {}
    for signal in signals:
        detector = _clean(signal.detector, field="detector").upper()
        if detector in by_detector:
            raise ValueError(f"duplicate release detector: {detector}")
        if not signal.evidence_ref.strip():
            raise ValueError(f"evidence_ref is required for {detector}")
        by_detector[detector] = ReleaseSignal(
            detector=detector,
            state=signal.state,
            evidence_ref=signal.evidence_ref.strip(),
            trusted=bool(signal.trusted),
            critical=bool(signal.critical),
        )

    trusted_failures = tuple(
        sorted(
            detector
            for detector, signal in by_detector.items()
            if signal.trusted and signal.critical and signal.state is ReleaseSignalState.FAIL
        )
    )
    evidence = tuple(sorted({signal.evidence_ref for signal in by_detector.values()}))
    if trusted_failures:
        return PreReleaseDecision(
            PreReleaseState.QUARANTINED_TRUSTED_SIGNAL,
            asset.asset_id,
            (),
            trusted_failures,
            evidence,
            bool(owner_release_observed),
            False,
        )

    required = tuple(sorted({_clean(item, field="required_detector").upper() for item in required_detectors}))
    missing = tuple(detector for detector in required if detector not in by_detector)
    if missing:
        return PreReleaseDecision(
            PreReleaseState.HOLD_MISSING_DETECTOR,
            asset.asset_id,
            missing,
            (),
            evidence,
            bool(owner_release_observed),
            False,
        )

    blocking = tuple(
        sorted(
            detector
            for detector in required
            if by_detector[detector].state is not ReleaseSignalState.PASS
        )
    )
    if blocking:
        return PreReleaseDecision(
            PreReleaseState.HOLD_SIGNAL,
            asset.asset_id,
            (),
            blocking,
            evidence,
            bool(owner_release_observed),
            False,
        )
    if not owner_release_observed:
        return PreReleaseDecision(
            PreReleaseState.HOLD_OWNER_RELEASE,
            asset.asset_id,
            (),
            (),
            evidence,
            False,
            False,
        )
    return PreReleaseDecision(
        PreReleaseState.PACKAGE_ELIGIBLE,
        asset.asset_id,
        (),
        (),
        evidence,
        True,
        True,
        publication_authorized=False,
        provider_effect_authorized=False,
        external_effect_performed=False,
    )


@dataclass(frozen=True, slots=True)
class AsyncMediaWorkPacket:
    schema: str
    mission_id: str
    production_plan_sha256: str
    selected_step_ids: tuple[str, ...]
    heavy_modalities: tuple[str, ...]
    idempotency_key: str
    max_attempts: int
    queue_class: str
    provider_execution_authorized: bool = False
    external_effect_performed: bool = False


def compile_async_media_work_packet(
    plan: ProductionPlan,
    *,
    heavy_modalities: Iterable[str] = ("video", "audio"),
    max_attempts: int = 3,
) -> AsyncMediaWorkPacket:
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    if plan.authority_inherited or plan.provider_execution_performed or plan.external_effect_performed:
        raise ValueError("effectful production plan is not admissible")
    if any(step.provider_execution_allowed for step in plan.steps):
        raise ValueError("provider-enabled production step is not admissible")
    modalities = _clean_tuple(item.lower() for item in heavy_modalities)
    actions = {f"PREPARE_{item.upper()}_WORK_PACKET" for item in modalities}
    selected = tuple(step.step_id for step in plan.steps if step.action in actions)
    base = {
        "schema": "SOVARA_SC_ASYNC_MEDIA_WORK_PACKET_V1",
        "mission_id": plan.mission_id,
        "production_plan_sha256": plan.plan_sha256,
        "selected_step_ids": list(selected),
        "heavy_modalities": list(modalities),
        "max_attempts": int(max_attempts),
        "queue_class": "HEAVY_MEDIA",
        "provider_execution_authorized": False,
        "external_effect_performed": False,
    }
    return AsyncMediaWorkPacket(
        schema=base["schema"],
        mission_id=plan.mission_id,
        production_plan_sha256=plan.plan_sha256,
        selected_step_ids=selected,
        heavy_modalities=modalities,
        idempotency_key=_digest(base),
        max_attempts=int(max_attempts),
        queue_class="HEAVY_MEDIA",
        provider_execution_authorized=False,
        external_effect_performed=False,
    )


@dataclass(frozen=True, slots=True)
class PerformanceObservation:
    observation_id: str
    asset_id: str
    tags: tuple[str, ...]
    reward: float
    sequence: int
    source: str = "OBSERVED_PERFORMANCE"
    synthetic: bool = False


@dataclass(frozen=True, slots=True)
class DiscoveryRecommendation:
    tag: str
    score: float
    observation_count: int


@dataclass(frozen=True, slots=True)
class DiscoveryReceipt:
    schema: str
    eligible_observation_count: int
    recommendation_count: int
    recommendations: tuple[DiscoveryRecommendation, ...]
    learning_ready: bool
    state_sha256: str
    authority_inherited: bool = False
    external_effect_performed: bool = False


class CreativeDiscoveryGraph:
    """Bounded performance-learning graph for content tags.

    Synthetic observations are retained for tests but excluded from promoted
    recommendations. The graph never publishes, routes spend, or mutates creative
    state by itself; it emits evidence that SC-PRODUCER/CFBE may challenge later.
    """

    def __init__(self, *, min_observations: int = 2) -> None:
        if min_observations < 1:
            raise ValueError("min_observations must be positive")
        self.min_observations = int(min_observations)
        self._observations: dict[str, PerformanceObservation] = {}

    def observe(self, observation: PerformanceObservation) -> None:
        oid = _clean(observation.observation_id, field="observation_id")
        if oid in self._observations:
            raise ValueError(f"duplicate observation_id: {oid}")
        if not -1.0 <= float(observation.reward) <= 1.0:
            raise ValueError("reward must be in [-1, 1]")
        if observation.sequence < 0:
            raise ValueError("sequence must be non-negative")
        tags = _clean_tuple(item.lower() for item in observation.tags)
        if not tags:
            raise ValueError("at least one tag is required")
        self._observations[oid] = PerformanceObservation(
            observation_id=oid,
            asset_id=_clean(observation.asset_id, field="asset_id"),
            tags=tags,
            reward=float(observation.reward),
            sequence=int(observation.sequence),
            source=_clean(observation.source, field="source"),
            synthetic=bool(observation.synthetic),
        )

    def observations(self) -> tuple[PerformanceObservation, ...]:
        return tuple(sorted(self._observations.values(), key=lambda item: (item.sequence, item.observation_id)))

    def receipt(self, *, limit: int = 10) -> DiscoveryReceipt:
        if limit < 1:
            raise ValueError("limit must be positive")
        eligible = tuple(item for item in self.observations() if not item.synthetic)
        scores: dict[str, list[float]] = {}
        for item in eligible:
            for tag in item.tags:
                scores.setdefault(tag, []).append(item.reward)
        recommendations = tuple(
            DiscoveryRecommendation(
                tag=tag,
                score=round(sum(values) / len(values), 12),
                observation_count=len(values),
            )
            for tag, values in sorted(
                scores.items(),
                key=lambda item: (-sum(item[1]) / len(item[1]), item[0]),
            )
            if len(values) >= self.min_observations
        )[:limit]
        state = {
            "schema": "SOVARA_SC_DISCOVERY_GRAPH_RECEIPT_V1",
            "eligible_observation_count": len(eligible),
            "recommendations": [
                {
                    "tag": item.tag,
                    "score": item.score,
                    "observation_count": item.observation_count,
                }
                for item in recommendations
            ],
            "learning_ready": bool(recommendations),
            "authority_inherited": False,
            "external_effect_performed": False,
        }
        return DiscoveryReceipt(
            schema=state["schema"],
            eligible_observation_count=len(eligible),
            recommendation_count=len(recommendations),
            recommendations=recommendations,
            learning_ready=bool(recommendations),
            state_sha256=_digest(state),
            authority_inherited=False,
            external_effect_performed=False,
        )
