from __future__ import annotations

"""Bounded topology-aware incident correlation for Sentinel Ω.

This extension preserves the conservative first-stage IncidentCorrelator and only
merges preliminary clusters when all of these are true:

1. the clusters are temporally close;
2. at least one cluster carries a change or trace context anchor; and
3. Federation Living State proves a dependency path between cluster targets.

Topology alone is never enough to group signals. A topology merge remains
correlation evidence and never upgrades a probable origin into verified causality.
"""

from typing import Any, Mapping, Sequence

from federation.living_state.evolution_intelligence import FederationEvolutionIntelligence
from federation.living_state.model import LivingWorldModel

from .observability_causal_fabric import (
    IncidentCluster,
    NormalizedObservation,
    SentinelAssessment,
    SentinelObservabilityCausalFabric as _BaseSentinelObservabilityCausalFabric,
    SignalKind,
    SLOWindowSample,
    _digest,
    _time,
)


class SentinelObservabilityCausalFabric(_BaseSentinelObservabilityCausalFabric):
    """Public Sentinel Ω facade with bounded topology-aware second-stage grouping."""

    def __init__(self, model: LivingWorldModel) -> None:
        super().__init__(model)
        self._topology = FederationEvolutionIntelligence(model)

    @staticmethod
    def _cluster_members(
        cluster: IncidentCluster,
        by_id: Mapping[str, NormalizedObservation],
    ) -> tuple[NormalizedObservation, ...]:
        return tuple(by_id[item] for item in cluster.observation_ids if item in by_id)

    def _time_close(self, left: IncidentCluster, right: IncidentCluster) -> bool:
        left_start = _time(left.first_seen)
        left_end = _time(left.last_seen)
        right_start = _time(right.first_seen)
        right_end = _time(right.last_seen)
        if right_start > left_end:
            gap = (right_start - left_end).total_seconds()
        elif left_start > right_end:
            gap = (left_start - right_end).total_seconds()
        else:
            gap = 0.0
        return gap <= self.correlator.window_seconds

    @staticmethod
    def _has_context_anchor(members: Sequence[NormalizedObservation]) -> bool:
        return any(
            item.signal_kind == SignalKind.CHANGE or item.change_ref or item.trace_id
            for item in members
        )

    def _topology_connected(self, left_targets: Sequence[str], right_targets: Sequence[str]) -> bool:
        left = set(left_targets)
        right = set(right_targets)
        nodes = self.model.current_nodes()
        for source in sorted(left | right):
            if source not in nodes:
                continue
            try:
                impact = self._topology.dependency_impact((source,))
            except Exception:
                continue
            reachable = set(impact.impacted_nodes) | {source}
            if source in left and reachable.intersection(right):
                return True
            if source in right and reachable.intersection(left):
                return True
        return False

    def _may_merge(
        self,
        left: IncidentCluster,
        right: IncidentCluster,
        by_id: Mapping[str, NormalizedObservation],
    ) -> bool:
        if not self._time_close(left, right):
            return False
        members = self._cluster_members(left, by_id) + self._cluster_members(right, by_id)
        if not self._has_context_anchor(members):
            return False
        return self._topology_connected(left.target_ids, right.target_ids)

    @staticmethod
    def _build_cluster(members: Sequence[NormalizedObservation]) -> IncidentCluster:
        ordered = tuple(sorted(members, key=lambda item: (_time(item.observed_at), item.observation_id)))
        body = {
            "observations": [item.observation_id for item in ordered],
            "targets": sorted({item.target_id for item in ordered}),
            "fingerprints": sorted({item.fingerprint for item in ordered}),
        }
        return IncidentCluster(
            incident_id="INC-" + _digest(body)[:20].upper(),
            observation_ids=tuple(body["observations"]),
            target_ids=tuple(body["targets"]),
            fingerprints=tuple(body["fingerprints"]),
            first_seen=ordered[0].observed_at,
            last_seen=ordered[-1].observed_at,
            severity=round(max(item.severity for item in ordered), 8),
            change_refs=tuple(sorted({item.change_ref for item in ordered if item.change_ref})),
            proof_refs=tuple(sorted({ref for item in ordered for ref in item.proof_refs})),
        )

    def _merge_topology_related(
        self,
        clusters: Sequence[IncidentCluster],
        observations: Sequence[NormalizedObservation],
    ) -> tuple[IncidentCluster, ...]:
        by_id = {item.observation_id: item for item in observations}
        work = list(clusters)
        changed = True
        while changed:
            changed = False
            for left_index in range(len(work)):
                if changed:
                    break
                for right_index in range(left_index + 1, len(work)):
                    left = work[left_index]
                    right = work[right_index]
                    if not self._may_merge(left, right, by_id):
                        continue
                    member_ids = tuple(dict.fromkeys(left.observation_ids + right.observation_ids))
                    merged = self._build_cluster(tuple(by_id[item] for item in member_ids))
                    work = [
                        cluster
                        for index, cluster in enumerate(work)
                        if index not in {left_index, right_index}
                    ] + [merged]
                    changed = True
                    break
        return tuple(sorted(work, key=lambda item: (-item.severity, item.first_seen, item.incident_id)))

    def assess(
        self,
        observations: Sequence[NormalizedObservation | Mapping[str, Any]],
        *,
        slo_samples: Mapping[str, Sequence[SLOWindowSample]] | None = None,
    ) -> SentinelAssessment:
        normalized = tuple(
            item.validate() if isinstance(item, NormalizedObservation) else self.normalizer.normalize(item)
            for item in observations
        )
        preliminary = self.correlator.cluster(normalized)
        clusters = self._merge_topology_related(preliminary, normalized)
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
            "schema": "SENTINEL-OMEGA-OBSERVABILITY-CAUSAL-FABRIC-V1",
            "correlation_stage": "TOPOLOGY_BOUNDED_V1",
            "clusters": [item.incident_id for item in clusters],
            "origins": {
                incident_id: [(item.target_id, item.score) for item in rows]
                for incident_id, rows in sorted(rankings.items())
            },
            "slo": [(item.service_id, item.disposition, item.windows) for item in slo_states],
            "actions": [item.action_id for item in actions],
        }
        return SentinelAssessment(
            clusters=clusters,
            origin_rankings=rankings,
            slo_states=slo_states,
            remediation_actions=actions,
            receipt_sha256=_digest(body),
            truth_boundary=(
                "Deterministic internal diagnosis only. Topology-aware incident merges require temporal proximity, "
                "a change/trace context anchor and a Living State dependency path. Grouping and probable-origin "
                "rankings remain correlation evidence, not verified causality. Remediation actions are A1-internal "
                "planning candidates and do not execute provider effects or grant authority."
            ),
        )
