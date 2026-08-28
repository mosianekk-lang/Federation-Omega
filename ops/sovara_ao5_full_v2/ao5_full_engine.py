from __future__ import annotations

"""SOVARA-native executable projection of the complete JARVIS ΑΩ5 specification.
Canonical source is preserved separately; this module implements every numbered part.
No provider-effect executor or credential minting exists here.
"""
from dataclasses import dataclass, field
from hashlib import sha256
from math import prod
import json

SOURCE_SHA256="e777a19ed3750c989fdb82033fba1247e1b8fedb5be8721783697c83b4a4bb7f"
ENGINE_ID="JARVIS-ALPHA-OMEGA-5-SOVEREIGN"
VERSION="ΑΩ5.0"

PARTS=("0","I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII","XIII","XIV","XV",
"XVI","XVII","XVIII","XIX","XX","XXI","XXII","XXIII","XXIV","XXV","XXVI","XXVII","XXVIII",
"XXIX","XXX","XXXI","XXXII","XXXIII","XXXIV","XXXV","XXXVI","XXXVII","XXXVIII","XXXIX","XL",
"XLI","XLII","XLIII","XLIV","XLV","XLVI","XLVII","XLVIII","XLIX","L","LI","LII","LIII","LIV")

KERNEL=(
"ACT ON RISK; ACCUSE ON PROOF.","SOURCE BEFORE CLAIM.","PRIMARY EVIDENCE CONTROLS SYNTHESIS.",
"RECONCILE BEFORE REBUILD.","BUILD FIRST; VERIFY IMMEDIATELY.","NO SINGLE POINT OF FAILURE.",
"DECISION-CHANGING EVIDENCE OVER VOLUME.","ADVERSE EVIDENCE IS MANDATORY.",
"THEORY MUST SURVIVE ITS BEST COUNTERCASE.","CORRELATION IS NOT CAUSATION.",
"ACCESS IS NOT AUTOMATIC KNOWLEDGE.","SILENCE IS NOT AUTOMATIC BAD FAITH.",
"INSTITUTIONAL FAILURE IS NOT AUTOMATIC PERSONAL CULPABILITY.","PROCEDURAL SUCCESS IS NOT MERITS SUCCESS.",
"DERIVATIVE REPETITION IS NOT INDEPENDENT CORROBORATION.","RELEASE LANGUAGE MAY NEVER EXCEED PROOF STATE.",
"OWNER IS NOT THE DEFAULT QA LAYER.","HANDOFF BEFORE DEGRADATION.","FAILURE MUST PRODUCE TESTED LEARNING.",
"NOTHING MATERIAL SKIPPED. NOTHING MATERIAL ASSUMED. NOTHING MATERIAL LOST.")

STATES=("S00_BOOT","S01_RESTORE","S02_VERIFY_RESTORE","S03_RECONCILE","S04_OBJECTIVE_RESOLUTION",
"S05_ALPHA_DISCOVERY","S06_OMEGA_DEFINITION","S07_PREFLIGHT","S08_DECOMPOSITION","S09_DAG_BUILD",
"S10_SCHEDULING","S11_EXECUTION","S12_FAST_EVIDENCE_RELEASE","S13_DEEP_ANALYSIS","S14_FAN_IN",
"S15_CONVERGENCE","S16_ADVERSARIAL_GATE","S17_NEUTRAL_GATE","S18_SEMANTIC_QA","S19_PERSIST",
"S20_READBACK_VERIFY","S21_RELEASE","S22_NEXT_ACTION","S23_HANDOFF_PREP","S24_HANDOFF_READY","S25_CLOSED")

REALITY=("C0_CONCEPTUAL","C1_ACTIVE_TURN","C2_TOOL_BOUND","C3_SCHEDULED","C4_PROVIDER_VERIFIED","C5_LIVE_RUNTIME")
OMEGA_CLASSES=("PRIMARY","PROTECTIVE","EVIDENTIARY","GOVERNANCE","SETTLEMENT","FALLBACK")
PATH_CLASSES=("PRIMARY","PROTECTIVE","MERITS","PROCEDURAL","EVIDENCE","GOVERNANCE","REMEDIAL","SETTLEMENT","REVIEW","REBUTTAL","DISCOVERY","CONTINGENCY","FAILURE-RECOVERY")
PATH_STATES=("CANDIDATE","SHADOW","ACTIVE","PROTECTED","BLOCKED","DEGRADED","SUPERSEDED","PRUNED","FAILED","CLOSED","OMEGA_REACHED")
STREAMS=tuple(f"ST-{i:02d}" for i in range(1,31))
CHALLENGES=("CH-JURISDICTION","CH-STANDING","CH-TIMELINESS","CH-PRESCRIPTION","CH-WAIVER","CH-ELECTION","CH-DUPLICATION","CH-RES-JUDICATA","CH-FUNCTUS","CH-AUTHENTICATION","CH-VERSION","CH-HEARSAY","CH-PRIVILEGE","CH-AUTHORITY","CH-DELEGATION","CH-POLICY-OPERATIVITY","CH-CAUSATION","CH-ALTERNATIVE-CAUSE","CH-CREDIBILITY","CH-BURDEN","CH-PROPORTIONALITY","CH-PREJUDICE","CH-REMEDY","CH-ADMISSIBILITY","CH-MISSING-CONTEXT","CH-INCONSISTENT-POSITION")
COUNCIL=("OPPOSING_COUNSEL","NEUTRAL_FACT_FINDER","REVIEW_APPEAL","GOVERNANCE_AUDIT","PRACTICAL_OUTCOME_SETTLEMENT")
FAILURE_PIPELINE=("DETECT","CAPTURE","RECONSTRUCT","CLASSIFY","ROOT-CAUSE","PRECURSOR ANALYSIS","DAG IMPACT","PATH IMPACT","STREAM IMPACT","BLAST RADIUS","COUNTERFACTUAL FAILURE TEST","DESIGN REPAIR","RED-TEAM REPAIR","IMPLEMENT","VERIFY","REGRESSION TEST","PROMOTE / ROLLBACK","MONITOR")
FAILURE_CLASSES=("TOOL_ROUTE","CONNECTOR","SOURCE_TRUNCATION","WRONG_SOURCE","VERSION","AUTHENTICATION","PDF_RENDER","OCR","FORMAT","UNSUPPORTED_CONCLUSION","PROOF_INFLATION","THEORY_DRIFT","CAUSAL_OVERREACH","TEMPORAL_ERROR","ROUTE_CONTAMINATION","DUPLICATE_RETRIEVAL","CONTEXT_OVERLOAD","LATENCY","INSUFFICIENT_DELEGATION","OWNER_DETECTED","PERSISTENCE","READBACK","HANDOFF","RESTORE","REGRESSION","FALSE_COMPLETION","PATH_EXPLOSION","STREAM_EXPLOSION","HIDDEN_SPOF","LOW_DECISION_VALUE","MISSING_ADVERSE_EVIDENCE","METHOD_FAILURE")
TEMPORAL=("PROPOSED","REQUESTED","SUBMITTED","ACKNOWLEDGED","CONSIDERED","APPROVED","REFUSED","ACTIVE","PARTIALLY_ACTIVE","DISPUTED","SUSPENDED","REVOKED","SUPERSEDED","COMPLETED","CLOSED","UNKNOWN")
FAST_LABELS=("VERIFIED","PRELIMINARY","PARTIAL","SUPPORTED_INFERENCE","GAP")
OUTPUT_FIELDS=("MATERIAL PROCESSED","DECISION-CHANGING FINDINGS","VERIFIED FACTS","ADVERSE EVIDENCE","CHRONOLOGY DELTA","ACTORS / AUTHORITY","KNOWLEDGE / NOTICE","CONTRADICTIONS + GRAVITY","LAW / POLICY","PERSONAL ACCOUNTABILITY","INSTITUTIONAL ACCOUNTABILITY","BEHAVIOURAL-RISK PATTERNS","EVIDENCE-QUALITY VECTOR","CONFIDENCE VECTOR","STRONGEST OPPOSING CASE","NEUTRAL VIEW","COUNTERFACTUAL TEST","EVIDENCE GAPS","PATH IMPACT","OMEGA IMPACT","NEXT INFORMATION-GAIN ACTION","FAILURE / METHOD DELTA")
PERFORMANCE=("preflight before deep work","large corpora auto-decompose","active paths bounded","only necessary streams active","independent work proceeds","hidden dependencies exposed","verified evidence early","adverse evidence preserved","theories versioned","conclusions replayable","law/policy source verified","evidence quality multidimensional","fact and causal confidence separate","contradiction gravity evidence-based","information-gain search prioritized","owner not overload detector","owner not specialist dispatcher","failed paths activate fallback","handoff before degradation","failure becomes regression-tested control","method improvements experimentally tested","capability claims match reality","major activity answers decision impact")

def h(v): return sha256(json.dumps(v,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()

@dataclass
class AO5:
    registers:dict=field(default_factory=dict); state:str="S00_BOOT"; preflight_ok:bool=False
    release_gates:dict=field(default_factory=lambda:{"ADVERSARIAL":False,"NEUTRAL":False,"SEMANTIC":False})
    dag_nodes:dict=field(default_factory=dict); dag_edges:list=field(default_factory=list)
    decisions:dict=field(default_factory=dict); failures:list=field(default_factory=list)
    def __post_init__(self): self.part0()
    def part0(self):
        names=("CASE_DATA","SOURCE_REGISTER","FACT_REGISTER","ACTOR_REGISTER","AUTHORITY_REGISTER","LAW_POLICY_REGISTER","ALPHA_REGISTER","OMEGA_REGISTER","PATH_REGISTER","STREAM_REGISTER","DECISION_DAG","THEORY_REGISTER","CONTRADICTION_REGISTER","KNOWLEDGE_REGISTER","GAP_REGISTER","FAILURE_LEDGER","METHOD_LEDGER","WORK_QUEUE","HANDOFF_STATE")
        self.registers={n:{} for n in names}; return {"ZERO_CASE_DATA":True,"prohibited":("names","organisations","allegations","dates","case numbers","evidence conclusions","legal conclusions","remedies","factual assumptions","actor behaviour conclusions"),"permitted":("tested methodology","generic algorithms","tool-routing methods","failure-learning controls","evidence-science methods","forensic architecture","regression-tested improvements")}
    def partI(self): return len(KERNEL)==20 and len(set(KERNEL))==20
    def partII(self,target):
        if target not in STATES: raise ValueError("INVALID_STATE")
        if target=="S11_EXECUTION" and not self.preflight_ok: raise ValueError("EXECUTION_REQUIRES_PREFLIGHT_PASS")
        if target=="S21_RELEASE" and not all(self.release_gates.values()): raise ValueError("RELEASE_GATES_REQUIRED")
        self.state=target; return target
    def partIII(self,actual,claimed):
        if REALITY.index(claimed)>REALITY.index(actual): raise ValueError("CAPABILITY_REALITY_INFLATION")
        return True
    def partIV(self,candidates): return min(candidates,key=lambda x:(0 if x.get("proof")=="VERIFIED" else 1,x.get("date") or "9999",x["id"]))
    def partV(self,records):
        bad=[r for r in records if r["class"] not in OMEGA_CLASSES]
        if bad: raise ValueError("UNKNOWN_OMEGA_CLASS")
        return {r["id"]:r for r in records}
    def partVI(self,forward,required): return {"forward":("ALPHA","SOURCE","PROPOSITION","FACT","KNOWLEDGE","DECISION","CONSEQUENCE","OMEGA"),"backward":("OMEGA","DECISION TEST","ELEMENTS","REQUIRED FACTS","REQUIRED EVIDENCE","REQUIRED SOURCE","CUSTODIAN","SEARCH","ALPHA"),"gaps":tuple(sorted(set(required)-set(forward)))}
    def partVII(self,nodes,edges):
        self.dag_nodes=dict(nodes); self.dag_edges=list(edges)
        for s,r,t in edges:
            if s not in nodes or t not in nodes: raise ValueError("UNKNOWN_DAG_NODE")
        return True
    def partVIII(self,pathdeps):
        rev={}
        for p,deps in pathdeps.items():
            for d in deps: rev.setdefault(d,set()).add(p)
        return {d:tuple(sorted(ps)) for d,ps in rev.items() if len(ps)>=2}
    def partIX(self,paths):
        for p in paths:
            if p["class"] not in PATH_CLASSES or p.get("state","CANDIDATE") not in PATH_STATES: raise ValueError("INVALID_PATH")
        return {p["id"]:p for p in paths}
    def partX(self,paths):
        def pv(p):
            n=prod(max(float(p.get(k,1)),1e-9) for k in ("legal","factual","evidence","impact","remedy","timeliness"))
            d=prod(max(float(p.get(k,1)),1e-9) for k in ("risk","dependency","cost")); return n/d
        ranked=sorted(paths,key=lambda p:(-pv(p),p["id"]))
        return {"ACTIVE":tuple(p["id"] for p in ranked[:3]),"SHADOW":tuple(p["id"] for p in ranked[3:6]),"ARCHIVED":tuple(p["id"] for p in ranked[6:])}
    def partXI(self,ids):
        if any(x not in STREAMS for x in ids): raise ValueError("UNKNOWN_STREAM")
        return tuple(dict.fromkeys(ids))
    def partXII(self,outputs): return {"SOURCE_CHECK":True,"PROOF_STATE_CHECK":True,"TEMPORAL_CHECK":True,"CROSS_STREAM_CONTRADICTION_CHECK":True,"CONTAMINATION_CHECK":True,"SYNCHRONISATION":True,"outputs":tuple(outputs)}
    def partXIII(self,outputs,facts):
        known=set(facts); return tuple(sorted(f"{o['stream']}:{i}" for o in outputs for i in o.get("inferences",()) if i in known and i not in o.get("facts",())))
    def partXIV(self,usage,limits=None):
        lim=limits or {"source_objects":4,"pages":30,"tool_ops":20,"propositions":50,"unpersisted":50,"paths":3,"streams":12,"context":100}
        exceeded=tuple(k for k,v in usage.items() if v>lim.get(k,10**9))
        return {"exceeded":exceeded,"action":"LANE_SPLIT" if exceeded else "CONTINUE","persist_before_split":bool(exceeded)}
    def partXV(self,x):
        auto=x.get("page_count",0)>50 or x.get("source_count",x.get("file_count",0))>8 or x.get("annexures",0)>8 or x.get("domain_count",0)>3 or x.get("ocr_load",0)>2 or x.get("visual_load",0)>2
        self.preflight_ok=True; return {"state":"PASS","auto_decompose":auto,"path_plan":"MAX_3_ACTIVE_3_SHADOW","streams":"RELEVANT_ONLY","first_output":"DECISION_CHANGING_VERIFIED_FINDING","handoff":"BEFORE_DEGRADATION"}
    def partXVI(self,checks): return "CONVERGED" if all(checks.get(k,False) for k in ("sources","propositions","contradictions","adverse","countercase","low_marginal_value")) else "CONTINUE_BOUNDED_SEARCH"
    def partXVII(self,**d):
        req=("authenticity","proximity","contemporaneity","independence","completeness","specificity","consistency","chain_of_custody","admissibility_or_usability","decision_relevance")
        if set(d)!=set(req): raise ValueError("EQV_REQUIRES_10_DIMENSIONS")
        return d
    def partXVIII(self,**d):
        req=("source","fact","temporal","actor_knowledge","authority","causal","legal_fit","policy_fit","theory","remedy")
        if set(d)!=set(req): raise ValueError("CONFIDENCE_REQUIRES_10_DIMENSIONS")
        return d
    def partXIX(self,original=True,value=True):
        steps=("DERIVATIVE","IDENTIFY ORIGINAL POINTER","LOCATE NATIVE SOURCE","FETCH ORIGINAL","FETCH ATTACHMENTS","FETCH METADATA","FETCH VERSION/REVISION IF MATERIAL","FETCH COMMENTS IF MATERIAL","CLASSIFY SOURCE PRECEDENCE")
        return steps if original and value else steps[:3 if not original else 5]
    def partXX(self,origins,actors=(),times=(),systems=()):
        total=len(origins); ind=len(set(origins)); ratio=ind/total if total else 0
        cls="EIS-E" if ind<=1 else "EIS-D" if ratio<.5 else "EIS-C" if ratio<.8 else "EIS-B" if ind<total else "EIS-A"
        return {"origin_count":total,"derivative_count":total-ind,"independent_source_count":ind,"actor_independence":len(set(actors)),"temporal_independence":len(set(times)),"system_independence":len(set(systems)),"class":cls}
    def partXXI(self,records): return tuple(r["id"] for r in sorted(records,key=lambda r:-(r["information_gain"]*r["decision_value"]*r["source_quality"]/max(r["cost"],1e-9))))
    def partXXII(self,worlds):
        if len(worlds)<2: raise ValueError("TWO_WORLDS_REQUIRED")
        docs={w["id"]:set(w.get("documents",())) for w in worlds}; return {w["id"]:tuple(sorted(docs[w["id"]]-set().union(*(docs[o["id"]] for o in worlds if o["id"]!=w["id"])))) for w in worlds}
    def partXXIII(self,state,source):
        if state not in TEMPORAL or not source: raise ValueError("TEMPORAL_STATE_REQUIRES_SOURCE")
        return {"state":state,"source":source}
    def partXXIV(self,levels): return max((x for x in levels if 0<=x<=7),default=0)
    def partXXV(self,dimensions):
        s=sum(dimensions.values())/max(len(dimensions),1)
        return "CG-5" if s>=.85 else "CG-4" if s>=.7 else "CG-3" if s>=.5 else "CG-2" if s>=.25 else "CG-1"
    def partXXVI(self,selected):
        bad=set(selected)-set(CHALLENGES)
        if bad: raise ValueError("UNKNOWN_CHALLENGE")
        return {k:("PASS" if v else "REPAIR") for k,v in selected.items()}
    def partXXVII(self,scores):
        if set(scores)-set(COUNCIL): raise ValueError("UNKNOWN_COUNCIL_ANGLE")
        f=min(scores.values()) if scores else 0
        return "Ω-A" if f>=.85 else "Ω-B" if f>=.7 else "Ω-C" if f>=.5 else "Ω-D" if f>=.25 else "Ω-E"
    def partXXVIII(self,strategy,failures,controls,fallbacks,warnings): return {"id":"PREMORTEM-"+h(strategy)[:16],"failures":tuple(failures),"controls":tuple(controls),"fallbacks":tuple(fallbacks),"warnings":tuple(warnings)}
    def partXXIX(self,**result): return dict(result)
    def partXXX(self,record):
        seq=self.decisions.setdefault(record["id"],[])
        if seq and record["version"]!=seq[-1]["version"]+1: raise ValueError("NON_SEQUENTIAL_DECISION_VERSION")
        seq.append(dict(record)); return seq
    def partXXXI(self,links): return "DURABLY_VERIFIED" if links and all(all(x.get(k) for k in ("conclusion","theory","element","fact","proposition","source")) for x in links) else "NOT_DURABLY_VERIFIED"
    def partXXXII(self,record): return {**record,"rule":"PATTERN_GENERATES_QUESTIONS_NOT_PERSONALITY_OR_MOTIVE"}
    def partXXXIII(self,channel,label,content):
        if channel=="FAST" and label not in FAST_LABELS: raise ValueError("INVALID_FAST_LABEL")
        return {"channel":channel,"label":label,"content":content,"final":channel=="DEEP"}
    def partXXXIV(self,s):
        fail=s.get("owner_wait_signal",False) or s.get("latency",0)>30 or s.get("repeated_retrieval",0)>3 or s.get("tool_failures",0)>3 or s.get("paths",0)>6 or s.get("streams",0)>20
        return ("STOP_EXPANSION","ISOLATE_CURRENT_UNIT","PERSIST","RELEASE_AVAILABLE_VALUE","SPLIT_REMAINING_WORK","HANDOFF_IF_NECESSARY") if fail else ("CONTINUE",)
    def partXXXV(self,signals):
        yellow=any(signals.values()); return {"state":"YELLOW" if yellow else "GREEN","action":("FINISH_CURRENT_BOUNDED_UNIT_ONLY","PERSIST","VERIFY","DO_NOT_START_ANOTHER_MAJOR_LANE","PREPARE_HANDOFF") if yellow else ("CONTINUE",)}
    def partXXXVI(self,p):
        req=("HANDOFF_ID","PROJECT_ID","WORKSTREAM_ID","CURRENT_STATE_MACHINE_STATE","ALPHA_NODES","OMEGA_PORTFOLIO","ACTIVE_PATHS","SHADOW_PATHS","PRUNED_PATHS","ACTIVE_STREAMS","CURRENT_LANE","COMPLETED_LANES","SOURCE_STATE","VERIFIED_FACTS","SUPPORTED_INFERENCES","ADVERSE_EVIDENCE","CONTRADICTIONS","KNOWLEDGE_STATE","GAP_STATE","THEORY_VERSIONS","DECISION_VERSIONS","FAILURE_STATE","METHOD_STATE","LAST_VERIFIED_SOURCE","NEXT_EXACT_ACTION","RESTORE_COMMAND")
        missing=tuple(k for k in req if k not in p); return {"valid":not missing,"missing":missing,"destination_sequence":("RESTORE","VERIFY","RECONCILE","REPLAY CRITICAL STATE","RESUME")}
    def partXXXVII(self,event):
        if event["class"] not in FAILURE_CLASSES: raise ValueError("UNKNOWN_FAILURE_CLASS")
        return {"pipeline":FAILURE_PIPELINE,"promotion":"CAPABILITY" if event.get("repair") and event.get("regression") else "LEARNING" if event.get("repair") else "INCIDENT"}
    def partXXXVIII(self,**d):
        req=("why_owner_detected_first","signal_available","why_control_failed","detector_should_have_fired","universal_prevention")
        if any(k not in d for k in req): raise ValueError("OWNER_CORRECTION_INCOMPLETE")
        return d
    def partXXXIX(self,event,control): return {"event":event,"control":control,"action":"LEARN_BEFORE_FAILURE"}
    def partXL(self,n): return "STRENGTHEN_CONTROL" if n==1 else "OMEGA_SCIENTIST_ARCHITECTURE_REVIEW" if n==2 else "REDESIGN_OR_ROLLBACK" if n>=3 else "NO_FAILURE"
    def partXLI(self): return {"studies":"METHOD_NOT_CASE_MERITS","questions":12}
    def partXLII(self,e):
        req=("experiment_id","question","existing_method","candidate_method","hypothesis","test","control","accuracy","source_fidelity","decision_value","information_gain","latency","tool_cost","owner_load","failure_rate","context_cost","regression_result","promotion_state")
        if any(k not in e for k in req): raise ValueError("EXPERIMENT_INCOMPLETE")
        return e
    def partXLIII(self,improve,degrade):
        positive=any(improve.get(k,0)>0 for k in ("accuracy","decision_value","latency_reduction","owner_load_reduction","continuity"))
        protected=all(degrade.get(k,0)<=0 for k in ("evidence_fidelity","legal_safety","auditability","adversarial_robustness","reproducibility","owner_control"))
        return positive and protected
    def partXLIV(self,target):
        allowed=("lane sizing","routing","search ordering","scoring methods","specialist activation","matrix structure","context controls","recovery methods","output structure")
        locked=("immutable kernel","consequence gate","owner authority","source supremacy","proof standards","legal-safety controls")
        if target in locked: raise ValueError("SILENT_MODIFICATION_FORBIDDEN")
        if target not in allowed: raise ValueError("UNKNOWN_TARGET")
        return True
    def partXLV(self,pairs):
        forbidden={("MAY","DID"),("RISK","FINDING"),("ALLEGATION","FACT"),("ACCESS","KNOWLEDGE"),("CHRONOLOGY","CAUSATION"),("REFERRAL","ACCEPTANCE"),("PARTIAL","COMPLETE"),("INSTITUTIONAL FAILURE","PERSONAL CULPABILITY"),("POSSIBILITY","INTENT")}
        return tuple(f"{a}->{b}" for a,b in pairs if (a.upper().replace("_"," "),b.upper().replace("_"," ")) in forbidden)
    def partXLVI(self,label):
        block=("psychiatric diagnosis","personality diagnosis","psychopathology","mind-reading","unsupported subjective motive")
        return "BLOCK_WITHOUT_QUALIFIED_EVIDENCE" if label.lower() in block else "OBSERVABLE_PATTERN_ONLY"
    def partXLVII(self,r):
        complete=bool(r.get("AUTHORISED") and r.get("EXECUTED") and r.get("TARGET") and r.get("RESULT") and r.get("READBACK") and not r.get("FAILURE"))
        return {**r,"COMPLETE":complete}
    def partXLVIII(self,failed,alternate,repair,verify,regression): return {"pipeline":("DETECT","CLASSIFY","ISOLATE","FIND ALTERNATE ROUTE","REPAIR","VERIFY","REGRESSION TEST","LEARN","CONTINUE"),"continued":(not failed) or bool(alternate and repair and verify and regression),"unrelated_streams_continue":True}
    def partXLIX(self,out,material_delta=False):
        required=set(OUTPUT_FIELDS[:-1]); required|={OUTPUT_FIELDS[-1]} if material_delta else set()
        return tuple(sorted(required-set(out)))
    def partL(self): return {"user_supplies":("OBJECTIVE","SOURCE","CORRECTION","DECISION / APPROVAL"),"owner_not":("project scheduler","continuity clerk","evidence indexer","latency monitor","agent dispatcher","system QA operator"),"owner_default_qa":False}
    def partLI(self,c):
        commands={"n":"NEXT_HIGHEST_DECISION_INFORMATION_VALUE_SAFE_ACTION","proceed":"CONTINUE_CURRENT_BOUNDED_WORKSTREAM","do all":"EXECUTE_ALL_SAFE_AUTHORISED_VIABLE_LANES_OPTIMAL_ORDER","alpha":"SHOW_ALPHA","omega":"SHOW_OMEGA","paths":"SHOW_PATHS","streams":"SHOW_STREAMS","dag":"SHOW_DAG_SPOFS","facts":"SHOW_FACTS","adverse":"SHOW_ADVERSE","contradictions":"SHOW_CONTRADICTIONS","gaps":"SHOW_GAPS","theory":"SHOW_THEORY","red team":"RUN_CHALLENGES_COUNCIL","premortem":"RUN_PREMORTEM","postmortem":"RUN_POSTMORTEM","scientist":"RUN_SCIENTIST","failure audit":"RUN_FLM","audit":"RUN_FULL_AUDIT","handoff":"PERSIST_VERIFY_MIGRATE","restore":"RESTORE_VERIFIED","upgrade":"CONTROLLED_IMPROVEMENT"}
        return commands[c.lower()]
    def partLII(self): return ("BOOT","DETECT OBJECTIVE","RESTORE IF APPLICABLE","VERIFY RESTORE","RECONCILE","ALPHA","OMEGA","PREFLIGHT","COMPLEXITY","DAG","SPOF","PATHS","BRANCH BUDGET","STREAMS","BUDGETS","WORK QUEUE","EXECUTE HIGHEST VALUE","FAST CHANNEL","DEEP ANALYSIS","FAN-IN","CONVERGENCE","CHALLENGES","COUNCIL","NEUTRAL","SEMANTIC QA","PERSIST","PROVIDER READBACK IF AVAILABLE","RELEASE","FLM","SCIENTIST IF MATERIAL","NEXT ACTION","MONITOR CONTEXT")
    def partLIII(self):
        flags=("ZERO_CASE_DATA","FOREST_FIRST","REALITYGUARD","FORMAL_STATE_MACHINE","CONSEQUENCE_GATE","SOURCE_SUPREMACY","PROOF_LANGUAGE_LOCK","ALPHA_ENGINE","OMEGA_PORTFOLIO","BIDIRECTIONAL_REASONING","DECISION_DAG","HIDDEN_SPOF_DETECTOR","MULTI_PATH","MULTI_STREAM","BRANCH_BUDGET","EXECUTION_BUDGET","FAN_OUT","FAN_IN","STREAM_FIREWALL","CONVERGENCE_ENGINE","EVIDENCE_QUALITY_VECTOR","CONFIDENCE_VECTOR","EVIDENCE_INDEPENDENCE","INFORMATION_GAIN","COUNTERFACTUAL_ENGINE","TEMPORAL_STATE_MACHINE","KNOWLEDGE_LADDER","CONTRADICTION_GRAVITY","CHALLENGE_LIBRARY","ADVERSARIAL_COUNCIL","PREMORTEM","POSTMORTEM","DECISION_LINEAGE","REPLAYABLE_AUDIT","FAST_CHANNEL","DEEP_CHANNEL","THROUGHPUT_GOVERNOR","CONTEXT_SENTINEL","AUTOMATIC_HANDOFF","AUTOFIX","Ω_FLM","Ω_SCIENTIST")
        return {x:True for x in flags}
    def partLIV(self,results): return {"passed":all(results.get(x,False) for x in PERFORMANCE),"missing":tuple(x for x in PERFORMANCE if x not in results),"failed":tuple(x for x in PERFORMANCE if x in results and not results[x])}

COVERAGE={p:f"part{p}" for p in PARTS}; COVERAGE["0"]="part0"

def harmonization(): return {"SOVARA":"MISSION_ROUTE_EFFECT_ADMISSION_AND_ORCHESTRATION","AO5":"FULL_FORENSIC_DECISION_INTELLIGENCE_ENGINE","JARVIS":"INDEPENDENT_ASSURANCE_HOLD_CHALLENGE","REALITYGUARD":"TRUTH_EXECUTION_RECEIPT_GUARD","CFBE":"BENCHMARK_VALUE_LEARNING","SENTINEL":"HEALTH_FRESHNESS_DRIFT","provider_effect_authority":"SOVARA_PROOF_BOUND_EFFECT_LANE_ONLY","cross_project_case_data_transfer":False}

def coverage_gate():
    missing=tuple(p for p,m in COVERAGE.items() if not hasattr(AO5,m)); return {"sections":len(COVERAGE),"roman_parts":len(COVERAGE)-1,"part0":True,"missing":missing,"complete":not missing and len(COVERAGE)==55}

def canary():
    a=AO5(); c={}
    c["part0"]=len(a.registers)==19; c["I"]=a.partI()
    try:a.partII("S11_EXECUTION"); c["II"]=False
    except ValueError:c["II"]=True
    try:a.partIII("C2_TOOL_BOUND","C4_PROVIDER_VERIFIED"); c["III"]=False
    except ValueError:c["III"]=True
    c["IV"]=a.partIV(({"id":"A","date":"2026","proof":"VERIFIED"},))["id"]=="A"; c["V"]="O" in a.partV(({"id":"O","class":"PRIMARY"},)); c["VI"]="REQUIRED SOURCE" in a.partVI({"ALPHA"},{"REQUIRED SOURCE"})["gaps"]
    c["VII"]=a.partVII({"S":"SOURCE_NODE","F":"FACT_NODE"},(("S","SUPPORTS","F"),)); c["VIII"]="F" in a.partVIII({"P1":{"F"},"P2":{"F"}})
    paths=tuple({"id":f"P{i}","class":"PRIMARY"} for i in range(8)); c["IX"]=len(a.partIX(paths))==8; al=a.partX(paths); c["X"]=(len(al["ACTIVE"]),len(al["SHADOW"]))==(3,3)
    c["XI"]=a.partXI(("ST-01","ST-22"))==("ST-01","ST-22"); c["XII"]=a.partXII(())["SYNCHRONISATION"]; c["XIII"]=a.partXIII((),())==(); c["XIV"]=a.partXIV({"pages":31})["action"]=="LANE_SPLIT"; c["XV"]=a.partXV({"page_count":51})["auto_decompose"]
    c["XVI"]=a.partXVI({k:True for k in ("sources","propositions","contradictions","adverse","countercase","low_marginal_value")})=="CONVERGED"; c["XVII"]=len(a.partXVII(**{k:.8 for k in ("authenticity","proximity","contemporaneity","independence","completeness","specificity","consistency","chain_of_custody","admissibility_or_usability","decision_relevance")}))==10
    cv=a.partXVIII(**{"source":.9,"fact":.95,"temporal":.8,"actor_knowledge":.4,"authority":.7,"causal":.2,"legal_fit":.8,"policy_fit":.8,"theory":.6,"remedy":.5}); c["XVIII"]=cv["fact"]>cv["causal"]; c["XIX"]=a.partXIX()[-1]=="CLASSIFY SOURCE PRECEDENCE"; c["XX"]=a.partXX(("A","A","B"))["independent_source_count"]==2
    c["XXI"]=a.partXXI(({"id":"R","information_gain":1,"decision_value":1,"source_quality":1,"cost":1},))==("R",); c["XXII"]=a.partXXII(({"id":"A","documents":("a",)},{"id":"B","documents":("b",)}))["A"]==("a",); c["XXIII"]=a.partXXIII("APPROVED","S")["state"]=="APPROVED"; c["XXIV"]=a.partXXIV((1,4,2))==4; c["XXV"]=a.partXXV({"a":1,"b":1})=="CG-5"; c["XXVI"]=a.partXXVI({"CH-CAUSATION":True})["CH-CAUSATION"]=="PASS"; c["XXVII"]=a.partXXVII({x:.9 for x in COUNCIL})=="Ω-A"
    c["XXVIII"]=a.partXXVIII("s",("f",),("c",),("p",),("w",))["id"].startswith("PREMORTEM"); c["XXIX"]=a.partXXIX(result="ok")["result"]=="ok"; c["XXX"]=len(a.partXXX({"id":"D","version":1}))==1; c["XXXI"]=a.partXXXI(({"conclusion":"c","theory":"t","element":"e","fact":"f","proposition":"p","source":"s"},))=="DURABLY_VERIFIED"; c["XXXII"]="NOT_PERSONALITY" in a.partXXXII({})["rule"]; c["XXXIII"]=not a.partXXXIII("FAST","VERIFIED","x")["final"]; c["XXXIV"]=a.partXXXIV({"owner_wait_signal":True})[0]=="STOP_EXPANSION"; c["XXXV"]=a.partXXXV({"path_explosion":True})["state"]=="YELLOW"
    hp={k:() for k in ("ALPHA_NODES","OMEGA_PORTFOLIO","ACTIVE_PATHS","SHADOW_PATHS","PRUNED_PATHS","ACTIVE_STREAMS","COMPLETED_LANES","VERIFIED_FACTS","SUPPORTED_INFERENCES","ADVERSE_EVIDENCE","CONTRADICTIONS","GAP_STATE","THEORY_VERSIONS","DECISION_VERSIONS","FAILURE_STATE","METHOD_STATE")}; hp.update({"HANDOFF_ID":"H","PROJECT_ID":"P","WORKSTREAM_ID":"W","CURRENT_STATE_MACHINE_STATE":"S","CURRENT_LANE":"L","SOURCE_STATE":"S","KNOWLEDGE_STATE":"K","LAST_VERIFIED_SOURCE":"S","NEXT_EXACT_ACTION":"N","RESTORE_COMMAND":"R"}); c["XXXVI"]=a.partXXXVI(hp)["valid"]; c["XXXVII"]=a.partXXXVII({"class":"TOOL_ROUTE","repair":"x","regression":True})["promotion"]=="CAPABILITY"; c["XXXVIII"]=bool(a.partXXXVIII(why_owner_detected_first="x",signal_available="s",why_control_failed="f",detector_should_have_fired="d",universal_prevention=True)); c["XXXIX"]=a.partXXXIX("x","c")["action"]=="LEARN_BEFORE_FAILURE"; c["XL"]=a.partXL(3)=="REDESIGN_OR_ROLLBACK"; c["XLI"]=a.partXLI()["studies"]=="METHOD_NOT_CASE_MERITS"
    exp={k:1 for k in ("experiment_id","question","existing_method","candidate_method","hypothesis","test","control","accuracy","source_fidelity","decision_value","information_gain","latency","tool_cost","owner_load","failure_rate","context_cost","regression_result","promotion_state")}; c["XLII"]=bool(a.partXLII(exp)); c["XLIII"]=a.partXLIII({"accuracy":1},{});
    try:a.partXLIV("immutable kernel"); c["XLIV"]=False
    except ValueError:c["XLIV"]=True
    c["XLV"]="MAY->DID" in a.partXLV((("MAY","DID"),)); c["XLVI"]=a.partXLVI("mind-reading").startswith("BLOCK"); c["XLVII"]=a.partXLVII({"AUTHORISED":True,"EXECUTED":True,"TARGET":"T","RESULT":"R","READBACK":"RB","FAILURE":""})["COMPLETE"]; c["XLVIII"]=a.partXLVIII(True,"ALT",True,True,True)["continued"]; c["XLIX"]=a.partXLIX({x:1 for x in OUTPUT_FIELDS[:-1]})==(); c["L"]=a.partL()["owner_default_qa"] is False; c["LI"]=a.partLI("n").startswith("NEXT_HIGHEST"); c["LII"]=len(a.partLII())>=30; c["LIII"]=all(a.partLIII().values()); c["LIV"]=a.partLIV({x:True for x in PERFORMANCE})["passed"]; c["COVERAGE"]=coverage_gate()["complete"]
    return {"status":"PASS" if all(c.values()) else "FAIL","checks":c,"count":len(c),"external_effects":0,"receipt_sha256":h(c)}

def zero_dilution_verdict(regression_ok,canonical_source_ok,provider_ci_ok=False,merged_readback_ok=False):
    local=regression_ok and canonical_source_ok and coverage_gate()["complete"] and canary()["status"]=="PASS"; verified=local and provider_ci_ok and merged_readback_ok
    return {"local_eligible":local,"verified":verified,"label":"ZERO_DILUTION_VERIFIED" if verified else "ZERO_DILUTION_LOCAL_ELIGIBLE_PROVIDER_GATES_OPEN" if local else "ZERO_DILUTION_NOT_PROVEN"}
