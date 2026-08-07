from __future__ import annotations
from dataclasses import dataclass
from html import escape
from typing import Iterable
@dataclass(frozen=True)
class WorkspaceSnapshot:
    company_name:str; mode:str; readiness_pct:int; indicative_value_low:float; indicative_value_high:float; diligence_pct:int; top_risks:tuple[str,...]; next_actions:tuple[str,...]; market_note:str=''
class WorkspaceComposer:
    def compose(self,*,company_name:str,mode:str,readiness_score:float,valuation_range:tuple[float,float],diligence_score:float,top_risks:Iterable[str],next_actions:Iterable[str],market_note:str='')->WorkspaceSnapshot:
        if mode not in {'GUIDED_OWNER','PROFESSIONAL'}:raise ValueError('unsupported workspace mode')
        if any(not 0<=x<=1 for x in (readiness_score,diligence_score)):raise ValueError('scores must be between 0 and 1')
        low,high=valuation_range
        if low<0 or high<low:raise ValueError('invalid valuation range')
        return WorkspaceSnapshot(company_name,mode,round(readiness_score*100),low,high,round(diligence_score*100),tuple(top_risks)[:5],tuple(next_actions)[:5],market_note)
class DashboardRenderer:
    def render(self,s:WorkspaceSnapshot)->str:
        risks=''.join(f'<li>{escape(x)}</li>' for x in s.top_risks) or '<li>No material risk surfaced in this snapshot.</li>'; actions=''.join(f'<li>{escape(x)}</li>' for x in s.next_actions) or '<li>No action required.</li>'; professional='' if s.mode=='GUIDED_OWNER' else '<section><h2>Professional drill-down</h2><p>Evidence graph, assumptions, calculations and source provenance are available through the underlying workspace objects.</p></section>'; return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(s.company_name)} — EvidenceOps</title><style>body{{font-family:Arial,sans-serif;max-width:1050px;margin:auto;padding:24px;background:#f7f7f5;color:#171717}}header,section{{background:white;border:1px solid #ddd;border-radius:16px;padding:22px;margin:14px 0}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}}.metric{{padding:16px;border:1px solid #e4e4e4;border-radius:12px}}.big{{font-size:30px;font-weight:700}}small{{color:#666}}</style></head><body><header><small>{escape(s.mode.replace('_',' ').title())}</small><h1>{escape(s.company_name)}</h1><p>Evidence-native transaction command view.</p></header><section class="grid"><div class="metric"><small>Transaction readiness</small><div class="big">{s.readiness_pct}%</div></div><div class="metric"><small>Diligence completeness</small><div class="big">{s.diligence_pct}%</div></div><div class="metric"><small>Indicative value range</small><div class="big">{s.indicative_value_low:,.0f} – {s.indicative_value_high:,.0f}</div></div></section><section><h2>What needs attention</h2><ul>{risks}</ul></section><section><h2>Next best actions</h2><ol>{actions}</ol></section><section><h2>Market context</h2><p>{escape(s.market_note or 'No public-market context attached.')}</p></section>{professional}</body></html>'''
