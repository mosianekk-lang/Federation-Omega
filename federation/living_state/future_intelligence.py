from __future__ import annotations

"""Future-state, experiment, explanation and retirement intelligence.

All outputs are internal simulations/proposals. No provider mutation, deletion,
or causal promotion is performed here.
"""

from dataclasses import asdict, dataclass
from typing import Any, Sequence

from .evolution_intelligence import FederationEvolutionIntelligence
from .model import LivingWorldModel
from .types import FabricError, NodeKind, ProofMaturity, _id, digest

FUTURE_INTELLIGENCE_SCHEMA = "FEDERATION-LIVING-FUTURE-INTELLIGENCE-V1"


@dataclass(frozen=True)
class ScenarioShock:
    scenario_id: str
    node_id: str
    assumed_state: str
    probability: float
    severity: float
    proof_ref: str

    def validate(self):
        _id(self.scenario_id, "scenario_id"); _id(self.node_id, "node_id")
        if not self.assumed_state or not self.proof_ref: raise ValueError("scenario state/proof required")
        if not 0 <= self.probability <= 1 or not 0 <= self.severity <= 1: raise ValueError("probability/severity must be in [0,1]")
        return self


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    node_id: str
    assumed_state: str
    probability: float
    severity: float
    blast_radius: int
    impacted_missions: tuple[str,...]
    weighted_exposure: float
    simulation_only: bool = True
    causal_claim: bool = False
    external_effect: bool = False


@dataclass(frozen=True)
class ExperimentCandidate:
    experiment_id: str
    hypothesis: str
    target_id: str
    information_gain: float
    falsifiability: float
    reversibility: float
    proof_gap: float
    cost: float
    risk: float
    proof_ref: str
    external_effect: bool = False

    def validate(self):
        _id(self.experiment_id, "experiment_id"); _id(self.target_id, "target_id")
        if not self.hypothesis or not self.proof_ref: raise ValueError("hypothesis/proof required")
        for n in ("information_gain","falsifiability","reversibility","proof_gap","cost","risk"):
            if not 0 <= float(getattr(self,n)) <= 1: raise ValueError(f"{n} must be in [0,1]")
        return self

    @property
    def utility(self):
        self.validate()
        return round(.30*self.information_gain+.24*self.falsifiability+.18*self.reversibility+.16*self.proof_gap-.05*self.cost-.07*self.risk,8)


@dataclass(frozen=True)
class ExperimentDecision:
    selected_experiment_id: str
    utility: float
    rejected: tuple[str,...]
    disposition: str
    causal_promotion: bool = False
    external_effect: bool = False


@dataclass(frozen=True)
class RetirementProposal:
    node_id: str
    state: str
    mission_exposure: int
    blast_radius: int
    archive_required: bool
    deletion_permitted: bool
    disposition: str
    proof_ref: str
    external_effect: bool = False


class FederationFutureIntelligence:
    def __init__(self, model: LivingWorldModel):
        self.model=model; self.evolution=FederationEvolutionIntelligence(model)

    def scenario_ensemble(self, shocks: Sequence[ScenarioShock]):
        if not shocks: raise ValueError("scenario ensemble requires shocks")
        out=[]
        for s in shocks:
            s.validate()
            if s.node_id not in self.model.current_nodes(): raise FabricError(f"scenario node absent: {s.node_id}")
            impact=self.evolution.dependency_impact((s.node_id,))
            out.append(ScenarioResult(s.scenario_id,s.node_id,s.assumed_state,s.probability,s.severity,impact.blast_radius,impact.impacted_missions,round(s.probability*s.severity*max(1,impact.blast_radius),8)))
        return tuple(sorted(out,key=lambda x:(x.weighted_exposure,x.scenario_id),reverse=True))

    def shared_dependency_stress(self, *, limit:int=10):
        if limit<1: raise ValueError("limit must be positive")
        return self.evolution.fragility_ranking()[:limit]

    def design_experiment(self, candidates: Sequence[ExperimentCandidate]):
        if not candidates: raise ValueError("experiment candidates required")
        rejected=[]; safe=[]
        for c in candidates:
            c.validate()
            if c.external_effect: rejected.append(c.experiment_id)
            else: safe.append(c)
        if not safe: return ExperimentDecision("",0.0,tuple(sorted(rejected)),"HOLD_FOR_SEPARATE_EFFECT_ADMISSION")
        winner=max(safe,key=lambda x:(x.utility,x.experiment_id))
        return ExperimentDecision(winner.experiment_id,winner.utility,tuple(sorted(rejected)),"RUN_REVERSIBLE_INTERNAL_FALSIFIER")

    def explain_state(self, node_id:str, *, now:str):
        _id(node_id,"node_id")
        estimate=self.model.state_estimate(node_id,now=now)
        if estimate.proof_maturity==ProofMaturity.UNKNOWN.value: raise FabricError(f"node absent: {node_id}")
        events=tuple(e.event_digest for e in self.model._events if e.object_id==node_id)
        return {"node_id":node_id,"selected_state":estimate.state,"fresh":estimate.fresh,"proof_maturity":estimate.proof_maturity,"proof_rank":estimate.proof_rank,"confidence":estimate.confidence,"source_ref":estimate.source_ref,"proof_ref":estimate.proof_ref,"split_brain":estimate.split_brain,"alternatives":estimate.alternatives,"event_lineage":events,"reason":"HIGHEST_FRESH_PROOF_RANK_THEN_RECENCY_CONFIDENCE","external_effect":False}

    def explain_route(self, route_id:str):
        _id(route_id,"route_id")
        estimates={x.route_id:x for x in self.model.route_estimates(min_samples=1)}
        if route_id not in estimates: raise FabricError(f"route absent: {route_id}")
        e=estimates[route_id]
        return {"route_id":route_id,"score":e.score,"samples":e.samples,"reliability":e.reliability,"proof_freshness":e.proof_freshness,"proof_strength":e.proof_strength,"penalties":{"latency":e.latency_penalty,"cost":e.cost_penalty,"owner_burden":e.owner_burden_penalty,"risk":e.risk_penalty},"failure_domains":e.failure_domains,"measured":e.measured,"reason":"PROOF_RELIABILITY_BENEFITS_MINUS_OPERATIONAL_PENALTIES","external_effect":False}

    def retirement_proposals(self, *, now:str):
        proposals=[]; nodes=self.model.current_nodes(now=now)
        for nid,node in sorted(nodes.items()):
            if node.kind!=NodeKind.CAPABILITY: continue
            estimate=self.model.state_estimate(nid,now=now)
            state=estimate.state.removeprefix("STALE:").upper()
            if state not in {"INACTIVE","DEPRECATED","RETIRED","DISABLED"} and estimate.fresh: continue
            impact=self.evolution.dependency_impact((nid,))
            safe=len(impact.impacted_missions)==0
            proposals.append(RetirementProposal(nid,estimate.state,len(impact.impacted_missions),impact.blast_radius,True,False,"ARCHIVE_THEN_REVIEW" if safe else "HOLD_ACTIVE_DEPENDENCY",estimate.proof_ref))
        return tuple(proposals)


def run_future_intelligence_canary() -> dict[str,Any]:
    from .types import EdgeKind, NodeKind, ProofMaturity, Provenance, RouteTelemetry, WorldEdge, WorldNode
    now="2026-08-28T06:00:00+00:00"; m=LivingWorldModel(); p=Provenance("s","p",now,ProofMaturity.DETERMINISTIC_TESTED,3600,.9)
    for n in (WorldNode("provider:P",NodeKind.PROVIDER,"P","READY",{},p),WorldNode("capability:ACTIVE",NodeKind.CAPABILITY,"A","ACTIVE",{},p),WorldNode("capability:OLD",NodeKind.CAPABILITY,"O","DEPRECATED",{},p),WorldNode("mission:M",NodeKind.MISSION,"M","ACTIVE",{},p)): m.observe_node(n)
    m.observe_edge(WorldEdge("e1","capability:ACTIVE","provider:P",EdgeKind.DEPENDS_ON,p)); m.observe_edge(WorldEdge("e2","mission:M","capability:ACTIVE",EdgeKind.DEPENDS_ON,p))
    for i in range(3): m.observe_route_telemetry(RouteTelemetry("route:A","M",now,True,10,.1,.1,.9,.9,.1,("FD",),f"r{i}"))
    intel=FederationFutureIntelligence(m)
    scenarios=intel.scenario_ensemble((ScenarioShock("S1","provider:P","DOWN",.4,.9,"scenario-proof"),))
    experiments=intel.design_experiment((ExperimentCandidate("E1","provider dependency causes mission exposure","provider:P",.9,.9,1,.8,.1,.1,"exp-proof"),ExperimentCandidate("E2","effectful probe","provider:P",1,1,.1,.8,.5,.5,"e2",True)))
    explanation=intel.explain_state("provider:P",now=now); route=intel.explain_route("route:A"); retire=intel.retirement_proposals(now=now); stress=intel.shared_dependency_stress()
    checks={"scenario_impacts_mission":"mission:M" in scenarios[0].impacted_missions,"scenario_is_not_causal_claim":scenarios[0].simulation_only and not scenarios[0].causal_claim,"stress_ranks_provider":stress[0]["node_id"]=="provider:P","experiment_prefers_reversible_internal":experiments.selected_experiment_id=="E1","experiment_rejects_effectful":"E2" in experiments.rejected and not experiments.external_effect,"experiment_does_not_promote_causation":not experiments.causal_promotion,"state_explanation_has_proof":explanation["proof_ref"]=="p" and bool(explanation["event_lineage"]),"route_explanation_has_components":route["proof_strength"]>.8 and "risk" in route["penalties"],"retirement_is_archive_first":retire and retire[0].node_id=="capability:OLD" and retire[0].archive_required,"retirement_never_deletes":all(not x.deletion_permitted for x in retire),"all_outputs_effect_free":all(not x.external_effect for x in scenarios+retire) and not experiments.external_effect,"zero_external_effects":m.external_effects==0}
    return {"schema":"FEDERATION-FUTURE-INTELLIGENCE-CANARY-V1","status":"PASS" if all(checks.values()) else "FAIL","count":len(checks),"checks":checks,"external_effects":m.external_effects,"receipt_sha256":digest({"checks":checks,"scenario":asdict(scenarios[0]),"experiment":asdict(experiments)}),"truth_boundary":{"scenario_is_simulation_not_prediction_fact":True,"scenario_topology_is_not_causation":True,"experiment_selection_does_not_execute_provider_actions":True,"explanation_is_trace_not_new_proof":True,"retirement_is_archive_first_and_non_deleting":True,"external_effect_authority_created":False}}


__all__=["FUTURE_INTELLIGENCE_SCHEMA","ScenarioShock","ScenarioResult","ExperimentCandidate","ExperimentDecision","RetirementProposal","FederationFutureIntelligence","run_future_intelligence_canary"]
