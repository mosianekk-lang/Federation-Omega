from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
@dataclass(frozen=True)
class DiligenceRequirement:
    requirement_id:str; category:str; document_type:str; materiality:float; rationale:str; stage:str='DILIGENCE'
    def validate(self):
        if not 0<=self.materiality<=1: raise ValueError('materiality must be between 0 and 1')
@dataclass(frozen=True)
class DiligenceGap: requirement_id:str; category:str; document_type:str; materiality:float; question:str
class DiligenceEngine:
    def missing(self,requirements:Iterable[DiligenceRequirement],available_document_types:Iterable[str])->list[DiligenceGap]:
        available={x.strip().lower() for x in available_document_types}; gaps=[]
        for r in requirements:
            r.validate()
            if r.document_type.strip().lower() not in available: gaps.append(DiligenceGap(r.requirement_id,r.category,r.document_type,r.materiality,f'Please provide the current {r.document_type} and identify any material exceptions relevant to {r.rationale}.'))
        return sorted(gaps,key=lambda g:(-g.materiality,g.category,g.requirement_id))
    def completeness(self,requirements:Iterable[DiligenceRequirement],available_document_types:Iterable[str])->float:
        req=list(requirements)
        if not req: return 1.0
        missing=self.missing(req,available_document_types); total=sum(max(r.materiality,.01) for r in req); missing_weight=sum(max(g.materiality,.01) for g in missing); return max(0.0,min(1.0,1-missing_weight/total))
    def standard_profile(self)->tuple[DiligenceRequirement,...]:
        rows=[('FIN-001','FINANCIAL','audited financial statements',1.0,'reported earnings and balance sheet'),('FIN-002','FINANCIAL','management accounts',.9,'current trading'),('TAX-001','TAX','tax returns',.8,'tax compliance'),('LEG-001','LEGAL','material contracts',1.0,'obligations and change-of-control'),('CORP-001','CORPORATE','share register',1.0,'ownership'),('HR-001','HR','employee register',.7,'workforce liabilities'),('IP-001','IP','intellectual property register',.7,'ownership of key IP'),('CYB-001','CYBER','cybersecurity assessment',.7,'technology risk'),('CUS-001','COMMERCIAL','customer revenue schedule',.9,'concentration and durability'),('SUP-001','SUPPLY_CHAIN','supplier schedule',.6,'supplier concentration')]; return tuple(DiligenceRequirement(*r) for r in rows)
class AnswerSufficiencyScorer:
    def score(self,answer:str,required_elements:Iterable[str])->dict[str,object]:
        text=(answer or '').lower(); elements=[e.lower() for e in required_elements]; matched=[e for e in elements if e in text]; ratio=1.0 if not elements else len(matched)/len(elements); return {'score':ratio,'matched':matched,'missing':[e for e in elements if e not in matched],'sufficient':ratio>=.8}
class DiligenceMaterialityRouter:
    def lane(self,materiality:float,uncertainty:float)->str:
        if any(not 0<=x<=1 for x in (materiality,uncertainty)): raise ValueError('inputs must be between 0 and 1')
        score=.7*materiality+.3*uncertainty; return 'CRITICAL' if score>=.8 else 'DEEP' if score>=.6 else 'STANDARD' if score>=.35 else 'LIGHT'
