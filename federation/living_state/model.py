from __future__ import annotations

"""Event-sourced world model, reconciliation and optimization runtime."""

from dataclasses import asdict
from typing import Any, Mapping, Sequence

from .types import (
    AUTHORITY_CEILING,
    CausalEvidence,
    CausalStatus,
    ConcurrencyResult,
    ContextState,
    EdgeKind,
    EvolutionCandidate,
    EvolutionState,
    FabricError,
    HealthState,
    LearningClass,
    LearningEvent,
    MissionLease,
    NodeKind,
    ObservationEvent,
    PlannerCandidate,
    PlannerDecision,
    ProofMaturity,
    Provenance,
    ReflexAction,
    RouteEstimate,
    RoutePortfolio,
    RouteTelemetry,
    SCHEMA,
    VERSION,
    StateEstimate,
    WorldEdge,
    WorldNode,
    _PROOF_RANK,
    _SHA40,
    _attr,
    _authority_ok,
    _enum_value,
    _id,
    _overlap,
    _parse_time,
    digest,
)

class LivingWorldModel:
    """Event-sourced Federation world model and safe optimization substrate."""

    def __init__(self, *, authority_ceiling: str = AUTHORITY_CEILING) -> None:
        if not _authority_ok(authority_ceiling):
            raise ValueError("living world authority exceeds Federation internal ceiling")
        self.authority_ceiling = authority_ceiling
        self._node_history: dict[str, list[WorldNode]] = {}
        self._edges: dict[str, WorldEdge] = {}
        self._events: list[ObservationEvent] = []
        self._telemetry: list[RouteTelemetry] = []
        self._learning: list[LearningEvent] = []
        self._contexts: dict[str, ContextState] = {}
        self._benchmark_observed_at: dict[str, str] = {}
        self._external_effects = 0

    @property
    def external_effects(self) -> int:
        return self._external_effects

    @property
    def event_count(self) -> int:
        return len(self._events)

    def _append_event(self, event_type: str, object_id: str, payload: Mapping[str, Any]) -> ObservationEvent:
        prior = self._events[-1].event_digest if self._events else "GENESIS"
        body = {
            "sequence": len(self._events) + 1,
            "event_type": event_type,
            "object_id": object_id,
            "payload": dict(payload),
            "prior_digest": prior,
        }
        event = ObservationEvent(event_digest=digest(body), **body)
        self._events.append(event)
        return event

    def observe_node(self, node: WorldNode) -> ObservationEvent:
        node.validate()
        if not _authority_ok(node.provenance.authority_ceiling, self.authority_ceiling):
            raise FabricError("node authority exceeds model ceiling")
        self._node_history.setdefault(node.node_id, []).append(node)
        return self._append_event("NODE_OBSERVED", node.node_id, {"node": asdict(node)})

    def observe_edge(self, edge: WorldEdge) -> ObservationEvent:
        edge.validate(self.current_nodes())
        self._edges[edge.edge_id] = edge
        return self._append_event("EDGE_OBSERVED", edge.edge_id, {"edge": asdict(edge)})

    def observe_route_telemetry(self, sample: RouteTelemetry) -> ObservationEvent:
        sample.validate()
        self._telemetry.append(sample)
        return self._append_event("ROUTE_TELEMETRY", sample.route_id, {"sample": asdict(sample)})

    def observe_context(self, context: ContextState) -> ObservationEvent:
        context.validate()
        self._contexts[context.context_id] = context
        return self._append_event("CONTEXT_OBSERVED", context.context_id, {"context": asdict(context)})

    def observe_learning(self, learning: LearningEvent) -> ObservationEvent:
        learning.validate()
        self._learning.append(learning)
        return self._append_event("LEARNING_OBSERVED", learning.learning_id, {"learning": asdict(learning)})

    def observe_benchmark(self, capability_id: str, observed_at: str, proof_ref: str) -> ObservationEvent:
        _id(capability_id, "capability_id")
        _parse_time(observed_at)
        if not proof_ref.strip():
            raise ValueError("benchmark observation requires proof")
        self._benchmark_observed_at[capability_id] = observed_at
        return self._append_event("BENCHMARK_OBSERVED", capability_id, {"observed_at": observed_at, "proof_ref": proof_ref})

    def state_estimate(self, node_id: str, *, now: str) -> StateEstimate:
        history = self._node_history.get(node_id, [])
        if not history:
            return StateEstimate(node_id, "UNKNOWN", False, ProofMaturity.UNKNOWN.value, 0, 0.0, "", "", "", False, ())
        fresh = [item for item in history if item.provenance.fresh_at(now)]
        pool = fresh if fresh else history
        ranked = sorted(
            pool,
            key=lambda item: (
                item.provenance.rank,
                _parse_time(item.provenance.observed_at),
                item.provenance.confidence,
                item.fingerprint,
            ),
            reverse=True,
        )
        best = ranked[0]
        best_time = _parse_time(best.provenance.observed_at)
        competing = [
            item for item in ranked[1:]
            if item.state != best.state
            and abs((_parse_time(item.provenance.observed_at) - best_time).total_seconds()) <= min(item.provenance.ttl_seconds, best.provenance.ttl_seconds)
            and item.provenance.rank >= _PROOF_RANK[ProofMaturity.SOURCE_READBACK]
            and item.provenance.confidence >= 0.5
        ]
        return StateEstimate(
            node_id=node_id,
            state=best.state if fresh else "STALE:" + best.state,
            fresh=bool(fresh),
            proof_maturity=best.provenance.proof_maturity.value,
            proof_rank=best.provenance.rank,
            confidence=float(best.provenance.confidence),
            source_ref=best.provenance.source_ref,
            proof_ref=best.provenance.proof_ref,
            observed_at=best.provenance.observed_at,
            split_brain=bool(competing),
            alternatives=tuple(sorted({item.state for item in competing})),
        )

    def current_nodes(self, *, now: str | None = None) -> dict[str, WorldNode]:
        result: dict[str, WorldNode] = {}
        for node_id, history in self._node_history.items():
            pool = history
            if now is not None:
                fresh = [item for item in history if item.provenance.fresh_at(now)]
                pool = fresh or history
            result[node_id] = max(
                pool,
                key=lambda item: (item.provenance.rank, _parse_time(item.provenance.observed_at), item.provenance.confidence, item.fingerprint),
            )
        return result

    def graph_digest(self, *, now: str) -> str:
        nodes = {
            node_id: asdict(self.state_estimate(node_id, now=now))
            for node_id in sorted(self._node_history)
        }
        edges = {
            edge_id: {
                "source": edge.source_id,
                "target": edge.target_id,
                "kind": edge.kind.value,
                "confidence": edge.confidence,
                "causal_status": edge.causal_status.value,
                "proof_ref": edge.provenance.proof_ref,
            }
            for edge_id, edge in sorted(self._edges.items())
        }
        return digest({"schema": SCHEMA, "nodes": nodes, "edges": edges, "event_head": self.event_head_digest})

    @property
    def event_head_digest(self) -> str:
        return self._events[-1].event_digest if self._events else "GENESIS"

    def verify_event_chain(self) -> bool:
        prior = "GENESIS"
        for index, event in enumerate(self._events, 1):
            body = {
                "sequence": index,
                "event_type": event.event_type,
                "object_id": event.object_id,
                "payload": dict(event.payload),
                "prior_digest": prior,
            }
            if event.sequence != index or event.prior_digest != prior or digest(body) != event.event_digest:
                return False
            prior = event.event_digest
        return True

    def export_event_log(self) -> tuple[dict[str, Any], ...]:
        return tuple(asdict(event) for event in self._events)

    @staticmethod
    def _provenance_from(data: Mapping[str, Any]) -> Provenance:
        values = dict(data)
        values["proof_maturity"] = ProofMaturity(_enum_value(values.get("proof_maturity", ProofMaturity.UNKNOWN.value)))
        return Provenance(**values).validate()

    @classmethod
    def replay(
        cls,
        events: Sequence[Mapping[str, Any]],
        *,
        authority_ceiling: str = AUTHORITY_CEILING,
    ) -> "LivingWorldModel":
        model = cls(authority_ceiling=authority_ceiling)
        expected_prior = "GENESIS"
        for expected_sequence, raw in enumerate(events, 1):
            event = ObservationEvent(
                sequence=int(raw["sequence"]),
                event_type=str(raw["event_type"]),
                object_id=str(raw["object_id"]),
                payload=dict(raw["payload"]),
                event_digest=str(raw["event_digest"]),
                prior_digest=str(raw["prior_digest"]),
            )
            body = {
                "sequence": event.sequence,
                "event_type": event.event_type,
                "object_id": event.object_id,
                "payload": dict(event.payload),
                "prior_digest": event.prior_digest,
            }
            if event.sequence != expected_sequence:
                raise FabricError("event journal sequence gap")
            if event.prior_digest != expected_prior:
                raise FabricError("event journal prior-digest mismatch")
            if digest(body) != event.event_digest:
                raise FabricError("event journal digest mismatch")

            if event.event_type == "NODE_OBSERVED":
                data = dict(event.payload["node"])
                data["kind"] = NodeKind(_enum_value(data["kind"]))
                data["provenance"] = cls._provenance_from(data["provenance"])
                generated = model.observe_node(WorldNode(**data))
            elif event.event_type == "EDGE_OBSERVED":
                data = dict(event.payload["edge"])
                data["kind"] = EdgeKind(_enum_value(data["kind"]))
                data["causal_status"] = CausalStatus(_enum_value(data.get("causal_status", CausalStatus.NONE.value)))
                data["causal_evidence"] = CausalEvidence(**dict(data.get("causal_evidence", {})))
                data["provenance"] = cls._provenance_from(data["provenance"])
                generated = model.observe_edge(WorldEdge(**data))
            elif event.event_type == "ROUTE_TELEMETRY":
                data = dict(event.payload["sample"])
                data["failure_domains"] = tuple(data.get("failure_domains", ()))
                generated = model.observe_route_telemetry(RouteTelemetry(**data))
            elif event.event_type == "CONTEXT_OBSERVED":
                data = dict(event.payload["context"])
                for key in (
                    "verified_facts", "adverse_evidence", "contradictions", "gaps",
                    "blockers", "decisions", "source_refs",
                ):
                    data[key] = tuple(data.get(key, ()))
                generated = model.observe_context(ContextState(**data))
            elif event.event_type == "LEARNING_OBSERVED":
                data = dict(event.payload["learning"])
                data["learning_class"] = LearningClass(_enum_value(data["learning_class"]))
                data["proof_refs"] = tuple(data.get("proof_refs", ()))
                generated = model.observe_learning(LearningEvent(**data))
            elif event.event_type == "BENCHMARK_OBSERVED":
                generated = model.observe_benchmark(
                    event.object_id,
                    str(event.payload["observed_at"]),
                    str(event.payload["proof_ref"]),
                )
            elif event.event_type == "OMEGA4_METRICS":
                generated = model._append_event("OMEGA4_METRICS", event.object_id, dict(event.payload))
            else:
                raise FabricError(f"unknown event type during replay: {event.event_type}")

            if generated.event_digest != event.event_digest:
                raise FabricError("semantic replay drift detected")
            expected_prior = event.event_digest
        if not model.verify_event_chain():
            raise FabricError("replayed event chain failed verification")
        return model

    def split_brain_nodes(self, *, now: str) -> tuple[str, ...]:
        return tuple(sorted(
            node_id for node_id in self._node_history
            if self.state_estimate(node_id, now=now).split_brain
        ))

    def route_estimates(self, *, min_samples: int = 3) -> tuple[RouteEstimate, ...]:
        grouped: dict[str, list[RouteTelemetry]] = {}
        for sample in self._telemetry:
            grouped.setdefault(sample.route_id, []).append(sample)
        estimates: list[RouteEstimate] = []
        for route_id, samples in sorted(grouped.items()):
            n = len(samples)
            successes = sum(int(item.success) for item in samples)
            posterior = (successes + 1) / (n + 2)
            evidence_weight = n / (n + max(1, min_samples))
            reliability = evidence_weight * posterior + (1 - evidence_weight) * 0.5
            freshness = sum(item.proof_freshness for item in samples) / n
            proof_strength = sum(item.proof_strength for item in samples) / n
            latency = sum(item.latency_ms for item in samples) / n
            cost = sum(item.cost_units for item in samples) / n
            burden = sum(item.owner_burden for item in samples) / n
            risk = sum(item.risk for item in samples) / n
            latency_penalty = latency / (latency + 1000.0)
            cost_penalty = cost / (cost + 1.0)
            burden_penalty = burden / (burden + 1.0)
            risk_penalty = risk / (risk + 1.0)
            score = (
                0.28 * reliability
                + 0.22 * freshness
                + 0.21 * proof_strength
                - 0.08 * latency_penalty
                - 0.07 * cost_penalty
                - 0.06 * burden_penalty
                - 0.08 * risk_penalty
            )
            domains = tuple(sorted({d for item in samples for d in item.failure_domains}))
            estimates.append(RouteEstimate(
                route_id=route_id,
                samples=n,
                successes=successes,
                reliability=round(reliability, 8),
                evidence_weight=round(evidence_weight, 8),
                proof_freshness=round(freshness, 8),
                proof_strength=round(proof_strength, 8),
                latency_penalty=round(latency_penalty, 8),
                cost_penalty=round(cost_penalty, 8),
                owner_burden_penalty=round(burden_penalty, 8),
                risk_penalty=round(risk_penalty, 8),
                score=round(score, 8),
                failure_domains=domains,
                measured=n >= min_samples,
            ))
        return tuple(estimates)

    def route_portfolio(self, *, max_shadows: int = 2, min_samples: int = 3) -> RoutePortfolio:
        estimates = sorted(self.route_estimates(min_samples=min_samples), key=lambda x: (x.score, x.route_id), reverse=True)
        if not estimates:
            return RoutePortfolio("", (), (), (), (), ())
        champion = estimates[0]
        shadows: list[str] = []
        reserves: list[str] = []
        rejected: list[str] = []
        champion_domains = set(champion.failure_domains)
        for item in estimates[1:]:
            if item.proof_freshness < 0.25 or item.proof_strength < 0.25:
                rejected.append(item.route_id)
                continue
            diverse = not champion_domains.intersection(item.failure_domains)
            if len(shadows) < max_shadows and diverse:
                shadows.append(item.route_id)
            else:
                reserves.append(item.route_id)
        selected_ids = [champion.route_id] + shadows
        selected = [next(x for x in estimates if x.route_id == rid) for rid in selected_ids]
        domain_counts: dict[str, int] = {}
        for item in selected:
            for domain in item.failure_domains:
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
        hidden = tuple(sorted(domain for domain, count in domain_counts.items() if count == len(selected) and count > 1))
        return RoutePortfolio(
            champion=champion.route_id,
            shadows=tuple(shadows),
            reserves=tuple(reserves),
            rejected=tuple(rejected),
            hidden_spofs=hidden,
            estimates=tuple(estimates),
        )

    def hidden_spofs(self, route_ids: Sequence[str]) -> tuple[str, ...]:
        estimates = {item.route_id: item for item in self.route_estimates(min_samples=1)}
        chosen = [estimates[rid] for rid in route_ids if rid in estimates]
        if len(chosen) < 2:
            return ()
        shared = set(chosen[0].failure_domains)
        for item in chosen[1:]:
            shared.intersection_update(item.failure_domains)
        return tuple(sorted(shared))

    def arbitrate_mission_write(
        self,
        *,
        lease: MissionLease,
        now: str,
        current_main_sha: str,
        current_main_changed_paths: Sequence[str] = (),
        concurrent_workstream_paths: Sequence[str] = (),
    ) -> ConcurrencyResult:
        lease.validate()
        if not _SHA40.fullmatch(current_main_sha):
            raise ValueError("current_main_sha must be SHA40")
        if not lease.active_at(now):
            return ConcurrencyResult(False, "HOLD", "LEASE_EXPIRED", ())
        overlaps = tuple(sorted({
            left for left in lease.paths for right in concurrent_workstream_paths if _overlap(left, right)
        }))
        if overlaps:
            return ConcurrencyResult(False, "HOLD", "ACTIVE_WORKSTREAM_OVERLAP", overlaps)
        if current_main_sha != lease.base_main_sha:
            main_overlaps = tuple(sorted({
                left for left in lease.paths for right in current_main_changed_paths if _overlap(left, right)
            }))
            if main_overlaps:
                return ConcurrencyResult(False, "RECONCILE", "STALE_MAIN_OVERLAP", main_overlaps)
            if lease.effectful:
                return ConcurrencyResult(False, "REBASE", "STALE_EFFECTFUL_LEASE", ())
            return ConcurrencyResult(False, "FAST_RECONVERGE", "STALE_DISJOINT_NON_EFFECTFUL", ())
        return ConcurrencyResult(True, "WRITE_WITH_FENCE", "FRESH_NON_OVERLAPPING_LEASE", ())

    def reflexes(self, *, now: str) -> tuple[dict[str, Any], ...]:
        actions: list[dict[str, Any]] = []
        for node_id in self.split_brain_nodes(now=now):
            node = self.current_nodes(now=now)[node_id]
            actions.append({
                "signal": "SPLIT_BRAIN",
                "node_id": node_id,
                "action": ReflexAction.HOLD_EFFECTFUL_ROUTE.value,
                "external_effect": False,
                "scope": node.provenance.matter_scope,
            })
        for node_id in sorted(self._node_history):
            estimate = self.state_estimate(node_id, now=now)
            if not estimate.fresh and estimate.proof_rank >= _PROOF_RANK[ProofMaturity.RUNTIME_READBACK]:
                actions.append({
                    "signal": "STALE_RUNTIME_OR_PROVIDER_PROOF",
                    "node_id": node_id,
                    "action": ReflexAction.REPROBE_PROOF.value,
                    "external_effect": False,
                })
        for context in self._contexts.values():
            action = context.action()
            if action == "CHECKPOINT_AND_HANDOFF":
                actions.append({"signal": "CONTEXT_PRESSURE", "node_id": context.context_id, "action": ReflexAction.CHECKPOINT.value, "external_effect": False})
            elif action == "PROTECTED_COMPACTION":
                actions.append({"signal": "CONTEXT_ENTROPY", "node_id": context.context_id, "action": ReflexAction.COMPACT_CONTEXT.value, "external_effect": False})
        for learning in self._learning:
            if learning.recurrence == 2:
                actions.append({"signal": learning.fingerprint, "node_id": learning.learning_id, "action": ReflexAction.SCIENTIST_REVIEW.value, "external_effect": False})
            elif learning.recurrence >= 3:
                actions.append({"signal": learning.fingerprint, "node_id": learning.learning_id, "action": ReflexAction.REDESIGN_OR_ROLLBACK.value, "external_effect": False})
        return tuple(actions)

    def plan(self, candidates: Sequence[PlannerCandidate], *, owner_authorized_external_effect: bool = False) -> PlannerDecision:
        if not candidates:
            raise ValueError("planner requires candidates")
        rejected: list[str] = []
        eligible: list[PlannerCandidate] = []
        for candidate in candidates:
            candidate.validate()
            if candidate.external_effect:
                rejected.append(candidate.action_id)
                continue
            eligible.append(candidate)
        if not eligible:
            return PlannerDecision("", 0.0, "HOLD_FOR_EFFECT_ADMISSION", tuple(sorted(rejected)), False)
        winner = max(eligible, key=lambda item: (item.utility, item.action_id))
        return PlannerDecision(winner.action_id, winner.utility, "PROPOSE_INTERNAL_ACTION", tuple(sorted(rejected)), False)

    def debt_report(self, *, now: str, benchmark_ttl_seconds: int = 7 * 86400) -> dict[str, Any]:
        estimates = [self.state_estimate(node_id, now=now) for node_id in self._node_history]
        proof_debt = sum(1 for item in estimates if item.proof_rank < _PROOF_RANK[ProofMaturity.DETERMINISTIC_TESTED])
        freshness_debt = sum(1 for item in estimates if not item.fresh)
        split_brain_debt = sum(1 for item in estimates if item.split_brain)
        benchmark_debt = 0
        for capability_id, observed_at in self._benchmark_observed_at.items():
            if (_parse_time(now) - _parse_time(observed_at)).total_seconds() > benchmark_ttl_seconds:
                benchmark_debt += 1
        context_debt = sum(1 for item in self._contexts.values() if item.action() != "NORMAL")
        portfolio = self.route_portfolio(min_samples=1)
        resilience_debt = len(portfolio.hidden_spofs)
        owner_burden_debt = sum(1 for item in portfolio.estimates if item.owner_burden_penalty >= 0.5)
        causal_debt = sum(1 for edge in self._edges.values() if edge.causal_status == CausalStatus.CANDIDATE)
        return {
            "proof_debt": proof_debt,
            "freshness_debt": freshness_debt,
            "split_brain_debt": split_brain_debt,
            "benchmark_debt": benchmark_debt,
            "context_debt": context_debt,
            "resilience_debt": resilience_debt,
            "owner_burden_debt": owner_burden_debt,
            "causal_debt": causal_debt,
            "external_effects": self.external_effects,
        }

    def homeostasis(self, *, now: str) -> dict[str, Any]:
        debt = self.debt_report(now=now)
        measured_keys = [key for key in debt if key != "external_effects"]
        if not self._node_history and not self._telemetry and not self._contexts:
            return {"state": HealthState.UNMEASURED.value, "debt": debt}
        drift = any(debt[key] > 0 for key in measured_keys)
        return {"state": HealthState.DRIFT.value if drift else HealthState.HOMEOSTATIC.value, "debt": debt}

    def predictions(self, *, now: str) -> tuple[dict[str, Any], ...]:
        debt = self.debt_report(now=now)
        signals: list[dict[str, Any]] = []
        mapping = {
            "freshness_debt": ("PROOF_OR_STATE_STALENESS", "REPROBE_HIGHEST_DECISION_VALUE_NODE"),
            "split_brain_debt": ("STATE_DIVERGENCE", "HOLD_EFFECTFUL_PATH_AND_RECONCILE"),
            "benchmark_debt": ("COMPETITIVE_BLINDNESS", "REFRESH_BENCHMARK_FRONTIER"),
            "context_debt": ("CONTEXT_DEGRADATION", "CHECKPOINT_COMPACT_OR_HANDOFF"),
            "resilience_debt": ("HIDDEN_SINGLE_POINT_OF_FAILURE", "FORM_DIVERSE_SHADOW_ROUTE"),
            "owner_burden_debt": ("OWNER_LOAD_DRIFT", "AUTOMATE_OR_REROUTE_SYSTEM_WORK"),
            "causal_debt": ("UNRESOLVED_CAUSAL_HYPOTHESIS", "RUN_REVERSIBLE_FALSIFIER_OR_INTERVENTION"),
            "proof_debt": ("PROOF_MATURITY_GAP", "SELECT_HIGHEST_INFORMATION_PROOF_UPGRADE"),
        }
        for key, (risk, action) in mapping.items():
            if debt[key] > 0:
                signals.append({"risk": risk, "count": debt[key], "preemptive_action": action, "external_effect": False})
        return tuple(signals)

    def evolution_state(self, candidate: EvolutionCandidate) -> dict[str, Any]:
        state = candidate.state
        return {
            "capability_id": candidate.capability_id,
            "state": state.value,
            "promotion_allowed": state == EvolutionState.PROMOTION_ELIGIBLE,
            "external_effect": False,
            "requires_effect_admission_after_source_promotion": True,
        }

    def snapshot(self, *, now: str) -> dict[str, Any]:
        nodes = {node_id: asdict(self.state_estimate(node_id, now=now)) for node_id in sorted(self._node_history)}
        payload = {
            "schema": SCHEMA,
            "version": VERSION,
            "authority_ceiling": self.authority_ceiling,
            "event_count": self.event_count,
            "event_head_digest": self.event_head_digest,
            "event_chain_valid": self.verify_event_chain(),
            "nodes": nodes,
            "edge_count": len(self._edges),
            "route_portfolio": asdict(self.route_portfolio(min_samples=1)),
            "homeostasis": self.homeostasis(now=now),
            "predictions": self.predictions(now=now),
            "reflexes": self.reflexes(now=now),
            "external_effects": self.external_effects,
            "truth_boundary": {
                "continuous_unattended_runtime_claimed": False,
                "hidden_cross_chat_access_claimed": False,
                "provider_authority_inferred": False,
                "synthetic_metrics_are_provider_performance": False,
                "living_fabric_executes_external_effects": False,
            },
        }
        payload["snapshot_sha256"] = digest(payload)
        return payload

    def ingest_capability_twin(self, twin: Any, *, observed_at: str | None = None) -> WorldNode:
        system_id = str(_attr(twin, "system_id"))
        runtime_state = _enum_value(_attr(twin, "runtime_state", "UNKNOWN"))
        semantic_state = _enum_value(_attr(twin, "semantic_state", "UNKNOWN"))
        readback_state = _enum_value(_attr(twin, "readback_state", "NONE"))
        proof_ref = str(_attr(twin, "proof_ref", ""))
        provider_ref = str(_attr(twin, "provider_readback_ref", ""))
        source_ref = str(_attr(twin, "source_ref", "capability-twin"))
        when = observed_at or str(_attr(twin, "observed_at"))
        ttl = int(_attr(twin, "ttl_seconds", 3600))
        confidence = float(getattr(twin, "confidence", _attr(twin, "confidence", 0.5)) if not isinstance(twin, Mapping) else twin.get("confidence", 0.5))
        proof = ProofMaturity.PROVIDER_READBACK if provider_ref and runtime_state == "PROVIDER_VERIFIED" else (
            ProofMaturity.RUNTIME_READBACK if runtime_state == "RUNTIME_VERIFIED" else ProofMaturity.DETERMINISTIC_TESTED
        )
        node = WorldNode(
            node_id=f"capability:{system_id}",
            kind=NodeKind.CAPABILITY,
            label=system_id,
            state=runtime_state,
            payload={"semantic_state": semantic_state, "readback_state": readback_state, "provider_readback_ref": provider_ref},
            provenance=Provenance(
                source_ref=source_ref,
                proof_ref=provider_ref or proof_ref or source_ref,
                observed_at=when,
                proof_maturity=proof,
                ttl_seconds=ttl,
                confidence=max(0.0, min(1.0, confidence)),
                authority_ceiling=str(_attr(twin, "authority_ceiling", AUTHORITY_CEILING)),
                matter_scope="GLOBAL",
                source_class="CAPABILITY_TWIN",
            ),
        )
        self.observe_node(node)
        return node

    def ingest_awareness_result(self, result: Mapping[str, Any], *, observed_at: str, matter_scope: str = "GLOBAL") -> tuple[str, ...]:
        ids: list[str] = []
        for route in result.get("routes", ()):
            alias = str(route.get("alias", ""))
            if not alias:
                continue
            provider = str(route.get("provider", "UNKNOWN"))
            state = str(route.get("state", "UNKNOWN"))
            node_id = f"route:{alias}"
            node = WorldNode(
                node_id=node_id,
                kind=NodeKind.ROUTE,
                label=alias,
                state=state,
                payload={"provider": provider, "awareness_score": route.get("score"), "runtime_readback": route.get("runtime_readback")},
                provenance=Provenance(
                    source_ref="FEDOMEGA-SURFACE-AWARENESS-V1",
                    proof_ref=str(result.get("receipt_sha256", result.get("observed_main", "awareness-result"))),
                    observed_at=observed_at,
                    proof_maturity=ProofMaturity.SOURCE_READBACK,
                    ttl_seconds=3600,
                    confidence=0.7,
                    matter_scope=matter_scope,
                    source_class="SURFACE_AWARENESS",
                ),
            )
            self.observe_node(node)
            ids.append(node_id)
        for opportunity in result.get("opportunities", ()):
            oid = str(opportunity.get("opportunity_id", ""))
            if not oid:
                continue
            node = WorldNode(
                node_id=f"opportunity:{oid}",
                kind=NodeKind.OPPORTUNITY,
                label=str(opportunity.get("title", oid)),
                state=str(opportunity.get("current_state", "OPEN")),
                payload={
                    "class": opportunity.get("opportunity_class"),
                    "desired_capability": opportunity.get("desired_capability"),
                    "buildable_now": opportunity.get("buildable_now"),
                    "priority": opportunity.get("priority"),
                },
                provenance=Provenance(
                    source_ref="AWARENESS_OPPORTUNITY_FOUNDRY",
                    proof_ref=str(result.get("receipt_sha256", "awareness-opportunity")),
                    observed_at=observed_at,
                    proof_maturity=ProofMaturity.DETERMINISTIC_TESTED,
                    ttl_seconds=86400,
                    confidence=0.75,
                    matter_scope=matter_scope,
                    source_class="OPPORTUNITY_FOUNDRY",
                ),
            )
            self.observe_node(node)
            ids.append(node.node_id)
        return tuple(ids)

    def ingest_omega4_snapshot(
        self,
        *,
        missions: Sequence[Mapping[str, Any]] = (),
        capabilities: Sequence[Mapping[str, Any]] = (),
        metrics: Mapping[str, float] | None = None,
        observed_at: str,
    ) -> tuple[str, ...]:
        ids: list[str] = []
        for mission in missions:
            mid = str(mission.get("mission_id", ""))
            if not mid:
                continue
            scope = str(mission.get("project_id", "GLOBAL")) or "GLOBAL"
            node = WorldNode(
                node_id=f"mission:{mid}",
                kind=NodeKind.MISSION,
                label=str(mission.get("objective", mid)),
                state=str(mission.get("current_stage", mission.get("stage", "UNKNOWN"))),
                payload={
                    "active_lanes": mission.get("active_lanes", ()),
                    "blockers": mission.get("blockers", ()),
                    "next_gate": mission.get("next_gate", ""),
                    "executable_next": bool(mission.get("executable_next", False)),
                },
                provenance=Provenance(
                    source_ref="BUBBLES_FEDERATION_GOVERNOR_OMEGA4",
                    proof_ref=f"omega4-mission:{mid}",
                    observed_at=observed_at,
                    proof_maturity=ProofMaturity.RUNTIME_READBACK,
                    ttl_seconds=1800,
                    confidence=0.85,
                    matter_scope=scope,
                    sensitivity="PROJECT",
                    source_class="OMEGA4_REGISTRY",
                ),
            )
            self.observe_node(node)
            ids.append(node.node_id)
        for capability in capabilities:
            cid = str(capability.get("capability_id", ""))
            if not cid:
                continue
            node = WorldNode(
                node_id=f"capability:{cid}",
                kind=NodeKind.CAPABILITY,
                label=str(capability.get("role", cid)),
                state="ACTIVE" if capability.get("active", True) else "INACTIVE",
                payload={"tags": capability.get("tags", capability.get("tags_json", ())), "registry_pointer": capability.get("registry_pointer", "")},
                provenance=Provenance(
                    source_ref="BUBBLES_FEDERATION_GOVERNOR_OMEGA4",
                    proof_ref=f"omega4-capability:{cid}",
                    observed_at=observed_at,
                    proof_maturity=ProofMaturity.RUNTIME_READBACK,
                    ttl_seconds=3600,
                    confidence=0.8,
                    matter_scope="GLOBAL",
                    source_class="OMEGA4_REGISTRY",
                ),
            )
            self.observe_node(node)
            ids.append(node.node_id)
        if metrics:
            self._append_event("OMEGA4_METRICS", "omega4:metrics", {k: float(v) for k, v in sorted(metrics.items())})
        return tuple(ids)

    def ingest_adaptive_route_receipt(self, receipt: Mapping[str, Any], *, mission_id: str, observed_at: str, matter_scope: str = "GLOBAL") -> None:
        route_id = str(receipt.get("selected_route_id", receipt.get("route_id", "")))
        if not route_id:
            raise ValueError("adaptive receipt lacks route id")
        self.observe_route_telemetry(RouteTelemetry(
            route_id=route_id,
            mission_id=mission_id,
            observed_at=observed_at,
            success=bool(receipt.get("success", receipt.get("status") == "PASS")),
            latency_ms=float(receipt.get("latency_ms", 0.0)),
            cost_units=float(receipt.get("cost_units", 0.0)),
            owner_burden=float(receipt.get("owner_burden", 0.0)),
            proof_freshness=float(receipt.get("proof_freshness", 0.5)),
            proof_strength=float(receipt.get("proof_strength", 0.5)),
            risk=float(receipt.get("risk", 0.0)),
            failure_domains=tuple(str(x) for x in receipt.get("failure_domains", ())),
            proof_ref=str(receipt.get("receipt_sha256", receipt.get("proof_ref", "adaptive-receipt"))),
            matter_scope=matter_scope,
            provider_effect=False,
        ))
