from __future__ import annotations
import re
from typing import Any, Dict, Sequence

def _tokens(s): return {x for x in re.findall(r"[a-z0-9]+",s.lower()) if len(x)>2}

class PredictiveRetrievalPlanner:
    """Ranks known project-scoped source pointers; prediction does not hydrate sources."""
    def __init__(self,graph): self.graph=graph
    def plan(self,project_id: str,claim_or_question: str,known_source_nodes: Sequence[str],limit: int=4):
        q=_tokens(claim_or_question); ranked=[]
        for nid in known_source_nodes:
            n=self.graph.node(project_id,nid)
            if not n or n["node_type"]!="SOURCE": continue
            lexical=len(q&_tokens(n["label"])); fanout=len(self.graph.outgoing(project_id,nid)); stale_penalty=3 if n["state"] in ("STALE","REVALIDATION_REQUIRED") else 0; score=lexical*4+min(fanout,5)-stale_penalty
            ranked.append({"source_node":nid,"source_pointer":n["source_pointer"],"score":score,"state":n["state"],"reason":{"lexical_overlap":lexical,"proof_fanout":fanout,"stale_penalty":stale_penalty}})
        ranked.sort(key=lambda x:(-x["score"],x["source_node"]))
        return {"immediate":ranked[:1],"probable_next":ranked[1:limit],"policy":"retrieve immediate only; expand to probable_next only after explicit proof dependency"}

class WorkloadScheduler:
    """Relative-priority scheduler; does not fabricate numerical precision from missing inputs."""
    def rank(self,missions: Sequence[Dict[str,Any]]):
        out=[]
        for m in missions:
            benefit=float(m.get("urgency",1))+float(m.get("proof_gain",1))+float(m.get("unblock_impact",1))+float(m.get("user_value",1))+float(m.get("reuse_value",1)); cost=max(0.1,float(m.get("latency_cost",1))+float(m.get("risk",1))+float(m.get("dependency_cost",1))); score=benefit/cost
            out.append({"mission_id":m["mission_id"],"priority_score":round(score,4),"benefit":benefit,"cost":cost})
        return sorted(out,key=lambda x:(-x["priority_score"],x["mission_id"]))

class MissionConvergenceDetector:
    """Deterministic semantic-overlap candidate detector; never auto-merges matter walls."""
    def candidates(self,missions: Sequence[Dict[str,Any]],threshold: float=0.45):
        pairs=[]
        for i,a in enumerate(missions):
            for b in missions[i+1:]:
                if a["project_id"]!=b["project_id"]: continue
                ta,tb=_tokens(a["objective"]),_tokens(b["objective"]); sim=len(ta&tb)/max(1,len(ta|tb)); shared=set(a.get("evidence_nodes",[]))&set(b.get("evidence_nodes",[])); effective=max(sim,min(1.0,len(shared)/2))
                if effective>=threshold: pairs.append({"a":a["mission_id"],"b":b["mission_id"],"score":round(effective,3),"shared_evidence":sorted(shared),"decision":"SHARED_SUBPROBLEM_CANDIDATE_NOT_AUTO_MERGED"})
        return sorted(pairs,key=lambda x:-x["score"])
