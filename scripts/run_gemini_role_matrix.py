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
CONTRACT = json.loads(
    (ROOT / "governance/fuse_gemini_role_matrix_request_v1.json").read_text(encoding="utf-8")
)
OUT = Path(os.environ.get("ROLE_MATRIX_OUT", "/tmp/fuse-gemini-role-matrix"))
OUT.mkdir(parents=True, exist_ok=True)

CASES = {
    "ALPHA_OMEGA_REASONER": (
        "Choose the strongest next action without changing the mission.",
        {
            "routes": [
                {"id": "A", "proof": 0.9, "closure": 0.8},
                {"id": "B", "proof": 0.5, "closure": 0.95},
            ],
            "hard_gate": "proof>=0.8",
        },
        ["decision", "assumptions", "risks", "next_action", "confidence"],
    ),
    "CFBE_CRITIC": (
        "Critique a candidate against a frozen benchmark.",
        {
            "candidate": {"latency_ms": 800, "quality": 0.82},
            "incumbent": {"latency_ms": 1200, "quality": 0.84},
            "rule": "quality must not regress >0.01",
        },
        ["strengths", "defects", "benchmark_gaps", "verdict"],
    ),
    "CREATIVE_BRIEF_COMPILER": (
        "Compile a synthetic creative request into an editable brief.",
        {
            "request": "Create a 6-second original cinematic reveal of a colossal floating observatory above an ocean at sunrise.",
            "audience": "science-fantasy viewers",
            "rights": "original",
        },
        ["objective", "audience", "mood", "deliverables", "constraints", "success_criteria"],
    ),
    "DESIGNIR_VALIDATOR": (
        "Validate the synthetic DesignIR.",
        {
            "design_id": "D1",
            "mission_id": "MISSION-FCC-GEMINI-PORTABLE-REASONING-V1",
            "medium": "VIDEO",
            "objective": "6-second reveal",
            "graph_node_refs": ["world", "camera", "observatory"],
            "output_spec": {"duration_s": 6, "fps": 24},
        },
        ["valid", "violations", "missing_fields", "repair_actions"],
    ),
    "ROUTE_RANKER": (
        "Rank only the supplied pre-qualified rendering routes.",
        {
            "routes": [
                {"route_id": "local", "quality": 0.6, "latency": 0.9, "eligible": True},
                {"route_id": "gpu", "quality": 0.9, "latency": 0.6, "eligible": True},
            ],
            "rule": "never rank an ineligible route",
        },
        ["ranking", "winner"],
    ),
    "STORYBOARD_CONTINUITY_CRITIC": (
        "Critique continuity of a synthetic two-shot storyboard.",
        {
            "shots": [
                {"id": "S1", "sun": "left", "observatory": "far", "camera": "wide"},
                {"id": "S2", "sun": "right", "observatory": "near", "camera": "medium"},
            ],
            "continuity_rule": "sun direction should remain stable unless motivated",
        },
        ["continuity_score", "issues", "shot_notes"],
    ),
    "PROVENANCE_ANALYST": (
        "Classify synthetic provenance completeness.",
        {
            "asset": {
                "source": "original",
                "recipe_sha256": "a" * 64,
                "model_id": "gemini-2.5-flash",
                "output_sha256": "b" * 64,
            },
            "missing": ["provider_request_id"],
        },
        ["provenance_state", "missing_evidence", "risk_flags"],
    ),
    "CHALLENGER_JUDGE": (
        "Judge incumbent A versus challenger B under frozen criteria.",
        {
            "criteria": ["quality", "latency", "editability"],
            "A": {"quality": 0.82, "latency": 0.55, "editability": 0.8},
            "B": {"quality": 0.9, "latency": 0.72, "editability": 0.86},
            "hard_rule": "no promotion if any required criterion regresses >0.1",
        },
        ["winner", "criteria_scores", "regressions", "promotion"],
    ),
}

RULES = [
    "Return one JSON object only.",
    "Do not reveal hidden chain-of-thought; return concise decision rationale only in requested fields.",
    "Do not invent provider authority, source evidence, eligibility, approval or completion.",
    "Evidence in INPUT_JSON outranks model confidence.",
    "This role cannot perform external effects and cannot promote itself.",
    "Use HOLD or PARTIAL where applicable if evidence is insufficient.",
    "Keep JSON compact: every free-text string <=160 characters and every list <=4 items unless INPUT_JSON forces more.",
]


def stable(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(value):
    payload = value if isinstance(value, bytes) else str(value).encode()
    return hashlib.sha256(payload).hexdigest()


def post(url, payload, token):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, separators=(",", ":")).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            raw = response.read().decode("utf-8", "replace")
            return (
                int(response.status),
                json.loads(raw) if raw else {},
                {k.lower(): v for k, v in response.headers.items()},
                (time.perf_counter() - started) * 1000,
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            body = json.loads(raw) if raw else {}
        except Exception:
            body = {"raw_sha256": sha(raw)}
        return (
            int(exc.code),
            body,
            {k.lower(): v for k, v in exc.headers.items()},
            (time.perf_counter() - started) * 1000,
        )


def invoke(role, token):
    objective, data, required = CASES[role]
    prompt = "\n".join(
        [
            f"ROLE={role}",
            f"OBJECTIVE={objective}",
            *[f"RULE={rule}" for rule in RULES],
            f"REQUIRED_KEYS={','.join(required)}",
            "INPUT_JSON=" + stable(data),
        ]
    )
    endpoint = (
        "https://aiplatform.googleapis.com/v1/projects/"
        f"{CONTRACT['project_id']}/locations/{CONTRACT['location']}/publishers/google/models/"
        f"{CONTRACT['model']}:generateContent"
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "candidateCount": 1,
            "maxOutputTokens": 768,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    status, body, headers, latency = post(endpoint, payload, token)
    candidates = (body.get("candidates") or [{}]) if isinstance(body, dict) else [{}]
    candidate = candidates[0] if candidates else {}
    parts = ((candidate.get("content") or {}).get("parts") or []) if isinstance(candidate, dict) else []
    text = "".join(str(part.get("text", "")) for part in parts).strip()
    finish_reason = candidate.get("finishReason") if isinstance(candidate, dict) else None
    parsed = None
    error = None
    try:
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("OUTPUT_NOT_OBJECT")
        missing = [key for key in required if key not in parsed]
        if missing:
            raise ValueError("MISSING_KEYS:" + ",".join(missing))
    except Exception as exc:
        error = str(exc)
        if finish_reason == "MAX_TOKENS":
            error = "MAX_TOKENS:" + error
    usage = (body.get("usageMetadata") or {}) if isinstance(body, dict) else {}
    request_id = (
        (body.get("responseId") if isinstance(body, dict) else None)
        or headers.get("x-request-id")
        or headers.get("x-goog-request-id")
    )
    normal_finish = finish_reason in (None, "STOP")
    receipt = {
        "schema": "FUSE_GEMINI_ROLE_RECEIPT_V1",
        "task_id": f"FCC-GEMINI-ROLE-{role}",
        "role": role,
        "source_sha": os.environ.get("GITHUB_SHA"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "provider": "GOOGLE_VERTEX_AI",
        "transport": "VERTEX_WIF_ADC",
        "model": CONTRACT["model"],
        "provider_model_version": body.get("modelVersion") if isinstance(body, dict) else None,
        "http_status": status,
        "provider_request_id": request_id,
        "input_sha256": sha(stable(data)),
        "prompt_sha256": sha(prompt),
        "response_text_sha256": sha(text) if text else None,
        "structured_output": parsed,
        "structured_output_valid": error is None,
        "shape_error": error,
        "finish_reason": finish_reason,
        "usage_metadata": {
            key: usage.get(key)
            for key in (
                "promptTokenCount",
                "candidatesTokenCount",
                "thoughtsTokenCount",
                "totalTokenCount",
                "cachedContentTokenCount",
            )
            if key in usage
        },
        "latency_ms": round(latency, 3),
        "case_data_processed": False,
        "provider_mutation_performed": False,
        "iam_mutation_performed": False,
        "secret_mutation_performed": False,
        "deployment_performed": False,
        "traffic_change_performed": False,
        "semantic_verified": status == 200
        and bool(request_id)
        and error is None
        and normal_finish,
    }
    receipt["receipt_sha256"] = sha(stable(receipt))
    (OUT / f"{role}.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def main():
    for key in (
        "case_data_allowed",
        "provider_mutation_allowed",
        "iam_mutation_allowed",
        "secret_mutation_allowed",
        "deployment_allowed",
        "traffic_change_allowed",
        "external_communication_allowed",
    ):
        if CONTRACT[key]:
            raise SystemExit(f"unsafe contract:{key}")
    token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
    roles = CONTRACT["roles"]
    started = time.perf_counter()
    workers = min(int(CONTRACT["max_parallel_requests"]), len(roles))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        receipts = list(pool.map(lambda role: invoke(role, token), roles))
    verified = sum(bool(receipt["semantic_verified"]) for receipt in receipts)
    summary = {
        "schema": "FUSE_GEMINI_ROLE_MATRIX_SUMMARY_V1",
        "provider": "GOOGLE_VERTEX_AI",
        "transport": "VERTEX_WIF_ADC",
        "model": CONTRACT["model"],
        "role_count": len(receipts),
        "verified_count": verified,
        "portfolio_state": "ROLE_PORTFOLIO_VERIFIED"
        if verified == len(receipts)
        else "ROLE_PORTFOLIO_PARTIAL",
        "max_parallel_requests": workers,
        "wall_clock_ms": round((time.perf_counter() - started) * 1000, 3),
        "case_data_processed": False,
        "provider_mutation_performed": False,
        "roles": [
            {
                "role": receipt["role"],
                "semantic_verified": receipt["semantic_verified"],
                "provider_request_id": receipt["provider_request_id"],
                "latency_ms": receipt["latency_ms"],
                "finish_reason": receipt["finish_reason"],
                "receipt_sha256": receipt["receipt_sha256"],
            }
            for receipt in receipts
        ],
    }
    summary["summary_sha256"] = sha(stable(summary))
    (OUT / "SUMMARY.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))
    if verified != len(receipts):
        raise SystemExit("role portfolio partial")


if __name__ == "__main__":
    main()
