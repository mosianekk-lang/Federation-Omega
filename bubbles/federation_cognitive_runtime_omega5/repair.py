from __future__ import annotations
from bubbles.federation_learning_omega45.store import LearningStore

DEFAULT_REPAIRS={
 "NO_SEARCH_DELTA":["reuse_known_pointer","broaden_query_once","metadata_lookup","stop_and_analyse"],
 "CONNECTOR_TIMEOUT":["retry_with_backoff","open_circuit_and_continue_other_lanes"],
 "DUPLICATE_RETRIEVAL":["reuse_verified_receipt","cancel_duplicate"],
 "CONTEXT_BLOAT":["compress_hot0","checkpoint_hot1","rollover_capsule"],
 "STALE_EVIDENCE":["revalidate_minimum_dependency_slice"],
}
class RepairPlanner:
    def __init__(self,learning_store: LearningStore): self.store=learning_store
    def rank(self,signature: str):
        strategies=DEFAULT_REPAIRS.get(signature,["isolate_lane","checkpoint","escalate_exact_dependency"]); stats={r["strategy"]:r for r in self.store.repair_stats(signature)}; ranked=[]
        for pos,s in enumerate(strategies):
            r=stats.get(s)
            if r: total=r["successes"]+r["failures"]; rate=r["successes"]/max(1,total); score=rate*10-float(r["avg_latency_ms"])/10000; evidence=total
            else: score=-(pos+1)*0.01; evidence=0
            ranked.append({"strategy":s,"score":round(score,4),"observations":evidence})
        return sorted(ranked,key=lambda x:(-x["score"],x["strategy"]))
    def record(self,signature,strategy,success,latency_ms): self.store.record_repair(signature,strategy,success,latency_ms)
