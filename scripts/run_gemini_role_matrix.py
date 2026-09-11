from __future__ import annotations
import concurrent.futures
import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "governance/fuse_gemini_role_matrix_request_v1.json").read_text(encoding="utf-8"))
OUT = Path(os.environ.get("ROLE_MATRIX_OUT", "/tmp/fuse-gemini-role-matrix"))
OUT.mkdir(parents=True, exist_ok=True)

ROLE_CASES = {
    "ALPHA_OMEGA_REASONER": {
        "objective": "Choose the strongest next action without changing the mission.",
        "input": {"routes":[{"id":"A","proof":0.9,"closure":0.8},{"id":"B","proof":0.5,"closure":0.95}],"hard_gate":"proof>=0.8"},
        "schema": {"decision":"string","assumptions":["string"],"risks":["string"],"next_action":"string","confidence":"number_0_to_1"}
    },
    "CFBE_CRITIC": {
        "objective": "Critique a candidate against a frozen benchmark.",
        "input": {"candidate":{"latency_ms":800,"quality":0.82},"incumbent":{"latency_ms":1200,"quality":0.84},"rule":"quality must not regress >0.01"},
        "schema": {"strengths":["string"],"defects":["string"],"benchmark_gaps":["string"],"verdict":"PASS|CHALLENGE|REJECT|HOLD"}
    },
    "CREATIVE_BRIEF_COMPILER": {
        "objective": "Compile a synthetic creative request into an editable brief.",
        "input": {"request":"Create a 6-second original cinematic reveal of a colossal floating observatory above an ocean at sunrise.","audience":"science-fantasy viewers","rights":"original"},
        "schema": {"objective":"string","audience":"string","mood":["string"],"deliverables":["string"],"constraints":["string"],"success_criteria":["string"]}
    },
    "DESIGNIR_VALIDATOR": {
        "objective": "Validate the synthetic DesignIR.",
        "input": {"design_id":"D1","mission_id":"MISSION-FCC-GEMINI-PORTABLE-REASONING-V1","medium":"VIDEO","objective":"6-second reveal","graph_node_refs":["world","camera","observatory"],"output_spec":{"duration_s":6,"fps":24}},
        "schema": {"valid":"boolean","violations":["string"],"missing_fields":["string"],"repair_actions":["string"]}
    },
    "ROUTE_RANKER": {
        "objective": "Rank only the supplied pre-qualified rendering routes.",
        "input": {"routes":[{"route_id":"local","quality":0.6,"latency":0.9,"eligible":True},{"route_id":"gpu","quality":0.9,"latency":0.6,"eligible":True}],"rule":"never rank an ineligible route"},
        "schema": {"ranking":[{"route_id":"string","score":"number_0_to_1","reason":"string"}],"winner":"route_id"}
    },
    "STORYBOARD_CONTINUITY_CRITIC": {
        "objective": "Critique continuity of a synthetic two-shot storyboard.",
        "input": {"shots":[{"id":"S1","sun":"left","observatory":"far","camera":"wide"},{"id":"S2","sun":"right","observatory":"near","camera":"medium"}],"continuity_rule":"sun direction should remain stable unless motivated"},
        "schema": {"continuity_score":"number_0_to_1","issues":["string"],"shot_notes":["string"]}
    },
    "PROVENANCE_ANALYST": {
        "objective": "Classify synthetic provenance completeness.",
        "input": {"asset":{"source":"original","recipe_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","model_id":"gemini-2.5-flash","output_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},"missing":["provider_request_id"]},
        "schema": {"provenance_state":"VERIFIED|PARTIAL|HELD","missing_evidence":["string"],"risk_flags":["string"]}
    },
    "CHALLENGER_JUDGE": {
        "objective": "Judge incumbent A versus challenger B under frozen criteria.",
        "input": {"criteria":["quality","latency","editability"],"A":{"quality":0.82,"latency":0.55,"editability":0.8},"B":{"quality":0.9,"latency":0.72,"editability":0.86},"hard_rule":"no promotion if any required criterion regresses >0.1"},
        "schema": {"winner":"A|B|TIE|HOLD","criteria_scores":{"A":{"criterion":"number_0_to_1"},"B":{"criterion":"number_0_to_1"}},"regressions":["string"],"promotion":"PROMOTE|HOLD|REJECT"}
    },
}

SYSTEM_RULES = [
    "Return JSON only.",
    "Do not reveal hidden chain-of-thought. Return concise decision rationale only through requested fields.",
    "Do not invent provider authority, source evidence, eligibility, approval or completion.",
    "Evidence in INPUT_JSON outranks model confidence.",
    "This role cannot perform external effects and cannot promote itself.",
    "If evidence is insufficient, use HOLD/PARTIAL where the schema permits it."
]

def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def stable(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",",":"), ensure_ascii=False)

def http_json(url, *, payload, token, timeout=90):
    data = json.dumps(payload, separators=(",",":")).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type":"application/json","Authorization":f"Bearer {token}"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8","replace")
            body = json.loads(raw) if raw else {}
            headers = {k.lower():v for k,v in response.headers.items()}
            return int(response.status), body, headers, time.perf_counter()-started
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8","replace")
        try: body = json.loads(raw) if raw else {}
        except Exception: body = {"raw_sha256":sha256_bytes(raw.encode())}
        return int(exc.code), body, {k.lower():v for k,v in exc.headers.items()}, time.perf_counter()-started

def prompt_for(role, case):
    return "\n".join([
        f"ROLE={role}",
        f"OBJECTIVE={case['objective']}",
        *[f"RULE={x}" for x in SYSTEM_RULES],
        "OUTPUT_SHAPE=" + stable(case["schema"]),
        "INPUT_JSON=" + stable(case["input"]),
    ])

def validate_shape(role, value):
    if not isinstance(value, dict):
        raise ValueError("OUTPUT_NOT_OBJECT")
    required = {
        "ALPHA_OMEGA_REASONER":["decision","assumptions","risks","next_action","confidence"],
        "CFBE_CRITIC":["strengths","defects","benchmark_gaps","verdict"],
        "CREATIVE_BRIEF_COMPILER":["objective","audience","mood","deliverables","constraints","success_criteria"],
        "DESIGNIR_VALIDATOR":["valid","violations","missing_fields","repair_actions"],
        "ROUTE_RANKER":["ranking","winner"],
        "STORYBOARD_CONTINUITY_CRITIC":["continuity_score","issues","shot_notes"],
        "PROVENANCE_ANALYST":["provenance_state","missing_evidence","risk_flags"],
        "CHALLENGER_JUDGE":["winner","criteria_scores","regressions","promotion"],
    }[role]
    missing=[k for k in required if k not in value]
    if missing:
        raise ValueError("MISSING_KEYS:" + ",".join(missing))

def invoke(role, token):
    case = ROLE_CASES[role]
    prompt = prompt_for(role, case)
    endpoint = "https://aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/publishers/google/models/{model}:generateContent".format(
        project=CONTRACT["project_id"], location=CONTRACT["location"], model=CONTRACT["model"])
    payload = {
        "contents":[{"role":"user","parts":[{"text":prompt}]}],
        "generationConfig":{"temperature":0,"candidateCount":1,"maxOutputTokens":512,"responseMimeType":"application/json"},
    }
    status, body, headers, elapsed = http_json(endpoint,payload=payload,token=token)
    parts = ((((body.get("candidates") or [{}])[0].get("content") or {}).get("parts")) or []) if isinstance(body,dict) else []
    text = "".join(str(p.get("text","")) for p in parts).strip()
    parsed = None
    shape_ok = False
    shape_error = None
    if status == 200 and text:
        try:
            parsed = json.loads(text)
            validate_shape(role, parsed)
            shape_ok = True
        except Exception as exc:
            shape_error = str(exc)
    usage = body.get("usageMetadata") or {} if isinstance(body,dict) else {}
    request_id = (body.get("responseId") if isinstance(body,dict) else None) or headers.get("x-request-id") or headers.get("x-goog-request-id")
    receipt = {
        "schema":"FUSE_GEMINI_ROLE_RECEIPT_V1",
        "task_id":f"FCC-GEMINI-ROLE-{role}",
        "role":role,
        "source_sha":os.environ.get("GITHUB_SHA"),
        "run_id":os.environ.get("GITHUB_RUN_ID"),
        "run_attempt":os.environ.get("GITHUB_RUN_ATTEMPT"),
        "provider":"GOOGLE_VERTEX_AI",
        "transport":"VERTEX_WIF_ADC",
        "model":CONTRACT["model"],
        "provider_model_version":body.get("modelVersion") if isinstance(body,dict) else None,
        "http_status":status,
        "provider_request_id":request_id,
        "input_sha256":sha256_bytes(stable(case["input"]).encode()),
        "prompt_sha256":sha256_bytes(prompt.encode()),
        "response_text_sha256":sha256_bytes(text.encode()) if text else None,
        "structured_output":parsed,
        "structured_output_valid":shape_ok,
        "shape_error":shape_error,
        "usage_metadata":{k:usage.get(k) for k in ("promptTokenCount","candidatesTokenCount","totalTokenCount","cachedContentTokenCount") if k in usage},
        "latency_ms":round(elapsed*1000,3),
        "case_data_processed":False,
        "provider_mutation_performed":False,
        "iam_mutation_performed":False,
        "secret_mutation_performed":False,
        "deployment_performed":False,
        "traffic_change_performed":False,
        "semantic_verified":status==200 and bool(request_id) and shape_ok,
    }
    raw = dict(receipt)
    receipt["receipt_sha256"] = sha256_bytes(stable(raw).encode())
    (OUT/f"{role}.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return receipt

def main():
    if CONTRACT["case_data_allowed"] or CONTRACT["provider_mutation_allowed"] or CONTRACT["iam_mutation_allowed"] or CONTRACT["secret_mutation_allowed"]:
        raise SystemExit("unsafe contract")
    token = subprocess.check_output(["gcloud","auth","print-access-token"],text=True).strip()
    if not token:
        raise SystemExit("WIF/ADC access token unavailable")
    roles = CONTRACT["roles"]
    max_workers = min(int(CONTRACT["max_parallel_requests"]), len(roles))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(invoke, role, token): role for role in roles}
        receipts = [f.result() for f in concurrent.futures.as_completed(futures)]
    receipts.sort(key=lambda x: x["role"])
    verified = sum(bool(r["semantic_verified"]) for r in receipts)
    summary = {
        "schema":"FUSE_GEMINI_ROLE_MATRIX_SUMMARY_V1",
        "provider":"GOOGLE_VERTEX_AI",
        "transport":"VERTEX_WIF_ADC",
        "model":CONTRACT["model"],
        "role_count":len(receipts),
        "verified_count":verified,
        "portfolio_state":"ROLE_PORTFOLIO_VERIFIED" if verified==len(receipts) else "ROLE_PORTFOLIO_PARTIAL",
        "max_parallel_requests":max_workers,
        "case_data_processed":False,
        "provider_mutation_performed":False,
        "roles":[{"role":r["role"],"semantic_verified":r["semantic_verified"],"provider_request_id":r["provider_request_id"],"latency_ms":r["latency_ms"],"receipt_sha256":r["receipt_sha256"]} for r in receipts],
    }
    summary["summary_sha256"] = sha256_bytes(stable(summary).encode())
    (OUT/"SUMMARY.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(summary,sort_keys=True))
    if verified != len(receipts):
        raise SystemExit("role portfolio partial")

if __name__ == "__main__":
    main()
