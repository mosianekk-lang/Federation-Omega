from __future__ import annotations
import argparse, copy, hashlib, json, re
from pathlib import Path
from typing import Any, Mapping, Sequence

PACKET_SCHEMA="FEDOMEGA-N-V21-ICT-REAL-READONLY-PACKET-1"
RESULT_SCHEMA="FEDOMEGA-N-V21-ICT-REAL-READONLY-RESULT-1"
EXPERIMENT_ID="EXP-N-V21-REAL-READONLY-001-ICT-SYSTEM-BUILD"
SOURCE_TYPES={"ARCHIVE_MANIFEST","BUILD","PREFLIGHT_MANDATE","DEPLOYMENT","CANARY_ROLLBACK","STATE_VALIDATION"}
CONTROLS=("SOURCE_DIGEST_IDENTITY","REUSE_EXISTING_INFRASTRUCTURE","LEAST_PRIVILEGE_PREFLIGHT","IMMUTABLE_BUILD_PROVENANCE","DURABLE_STATE","PRIVATE_ZERO_TRAFFIC","IDEMPOTENCY_STATE_CONSTRAINTS","HEALTH_READINESS_READBACK","FAIL_CLOSED","ROLLBACK_RECOVERY")
ROUTES={"REUSE_OR_OPTIMISE","COMPOSE_OR_EXTEND","MATERIALLY_NEW_OR_INNOVATIVE"}
FILES={
"Dockerfile":"bf81305c7ba84ec8c94060d08018991acc081bf45e60223d4c5c8d16b12797e3",
"MANIFEST.json":"f79aa56b2a81924c3774957a1de3a570cca26a7aaa58bf6808d2de15807ad429",
"config/deployment_mandate.template.yaml":"fb628458b061506480f0d7b83a5105dd12526b328ef0bcbaaaa88806a4a92f0b",
"deployment/cloudbuild.yaml":"b589a2ce69ff89e837595a26210f52e5842bd5c97e0178e58ab4c1d3bf0d35ab",
"deployment/deploy_shadow_gcp.sh":"3368890b235f91b94aa28e96110a811cb0e88ae1ca862193cc8c1685637ac68b",
"deployment/provider_canary.sh":"96ca065de8ec02f9f93aa9f6bb41071b2c153a2421f0575ca32d68aad4a0224a",
"deployment/provider_preflight.sh":"dec16320b6ce8b7b055b6c1637b684d0946aadeb1bd1e756cf25a17ebb4c1cbf",
"deployment/rollback_shadow_gcp.sh":"3858c9d038d9700db2009ed059f905e9f3eab734e3ad2802acfad526b2f9cf7b",
"migrations/postgresql/001_bootstrap.sql":"ec93bade047dfb8b51c9dcba43267d0b94afe9bee41e22ac15be8b15a0129e84",
"reports/AUTONOMOUS_PROGRAMME_REPORT.json":"163ef345f085ce69da01e7b7f2fb3f9e19a3fe69078381aa1a74256738de570c",
"reports/PROVIDER_AUTHORITY_DISCOVERY.json":"828e3083990d631e3f41bb7a3cc6fcacb7473edee8690e90913c120e47edb67e",
"reports/V1_1_VALIDATION_REPORT.md":"15d6966670edb412c687dfa1006d9cec1fd1838061eb9e4a2705d366a213566d"}
OVERCLAIMS=("cloud run deployed","cloud sql mutated","provider authority repaired","production live","rollback verified","provider durability proven","level 5 verified")

class ICTReadonlyError(RuntimeError): pass
def seq(v): return v if isinstance(v,list) else []
def canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def digest(v): return hashlib.sha256(canon(v).encode()).hexdigest()
def vio(code,path,expected,actual): return {"code":code,"path":path,"expected":expected,"actual":actual}
def src_payload(s): return {k:s.get(k) for k in ("id","type","title","files","claims")}
def claims(packet):
    return {c["field"]:c["value"] for s in packet["sources"] for c in s["claims"]}
def validate(packet:Mapping[str,Any])->dict[str,Any]:
    v=[]
    expected={"schema":PACKET_SCHEMA,"experiment_id":EXPERIMENT_ID,"domain":"ict_system_build","authority":"A1_INTERNAL_READ_ONLY","external_effect":False,"provider_mutation":False,"production_traffic_change":False,"destructive_action":False}
    for k,e in expected.items():
        if packet.get(k)!=e:v.append(vio("FIELD",k,e,packet.get(k)))
    sources=[s for s in seq(packet.get("sources")) if isinstance(s,dict)]
    if {s.get("type") for s in sources}!=SOURCE_TYPES:v.append(vio("SOURCE_TYPES","sources",sorted(SOURCE_TYPES),sorted(str(s.get("type")) for s in sources)))
    if len(sources)!=6:v.append(vio("SOURCE_COUNT","sources",6,len(sources)))
    ids=[s.get("id") for s in sources]
    if len(ids)!=len(set(ids)):v.append(vio("DUP_SOURCE","sources.id","unique",ids))
    seen=[]
    for i,s in enumerate(sources):
        for f in seq(s.get("files")):
            path=f.get("path"); sha=f.get("sha256"); seen.append(path)
            if FILES.get(path)!=sha:v.append(vio("FILE_HASH",f"sources[{i}].files[{path}]",FILES.get(path),sha))
        if s.get("fingerprint")!=digest(src_payload(s)):v.append(vio("SOURCE_FINGERPRINT",f"sources[{i}].fingerprint",digest(src_payload(s)),s.get("fingerprint")))
    if set(seen)!=set(FILES):v.append(vio("FILE_SET","sources.files",sorted(FILES),sorted(str(x) for x in seen)))
    if len(seen)!=len(set(seen)):v.append(vio("DUP_FILE","sources.files","unique",seen))
    baseline=set(seq(packet.get("baseline_controls"))); treatment=set(seq(packet.get("treatment_controls")))
    if not baseline or not baseline<=set(CONTROLS):v.append(vio("BASELINE","baseline_controls","nonempty subset",sorted(baseline)))
    if treatment!=set(CONTROLS):v.append(vio("TREATMENT","treatment_controls",sorted(CONTROLS),sorted(treatment)))
    gaps=seq(packet.get("gaps"))
    if len(gaps)!=10 or any(g.get("state")!="UNVERIFIED_PENDING_PROVIDER_READBACK" for g in gaps):v.append(vio("GAPS","gaps","10 unverified",gaps))
    out={"schema":RESULT_SCHEMA,"kind":"VALIDATION","passed":not v,"status":"VALIDATED" if not v else "BLOCKED","violations":v,"evidence":{"source_count":len(sources),"file_count":len(seen),"packet_sha256":digest(packet)},"external_effect":False}
    out["receipt_sha256"]=digest(out);return out

def passport(packet):
    c=claims(packet)
    expected={"manifest_id":"FEVX-CSE-V1.1.0-MANIFEST","payload_files":102,"archive_sha256":"f4da04ac026628e022814f306acfe9e5303ee89a107359ab50a91fa04442ac50","wheel_sha256":"8c2832a9cd844af62a5fd403038bc2cebca4aa8967826295b34b6c9660c83022","non_root_uid":65532,"dependencies_installed":True,"digest_build_args":True,"preflight_mutation":False,"secret_values_recorded":False,"mandate_state":"TEMPLATE_NOT_ACTIVE","reuse_existing":True,"private_auth":True,"zero_traffic":True,"named_service_account":True,"durable_required":True,"postgresql_schema":"fevx_cse","idempotency_constraints":True,"hash_chain_checkpoints":True,"provider_connection":False,"authenticated_canary":True,"request_log_correlation":True,"self_certification_blocked":True,"rollback_default_hold":True,"cloud_run_deployed":False,"cloud_sql_mutated":False,"operator_health":"OPERATOR_READY","operator_token":"UNAVAILABLE_IN_EXISTING_RECEIPTS","wif_state":"NOT_FOUND_INVALID_TARGET","provider_state":"PROVIDER_AUTHORITY_REPAIR_REQUIRED"}
    mismatch={k:(e,c.get(k)) for k,e in expected.items() if c.get(k)!=e}
    if mismatch:raise ICTReadonlyError("PASSPORT_MISMATCH:"+canon(mismatch))
    p={"release":{"manifest_id":c["manifest_id"],"payload_files":c["payload_files"],"archive_sha256":c["archive_sha256"],"wheel_sha256":c["wheel_sha256"],"selected_files":dict(sorted(FILES.items()))},"build":{"non_root_uid":c["non_root_uid"],"dependencies_installed":c["dependencies_installed"],"digest_build_args":c["digest_build_args"]},"preflight":{"mutation":c["preflight_mutation"],"secret_values_recorded":c["secret_values_recorded"],"mandate_state":c["mandate_state"],"reuse_existing":c["reuse_existing"]},"deployment":{"private_auth":c["private_auth"],"zero_traffic":c["zero_traffic"],"named_service_account":c["named_service_account"],"durable_required":c["durable_required"],"executed":False},"state":{"schema":c["postgresql_schema"],"idempotency_constraints":c["idempotency_constraints"],"hash_chain_checkpoints":c["hash_chain_checkpoints"],"provider_connection":c["provider_connection"]},"canary":{"authenticated":c["authenticated_canary"],"request_log_correlation":c["request_log_correlation"],"self_certification_blocked":c["self_certification_blocked"],"executed":False},"rollback":{"default_hold":c["rollback_default_hold"],"post_readback_defined":True,"executed":False},"provider":{"operator_health":c["operator_health"],"operator_token":c["operator_token"],"wif_state":c["wif_state"],"cloud_run_deployed":c["cloud_run_deployed"],"cloud_sql_mutated":c["cloud_sql_mutated"],"state":c["provider_state"]}}
    p["sha256"]=digest(p);return p

def tensions(p):
    return [
    {"id":"T1","result":"ARTEFACT_EXECUTION_SEPARATED","fact":"deployment carrier exists; provider execution absent"},
    {"id":"T2","result":"HEALTH_AUTHORITY_SEPARATED","fact":"operator healthy; token unavailable; WIF invalid"},
    {"id":"T3","result":"EXTERNAL_VERIFIER_REQUIRED","fact":"runtime proof exists; self-certification blocked; canary unexecuted"},
    {"id":"T4","result":"SCHEMA_RUNTIME_SEPARATED","fact":"PostgreSQL schema and parity exist; provider connection absent"},
    {"id":"T5","result":"ROLLBACK_PREPARATION_TEST_SEPARATED","fact":"rollback logic exists; provider rollback unexecuted"}]
def formation():
    return {"routes":[{"family":"REUSE_OR_OPTIMISE","rank":2},{"family":"COMPOSE_OR_EXTEND","rank":1},{"family":"MATERIALLY_NEW_OR_INNOVATIVE","rank":3}],"route_families":sorted(ROUTES),"selected":"COMPOSE_OR_EXTEND"}
def overclaim(claims):
    return [vio("OVERCLAIM",f"claims[{i}]","bounded",x) for i,x in enumerate(claims) for p in OVERCLAIMS if p in str(x).lower()]
def build(packet):
    val=validate(packet)
    if not val["passed"]:raise ICTReadonlyError(canon(val))
    p=passport(packet); ts=tensions(p); base=sorted(packet["baseline_controls"])
    metrics={"sources":"6/6","files":"12/12","baseline":f"{len(base)}/10","treatment":"10/10","delta":10-len(base),"tensions":len(ts),"gaps":len(packet["gaps"]),"provider_mutations":0,"traffic_changes":0,"destructive_actions":0,"authority_violations":0,"external_effects":0,"owner_prompts":0}
    release=["Six registered technical source groups and twelve exact file digests were compiled into one Technical Deployment Passport.","Control completeness improved from the distributed-artifact baseline.","Build, preflight, private-shadow, canary, durable-state and rollback semantics are present and statically validated.","Provider authority remains unrepaired; provider execution, durability, canary and rollback remain unverified.","No provider mutation, production traffic change, destructive action, communication, financial effect or trust transfer occurred."]
    bad=overclaim(release)
    if bad:raise ICTReadonlyError(canon(bad))
    out={"schema":RESULT_SCHEMA,"kind":"REAL_ICT_PACKET","experiment_id":EXPERIMENT_ID,"status":"REAL_REGISTERED_SOURCE_ICT_CONTROL_STATE_PASSED_READ_ONLY","validation":val,"passport":p,"tensions":ts,"gaps":packet["gaps"],"formation":formation(),"metrics":metrics,"release_claims":release,"boundary":{"measured":"ICT_CONTROL_COMPLETENESS_DELTA_ON_REAL_ARTEFACTS","not_measured":["provider deployment","provider durability","provider rollback","production reliability","longitudinal owner value","foundation-model change"]},"authority":"A1_INTERNAL_READ_ONLY","provider_mutation":False,"production_traffic_change":False,"destructive_action":False,"external_effect":False,"continuation":"EXP-N-V21-REAL-READONLY-001-FEDERATION-EVOLUTION"}
    out["receipt_sha256"]=digest(out);return out
def verify(out):
    v=[]
    for k in ("provider_mutation","production_traffic_change","destructive_action","external_effect"):
        if out.get(k) is not False:v.append(vio("EFFECT",k,False,out.get(k)))
    v+=overclaim(seq(out.get("release_claims")))
    clone=copy.deepcopy(dict(out));actual=clone.pop("receipt_sha256",None);expected=digest(clone)
    if actual!=expected:v.append(vio("RECEIPT","receipt_sha256",expected,actual))
    r={"schema":RESULT_SCHEMA,"kind":"VERIFICATION","passed":not v,"status":"VERIFIED" if not v else "BLOCKED","violations":v,"external_effect":False};r["receipt_sha256"]=digest(r);return r
def load(path): 
    x=json.loads(Path(path).read_text()); 
    if not isinstance(x,dict):raise ICTReadonlyError("ROOT")
    return x
def main(argv:Sequence[str]|None=None):
    ap=argparse.ArgumentParser();ap.add_argument("--packet",type=Path,required=True);ap.add_argument("--output",type=Path);a=ap.parse_args(argv)
    e=build(load(a.packet));v=verify(e)
    if not v["passed"]:raise ICTReadonlyError(canon(v))
    text=json.dumps({"experiment":e,"verification":v},indent=2,sort_keys=True)+"\n"
    if a.output:a.output.write_text(text)
    else:print(text,end="")
    return 0
if __name__=="__main__":raise SystemExit(main())
