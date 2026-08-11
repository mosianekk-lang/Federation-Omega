from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

@dataclass(frozen=True)
class AcquisitionThesis:
    sectors: tuple[str, ...] = ()
    geographies: tuple[str, ...] = ()
    min_revenue: float = 0.0
    max_revenue: float | None = None
    min_ebitda_margin: float = 0.0
    max_leverage: float | None = None
    required_recurring_revenue: float = 0.0
    strategic_priorities: tuple[str, ...] = ()

@dataclass(frozen=True)
class TargetCandidate:
    target_id: str
    name: str
    sector: str
    geography: str
    revenue: float
    ebitda_margin: float
    leverage: float
    recurring_revenue: float
    strategic_tags: tuple[str, ...] = ()

@dataclass(frozen=True)
class TargetAssessment:
    target_id: str
    eligible: bool
    score: float
    hard_failures: tuple[str, ...]
    strengths: tuple[str, ...]

class ThesisCompiler:
    """Compile owner/investor objectives into deterministic acquisition gates."""
    def compile(self, objective: Mapping[str, object]) -> AcquisitionThesis:
        sectors=tuple(str(x).strip().lower() for x in objective.get('sectors',()) if str(x).strip())
        geos=tuple(str(x).strip().lower() for x in objective.get('geographies',()) if str(x).strip())
        priorities=tuple(str(x).strip().lower() for x in objective.get('strategic_priorities',()) if str(x).strip())
        mr=objective.get('max_revenue'); ml=objective.get('max_leverage')
        thesis=AcquisitionThesis(sectors,geos,max(0.0,float(objective.get('min_revenue',0.0))),None if mr in (None,'') else float(mr),float(objective.get('min_ebitda_margin',0.0)),None if ml in (None,'') else float(ml),min(1.0,max(0.0,float(objective.get('required_recurring_revenue',0.0)))),priorities)
        if thesis.max_revenue is not None and thesis.max_revenue < thesis.min_revenue: raise ValueError('max_revenue must be >= min_revenue')
        if thesis.max_leverage is not None and thesis.max_leverage < 0: raise ValueError('max_leverage cannot be negative')
        return thesis

class TargetScreenEngine:
    def assess(self, thesis: AcquisitionThesis, target: TargetCandidate) -> TargetAssessment:
        failures=[]; sector=target.sector.strip().lower(); geo=target.geography.strip().lower()
        if thesis.sectors and sector not in thesis.sectors: failures.append('SECTOR_OUTSIDE_THESIS')
        if thesis.geographies and geo not in thesis.geographies: failures.append('GEOGRAPHY_OUTSIDE_THESIS')
        if target.revenue < thesis.min_revenue: failures.append('REVENUE_BELOW_MINIMUM')
        if thesis.max_revenue is not None and target.revenue > thesis.max_revenue: failures.append('REVENUE_ABOVE_MAXIMUM')
        if target.ebitda_margin < thesis.min_ebitda_margin: failures.append('MARGIN_BELOW_MINIMUM')
        if thesis.max_leverage is not None and target.leverage > thesis.max_leverage: failures.append('LEVERAGE_ABOVE_MAXIMUM')
        if target.recurring_revenue < thesis.required_recurring_revenue: failures.append('RECURRING_REVENUE_BELOW_MINIMUM')
        matches=len(set(x.lower() for x in target.strategic_tags)&set(thesis.strategic_priorities)); fit=matches/max(1,len(thesis.strategic_priorities))
        margin=max(0.0,min(1.0,(target.ebitda_margin-thesis.min_ebitda_margin+0.10)/0.30)); recurring=max(0.0,min(1.0,target.recurring_revenue)); leverage=1.0 if thesis.max_leverage is None else max(0.0,min(1.0,1-target.leverage/max(thesis.max_leverage,0.01)))
        score=round(100*(.35*fit+.25*margin+.25*recurring+.15*leverage),2)
        strengths=[]
        if fit>=.5: strengths.append('STRATEGIC_PRIORITY_MATCH')
        if recurring>=.7: strengths.append('HIGH_RECURRING_REVENUE')
        if target.ebitda_margin>=max(.20,thesis.min_ebitda_margin): strengths.append('STRONG_MARGIN')
        return TargetAssessment(target.target_id,not failures,score if not failures else 0.0,tuple(failures),tuple(strengths))
    def rank(self, thesis: AcquisitionThesis, targets: Iterable[TargetCandidate]) -> list[TargetAssessment]:
        return sorted((self.assess(thesis,t) for t in targets),key=lambda x:(x.eligible,x.score),reverse=True)

@dataclass(frozen=True)
class StrategicRoute:
    route: str
    expected_value: float
    cash_cost: float
    months_to_capability: float
    control: float
    execution_risk: float
@dataclass(frozen=True)
class RouteAssessment:
    route: str
    score: float
class BuildBuyPartnerEngine:
    def rank(self, routes: Sequence[StrategicRoute]) -> list[RouteAssessment]:
        if not routes:return []
        mv=max(max(r.expected_value,0.0) for r in routes) or 1.0; mc=max(max(r.cash_cost,0.0) for r in routes) or 1.0; mt=max(max(r.months_to_capability,0.0) for r in routes) or 1.0
        out=[]
        for r in routes:
            score=100*(.35*max(0,r.expected_value)/mv+.15*(1-max(0,r.cash_cost)/mc)+.15*(1-max(0,r.months_to_capability)/mt)+.20*max(0,min(1,r.control))+.15*(1-max(0,min(1,r.execution_risk))))
            out.append(RouteAssessment(r.route,round(score,2)))
        return sorted(out,key=lambda x:x.score,reverse=True)
class StrategicScarcityEngine:
    def score(self, *, qualified_targets:int, buyer_competition:float, capability_uniqueness:float) -> float:
        scarcity=1-min(1,max(0,qualified_targets)/20);return round(100*(.45*scarcity+.30*max(0,min(1,buyer_competition))+.25*max(0,min(1,capability_uniqueness))),2)
class WhiteSpaceDetector:
    def gaps(self, required_capabilities: Iterable[str], owned_capabilities: Iterable[str]) -> tuple[str,...]:
        owned={x.strip().lower() for x in owned_capabilities};return tuple(sorted({x.strip().lower() for x in required_capabilities if x.strip() and x.strip().lower() not in owned}))
