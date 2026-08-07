from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping, Protocol
import math

from .models import Claim, Domain, EvidenceRef, EvidenceStatus, Event, InformationClass, stable_sha256

@dataclass(frozen=True)
class PublicMarketObservation:
    source_id: str; instrument_id: str; metric: str; value: float; observed_at: str; locator: str
    currency: str | None = None; unit: str | None = None
    information_class: InformationClass = InformationClass.PUBLIC
    source_type: str = "public_market_data"
    def validate(self) -> None:
        if self.information_class is not InformationClass.PUBLIC: raise PermissionError("MARKET_BRIDGE_PUBLIC_DATA_ONLY")
        if not all((self.source_id,self.instrument_id,self.metric,self.observed_at,self.locator)): raise ValueError("market observation provenance fields are required")
        if not math.isfinite(float(self.value)): raise ValueError("market observation value must be finite")
        datetime.fromisoformat(self.observed_at.replace("Z","+00:00"))
    def fingerprint(self) -> str:
        return stable_sha256({"source_id":self.source_id,"instrument_id":self.instrument_id,"metric":self.metric,"value":self.value,"observed_at":self.observed_at,"locator":self.locator,"currency":self.currency,"unit":self.unit,"source_type":self.source_type})

class PublicMarketEvidenceAdapter(Protocol):
    def observations(self) -> Iterable[PublicMarketObservation]: ...

class MarketTruthGate:
    def accept(self, observation: PublicMarketObservation) -> PublicMarketObservation:
        observation.validate(); return observation
    def to_claim(self, observation: PublicMarketObservation) -> Claim:
        self.accept(observation)
        ref=EvidenceRef(observation.source_id,observation.source_type,observation.locator,observation.observed_at,observation.fingerprint(),"PUBLIC_MARKET_SOURCE")
        return Claim(observation.instrument_id,observation.metric,{"value":observation.value,"currency":observation.currency,"unit":observation.unit},EvidenceStatus.VERIFIED,[ref],InformationClass.PUBLIC,Domain.PUBLIC_MARKETS,1.0)
    def to_event(self, observation: PublicMarketObservation, materiality: float=0.5) -> Event:
        self.accept(observation)
        return Event("PUBLIC_MARKET_OBSERVATION",observation.source_id,observation.instrument_id,{"metric":observation.metric,"value":observation.value,"currency":observation.currency,"unit":observation.unit,"observation_hash":observation.fingerprint()},Domain.PUBLIC_MARKETS,InformationClass.PUBLIC,max(0.0,min(1.0,materiality)),occurred_at=observation.observed_at)

class MarketTwin:
    def __init__(self) -> None: self._gate=MarketTruthGate(); self._observations: dict[tuple[str,str],list[PublicMarketObservation]]={}
    def ingest(self, observations: Iterable[PublicMarketObservation]) -> int:
        count=0
        for observation in observations:
            obs=self._gate.accept(observation); key=(obs.instrument_id,obs.metric)
            if any(x.fingerprint()==obs.fingerprint() for x in self._observations.get(key,[])): continue
            self._observations.setdefault(key,[]).append(obs); self._observations[key].sort(key=lambda x:(x.observed_at,x.fingerprint())); count+=1
        return count
    def latest(self, instrument_id: str, metric: str) -> PublicMarketObservation | None:
        values=self._observations.get((instrument_id,metric),[]); return values[-1] if values else None
    def freshness_days(self, instrument_id: str, metric: str, now: datetime | None=None) -> float | None:
        latest=self.latest(instrument_id,metric)
        if latest is None: return None
        now=now or datetime.now(timezone.utc); observed=datetime.fromisoformat(latest.observed_at.replace("Z","+00:00")); return max(0.0,(now-observed).total_seconds()/86400)

@dataclass(frozen=True)
class FundamentalSignal:
    name: str; completion_probability: float; reliability: float
@dataclass(frozen=True)
class MarketDealTerms:
    current_target_price: float; consideration_value: float; downside_price: float; years_to_close: float=0.25; annual_discount_rate: float=0.05

class DealCompletionProbabilityEngine:
    def fundamental(self, signals: Iterable[FundamentalSignal]) -> float:
        signals=list(signals)
        if not signals: raise ValueError("at least one fundamental signal is required")
        for s in signals:
            if not 0<=s.completion_probability<=1 or not 0<=s.reliability<=1: raise ValueError("signal probabilities and reliability must be between 0 and 1")
        weight=sum(s.reliability for s in signals)
        if weight<=0: raise ValueError("fundamental signal reliability cannot sum to zero")
        return sum(s.completion_probability*s.reliability for s in signals)/weight
    def market_implied_proxy(self, terms: MarketDealTerms) -> float:
        if terms.consideration_value<=0 or terms.current_target_price<0 or terms.downside_price<0 or terms.years_to_close<0 or terms.annual_discount_rate<=-1: raise ValueError("invalid market deal terms")
        pv=terms.consideration_value/((1+terms.annual_discount_rate)**terms.years_to_close); denominator=pv-terms.downside_price
        if denominator<=0: raise ValueError("discounted consideration must exceed downside price")
        return max(0.0,min(1.0,(terms.current_target_price-terms.downside_price)/denominator))
    def expectation_gap(self, fundamental_probability: float, market_probability: float) -> float:
        if any(not 0<=p<=1 for p in (fundamental_probability,market_probability)): raise ValueError("probabilities must be between 0 and 1")
        return fundamental_probability-market_probability

@dataclass(frozen=True)
class RegimeScenario:
    name: str; risk_free_rate_delta: float=0.0; credit_spread_delta: float=0.0; equity_risk_premium_delta: float=0.0; terminal_multiple_delta_pct: float=0.0; probability: float=1.0

class RegimeAwareValuationEngine:
    def scenario(self, *, base_wacc: float, base_terminal_multiple: float, scenario: RegimeScenario) -> dict[str,float|str]:
        if base_wacc<=-1 or base_terminal_multiple<=0 or not 0<=scenario.probability<=1: raise ValueError("invalid valuation inputs")
        wacc=base_wacc+scenario.risk_free_rate_delta+scenario.credit_spread_delta+scenario.equity_risk_premium_delta; multiple=base_terminal_multiple*(1+scenario.terminal_multiple_delta_pct)
        if wacc<=-1 or multiple<=0: raise ValueError("scenario creates invalid valuation state")
        return {"scenario":scenario.name,"wacc":wacc,"terminal_multiple":multiple,"probability":scenario.probability}
    def expected_parameters(self, scenarios: Iterable[Mapping[str,float|str]]) -> dict[str,float]:
        scenarios=list(scenarios); total=sum(float(s["probability"]) for s in scenarios)
        if not scenarios or total<=0: raise ValueError("positive scenario probability is required")
        return {"expected_wacc":sum(float(s["wacc"])*float(s["probability"]) for s in scenarios)/total,"expected_terminal_multiple":sum(float(s["terminal_multiple"])*float(s["probability"]) for s in scenarios)/total}

class ExposureImpactBridge:
    def impact(self, exposures: Mapping[str,float], shocks: Mapping[str,float]) -> dict[str,float]:
        drivers=sorted(set(exposures)|set(shocks)); impacts={d:float(exposures.get(d,0))*float(shocks.get(d,0)) for d in drivers}; impacts["TOTAL"]=sum(impacts.values()); return impacts

class FinancingMarketRadar:
    def annual_cost_delta(self, debt_amount: float, benchmark_rate_delta: float, credit_spread_delta: float=0.0, hedge_offset: float=0.0) -> float:
        if debt_amount<0: raise ValueError("debt_amount cannot be negative")
        return debt_amount*(benchmark_rate_delta+credit_spread_delta-hedge_offset)

class PublicTradingIntelligenceBridge:
    """One-way PUBLIC evidence bridge. It intentionally has no order/transfer interface."""
    def __init__(self, adapter: PublicMarketEvidenceAdapter) -> None: self.adapter=adapter; self.gate=MarketTruthGate()
    def read_public_evidence(self) -> list[PublicMarketObservation]: return [self.gate.accept(x) for x in self.adapter.observations()]
    def private_claim_to_market(self, claim: Claim) -> None: raise PermissionError("PRIVATE_MNA_TO_TRADING_BRIDGE_DOES_NOT_EXIST")
