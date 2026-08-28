from __future__ import annotations

"""Federation-level intelligence over the Living State graph.

Internal/advisory only: topology simulation, calibration, attention allocation,
immune signals and capability-genome experiments. It creates no provider or
external-effect authority.
"""

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Sequence

from .model import LivingWorldModel
from .types import (
    CausalStatus, EdgeKind, FabricError, LearningClass, NodeKind, ProofMaturity,
    RouteEstimate, _PROOF_RANK, _id, digest,
)

EVOLUTION_INTELLIGENCE_SCHEMA = "FEDERATION-LIVING-EVOLUTION-INTELLIGENCE-V1"


@dataclass(frozen=True)
class MissionAttentionSignal:
    mission_id: str
    consequence: float
    deadline_pressure: float
    uncertainty: float
    information_gain: float
    proof_gap: float
    blocker_pressure: float
    owner_burden: float
    reversible: bool = True
    matter_scope: str = "GLOBAL"

    def validate(self):
        _id(self.mission_id, "mission_id")
        for name in ("consequence","deadline_pressure","uncertainty","information_gain","proof_gap","blocker_pressure","owner_burden"):
            if not 0 <= float(getattr(self, name)) <= 1:
                raise ValueError(f"{name} must be in [0,1]")
        if not self.matter_scope:
            raise ValueError("matter_scope required")
        return self

    @property
    def priority(self) -> float:
        self.validate()
        return max(0.0, round(
            .25*self.consequence + .18*self.deadline_pressure + .15*self.uncertainty
            + .16*self.information_gain + .12*self.proof_gap + .10*self.blocker_pressure
            - .08*self.owner_burden + (.06 if self.reversible else -.04), 8))


@dataclass(frozen=True)
class AttentionAllocation:
    mission_id: str
    share: float
    priority: float
    disposition: str
    external_effect: bool = False


@dataclass(frozen=True)
class CounterfactualResult:
    removed_nodes: tuple[str, ...]
    impacted_nodes: tuple[str, ...]
    impacted_missions: tuple[str, ...]
    impacted_capabilities: tuple[str, ...]
    blast_radius: int
    topology_only: bool = True
    causal_claim: bool = False
    external_effect: bool = False


@dataclass(frozen=True)
class CalibrationReport:
    route_id: str
    samples: int
    predicted_reliability: float
    observed_rate: float
    absolute_error: float
    brier_like_error: float
    calibrated: bool
    external_effect: bool = False


@dataclass(frozen=True)
class ImmuneSignal:
    signal_id: str
    severity: str
    signal_class: str
    target_id: str
    evidence_refs: tuple[str, ...]
    recommended_response: str
    quarantine_effectful_path: bool
    external_effect: bool = False


@dataclass(frozen=True)
class GenomeCandidate:
    candidate_id: str
    action: str
    target_ids: tuple[str, ...]
    expected_debt_reduction: float
    reuse_score: float
    proof_gain: float
    resilience_gain: float
    owner_load_reduction: float
    complexity_cost: float
    score: float
    disposition: str = "SHADOW_EXPERIMENT_ONLY"
    external_effect: bool = False


@dataclass(frozen=True)
class FitnessVector:
    proof: float
    freshness: float
    resilience: float
    calibration: float
    context: float
    owner_load: float
    causal_integrity: float
    opportunity_readiness: float
    measured_dimensions: int

    @property
    def harmonic_fitness(self) -> float:
        values = [x for x in (self.proof,self.freshness,self.resilience,self.calibration,self.context,self.owner_load,self.causal_integrity,self.opportunity_readiness) if x >= 0]
        if not values:
            return 0.0
        return round(len(values) / sum(1.0/max(1e-6,x) for x in values), 8)


class FederationEvolutionIntelligence:
    def __init__(self, model: LivingWorldModel):
        self.model = model

    def dependency_impact(self, removed_nodes: Sequence[str]) -> CounterfactualResult:
        removed = tuple(sorted({_id(x, "removed_node") for x in removed_nodes}))
        if not removed:
            raise ValueError("counterfactual requires at least one removed node")
        nodes = self.model.current_nodes()
        missing = [x for x in removed if x not in nodes]
        if missing:
            raise FabricError(f"counterfactual node absent: {missing[0]}")
        reverse: dict[str,set[str]] = {}
        for edge in self.model._edges.values():
            if edge.kind in {EdgeKind.DEPENDS_ON,EdgeKind.ROUTES_THROUGH,EdgeKind.CONSUMES,EdgeKind.PROVEN_BY}:
                reverse.setdefault(edge.target_id,set()).add(edge.source_id)
            elif edge.kind in {EdgeKind.PROVIDES,EdgeKind.IMPROVES}:
                reverse.setdefault(edge.source_id,set()).add(edge.target_id)
            elif edge.kind == EdgeKind.CAUSES and edge.causal_status == CausalStatus.VERIFIED:
                reverse.setdefault(edge.source_id,set()).add(edge.target_id)
        impacted, frontier = set(removed), list(removed)
        while frontier:
            for dep in sorted(reverse.get(frontier.pop(), ())):
                if dep not in impacted:
                    impacted.add(dep); frontier.append(dep)
        impacted_nodes = tuple(sorted(impacted.difference(removed)))
        return CounterfactualResult(
            removed, impacted_nodes,
            tuple(sorted(x for x in impacted_nodes if nodes[x].kind == NodeKind.MISSION)),
            tuple(sorted(x for x in impacted_nodes if nodes[x].kind == NodeKind.CAPABILITY)),
            len(impacted_nodes))

    def fragility_ranking(self):
        nodes = self.model.current_nodes()
        rows=[]
        for nid in sorted(nodes):
            r=self.dependency_impact((nid,))
            rows.append({"node_id":nid,"kind":nodes[nid].kind.value,"blast_radius":r.blast_radius,"mission_exposure":len(r.impacted_missions),"capability_exposure":len(r.impacted_capabilities),"topology_only":True})
        return tuple(sorted(rows,key=lambda x:(x["mission_exposure"],x["blast_radius"],x["node_id"]),reverse=True))

    @staticmethod
    def _dominates(a: RouteEstimate,b: RouteEstimate) -> bool:
        ab=(a.reliability,a.proof_freshness,a.proof_strength); bb=(b.reliability,b.proof_freshness,b.proof_strength)
        ac=(a.latency_penalty,a.cost_penalty,a.owner_burden_penalty,a.risk_penalty); bc=(b.latency_penalty,b.cost_penalty,b.owner_burden_penalty,b.risk_penalty)
        return all(x>=y for x,y in zip(ab,bb)) and all(x<=y for x,y in zip(ac,bc)) and (any(x>y for x,y in zip(ab,bb)) or any(x<y for x,y in zip(ac,bc)))

    def route_pareto_frontier(self, *, min_samples: int=1):
        est=self.model.route_estimates(min_samples=min_samples)
        return tuple(sorted((x for x in est if not any(y.route_id!=x.route_id and self._dominates(y,x) for y in est)),key=lambda x:(x.score,x.route_id),reverse=True))

    def calibration(self, *, min_samples: int=3):
        estimates={x.route_id:x for x in self.model.route_estimates(min_samples=min_samples)}
        grouped: dict[str,list[bool]]={}
        for s in self.model._telemetry: grouped.setdefault(s.route_id,[]).append(bool(s.success))
        out=[]
        for rid, outcomes in sorted(grouped.items()):
            e=estimates[rid]; obs=sum(outcomes)/len(outcomes); err=abs(e.reliability-obs)
            out.append(CalibrationReport(rid,len(outcomes),round(e.reliability,8),round(obs,8),round(err,8),round((e.reliability-obs)**2,8),len(outcomes)>=min_samples and err<=.20))
        return tuple(out)

    def allocate_attention(self, signals: Sequence[MissionAttentionSignal], *, total_budget: float=1.0, reserve_fraction: float=.10):
        if not 0 < total_budget <= 1 or not 0 <= reserve_fraction < 1: raise ValueError("invalid attention budget")
        if not signals: return ()
        vals=[x.validate() for x in signals]; scores=[x.priority for x in vals]; d=sum(scores); budget=total_budget*(1-reserve_fraction)
        if d<=0: return tuple(AttentionAllocation(x.mission_id,round(budget/len(vals),8),x.priority,"EQUAL_UNMEASURED") for x in vals)
        return tuple(AttentionAllocation(x.mission_id,round(budget*s/d,8),s,"ALLOCATE_INTERNAL_ATTENTION") for x,s in sorted(zip(vals,scores),key=lambda p:(p[1],p[0].mission_id),reverse=True))

    @staticmethod
    def _immune(cls,target,severity,refs,response,quarantine):
        refs=tuple(sorted(set(str(x) for x in refs if str(x)))); body={"class":cls,"target":target,"severity":severity,"refs":refs,"response":response}
        return ImmuneSignal(f"IMM-{digest(body)[:20].upper()}",severity,cls,target,refs,response,quarantine)

    def immune_scan(self, *, now: str):
        out=[]
        for nid in self.model.split_brain_nodes(now=now):
            e=self.model.state_estimate(nid,now=now); out.append(self._immune("SPLIT_BRAIN",nid,"HIGH",(e.proof_ref,),"RECONCILE_AND_HOLD_EFFECTFUL_PATH",True))
        for nid in sorted(self.model._node_history):
            e=self.model.state_estimate(nid,now=now)
            if not e.fresh and e.proof_rank>=_PROOF_RANK[ProofMaturity.RUNTIME_READBACK]: out.append(self._immune("STALE_RUNTIME_PROOF",nid,"MEDIUM",(e.proof_ref,),"REPROBE_BEFORE_USE",True))
        p=self.model.route_portfolio(min_samples=1)
        for fd in p.hidden_spofs: out.append(self._immune("HIDDEN_SPOF",fd,"HIGH",(x.route_id for x in p.estimates),"FORM_DIVERSE_SHADOW",False))
        for l in self.model._learning:
            if l.recurrence>=3: out.append(self._immune("RECURRING_FAILURE",l.learning_id,"HIGH",l.proof_refs,"REDESIGN_OR_ROLLBACK",False))
            elif l.learning_class==LearningClass.NEAR_MISS and l.recurrence>=2: out.append(self._immune("REPEATED_NEAR_MISS",l.learning_id,"MEDIUM",l.proof_refs,"STRENGTHEN_PREVENTIVE_CONTROL",False))
        for c in self.model._contexts.values():
            if c.action()=="CHECKPOINT_AND_HANDOFF": out.append(self._immune("CONTEXT_EXHAUSTION",c.context_id,"MEDIUM",c.source_refs,"CHECKPOINT_AND_HANDOFF",False))
        return tuple(sorted(out,key=lambda x:(x.severity,x.signal_class,x.target_id),reverse=True))

    def genome_candidates(self, *, now: str):
        debt=self.model.debt_report(now=now); out=[]
        mapping=(("proof_debt","STRENGTHEN_PROOF_SENSOR",.9,.8,.2,.5),("freshness_debt","ADD_FRESHNESS_REFLEX",.95,.75,.1,.35),("resilience_debt","ADD_DIVERSE_SHADOW_ROUTE",.75,.9,.2,.55),("context_debt","ADD_CONTEXT_COMPACTION_GENE",.85,.55,.8,.30),("owner_burden_debt","AUTOMATE_OWNER_LOAD_GENE",.80,.50,.95,.40),("causal_debt","ADD_CAUSAL_FALSIFIER_EXPERIMENT",.65,.45,.1,.50),("benchmark_debt","REFRESH_CFBE_GENE",.90,.30,.2,.20))
        for key,action,reuse,resilience,owner,complexity in mapping:
            count=int(debt.get(key,0))
            if count<=0: continue
            reduction=min(1.0,.35+.12*count); proof=.8 if key in {"proof_debt","freshness_debt","benchmark_debt","causal_debt"} else .45
            score=.28*reduction+.18*reuse+.18*proof+.16*resilience+.14*owner-.06*complexity
            out.append(GenomeCandidate(f"GENE-{digest({'debt':key,'action':action,'count':count})[:20].upper()}",action,(key,),round(reduction,8),reuse,proof,resilience,owner,complexity,round(score,8)))
        return tuple(sorted(out,key=lambda x:(x.score,x.candidate_id),reverse=True))

    def fitness_vector(self, *, now: str):
        nodes=[self.model.state_estimate(x,now=now) for x in self.model._node_history]; routes=self.model.route_estimates(min_samples=1); cals=self.calibration(min_samples=1); contexts=tuple(self.model._contexts.values())
        proof=sum(min(1,x.proof_rank/max(_PROOF_RANK.values())) for x in nodes)/len(nodes) if nodes else -1
        fresh=sum(1 if x.fresh else 0 for x in nodes)/len(nodes) if nodes else -1
        resilience=1.0 if not routes else max(0.0,1.0-min(1.0,len(self.model.route_portfolio(min_samples=1).hidden_spofs)))
        calibration=sum(max(0,1-x.absolute_error) for x in cals)/len(cals) if cals else -1
        context=sum(1-min(1,x.pressure) for x in contexts)/len(contexts) if contexts else -1
        owner=sum(1-x.owner_burden_penalty for x in routes)/len(routes) if routes else -1
        causal=[x for x in self.model._edges.values() if x.kind in {EdgeKind.CAUSES,EdgeKind.CORRELATES_WITH}]
        causal_integrity=sum(1 if x.kind!=EdgeKind.CAUSES or x.causal_evidence.verified else 0 for x in causal)/len(causal) if causal else 1.0
        opp=[x for x in self.model.current_nodes().values() if x.kind==NodeKind.OPPORTUNITY]
        opportunity=sum(1 if x.payload.get("buildable_now") else .5 for x in opp)/len(opp) if opp else -1
        vals=[proof,fresh,resilience,calibration,context,owner,causal_integrity,opportunity]
        return FitnessVector(*[round(x,8) for x in vals],measured_dimensions=sum(1 for x in vals if x>=0))

    def anti_goodhart_gate(self, *, baseline: FitnessVector, candidate: FitnessVector, claimed_target_improvement: str, regression_tolerance: float=.10):
        if not 0<=regression_tolerance<=1: raise ValueError("regression_tolerance must be in [0,1]")
        fields=("proof","freshness","resilience","calibration","context","owner_load","causal_integrity","opportunity_readiness")
        if claimed_target_improvement not in fields: raise ValueError("claimed target must be a fitness dimension")
        regressions=tuple(f for f in fields if getattr(baseline,f)>=0 and getattr(candidate,f)>=0 and getattr(candidate,f)+regression_tolerance<getattr(baseline,f))
        improved=getattr(baseline,claimed_target_improvement)>=0 and getattr(candidate,claimed_target_improvement)>getattr(baseline,claimed_target_improvement)
        harmonic=candidate.harmonic_fitness+regression_tolerance>=baseline.harmonic_fitness; passed=improved and harmonic and not regressions
        return {"passed":passed,"target":claimed_target_improvement,"target_improved":improved,"harmonic_not_worse":harmonic,"material_regressions":regressions,"disposition":"PROMOTION_GATE_CONTINUE" if passed else "HOLD_GOODHART_RISK","external_effect":False}


def run_evolution_intelligence_canary() -> dict[str,Any]:
    from .canary import learning_event
    from .types import ContextState, Provenance, RouteTelemetry, WorldEdge, WorldNode
    now="2026-08-28T05:00:00+00:00"; m=LivingWorldModel(); p=Provenance("source","proof",now,ProofMaturity.DETERMINISTIC_TESTED,3600,.9)
    for n in (WorldNode("provider:P",NodeKind.PROVIDER,"P","READY",{},p),WorldNode("capability:C",NodeKind.CAPABILITY,"C","ACTIVE",{},p),WorldNode("mission:M",NodeKind.MISSION,"M","ACTIVE",{},p)): m.observe_node(n)
    m.observe_edge(WorldEdge("e1","capability:C","provider:P",EdgeKind.DEPENDS_ON,p)); m.observe_edge(WorldEdge("e2","mission:M","capability:C",EdgeKind.DEPENDS_ON,p))
    for rid,fd,outs in (("A","FD1",(1,1,1)),("B","FD2",(1,1,0)),("C","FD1",(1,0,0))):
        for i,s in enumerate(outs): m.observe_route_telemetry(RouteTelemetry(rid,"M",now,bool(s),10+i,.1,.1,.9,.9,.1,(fd,),f"p-{rid}-{i}"))
    m.observe_context(ContextState("CTX",950,1000,.2,2,source_refs=("ctx",)))
    m.observe_learning(learning_event(learning_class=LearningClass.NEAR_MISS,fingerprint="NEAR-MISS",observed_at=now,matter_scope="GLOBAL",route_id="A",signal="s",diagnosis="d",hypothesis="h",test_ref="t",result_ref="r",proof_refs=("near",),recurrence=2,independent_evidence=True))
    intel=FederationEvolutionIntelligence(m); impact=intel.dependency_impact(("provider:P",)); frag=intel.fragility_ranking(); frontier=intel.route_pareto_frontier(); cal=intel.calibration()
    attention=intel.allocate_attention((MissionAttentionSignal("M",1,1,.8,.9,.7,.5,.1),MissionAttentionSignal("M2",.2,.1,.2,.2,.2,.1,.1)))
    immune=intel.immune_scan(now=now); genome=intel.genome_candidates(now=now); fitness=intel.fitness_vector(now=now)
    base=FitnessVector(.7,.7,.7,.7,.7,.7,.9,.5,8); good=FitnessVector(.8,.75,.7,.72,.7,.72,.9,.6,8); bad=FitnessVector(.9,.2,.2,.7,.7,.7,.9,.5,8)
    gg=intel.anti_goodhart_gate(baseline=base,candidate=good,claimed_target_improvement="proof"); gb=intel.anti_goodhart_gate(baseline=base,candidate=bad,claimed_target_improvement="proof")
    checks={"counterfactual_impacts_mission":"mission:M" in impact.impacted_missions,"counterfactual_is_not_causal_claim":impact.topology_only and not impact.causal_claim,"fragility_ranking_present":bool(frag),"pareto_frontier_nonempty":bool(frontier),"calibration_nonempty":bool(cal),"attention_prioritizes_high_value_mission":attention[0].mission_id=="M" and attention[0].share>attention[1].share,"attention_reserves_budget":sum(x.share for x in attention)<1,"immune_detects_context_exhaustion":any(x.signal_class=="CONTEXT_EXHAUSTION" for x in immune),"immune_detects_repeated_near_miss":any(x.signal_class=="REPEATED_NEAR_MISS" for x in immune),"genome_candidate_created":bool(genome),"genome_stays_shadow_experiment":all(x.disposition=="SHADOW_EXPERIMENT_ONLY" for x in genome),"fitness_is_multi_dimensional":fitness.measured_dimensions>=6,"goodhart_allows_balanced_improvement":gg["passed"],"goodhart_blocks_metric_gaming":not gb["passed"] and "freshness" in gb["material_regressions"],"zero_external_effects":m.external_effects==0 and all(not x.external_effect for x in immune)}
    return {"schema":"FEDERATION-EVOLUTION-INTELLIGENCE-CANARY-V1","status":"PASS" if all(checks.values()) else "FAIL","count":len(checks),"checks":checks,"external_effects":m.external_effects,"receipt_sha256":digest({"checks":checks,"fitness":asdict(fitness),"impact":asdict(impact)}),"truth_boundary":{"counterfactual_is_topology_not_causation":True,"attention_is_internal_budget_not_compute_execution":True,"genome_candidates_are_shadow_only":True,"immune_actions_are_recommendations_not_provider_mutations":True,"external_effect_authority_created":False}}


__all__=["EVOLUTION_INTELLIGENCE_SCHEMA","MissionAttentionSignal","AttentionAllocation","CounterfactualResult","CalibrationReport","ImmuneSignal","GenomeCandidate","FitnessVector","FederationEvolutionIntelligence","run_evolution_intelligence_canary"]
