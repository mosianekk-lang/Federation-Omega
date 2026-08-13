from __future__ import annotations
from typing import Any,Dict,Sequence
from bubbles.federation_learning_omega45.runtime import OperationalLearningRuntime
from .graph import KnowledgeGraph
from .planner import PredictiveRetrievalPlanner,WorkloadScheduler,MissionConvergenceDetector
from .repair import RepairPlanner
from .twin import FederationDigitalTwin
VERSION="5.0.0"
class AdaptiveCognitiveRuntime:
    """Ω5 composes evidence-backed learning, graph reasoning, prediction and simulation."""
    def __init__(self,graph_path="bubbles_federation_cognitive_omega5.sqlite3",learning_path="bubbles_federation_learning_omega45.sqlite3"):
        self.learning=OperationalLearningRuntime(learning_path); self.graph=KnowledgeGraph(graph_path); self.retrieval=PredictiveRetrievalPlanner(self.graph); self.scheduler=WorkloadScheduler(); self.convergence=MissionConvergenceDetector(); self.repairs=RepairPlanner(self.learning.store); self.twin=FederationDigitalTwin(self.graph)
    def cycle(self,*,project_id:str,question:str,known_sources:Sequence[str],missions:Sequence[Dict[str,Any]]):
        return {"runtime":"BUBBLES_FEDERATION_ADAPTIVE_COGNITIVE_RUNTIME_OMEGA5","version":VERSION,"retrieval_plan":self.retrieval.plan(project_id,question,known_sources),"workload_order":self.scheduler.rank(missions),"convergence_candidates":self.convergence.candidates(missions),"active_learned_policy":self.learning.active_policy(project_id,"general"),"truth_boundary":"Predictions and simulations guide governed work; they are not provider execution or hidden ChatGPT runtime control."}
    def close(self): self.graph.close(); self.learning.close()
