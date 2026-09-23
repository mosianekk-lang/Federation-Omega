"""FUSE Autonomic Mission Spine v1.

Binds the proof-bounded FUSE control chain into one monotonic state machine:
Capability Truth -> Mission Admission -> Live Worker/Topology -> Action Admission ->
Execution/Readback Closure -> Mission Outcome/Value.

The spine is provider-neutral. It never invents runtime capacity, authority, provider
execution, readback, behaviour or value. It only advances when the specialist court
for the next stage returns a qualifying receipt, and every snapshot is digest-chained
to the exact prior snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from hashlib import sha256
import json
from typing import Mapping, Sequence

from benchmarking.cfbe_omega.n_omega_agentic_frontier_v1 import (
    AgenticFrontierCompiler,
    MissionProfile as FrontierMissionProfile,
    SuperstackPlan,
)
from federation.action_admission_gate_v1 import (
    ActionAdmissionGate,
    ActionAdmissionReceipt,
    ActionRequest,
    AuthorityGrant,
)
from federation.capability_truth_v1 import CapabilityTruthRecord
from federation.cfbe_chat_hyperperformance_v1 import FreshResultCache, RouteProfile
from federation.execution_readback_closure_v1 import (
    ClosureState,
    ExecutionAttempt,
    ExecutionClosureReceipt,
    ExecutionReadbackClosure,
    IdempotencyLedger,
    RollbackReceipt,
    SemanticReadback,
)
from federation.execution_topology_compiler_v1 import (
    ExecutionTopologyCompiler,
    ExecutionTopologyReceipt,
    TopologyTask,
)
from federation.live_worker_attestation_v1 import CapabilityEpoch, WorkerAttestation
from federation.mission_capability_admission_v1 import (
    MissionAdmissionReceipt,
    MissionCapabilityCompiler,
    MissionCapabilityRequirement,
)
from federation.mission_ir import MissionIR
from federation.mission_outcome_value_court_v1 import (
    MissionOutcomeReceipt,
    MissionOutcomeState,
    MissionOutcomeValueCourt,
    OutcomeEvidence,
    RequiredAction,
    ValueObservation,
)

SCHEMA = "FUSE-AUTONOMIC-MISSION-SPINE-V1"
VERSION = "1.0.0"


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: object) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


class SpineStage(IntEnum):
    INIT = 0
    FRONTIER_COMPILED = 5
    CAPABILITY_ADMITTED = 10
    TOPOLOGY_READY = 20
    ACTIONS_ADMITTED = 30
    EXECUTION_CLOSED = 40
    OUTCOME_PROVEN = 50
    VALUE_OBSERVED = 60
    HELD = 90


@dataclass(frozen=True, slots=True)
class SpineSnapshot:
    mission_id: str
    mission_digest: str
    stage: SpineStage
    state: str
    predecessor_digest: str
    stage_receipt_digest: str
    reasons: tuple[str, ...]
    snapshot_digest: str

    @property
    def terminal_value(self) -> bool:
        return self.stage is SpineStage.VALUE_OBSERVED


@dataclass(frozen=True, slots=True)
class ActionExecutionBundle:
    request: ActionRequest
    grant: AuthorityGrant | None
    attempt: ExecutionAttempt | None = None
    readback: SemanticReadback | None = None
    rollback: RollbackReceipt | None = None
    provider_readiness: Mapping[str, bool] | None = None


@dataclass(frozen=True, slots=True)
class SpineRunReceipt:
    mission_id: str
    snapshots: tuple[SpineSnapshot, ...]
    frontier_gene_ids: tuple[str, ...]
    frontier_plan_digest: str
    mission_admission: MissionAdmissionReceipt | None
    topology: ExecutionTopologyReceipt | None
    action_admissions: tuple[ActionAdmissionReceipt, ...]
    closures: tuple[ExecutionClosureReceipt, ...]
    outcome: MissionOutcomeReceipt | None
    receipt_digest: str

    @property
    def final_snapshot(self) -> SpineSnapshot:
        return self.snapshots[-1]


class AutonomicMissionSpine:
    """One-way mission progression across the existing FUSE specialist courts."""

    def __init__(self) -> None:
        self.frontier_compiler = AgenticFrontierCompiler()
        self.capability_compiler = MissionCapabilityCompiler()
        self.topology_compiler = ExecutionTopologyCompiler()
        self.action_gate = ActionAdmissionGate()
        self.closure_court = ExecutionReadbackClosure()
        self.outcome_court = MissionOutcomeValueCourt()


    @staticmethod
    def _metadata_flag(mission: MissionIR, key: str) -> bool:
        value = str(dict(mission.metadata).get(key, "")).strip().casefold()
        return value in {"1", "true", "yes", "required", "enabled", "on"}

    def _compile_frontier_plan(
        self,
        mission: MissionIR,
        capability_requirements: Sequence[MissionCapabilityRequirement],
        topology_tasks: Sequence[TopologyTask],
        *,
        require_swarm: bool,
    ) -> SuperstackPlan:
        """Compile provider-neutral frontier capabilities before mission admission.

        Selection uses only typed mission/task/capability facts already entering the
        spine. It does not grant authority, invent provider availability, or execute
        a model/provider.
        """
        corpus = " ".join(
            [
                mission.domain,
                mission.objective,
                mission.outcome_contract,
                *(item.capability_id for item in capability_requirements),
                *(task.capability_id for task in topology_tasks),
                *(task.unit.operation for task in topology_tasks),
                *(task.unit.surface for task in topology_tasks),
            ]
        ).casefold()
        has = lambda *terms: any(term in corpus for term in terms)

        multi_agent = (
            require_swarm
            or len(topology_tasks) > 1
            or self._metadata_flag(mission, "multi_agent")
        )
        tool_heavy = (
            len(capability_requirements) >= 3
            or has("tool", "mcp", "api", "browser", "terminal", "connector")
            or self._metadata_flag(mission, "tool_heavy")
        )
        browser_or_computer = (
            has("browser", "computer", "desktop", "device", "gui", "ui automation")
            or self._metadata_flag(mission, "browser_or_computer")
        )
        code_execution = (
            has("code", "shell", "terminal", "compile", "test")
            or self._metadata_flag(mission, "code_execution")
        )
        requires_memory = (
            has("memory", "context", "knowledge", "bible", "kdv")
            or self._metadata_flag(mission, "requires_memory")
        )
        requires_dynamic_models = (
            has("model", "llm", "reasoning", "gemini", "openai", "claude", "grok", "copilot")
            or self._metadata_flag(mission, "requires_dynamic_models")
        )
        long_running = (
            self._metadata_flag(mission, "long_running")
            or self._metadata_flag(mission, "persistent_agent")
            or self._metadata_flag(mission, "durable")
        )
        requires_release = (
            self._metadata_flag(mission, "requires_release")
            or has("release", "merge", "deploy", "promotion")
        )
        artifact_production = (
            has("document", "spreadsheet", "presentation", "pdf", "artifact")
            or self._metadata_flag(mission, "requires_artifact_production")
        )
        local_multimodal = (
            self._metadata_flag(mission, "requires_local_multimodal")
            or has("local multimodal", "offline multimodal")
        )
        consequential = mission.effect_class == "CONSEQUENTIAL_EFFECT"

        domains = {"SPECIFICATION", "CONTROL", "PROOF", "GOVERNANCE", "EVALUATION"}
        if multi_agent:
            domains.add("ORCHESTRATION")
        if tool_heavy:
            domains.add("TOOLS")
        if requires_memory:
            domains.update({"MEMORY", "KNOWLEDGE"})
        if requires_dynamic_models:
            domains.add("ROUTING")
        if mission.value_metrics:
            domains.add("VALUE")
        if consequential:
            domains.add("SECURITY")

        return self.frontier_compiler.compile(
            FrontierMissionProfile(
                mission_id=mission.mission_id,
                domains=frozenset(domains),
                long_running=long_running,
                multi_agent=multi_agent,
                tool_heavy=tool_heavy,
                code_execution=code_execution,
                browser_or_computer=browser_or_computer,
                legacy_ui=self._metadata_flag(mission, "legacy_ui"),
                customer_facing=self._metadata_flag(mission, "customer_facing"),
                consequential=consequential,
                requires_memory=requires_memory,
                requires_dynamic_models=requires_dynamic_models,
                requires_release=requires_release,
                requires_adaptive_effort=True,
                requires_cross_window_context=long_running,
                requires_dynamic_tools=tool_heavy,
                requires_portable_skills=tool_heavy,
                requires_persistent_agent=long_running,
                requires_adaptive_computer_use=browser_or_computer,
                requires_hypothesis_evolution=multi_agent,
                requires_strict_self_verification=True,
                requires_harness_simplification=requires_release,
                requires_artifact_production=artifact_production,
                requires_local_multimodal=local_multimodal,
            )
        )

    @staticmethod
    def _frontier_digest(plan: SuperstackPlan) -> str:
        return _digest({
            "mission_id": plan.mission_id,
            "selected_gene_ids": plan.selected_gene_ids,
            "orchestration": plan.orchestration,
            "max_mutating_lanes": plan.max_mutating_lanes,
            "external_model_authority": plan.external_model_authority,
            "proof_required": plan.proof_required,
            "route_score": plan.route_score,
        })

    @staticmethod
    def _snapshot(
        mission: MissionIR,
        stage: SpineStage,
        state: str,
        *,
        predecessor: SpineSnapshot | None,
        stage_receipt_digest: str,
        reasons: Sequence[str] = (),
    ) -> SpineSnapshot:
        predecessor_digest = predecessor.snapshot_digest if predecessor else "GENESIS"
        material = {
            "schema": SCHEMA,
            "version": VERSION,
            "mission_id": mission.mission_id,
            "mission_digest": mission.digest(),
            "stage": int(stage),
            "state": state,
            "predecessor": predecessor_digest,
            "stage_receipt": stage_receipt_digest,
            "reasons": tuple(reasons),
        }
        return SpineSnapshot(
            mission_id=mission.mission_id,
            mission_digest=mission.digest(),
            stage=stage,
            state=state,
            predecessor_digest=predecessor_digest,
            stage_receipt_digest=stage_receipt_digest,
            reasons=tuple(reasons),
            snapshot_digest=_digest(material),
        )

    @staticmethod
    def verify_chain(snapshots: Sequence[SpineSnapshot]) -> bool:
        if not snapshots:
            return False
        previous = "GENESIS"
        last_stage = SpineStage.INIT
        for index, item in enumerate(snapshots):
            if item.predecessor_digest != previous:
                return False
            if index and item.stage is not SpineStage.HELD and int(item.stage) <= int(last_stage):
                return False
            previous = item.snapshot_digest
            last_stage = item.stage
        return True

    def run(
        self,
        *,
        mission: MissionIR,
        capability_requirements: Sequence[MissionCapabilityRequirement],
        truth_records: Mapping[str, CapabilityTruthRecord],
        topology_tasks: Sequence[TopologyTask],
        routes: Sequence[RouteProfile],
        worker_attestations: Sequence[WorkerAttestation],
        capability_epochs: Mapping[str, CapabilityEpoch],
        action_bundles: Sequence[ActionExecutionBundle],
        required_actions: Sequence[RequiredAction],
        now: str,
        outcome_evidence: OutcomeEvidence | None = None,
        proof_evidence: Mapping[str, str] | None = None,
        value_observations: Sequence[ValueObservation] = (),
        cache: FreshResultCache | None = None,
        require_swarm: bool = False,
        ledger: IdempotencyLedger | None = None,
    ) -> SpineRunReceipt:
        mission.validate()
        snapshots: list[SpineSnapshot] = []
        init = self._snapshot(mission, SpineStage.INIT, "MISSION_INGESTED", predecessor=None, stage_receipt_digest=mission.digest())
        snapshots.append(init)

        frontier_plan = self._compile_frontier_plan(
            mission,
            capability_requirements,
            topology_tasks,
            require_swarm=require_swarm,
        )
        frontier_digest = self._frontier_digest(frontier_plan)
        snapshots.append(self._snapshot(
            mission,
            SpineStage.FRONTIER_COMPILED,
            "FRONTIER_SUPERSTACK_COMPILED",
            predecessor=snapshots[-1],
            stage_receipt_digest=frontier_digest,
            reasons=frontier_plan.selected_gene_ids,
        ))

        admission = self.capability_compiler.admit(mission, capability_requirements, truth_records)
        if not admission.admitted:
            snapshots.append(self._snapshot(
                mission, SpineStage.HELD, admission.state,
                predecessor=snapshots[-1], stage_receipt_digest=admission.receipt_digest,
                reasons=admission.blocking_capabilities,
            ))
            return self._run_receipt(mission, snapshots, admission, None, (), (), None, frontier_plan, frontier_digest)
        snapshots.append(self._snapshot(
            mission, SpineStage.CAPABILITY_ADMITTED, admission.state,
            predecessor=snapshots[-1], stage_receipt_digest=admission.receipt_digest,
        ))

        topology = self.topology_compiler.compile(
            mission=mission,
            admission=admission,
            tasks=topology_tasks,
            routes=routes,
            attestations=worker_attestations,
            epochs=capability_epochs,
            now=now,
            cache=cache,
            require_swarm=require_swarm,
        )
        if not topology.executable:
            snapshots.append(self._snapshot(
                mission, SpineStage.HELD, topology.state,
                predecessor=snapshots[-1], stage_receipt_digest=topology.receipt_digest,
                reasons=topology.blocked_units,
            ))
            return self._run_receipt(mission, snapshots, admission, topology, (), (), None, frontier_plan, frontier_digest)
        snapshots.append(self._snapshot(
            mission, SpineStage.TOPOLOGY_READY, topology.state,
            predecessor=snapshots[-1], stage_receipt_digest=topology.receipt_digest,
        ))

        topology_units = {item.unit_id for item in topology.assignments}
        bundle_by_unit: dict[str, ActionExecutionBundle] = {}
        for bundle in action_bundles:
            bundle.request.validate()
            if bundle.request.unit_id in bundle_by_unit:
                raise ValueError("DUPLICATE_SPINE_ACTION_UNIT")
            bundle_by_unit[bundle.request.unit_id] = bundle
        missing_bundles = sorted(topology_units - set(bundle_by_unit))
        if missing_bundles:
            snapshots.append(self._snapshot(
                mission, SpineStage.HELD, "ACTIONS_HELD_BUNDLE_MISSING",
                predecessor=snapshots[-1], stage_receipt_digest=_digest(missing_bundles),
                reasons=missing_bundles,
            ))
            return self._run_receipt(mission, snapshots, admission, topology, (), (), None, frontier_plan, frontier_digest)

        action_admissions: list[ActionAdmissionReceipt] = []
        held_actions: list[str] = []
        for unit_id in sorted(topology_units):
            bundle = bundle_by_unit[unit_id]
            receipt = self.action_gate.admit(
                mission=mission,
                topology=topology,
                request=bundle.request,
                now=now,
                grant=bundle.grant,
                provider_readiness=bundle.provider_readiness,
            )
            action_admissions.append(receipt)
            if not receipt.admitted:
                held_actions.append(receipt.action_id)
        action_digest = _digest([x.receipt_digest for x in action_admissions])
        if held_actions:
            snapshots.append(self._snapshot(
                mission, SpineStage.HELD, "ACTIONS_HELD_NOT_ADMITTED",
                predecessor=snapshots[-1], stage_receipt_digest=action_digest,
                reasons=sorted(held_actions),
            ))
            return self._run_receipt(mission, snapshots, admission, topology, tuple(action_admissions), (), None, frontier_plan, frontier_digest)
        snapshots.append(self._snapshot(
            mission, SpineStage.ACTIONS_ADMITTED, "ALL_ACTIONS_ADMITTED",
            predecessor=snapshots[-1], stage_receipt_digest=action_digest,
        ))

        ledger = ledger or IdempotencyLedger()
        closures: list[ExecutionClosureReceipt] = []
        nonterminal: list[str] = []
        admissions_by_unit = {x.unit_id: x for x in action_admissions}
        for unit_id in sorted(topology_units):
            bundle = bundle_by_unit[unit_id]
            action_admission = admissions_by_unit[unit_id]
            if bundle.attempt is None:
                nonterminal.append(action_admission.action_id + ":NO_EXECUTION_ATTEMPT")
                continue
            closure = self.closure_court.close(
                admission=action_admission,
                attempt=bundle.attempt,
                ledger=ledger,
                readback=bundle.readback,
                rollback=bundle.rollback,
                rollback_required=mission.rollback_required,
            )
            closures.append(closure)
            if closure.state not in {ClosureState.EFFECT_VERIFIED, ClosureState.BEHAVIOUR_VERIFIED}:
                nonterminal.append(closure.action_id + ":" + closure.state.value)
        closure_digest = _digest([x.receipt_digest for x in closures])
        if nonterminal:
            snapshots.append(self._snapshot(
                mission, SpineStage.HELD, "EXECUTION_HELD_NOT_SEMANTICALLY_CLOSED",
                predecessor=snapshots[-1], stage_receipt_digest=closure_digest,
                reasons=sorted(nonterminal),
            ))
            return self._run_receipt(mission, snapshots, admission, topology, tuple(action_admissions), tuple(closures), None, frontier_plan, frontier_digest)
        snapshots.append(self._snapshot(
            mission, SpineStage.EXECUTION_CLOSED, "ALL_ACTIONS_SEMANTICALLY_CLOSED",
            predecessor=snapshots[-1], stage_receipt_digest=closure_digest,
        ))

        outcome = self.outcome_court.decide(
            mission=mission,
            required_actions=required_actions,
            closures=closures,
            outcome_evidence=outcome_evidence,
            proof_evidence=proof_evidence,
            value_observations=value_observations,
        )
        if outcome.state is MissionOutcomeState.HELD:
            snapshots.append(self._snapshot(
                mission, SpineStage.HELD, outcome.state.value,
                predecessor=snapshots[-1], stage_receipt_digest=outcome.receipt_digest,
                reasons=outcome.reasons,
            ))
        elif outcome.state is MissionOutcomeState.VALUE_OBSERVED:
            snapshots.append(self._snapshot(
                mission, SpineStage.VALUE_OBSERVED, outcome.state.value,
                predecessor=snapshots[-1], stage_receipt_digest=outcome.receipt_digest,
            ))
        else:
            snapshots.append(self._snapshot(
                mission, SpineStage.OUTCOME_PROVEN, outcome.state.value,
                predecessor=snapshots[-1], stage_receipt_digest=outcome.receipt_digest,
            ))
        return self._run_receipt(
            mission, snapshots, admission, topology,
            tuple(action_admissions), tuple(closures), outcome,
            frontier_plan, frontier_digest,
        )

    def _run_receipt(
        self,
        mission: MissionIR,
        snapshots: Sequence[SpineSnapshot],
        admission: MissionAdmissionReceipt | None,
        topology: ExecutionTopologyReceipt | None,
        action_admissions: tuple[ActionAdmissionReceipt, ...],
        closures: tuple[ExecutionClosureReceipt, ...],
        outcome: MissionOutcomeReceipt | None,
        frontier_plan: SuperstackPlan,
        frontier_plan_digest: str,
    ) -> SpineRunReceipt:
        if not self.verify_chain(snapshots):
            raise ValueError("AUTONOMIC_SPINE_CHAIN_INVALID")
        material = {
            "schema": SCHEMA,
            "version": VERSION,
            "mission": mission.digest(),
            "frontier_plan_digest": frontier_plan_digest,
            "frontier_gene_ids": frontier_plan.selected_gene_ids,
            "snapshots": [x.snapshot_digest for x in snapshots],
            "admission": admission.receipt_digest if admission else "",
            "topology": topology.receipt_digest if topology else "",
            "actions": [x.receipt_digest for x in action_admissions],
            "closures": [x.receipt_digest for x in closures],
            "outcome": outcome.receipt_digest if outcome else "",
        }
        return SpineRunReceipt(
            mission_id=mission.mission_id,
            snapshots=tuple(snapshots),
            frontier_gene_ids=frontier_plan.selected_gene_ids,
            frontier_plan_digest=frontier_plan_digest,
            mission_admission=admission,
            topology=topology,
            action_admissions=action_admissions,
            closures=closures,
            outcome=outcome,
            receipt_digest=_digest(material),
        )


__all__ = [
    "SCHEMA", "VERSION", "SpineStage", "SpineSnapshot", "ActionExecutionBundle",
    "SpineRunReceipt", "AutonomicMissionSpine",
]
