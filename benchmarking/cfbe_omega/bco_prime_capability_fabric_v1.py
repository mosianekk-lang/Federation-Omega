from __future__ import annotations

"""BCOmega PRIME deterministic 100-capability fabric v1.

The fabric turns common mission-control calculations into individually
addressable, zero-manual, A1-internal functions.  It is intentionally pure:
no network, filesystem, subprocess, clock, random, provider, or user-input
side effect is available through a capability call.
"""

from argparse import ArgumentParser
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any, Callable, Mapping, Sequence


SCHEMA = "BCO_PRIME_CAPABILITY_FABRIC_V1"
RECEIPT_SCHEMA = "BCO_PRIME_CAPABILITY_RECEIPT_V1"
CAPABILITY_COUNT = 100
AUTHORITY_CEILING = "A1_INTERNAL"

DOMAIN_OPERATIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("intent", ("objective_normalize", "requirement_trace", "scope_closure", "terminal_fruit", "constraint_lock", "assumption_extract", "ambiguity_flag", "priority_score", "cancellation_check", "mission_fingerprint")),
    ("evidence", ("reference_canonicalize", "reference_deduplicate", "coverage_measure", "contradiction_scan", "freshness_gate", "trust_gate", "source_binding", "receipt_digest", "missing_proof", "proof_ceiling")),
    ("planning", ("dependency_order", "critical_path", "parallel_waves", "retry_budget", "route_utility", "route_diversity", "rollback_plan", "stop_conditions", "budget_allocation", "plan_fingerprint")),
    ("execution", ("authority_gate", "cost_gate", "burden_gate", "idempotency_key", "cancellation_gate", "timeout_policy", "retry_decision", "circuit_state", "dead_letter_decision", "execution_envelope")),
    ("quality", ("schema_score", "completeness_score", "invariant_violations", "verified_output_ratio", "trace_score", "regression_delta", "consistency_check", "deterministic_checksum", "boundary_defects", "quality_gate")),
    ("safety", ("effect_classify", "privilege_expansion", "secret_indicators", "privacy_minimize", "unsafe_route", "reversibility_check", "blast_radius", "approval_need", "policy_violations", "safe_disposition")),
    ("continuity", ("checkpoint_digest", "resume_cursor", "replay_guard", "stale_state", "lineage_chain", "merge_delta", "restore_plan", "capsule_summary", "successor_binding", "continuity_state")),
    ("learning", ("failure_fingerprint", "failure_classify", "smallest_repair", "lesson_candidate", "route_confidence", "quarantine_decision", "promotion_eligibility", "novelty_score", "value_delta", "learning_receipt")),
    ("orchestration", ("lane_independence", "fanout_bound", "fanin_contract", "stream_load", "contention_risk", "scheduler_mode", "next_best_action", "owner_interrupt", "provider_readiness", "orchestration_receipt")),
    ("value", ("owner_burden_delta", "time_delta", "verified_output_delta", "intervention_ratio", "cost_delta", "risk_adjusted_value", "pair_completeness", "minimum_cases", "promotion_hold", "value_receipt")),
)

_SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile("github" + r"_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile("-----BEGIN " + r"[A-Z ]*PRIVATE KEY-----"),
)


@dataclass(frozen=True, slots=True)
class CapabilitySpec:
    capability_id: str
    function_name: str
    domain: str
    operation: str
    ordinal: int


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False, default=str)


def _hash(value: Any) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _clamp(value: Any, low: float = 0.0, high: float = 1.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = low
    return round(min(high, max(low, number)), 9)


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else [value]
    return [" ".join(str(item).split()) for item in values if str(item).strip()]


def _unique(value: Any) -> list[str]:
    return sorted(set(_strings(value)), key=lambda item: (item.casefold(), item))


def _items(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = payload.get(key, [])
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _score(payload: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    return _clamp(payload.get(key, default))


def _delta(payload: Mapping[str, Any], before: str, after: str) -> float:
    return round(float(payload.get(after, 0) or 0) - float(payload.get(before, 0) or 0), 9)


def _topological(nodes: Sequence[Mapping[str, Any]]) -> list[str]:
    graph: dict[str, set[str]] = {}
    for node in nodes:
        node_id = " ".join(str(node.get("id", "")).split())
        if not node_id:
            raise ValueError("DEPENDENCY_NODE_ID_REQUIRED")
        if node_id in graph:
            raise ValueError("DUPLICATE_DEPENDENCY_NODE")
        graph[node_id] = set(_strings(node.get("depends_on", [])))
    unknown = sorted({dep for deps in graph.values() for dep in deps if dep not in graph})
    if unknown:
        raise ValueError("UNKNOWN_DEPENDENCY:" + ",".join(unknown))
    result: list[str] = []
    remaining = {key: set(value) for key, value in graph.items()}
    while remaining:
        ready = sorted(key for key, deps in remaining.items() if not deps)
        if not ready:
            raise ValueError("DEPENDENCY_CYCLE")
        result.extend(ready)
        for key in ready:
            remaining.pop(key)
        for deps in remaining.values():
            deps.difference_update(ready)
    return result


def _waves(nodes: Sequence[Mapping[str, Any]]) -> list[list[str]]:
    graph: dict[str, set[str]] = {}
    for node in nodes:
        node_id = str(node.get("id", "")).strip()
        if not node_id or node_id in graph:
            raise ValueError("PARALLEL_WAVE_NODE_INVALID")
        graph[node_id] = set(_strings(node.get("depends_on", [])))
    if any(dep not in graph for deps in graph.values() for dep in deps):
        raise ValueError("UNKNOWN_DEPENDENCY")
    result: list[list[str]] = []
    done: set[str] = set()
    while len(done) < len(graph):
        ready = sorted(key for key, deps in graph.items() if key not in done and deps <= done)
        if not ready:
            raise ValueError("DEPENDENCY_CYCLE")
        result.append(ready)
        done.update(ready)
    return result


def _boundary_guard(payload: Mapping[str, Any]) -> None:
    manual = payload.get("manual_user_tasks")
    if manual not in (None, 0, [], ()):
        raise ValueError("CAPABILITY_FABRIC_BOUNDARY:MANUAL_USER_TASK_PROHIBITED")
    for key in ("external_effect", "provider_effect_authorized", "authority_expansion"):
        if payload.get(key) is True:
            raise ValueError(f"CAPABILITY_FABRIC_BOUNDARY:{key.upper()}_PROHIBITED")


def _intent(operation: str, p: Mapping[str, Any]) -> Mapping[str, Any]:
    if operation == "objective_normalize": return {"normalized_objective": " ".join(str(p.get("objective", "")).split())}
    if operation == "requirement_trace":
        reqs, refs = _unique(p.get("requirements")), _unique(p.get("evidence_refs"))
        return {"requirements": reqs, "evidence_refs": refs, "trace_complete": bool(reqs) and len(refs) >= len(reqs)}
    if operation == "scope_closure":
        requested, completed = set(_strings(p.get("requested"))), set(_strings(p.get("completed")))
        return {"open": sorted(requested - completed), "closed": sorted(requested & completed), "complete": requested <= completed}
    if operation == "terminal_fruit":
        desired, produced = set(_strings(p.get("desired_outputs"))), set(_strings(p.get("produced_outputs")))
        return {"missing_outputs": sorted(desired - produced), "fruit_complete": bool(desired) and desired <= produced}
    if operation == "constraint_lock": return {"constraints": _unique(p.get("constraints")), "constraint_sha256": _hash(_unique(p.get("constraints")))}
    if operation == "assumption_extract": return {"assumptions": _unique(p.get("assumptions")), "assumption_count": len(_unique(p.get("assumptions")))}
    if operation == "ambiguity_flag":
        text = str(p.get("text", "")); markers = [item for item in ("?", "TBD", "unknown", "unspecified", "maybe") if item.casefold() in text.casefold()]
        return {"ambiguous": bool(markers), "marker_types": markers}
    if operation == "priority_score":
        score = .30*_score(p,"value")+.25*_score(p,"urgency")+.20*_score(p,"dependency_unlock")+.15*_score(p,"reversibility")-.05*_score(p,"cost")-.05*_score(p,"risk")
        return {"priority_score": round(score, 9), "eligible": score > 0}
    if operation == "cancellation_check":
        cancelled = any(p.get(key) is True for key in ("stop_requested", "stale", "superseded"))
        return {"cancelled": cancelled, "disposition": "STOP" if cancelled else "CONTINUE"}
    return {"mission_fingerprint": _hash({key:p.get(key) for key in ("mission_id","version","objective","requirements","constraints")})}


def _evidence(operation: str, p: Mapping[str, Any]) -> Mapping[str, Any]:
    refs = _strings(p.get("evidence_refs", p.get("refs", [])))
    if operation == "reference_canonicalize": return {"canonical_refs": sorted(item.strip() for item in refs)}
    if operation == "reference_deduplicate": return {"unique_refs": _unique(refs), "duplicates_removed": len(refs)-len(_unique(refs))}
    if operation == "coverage_measure":
        required, covered = set(_strings(p.get("required"))), set(_strings(p.get("covered")))
        return {"coverage": round(len(required & covered)/len(required),9) if required else 0.0, "missing": sorted(required-covered)}
    if operation == "contradiction_scan":
        claims = _items(p,"claims"); grouped: dict[str,set[str]] = {}
        for item in claims: grouped.setdefault(str(item.get("subject","")).strip(),set()).add(str(item.get("polarity","")).upper())
        conflicts = sorted(key for key, vals in grouped.items() if {"TRUE","FALSE"} <= vals)
        return {"contradictions": conflicts, "contradiction_count": len(conflicts)}
    if operation == "freshness_gate":
        max_age=float(p.get("max_age_hours",24) or 24); age=float(p.get("age_hours",max_age+1) or 0)
        return {"fresh": age <= max_age, "age_hours": age, "max_age_hours": max_age}
    if operation == "trust_gate":
        trust=_score(p,"trust"); independent=bool(p.get("independently_read_back",False))
        return {"trusted": trust >= _score(p,"minimum_trust",.7) and independent, "trust":trust, "independent":independent}
    if operation == "source_binding": return {"bound": bool(p.get("source_id")) and bool(p.get("source_sha256")), "binding_sha256": _hash([p.get("source_id"),p.get("source_sha256")])}
    if operation == "receipt_digest": return {"digest": _hash(p.get("receipt",{}))}
    if operation == "missing_proof":
        required, present=set(_strings(p.get("required_proof"))),set(_strings(p.get("present_proof")))
        return {"missing_proof":sorted(required-present),"proof_complete":bool(required) and required<=present}
    ceilings=[str(item.get("maturity","SOURCE_ONLY")) for item in _items(p,"evidence")]
    order=["NONE","SOURCE_ONLY","TESTED_LOCAL","HOSTED_SHADOW","CANARY","OPERATIONAL_VERIFIED"]
    level=min((order.index(x) for x in ceilings if x in order),default=0)
    return {"proof_ceiling":order[level],"promotion_beyond_ceiling_allowed":False}


def _planning(operation: str, p: Mapping[str, Any]) -> Mapping[str, Any]:
    nodes=_items(p,"nodes")
    if operation == "dependency_order": return {"ordered":_topological(nodes)}
    if operation == "critical_path":
        order=_topological(nodes); by={str(x.get("id")):x for x in nodes}; totals:dict[str,float]={}
        for node in order: totals[node]=float(by[node].get("duration",1) or 1)+max((totals[d] for d in _strings(by[node].get("depends_on"))),default=0)
        end=max(totals,key=lambda k:(totals[k],k)) if totals else None
        return {"critical_duration":round(totals.get(end,0),9),"terminal_node":end}
    if operation == "parallel_waves": return {"waves":_waves(nodes),"wave_count":len(_waves(nodes))}
    if operation == "retry_budget":
        risk=_score(p,"risk"); reversible=bool(p.get("reversible",True)); attempts=0 if not reversible else max(1,min(5,int(round(5*(1-risk)))))
        return {"max_attempts":attempts,"retry_allowed":attempts>0}
    if operation == "route_utility":
        value=_score(p,"value"); utility=value-_score(p,"risk")-_score(p,"burden")-_score(p,"cost")+(0.1 if p.get("reversible",True) else 0)
        return {"utility":round(utility,9),"eligible":utility>0}
    if operation == "route_diversity":
        domains=_strings(p.get("failure_domains")); return {"unique_failure_domains":len(set(domains)),"diversity_ratio":round(len(set(domains))/len(domains),9) if domains else 0.0}
    if operation == "rollback_plan": return {"rollback_ready":bool(p.get("checkpoint_ref")) and bool(p.get("rollback_tested",False)),"checkpoint_ref_present":bool(p.get("checkpoint_ref"))}
    if operation == "stop_conditions": return {"stop_conditions":_unique(p.get("stop_conditions")),"fail_closed":bool(_strings(p.get("stop_conditions")))}
    if operation == "budget_allocation":
        weights=[max(0,float(x)) for x in p.get("weights",[]) if isinstance(x,(int,float))]; total=sum(weights)
        return {"allocation":[round(x/total,9) for x in weights] if total else [],"sum":1.0 if total else 0.0}
    return {"plan_fingerprint":_hash({"nodes":nodes,"routes":p.get("routes",[]),"constraints":p.get("constraints",[])})}


def _execution(operation: str, p: Mapping[str, Any]) -> Mapping[str, Any]:
    if operation == "authority_gate":
        exact=bool(p.get("exact_authority",False)); requested=str(p.get("requested_class","A1_INTERNAL")); return {"authorized":exact and requested in {"A0","A1_INTERNAL"},"ceiling":AUTHORITY_CEILING}
    if operation == "cost_gate":
        cost=float(p.get("incremental_cost",0) or 0); limit=float(p.get("maximum_cost",0) or 0); return {"allowed":cost<=limit,"incremental_cost":cost,"maximum_cost":limit}
    if operation == "burden_gate":
        burden=float(p.get("owner_burden",0) or 0); return {"allowed":burden<=0,"owner_burden":burden,"maximum_owner_burden":0}
    if operation == "idempotency_key": return {"idempotency_key":_hash({"mission":p.get("mission_id"),"action":p.get("action"),"payload":p.get("payload")})}
    if operation == "cancellation_gate":
        stop=any(p.get(x) is True for x in ("cancelled","stop_requested","stale")); return {"execute":not stop,"disposition":"CANCEL" if stop else "EXECUTE"}
    if operation == "timeout_policy":
        requested=max(1,int(p.get("requested_seconds",30) or 30)); ceiling=max(1,int(p.get("ceiling_seconds",300) or 300)); return {"timeout_seconds":min(requested,ceiling),"bounded":True}
    if operation == "retry_decision":
        attempts=int(p.get("attempts",0) or 0); maximum=int(p.get("maximum_attempts",3) or 3); repeat=bool(p.get("same_failure_fingerprint",False)); return {"retry":attempts<maximum and not repeat,"route_change_required":repeat}
    if operation == "circuit_state":
        failures=int(p.get("repeated_failures",0) or 0); threshold=int(p.get("threshold",2) or 2); return {"state":"OPEN" if failures>=threshold else "CLOSED","failure_count":failures}
    if operation == "dead_letter_decision":
        exhausted=bool(p.get("retries_exhausted",False)); recoverable=bool(p.get("recoverable",True)); return {"dead_letter":exhausted and not recoverable,"preserve_evidence":exhausted}
    return {"envelope_sha256":_hash({"mission_id":p.get("mission_id"),"authority":p.get("authority"),"action":p.get("action"),"idempotency":p.get("idempotency_key")}),"effect_class":"NO_EFFECT"}


def _quality(operation: str, p: Mapping[str, Any]) -> Mapping[str, Any]:
    if operation in {"schema_score","completeness_score"}:
        required=set(_strings(p.get("required_fields"))); present=set(_strings(p.get("present_fields")))
        return {"score":round(len(required&present)/len(required),9) if required else 0.0,"missing":sorted(required-present)}
    if operation == "invariant_violations":
        violations=_unique(p.get("violations")); return {"violations":violations,"count":len(violations),"pass":not violations}
    if operation == "verified_output_ratio":
        total=max(0,int(p.get("total_outputs",0) or 0)); verified=max(0,int(p.get("verified_outputs",0) or 0)); return {"ratio":round(min(verified,total)/total,9) if total else 0.0}
    if operation == "trace_score":
        req=max(0,int(p.get("requirements",0) or 0)); traced=max(0,int(p.get("traced_requirements",0) or 0)); return {"trace_score":round(min(req,traced)/req,9) if req else 0.0}
    if operation == "regression_delta": return {"delta":_delta(p,"baseline_score","candidate_score"),"regressed":_delta(p,"baseline_score","candidate_score")<0}
    if operation == "consistency_check":
        values=p.get("values",[]); canonical=[_canonical_json(x) for x in values] if isinstance(values,Sequence) and not isinstance(values,(str,bytes)) else []
        return {"consistent":len(set(canonical))<=1,"sample_count":len(canonical)}
    if operation == "deterministic_checksum": return {"checksum":_hash(p.get("value",p.get("values",[])))}
    if operation == "boundary_defects":
        defects=[key for key in ("manual_user_tasks","external_effect","authority_expansion","provider_effect_authorized") if p.get(key) not in (None,False,0,[],())]
        return {"defects":defects,"pass":not defects}
    thresholds={"schema":.9,"completeness":.9,"trace":.8,"verified_output":.9}
    scores={key:_score(p,key) for key in thresholds}; failed=sorted(key for key,val in scores.items() if val<thresholds[key])
    return {"pass":not failed and int(p.get("hard_regressions",0) or 0)==0,"failed_dimensions":failed,"hard_regressions":int(p.get("hard_regressions",0) or 0)}


def _safety(operation: str, p: Mapping[str, Any]) -> Mapping[str, Any]:
    if operation == "effect_classify":
        if p.get("destructive") or p.get("send") or p.get("publish"): effect="CONSEQUENTIAL"
        elif p.get("write") and p.get("reversible"): effect="PRIVATE_REVERSIBLE"
        elif p.get("read"): effect="READ_ONLY"
        else: effect="NO_EFFECT"
        return {"effect_class":effect,"serialized":effect=="CONSEQUENTIAL"}
    if operation == "privilege_expansion":
        current=set(_strings(p.get("current_permissions"))); requested=set(_strings(p.get("requested_permissions"))); extra=sorted(requested-current)
        return {"expansion":bool(extra),"additional_permission_count":len(extra)}
    if operation == "secret_indicators":
        text=str(p.get("text","")); types=[f"PATTERN_{i+1}" for i,pattern in enumerate(_SECRET_PATTERNS) if pattern.search(text)]
        return {"secret_indicator_detected":bool(types),"indicator_types":types,"redacted":True}
    if operation == "privacy_minimize":
        requested=set(_strings(p.get("required_fields"))); supplied=set(_strings(p.get("supplied_fields"))); return {"excess_fields":sorted(supplied-requested),"minimal":supplied<=requested}
    if operation == "unsafe_route":
        unsafe=any(p.get(key) is True for key in ("bypass","force","unverified_authority","destructive")); return {"unsafe":unsafe,"disposition":"REJECT" if unsafe else "ALLOW_INTERNAL"}
    if operation == "reversibility_check": return {"reversible":bool(p.get("rollback_ref")) and bool(p.get("rollback_tested",False)),"rollback_ref_present":bool(p.get("rollback_ref"))}
    if operation == "blast_radius":
        targets=max(0,int(p.get("target_count",0) or 0)); shared=_score(p,"shared_state"); return {"blast_radius_score":_clamp(min(1,targets/10)*.6+shared*.4),"target_count":targets}
    if operation == "approval_need":
        needed=any(p.get(key) is True for key in ("send","publish","delete","purchase","sign","production_mutation")); return {"approval_required":needed,"owner_interrupt":needed}
    if operation == "policy_violations":
        violations=_unique(p.get("policy_violations")); return {"violations":violations,"blocked":bool(violations)}
    unsafe=bool(p.get("unsafe",False) or p.get("approval_required",False) or p.get("policy_violations"))
    return {"disposition":"HOLD" if unsafe else "SAFE_INTERNAL","external_effect_authorized":False}


def _continuity(operation: str, p: Mapping[str, Any]) -> Mapping[str, Any]:
    if operation == "checkpoint_digest": return {"checkpoint_sha256":_hash(p.get("checkpoint",{}))}
    if operation == "resume_cursor": return {"cursor":_hash([p.get("mission_id"),p.get("checkpoint_id"),p.get("completed_steps",[])])[:24],"resumable":bool(p.get("checkpoint_id"))}
    if operation == "replay_guard": return {"duplicate":p.get("event_id") in set(_strings(p.get("seen_event_ids"))),"idempotency_preserved":True}
    if operation == "stale_state":
        current=int(p.get("current_version",0) or 0); observed=int(p.get("observed_version",0) or 0); return {"stale":observed<current,"current_version":current,"observed_version":observed}
    if operation == "lineage_chain":
        chain=_strings(p.get("lineage")); return {"lineage":chain,"chain_sha256":_hash(chain),"duplicate_nodes":len(chain)!=len(set(chain))}
    if operation == "merge_delta":
        before=set(_strings(p.get("before"))); after=set(_strings(p.get("after"))); return {"added":sorted(after-before),"removed":sorted(before-after),"unchanged":sorted(before&after)}
    if operation == "restore_plan": return {"restore_ready":bool(p.get("checkpoint_ref")) and bool(p.get("schema_version")),"steps":["VALIDATE_CHECKPOINT","RESTORE","READBACK","REGRESSION"]}
    if operation == "capsule_summary":
        return {"mission_id":p.get("mission_id"),"state":p.get("state","UNKNOWN"),"open_count":len(_strings(p.get("open_items"))),"proof_count":len(_strings(p.get("proof_refs")))}
    if operation == "successor_binding": return {"binding_sha256":_hash([p.get("predecessor"),p.get("successor"),p.get("scope")]),"bound":bool(p.get("predecessor")) and bool(p.get("successor"))}
    blocked=bool(p.get("stale") or p.get("duplicate") or p.get("lineage_broken")); return {"state":"HOLD" if blocked else "CONTINUITY_READY","blocked":blocked}


def _learning(operation: str, p: Mapping[str, Any]) -> Mapping[str, Any]:
    if operation == "failure_fingerprint": return {"failure_fingerprint":_hash({key:p.get(key) for key in ("error_type","message","route","stage")})}
    if operation == "failure_classify":
        text=str(p.get("error","")).casefold(); kind="AUTHORITY" if "permission" in text or "authority" in text else "TIMEOUT" if "timeout" in text else "SCHEMA" if "schema" in text else "UNKNOWN"
        return {"failure_class":kind,"deterministic":kind!="UNKNOWN"}
    if operation == "smallest_repair":
        candidates=_items(p,"repairs"); ranked=sorted(candidates,key=lambda x:(float(x.get("risk",1)),float(x.get("cost",1)),str(x.get("id",""))))
        return {"selected_repair":ranked[0].get("id") if ranked else None,"candidate_count":len(ranked)}
    if operation == "lesson_candidate": return {"lesson_sha256":_hash({"trigger":p.get("trigger"),"repair":p.get("repair"),"proof":p.get("proof")}),"eligible":bool(p.get("repair")) and bool(p.get("proof"))}
    if operation == "route_confidence":
        success=max(0,int(p.get("successes",0) or 0)); failure=max(0,int(p.get("failures",0) or 0)); return {"confidence":round((success+1)/(success+failure+2),9),"sample_count":success+failure}
    if operation == "quarantine_decision":
        repeat=int(p.get("repeated_failures",0) or 0); hard=bool(p.get("hard_regression",False)); return {"quarantine":hard or repeat>=2,"route_change_required":repeat>=2}
    if operation == "promotion_eligibility":
        eligible=bool(p.get("tested")) and bool(p.get("independent_readback")) and bool(p.get("rollback")) and int(p.get("hard_regressions",0) or 0)==0
        return {"eligible":eligible,"stable_self_promotion_authorized":False}
    if operation == "novelty_score":
        known=set(_strings(p.get("known_features"))); candidate=set(_strings(p.get("candidate_features"))); return {"novelty":round(len(candidate-known)/len(candidate),9) if candidate else 0.0,"new_features":sorted(candidate-known)}
    if operation == "value_delta": return {"value_delta":_delta(p,"baseline_value","candidate_value"),"positive":_delta(p,"baseline_value","candidate_value")>0}
    return {"learning_receipt":_hash({key:p.get(key) for key in ("failure","repair","test","value_delta")}),"authority_expansion":False}


def _orchestration(operation: str, p: Mapping[str, Any]) -> Mapping[str, Any]:
    if operation == "lane_independence":
        keys=[set(_strings(item.get("write_keys"))) for item in _items(p,"lanes")]; collisions=sorted(set().union(*(a&b for i,a in enumerate(keys) for b in keys[i+1:])) if keys else set())
        return {"independent":not collisions,"collision_keys":collisions}
    if operation == "fanout_bound":
        requested=max(0,int(p.get("requested",0) or 0)); maximum=max(1,int(p.get("maximum",4) or 4)); return {"fanout":min(requested,maximum),"throttled":requested>maximum}
    if operation == "fanin_contract": return {"single_fanin":int(p.get("fanin_count",1) or 1)==1,"required_fanin":1}
    if operation == "stream_load":
        active=max(0,int(p.get("active",0) or 0)); capacity=max(1,int(p.get("capacity",4) or 4)); return {"load":round(active/capacity,9),"overloaded":active>capacity}
    if operation == "contention_risk": return {"contention_risk":_clamp(.6*_score(p,"shared_write_pressure")+.4*_score(p,"lock_wait_ratio"))}
    if operation == "scheduler_mode":
        mode="SERIAL" if p.get("external_effect") or _score(p,"shared_write_pressure")>=.7 else "PARALLEL" if int(p.get("ready_count",0) or 0)>=2 else "DIRECT"
        return {"scheduler_mode":mode,"external_effects_serialized":True}
    if operation == "next_best_action":
        candidates=_items(p,"candidates"); ranked=sorted(candidates,key=lambda x:(-(float(x.get("value",0))-float(x.get("risk",0))-float(x.get("burden",0))),str(x.get("id",""))))
        return {"action_id":ranked[0].get("id") if ranked else None,"candidate_count":len(ranked)}
    if operation == "owner_interrupt":
        exact=bool(p.get("exact_owner_decision_required",False)); safe=int(p.get("safe_routes_remaining",0) or 0); return {"interrupt_owner":exact and safe==0,"safe_routes_remaining":safe}
    if operation == "provider_readiness":
        ready=all(bool(p.get(key)) for key in ("identity_verified","target_verified","scope_verified","readback_available")); return {"provider_ready":ready,"provider_effect_authorized":False}
    return {"orchestration_receipt":_hash({key:p.get(key) for key in ("lanes","waves","scheduler_mode","next_action")}),"single_fanin":True}


def _value(operation: str, p: Mapping[str, Any]) -> Mapping[str, Any]:
    if operation == "owner_burden_delta": return {"delta":_delta(p,"baseline_burden","candidate_burden"),"improved":_delta(p,"baseline_burden","candidate_burden")<0}
    if operation == "time_delta": return {"seconds_saved":round(float(p.get("baseline_seconds",0) or 0)-float(p.get("candidate_seconds",0) or 0),9)}
    if operation == "verified_output_delta": return {"delta":_delta(p,"baseline_verified_outputs","candidate_verified_outputs"),"improved":_delta(p,"baseline_verified_outputs","candidate_verified_outputs")>0}
    if operation == "intervention_ratio":
        tasks=max(0,int(p.get("tasks",0) or 0)); interventions=max(0,int(p.get("interventions",0) or 0)); return {"ratio":round(interventions/tasks,9) if tasks else 0.0,"zero_manual":interventions==0}
    if operation == "cost_delta": return {"cost_saved":round(float(p.get("baseline_cost",0) or 0)-float(p.get("candidate_cost",0) or 0),9),"recurring_cost":0}
    if operation == "risk_adjusted_value":
        value=float(p.get("value",0) or 0); return {"risk_adjusted_value":round(value*(1-_score(p,"risk"))-_score(p,"burden")-float(p.get("cost",0) or 0),9)}
    if operation == "pair_completeness":
        base=set(_strings(p.get("baseline_ids"))); cand=set(_strings(p.get("candidate_ids"))); return {"paired_ids":sorted(base&cand),"pair_count":len(base&cand),"unpaired":sorted(base^cand)}
    if operation == "minimum_cases":
        observed=max(0,int(p.get("observed",0) or 0)); required=max(1,int(p.get("required",30) or 30)); return {"met":observed>=required,"observed":observed,"required":required}
    if operation == "promotion_hold":
        reasons=_unique(p.get("blockers")); value=bool(p.get("owner_value_proven",False)); regressions=int(p.get("hard_regressions",0) or 0); hold=bool(reasons) or not value or regressions>0
        return {"hold":hold,"bounded_candidate":not hold,"stable_self_promotion_authorized":False}
    return {"value_receipt":_hash({key:p.get(key) for key in ("burden_delta","time_delta","output_delta","cost_delta","risk_adjusted_value")}),"observed_value_required":True}


_DOMAIN_EVALUATORS: Mapping[str, Callable[[str, Mapping[str, Any]], Mapping[str, Any]]] = {
    "intent": _intent, "evidence": _evidence, "planning": _planning, "execution": _execution,
    "quality": _quality, "safety": _safety, "continuity": _continuity, "learning": _learning,
    "orchestration": _orchestration, "value": _value,
}


def _build_specs() -> tuple[CapabilitySpec, ...]:
    specs: list[CapabilitySpec] = []
    ordinal = 0
    for domain, operations in DOMAIN_OPERATIONS:
        for operation in operations:
            ordinal += 1
            specs.append(CapabilitySpec(f"BCO-PRIME-CAP-{ordinal:03d}", f"cap_{ordinal:03d}_{operation}", domain, operation, ordinal))
    if ordinal != CAPABILITY_COUNT:
        raise RuntimeError("BCO_PRIME_CAPABILITY_COUNT_INVALID")
    return tuple(specs)


CAPABILITY_SPECS = _build_specs()
_SPEC_BY_ID = {item.capability_id: item for item in CAPABILITY_SPECS}


def execute_capability(capability_id: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if capability_id not in _SPEC_BY_ID:
        raise KeyError(f"UNKNOWN_BCO_PRIME_CAPABILITY:{capability_id}")
    if payload is None:
        payload = {}
    if not isinstance(payload, Mapping):
        raise TypeError("CAPABILITY_PAYLOAD_MAPPING_REQUIRED")
    _boundary_guard(payload)
    spec = _SPEC_BY_ID[capability_id]
    output = dict(_DOMAIN_EVALUATORS[spec.domain](spec.operation, payload))
    draft: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "fabric_schema": SCHEMA,
        "capability_id": spec.capability_id,
        "function_name": spec.function_name,
        "domain": spec.domain,
        "operation": spec.operation,
        "status": "SUCCESS",
        "input_sha256": _hash(payload),
        "output": output,
        "authority_ceiling": AUTHORITY_CEILING,
        "authority_expansion": False,
        "external_effect": False,
        "provider_effect_authorized": False,
        "stable_self_promotion_authorized": False,
        "manual_user_tasks": [],
        "owner_action_required": False,
        "rollback": "NO_EFFECT_REPLAY_SAFE",
        "truth_boundary": "deterministic local decision support; no provider effect or authority",
    }
    return {**draft, "receipt_sha256": _hash(draft)}


def _make_capability(spec: CapabilitySpec) -> Callable[[Mapping[str, Any] | None], dict[str, Any]]:
    def capability(payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return execute_capability(spec.capability_id, payload)
    capability.__name__ = spec.function_name
    capability.__qualname__ = spec.function_name
    capability.__doc__ = f"Execute {spec.capability_id}: {spec.domain}.{spec.operation}."
    return capability


FUNCTION_REGISTRY: dict[str, Callable[[Mapping[str, Any] | None], dict[str, Any]]] = {}
for _spec in CAPABILITY_SPECS:
    _function = _make_capability(_spec)
    globals()[_spec.function_name] = _function
    FUNCTION_REGISTRY[_spec.capability_id] = _function


def capability_manifest() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "capability_count": len(CAPABILITY_SPECS),
        "domain_count": len(DOMAIN_OPERATIONS),
        "domains": {domain: len(operations) for domain, operations in DOMAIN_OPERATIONS},
        "capabilities": [asdict(item) for item in CAPABILITY_SPECS],
        "manual_user_tasks": [],
        "owner_action_required": False,
        "external_effect": False,
        "provider_effect_authorized": False,
        "authority_expansion": False,
    }


def main() -> int:
    parser = ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    run = subparsers.add_parser("run")
    run.add_argument("capability_id")
    run.add_argument("--payload-json", default="{}")
    args = parser.parse_args()
    if args.command == "list":
        print(json.dumps(capability_manifest(), sort_keys=True))
        return 0
    payload = json.loads(args.payload_json)
    print(json.dumps(execute_capability(args.capability_id, payload), sort_keys=True))
    return 0


__all__ = ["CAPABILITY_COUNT", "CAPABILITY_SPECS", "FUNCTION_REGISTRY", "capability_manifest", "execute_capability"] + [item.function_name for item in CAPABILITY_SPECS]


if __name__ == "__main__":
    raise SystemExit(main())
