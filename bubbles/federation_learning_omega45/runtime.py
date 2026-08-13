from __future__ import annotations
from dataclasses import asdict
from typing import Any, Dict
from .store import LearningStore, Observation
from .policy import PolicyLearner, ShadowPolicyEvaluator, AdaptivePolicy

VERSION="4.5.0"
class OperationalLearningRuntime:
    def __init__(self, path="bubbles_federation_learning_omega45.sqlite3"):
        self.store=LearningStore(path); self.learner=PolicyLearner(self.store); self.shadow=ShadowPolicyEvaluator(self.store)
    def observe(self, **kwargs) -> str: return self.store.add(Observation(**kwargs))
    def propose(self, project_id: str, mission_type: str) -> Dict[str,Any]: return self.learner.candidate(project_id,mission_type)
    def promote_if_qualified(self, project_id: str, mission_type: str) -> Dict[str,Any]:
        c=self.learner.candidate(project_id,mission_type); p=AdaptivePolicy(**c["policy"]); shadow=self.shadow.evaluate(project_id,mission_type,p); key=f"{project_id}:{mission_type}"
        if c["eligible"] and shadow["qualified"]:
            self.store.save_policy(key,asdict(p),"PROMOTED",p.sample_count,p.confidence,True); return {"promoted":True,"policy":asdict(p),"shadow":shadow}
        return {"promoted":False,"policy":asdict(p),"shadow":shadow}
    def active_policy(self, project_id: str, mission_type: str):
        p=self.store.policy(f"{project_id}:{mission_type}"); return p["payload"] if p and p["state"]=="PROMOTED" else None
    def close(self): self.store.close()
