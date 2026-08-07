from __future__ import annotations
from pathlib import Path
from .product_ui import DashboardRenderer,WorkspaceComposer
def build_demo_dashboard(destination:str|Path)->dict[str,object]:
    snapshot=WorkspaceComposer().compose(company_name='Synthetic Logistics Co',mode='GUIDED_OWNER',readiness_score=.68,valuation_range=(24000000,32000000),diligence_score=.57,top_risks=['Customer concentration','Undocumented intellectual property','Working-capital volatility'],next_actions=['Obtain customer revenue schedule','Document IP ownership','Normalize working-capital history'],market_note='Financing-cost sensitivity is elevated in the current synthetic scenario.'); html=DashboardRenderer().render(snapshot); destination=Path(destination); destination.write_text(html,encoding='utf-8'); return {'path':str(destination),'bytes':destination.stat().st_size,'contains_company':snapshot.company_name in html,'mode':snapshot.mode}
