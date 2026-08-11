from __future__ import annotations
from dataclasses import dataclass
from statistics import median
from typing import Iterable
import math
@dataclass(frozen=True)
class ForecastCashFlow: year:int; free_cash_flow:float
@dataclass(frozen=True)
class DCFResult:
    enterprise_value:float; pv_explicit_cash_flows:float; pv_terminal_value:float; terminal_value:float; wacc:float; terminal_growth:float
class DCFEngine:
    def value(self,forecasts:Iterable[ForecastCashFlow],wacc:float,terminal_growth:float)->DCFResult:
        flows=sorted(list(forecasts),key=lambda x:x.year)
        if not flows: raise ValueError('forecast cash flows required')
        if any(f.year<=0 for f in flows) or len({f.year for f in flows})!=len(flows): raise ValueError('forecast years must be unique positive integers')
        if wacc<=terminal_growth or wacc<=-1 or terminal_growth<=-1: raise ValueError('wacc must exceed terminal growth and rates must be valid')
        pv=sum(f.free_cash_flow/((1+wacc)**f.year) for f in flows); last=flows[-1]; terminal=last.free_cash_flow*(1+terminal_growth)/(wacc-terminal_growth); pvt=terminal/((1+wacc)**last.year); return DCFResult(pv+pvt,pv,pvt,terminal,wacc,terminal_growth)
    def sensitivity(self,forecasts:Iterable[ForecastCashFlow],wacc_values:Iterable[float],growth_values:Iterable[float])->dict[tuple[float,float],float|None]:
        flows=list(forecasts); result={}
        for w in wacc_values:
            for g in growth_values:
                try: result[(w,g)]=self.value(flows,w,g).enterprise_value
                except ValueError: result[(w,g)]=None
        return result
@dataclass(frozen=True)
class EquityBridge:
    enterprise_value:float; cash:float=0.0; debt:float=0.0; debt_like:float=0.0; non_operating_assets:float=0.0; minority_interest:float=0.0
    def equity_value(self)->float: return self.enterprise_value+self.cash+self.non_operating_assets-self.debt-self.debt_like-self.minority_interest
class ComparableValuationEngine:
    def implied_enterprise_value(self,target_metric:float,peer_multiples:Iterable[float])->dict[str,float]:
        multiples=sorted(float(x) for x in peer_multiples)
        if target_metric<0 or not multiples or any(x<=0 or not math.isfinite(x) for x in multiples): raise ValueError('invalid comparable inputs')
        med=median(multiples); return {'median_multiple':med,'implied_enterprise_value':target_metric*med,'low':target_metric*multiples[0],'high':target_metric*multiples[-1]}
class ReturnEngine:
    def moic(self,invested_equity:float,exit_equity:float)->float:
        if invested_equity<=0: raise ValueError('invested equity must be positive')
        return exit_equity/invested_equity
    def irr(self,cash_flows:Iterable[float],lower:float=-.9999,upper:float=10.0,tolerance:float=1e-8,max_iter:int=300)->float:
        flows=list(cash_flows)
        if len(flows)<2 or flows[0]>=0 or not any(x>0 for x in flows[1:]): raise ValueError('IRR requires initial outflow and later inflow')
        def npv(rate): return sum(cf/((1+rate)**i) for i,cf in enumerate(flows))
        lo,hi=lower,upper; flo,fhi=npv(lo),npv(hi)
        if flo*fhi>0: raise ValueError('IRR root not bracketed')
        for _ in range(max_iter):
            mid=(lo+hi)/2; fm=npv(mid)
            if abs(fm)<tolerance or hi-lo<tolerance: return mid
            if flo*fm<=0: hi=mid; fhi=fm
            else: lo=mid; flo=fm
        return (lo+hi)/2
class PurchasePriceBridge:
    def equity_purchase_price(self,enterprise_value:float,cash:float,debt:float,debt_like:float,normalized_working_capital_adjustment:float=0.0)->float: return enterprise_value+cash-debt-debt_like+normalized_working_capital_adjustment
