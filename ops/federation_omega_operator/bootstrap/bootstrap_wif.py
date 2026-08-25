#!/usr/bin/env python3
"""Idempotent keyless GitHub WIF bootstrap for Federation Omega."""
from __future__ import annotations
import argparse, hashlib, json, os, pathlib, subprocess, sys
REQUIRED_KEYS={"projectId","projectNumber","poolId","providerId","issuerUri","repositoryId","repositoryOwnerId","allowedRef","allowedEvent","deployerServiceAccountId","operatorServiceAccount","sourceSha256","embeddedRepairSha256","manifestSha256"}
PROJECT_ROLES=("roles/run.admin","roles/cloudbuild.builds.editor","roles/artifactregistry.writer","roles/serviceusage.serviceUsageConsumer")
APIS=("iam.googleapis.com","iamcredentials.googleapis.com","sts.googleapis.com","run.googleapis.com","cloudbuild.googleapis.com","artifactregistry.googleapis.com")
class BootstrapError(RuntimeError): pass
def load_config(path:pathlib.Path)->dict:
    value=json.loads(path.read_text(encoding="utf-8")); missing=sorted(REQUIRED_KEYS-set(value))
    if missing: raise BootstrapError("missing config keys: "+",".join(missing))
    for key in ("projectNumber","repositoryId","repositoryOwnerId"):
        if not str(value[key]).isdigit(): raise BootstrapError(f"{key} must be numeric")
    for key in ("sourceSha256","embeddedRepairSha256","manifestSha256"):
        if len(value[key])!=64 or any(c not in "0123456789abcdef" for c in value[key]): raise BootstrapError(f"{key} must be lowercase SHA-256")
    if value["allowedRef"]!="refs/heads/main" or value["allowedEvent"]!="workflow_dispatch": raise BootstrapError("scope must remain main/workflow_dispatch")
    return value
def condition(c:dict)->str:
    return " && ".join((f"assertion.repository_id=='{c['repositoryId']}'",f"assertion.repository_owner_id=='{c['repositoryOwnerId']}'",f"assertion.ref=='{c['allowedRef']}'",f"assertion.event_name=='{c['allowedEvent']}'"))
def mapping()->str:
    return ",".join(("google.subject=assertion.sub","attribute.repository_id=assertion.repository_id","attribute.repository_owner_id=assertion.repository_owner_id","attribute.ref=assertion.ref","attribute.event_name=assertion.event_name"))
def verify_provider(c:dict,value:dict)->None:
    expected_mapping={item.split("=",1)[0]:item.split("=",1)[1] for item in mapping().split(",")}
    checks={
      "issuerUri":value.get("oidc",{}).get("issuerUri")==c["issuerUri"],
      "attributeCondition":value.get("attributeCondition")==condition(c),
      "attributeMapping":value.get("attributeMapping")==expected_mapping,
      "state":value.get("state") in (None,"ACTIVE"),
    }
    failed=sorted(key for key,valid in checks.items() if not valid)
    if failed: raise BootstrapError("existing provider drift: "+",".join(failed))
def commands(c:dict)->list[list[str]]:
    p=c["projectId"]; n=c["projectNumber"]; pool=c["poolId"]; provider=c["providerId"]; deployer=f"{c['deployerServiceAccountId']}@{p}.iam.gserviceaccount.com"; principal=f"principalSet://iam.googleapis.com/projects/{n}/locations/global/workloadIdentityPools/{pool}/attribute.repository_id/{c['repositoryId']}"
    out=[
      ["gcloud","services","enable",*APIS,"--project",p,"--quiet"],
      ["gcloud","iam","workload-identity-pools","create",pool,"--project",p,"--location","global","--display-name","Federation Omega GitHub","--quiet"],
      ["gcloud","iam","workload-identity-pools","providers","create-oidc",provider,"--project",p,"--location","global","--workload-identity-pool",pool,"--issuer-uri",c["issuerUri"],"--attribute-mapping",mapping(),"--attribute-condition",condition(c),"--quiet"],
      ["gcloud","iam","service-accounts","create",c["deployerServiceAccountId"],"--project",p,"--display-name","Federation Omega GitHub deployer","--quiet"]]
    for role in PROJECT_ROLES: out.append(["gcloud","projects","add-iam-policy-binding",p,"--member",f"serviceAccount:{deployer}","--role",role,"--condition=None","--quiet"])
    out += [
      ["gcloud","iam","service-accounts","add-iam-policy-binding",deployer,"--project",p,"--member",principal,"--role","roles/iam.workloadIdentityUser","--quiet"],
      ["gcloud","iam","service-accounts","add-iam-policy-binding",deployer,"--project",p,"--member",principal,"--role","roles/iam.serviceAccountOpenIdTokenCreator","--quiet"],
      ["gcloud","iam","service-accounts","add-iam-policy-binding",c["operatorServiceAccount"],"--project",p,"--member",f"serviceAccount:{deployer}","--role","roles/iam.serviceAccountUser","--quiet"]]
    return out
def present(args:list[str])->bool: return subprocess.run(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
def read_json(args:list[str])->dict:
    return json.loads(subprocess.check_output([*args,"--format=json"],text=True))
def run(c:dict,apply:bool)->dict:
    plan=commands(c); receipt={"schema":"FO_GITHUB_WIF_BOOTSTRAP_RECEIPT_V1","mode":"APPLY" if apply else "DRY_RUN","configSha256":hashlib.sha256(json.dumps(c,sort_keys=True,separators=(",",":")).encode()).hexdigest(),"condition":condition(c),"commandCount":len(plan),"executed":[]}
    if not apply: receipt["plan"]=[cmd[:4]+["…"] for cmd in plan]; return receipt
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and not present(["gcloud","auth","print-access-token"]): raise BootstrapError("trusted Google machine identity unavailable")
    for cmd in plan:
        if cmd[1:4]==["iam","workload-identity-pools","create"] and present(["gcloud","iam","workload-identity-pools","describe",c["poolId"],"--project",c["projectId"],"--location","global"]): receipt["executed"].append({"state":"REUSED","resource":"pool"}); continue
        if cmd[1:5]==["iam","workload-identity-pools","providers","create-oidc"] and present(["gcloud","iam","workload-identity-pools","providers","describe",c["providerId"],"--project",c["projectId"],"--location","global","--workload-identity-pool",c["poolId"]]):
            verify_provider(c,read_json(["gcloud","iam","workload-identity-pools","providers","describe",c["providerId"],"--project",c["projectId"],"--location","global","--workload-identity-pool",c["poolId"]])); receipt["executed"].append({"state":"REUSED_VERIFIED","resource":"provider"}); continue
        if cmd[1:4]==["iam","service-accounts","create"] and present(["gcloud","iam","service-accounts","describe",f"{c['deployerServiceAccountId']}@{c['projectId']}.iam.gserviceaccount.com","--project",c["projectId"]]): receipt["executed"].append({"state":"REUSED","resource":"service-account"}); continue
        subprocess.run(cmd,check=True); receipt["executed"].append({"state":"APPLIED","command":cmd[1:3]})
    provider=read_json(["gcloud","iam","workload-identity-pools","providers","describe",c["providerId"],"--project",c["projectId"],"--location","global","--workload-identity-pool",c["poolId"]]); verify_provider(c,provider)
    receipt["readback"]={"provider":"VERIFIED","attributeCondition":condition(c),"deployerServiceAccount":f"{c['deployerServiceAccountId']}@{c['projectId']}.iam.gserviceaccount.com"}
    receipt["status"]="BOOTSTRAP_APPLIED_AND_VERIFIED"; return receipt
def main()->int:
    parser=argparse.ArgumentParser(); parser.add_argument("--config",required=True); parser.add_argument("--apply",action="store_true"); parser.add_argument("--out"); args=parser.parse_args()
    try:
        result=run(load_config(pathlib.Path(args.config)),args.apply); encoded=json.dumps(result,indent=2,sort_keys=True)
        if args.out: pathlib.Path(args.out).write_text(encoded+"\n",encoding="utf-8")
        print(encoded); return 0
    except (BootstrapError,subprocess.CalledProcessError,FileNotFoundError) as exc:
        print(json.dumps({"status":"FAIL_CLOSED","errorType":type(exc).__name__}),file=sys.stderr); return 2
if __name__=="__main__": raise SystemExit(main())
