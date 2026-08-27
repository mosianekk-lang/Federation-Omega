#!/usr/bin/env python3
import argparse, json, re
from pathlib import Path

BLOCKED={"BLOCKED_OR_UNVERIFIED","ADAPTER_REQUIRED","QUARANTINED"}
ALIASES={
 "propagation":"continuity","propagate":"continuity","synchronization":"continuity","synchronize":"continuity","sync":"continuity",
 "inheritance":"continuity","inherit":"continuity","respawn":"continuity","bootstrap":"continuity","future-chat":"continuity","restore":"continuity"
}

FAILURE_CONTINUITY_TERMS={"kernel","operational","recovery","recover","win"}

def normalized_goals(goal):
    text=goal.lower().replace("future chat","future-chat")
    tokens=set(re.findall(r"[a-z0-9-]+",text))
    tokens|={ALIASES[t] for t in tokens if t in ALIASES}
    if "failure" in tokens and tokens.intersection(FAILURE_CONTINUITY_TERMS):
        tokens.add("continuity")
    return tokens

def select(registry,goal,external_write=False,max_latency=240):
    surfaces={r["id"]:r for r in registry["surfaces"]}; wanted=normalized_goals(goal); results=[]
    for bundle in registry["bundles"]:
        if not wanted.intersection(set(bundle["goals"])): continue
        members=[surfaces[x] for x in bundle["members"]]; blocked=[r["id"] for r in members if r["state"] in BLOCKED]
        latency=sum(r.get("latency",0) for r in members)
        results.append({"bundle":bundle["id"],"members":bundle["members"],"fallback":bundle.get("fallback",[]),"estimatedLatencySeconds":latency,"authority":"FORMATION_PERMIT_AND_PROVIDER_AUTHORITY_REQUIRED" if external_write and any(r.get("write") for r in members) else "READ_OR_LOCAL_AUTHORITY","blocked":blocked,"eligible":not blocked and latency<=max_latency,"score":sum(r.get("proof",0)*4+r.get("privacy",0)*2 for r in members)-latency-100*len(blocked)+3*len(bundle.get("fallback",[]))})
    return sorted(results,key=lambda r:(r["eligible"],r["score"]),reverse=True)

def main():
    p=argparse.ArgumentParser(); p.add_argument("--registry",required=True); p.add_argument("--goal",required=True); p.add_argument("--external-write",action="store_true"); p.add_argument("--max-latency",type=int,default=240); a=p.parse_args()
    routes=select(json.loads(Path(a.registry).read_text()),a.goal,a.external_write,a.max_latency)
    print(json.dumps({"decision":"ROUTE_SELECTED" if routes and routes[0]["eligible"] else "NO_ELIGIBLE_ROUTE","goal":a.goal,"routes":routes},indent=2))
if __name__=="__main__": main()
