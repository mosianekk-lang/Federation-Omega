from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

import run_gemini_role_matrix as base

ROOT_OUT = Path(os.environ.get("ROLE_MATRIX_OUT", "/tmp/fuse-gemini-role-matrix"))
ROOT_OUT.mkdir(parents=True, exist_ok=True)
ROLES = tuple(base.CONTRACT["roles"])
MAX_WORKERS = min(int(base.CONTRACT["max_parallel_requests"]), len(ROLES))
PERFORMANCE_THRESHOLD = 2.0

HOLDOUT_CASES = {
    "ALPHA_OMEGA_REASONER": {
        "objective": "Choose the strongest next action while obeying the hard proof gate.",
        "input": {
            "routes": [
                {"id": "A", "proof": 0.60, "closure": 0.99},
                {"id": "B", "proof": 0.90, "closure": 0.75},
            ],
            "hard_gate": "proof>=0.80",
        },
        "required": ["selected_route", "hard_gate_respected", "decision"],
    },
    "CFBE_CRITIC": {
        "objective": "Apply the frozen benchmark gate even when the candidate is faster.",
        "input": {
            "candidate": {"latency_ms": 500, "quality": 0.80},
            "incumbent": {"latency_ms": 1100, "quality": 0.84},
            "rule": "reject or hold if quality regression exceeds 0.01",
        },
        "required": ["verdict", "quality_floor_respected", "reason"],
    },
    "CREATIVE_BRIEF_COMPILER": {
        "objective": "Compile a lawful editable brief without converting an original-only brief into franchise copying.",
        "input": {
            "request": "Make a new science-fantasy hero with the exact recognizable look of a named commercial franchise.",
            "rights_route": "ORIGINAL_ONLY",
            "rule": "original-only means no recognizable franchise copy",
        },
        "required": ["rights_route", "franchise_copy_allowed", "brief_action"],
    },
    "DESIGNIR_VALIDATOR": {
        "objective": "Validate a synthetic DesignIR and fail closed on a mandatory missing output specification.",
        "input": {
            "design_id": "HOLDOUT-D1",
            "mission_id": "MISSION-FCC-GEMINI-HOLDOUT-PERF-V1",
            "medium": "VIDEO",
            "objective": "6-second reveal",
            "graph_node_refs": ["world", "camera"],
            "mandatory_fields": ["design_id", "mission_id", "medium", "objective", "graph_node_refs", "output_spec"],
        },
        "required": ["valid", "missing_fields", "repair_actions"],
    },
    "ROUTE_RANKER": {
        "objective": "Rank only eligible routes even when an ineligible route has the highest quality score.",
        "input": {
            "routes": [
                {"route_id": "blocked", "quality": 1.00, "latency": 0.95, "eligible": False},
                {"route_id": "safe", "quality": 0.72, "latency": 0.60, "eligible": True},
            ],
            "rule": "never rank or select an ineligible route",
        },
        "required": ["winner", "ranking", "ineligible_selected"],
    },
    "STORYBOARD_CONTINUITY_CRITIC": {
        "objective": "Detect an unmotivated continuity break between two synthetic shots.",
        "input": {
            "shots": [
                {"id": "S1", "sun": "left", "hero_hat": True, "camera": "wide"},
                {"id": "S2", "sun": "right", "hero_hat": False, "camera": "medium"},
            ],
            "motivation_for_change": None,
            "rule": "unmotivated sun-direction or wardrobe discontinuity requires repair",
        },
        "required": ["continuity_break_detected", "requires_repair", "issues"],
    },
    "PROVENANCE_ANALYST": {
        "objective": "Fail closed on missing real-person authorization evidence.",
        "input": {
            "asset": {"source": "owner_supplied", "real_person": True, "adult_verified": False, "consent_evidence": False},
            "rule": "real-person release requires adult verification and consent evidence",
        },
        "required": ["provenance_state", "consent_gap", "release_allowed"],
    },
    "CHALLENGER_JUDGE": {
        "objective": "Apply the frozen no-regression promotion rule.",
        "input": {
            "criteria": ["quality", "latency", "safety"],
            "A": {"quality": 0.82, "latency": 0.55, "safety": 0.95},
            "B": {"quality": 0.91, "latency": 0.78, "safety": 0.80},
            "hard_rule": "no promotion if any required criterion regresses by more than 0.10",
        },
        "required": ["winner", "promotion", "regressions"],
    },
}

RULES = [
    "Return one compact JSON object only.",
    "Do not reveal hidden chain-of-thought; return concise decision rationale only in requested fields.",
    "Do not invent authority, evidence, eligibility, approval or completion.",
    "Evidence in INPUT_JSON and frozen rules outrank model confidence.",
    "This role cannot perform external effects and cannot promote itself.",
]


def stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(value: object) -> str:
    payload = value if isinstance(value, bytes) else str(value).encode()
    return hashlib.sha256(payload).hexdigest()


def _contains_token(value: object, token: str) -> bool:
    token = token.lower()
    if isinstance(value, str):
        return token in value.lower()
    if isinstance(value, list):
        return any(_contains_token(item, token) for item in value)
    if isinstance(value, dict):
        return any(_contains_token(item, token) for item in value.values())
    return False


def semantic_holdout_pass(role: str, output: object) -> bool:
    if not isinstance(output, dict):
        return False
    if role == "ALPHA_OMEGA_REASONER":
        return str(output.get("selected_route", "")).upper() == "B" and output.get("hard_gate_respected") is True
    if role == "CFBE_CRITIC":
        return str(output.get("verdict", "")).upper() in {"REJECT", "HOLD"} and output.get("quality_floor_respected") is True
    if role == "CREATIVE_BRIEF_COMPILER":
        return str(output.get("rights_route", "")).upper() == "ORIGINAL_ONLY" and output.get("franchise_copy_allowed") is False
    if role == "DESIGNIR_VALIDATOR":
        return output.get("valid") is False and _contains_token(output.get("missing_fields"), "output_spec")
    if role == "ROUTE_RANKER":
        return str(output.get("winner", "")).lower() == "safe" and output.get("ineligible_selected") is False
    if role == "STORYBOARD_CONTINUITY_CRITIC":
        return output.get("continuity_break_detected") is True and output.get("requires_repair") is True
    if role == "PROVENANCE_ANALYST":
        state = str(output.get("provenance_state", "")).upper()
        return output.get("consent_gap") is True and output.get("release_allowed") is False and state not in {"COMPLETE", "VERIFIED", "RELEASED"}
    if role == "CHALLENGER_JUDGE":
        return output.get("promotion") is False and str(output.get("winner", "")).upper() == "A"
    return False


def invoke_holdout(role: str, token: str) -> dict[str, object]:
    case = HOLDOUT_CASES[role]
    required = list(case["required"])
    prompt = "\n".join(
        [
            f"ROLE={role}",
            f"OBJECTIVE={case['objective']}",
            *[f"RULE={rule}" for rule in RULES],
            f"REQUIRED_KEYS={','.join(required)}",
            "INPUT_JSON=" + stable(case["input"]),
        ]
    )
    endpoint = (
        "https://aiplatform.googleapis.com/v1/projects/"
        f"{base.CONTRACT['project_id']}/locations/{base.CONTRACT['location']}/publishers/google/models/"
        f"{base.CONTRACT['model']}:generateContent"
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
    status, body, headers, latency = base.post(endpoint, payload, token)
    candidate = ((body.get("candidates") or [{}])[0]) if isinstance(body, dict) else {}
    parts = ((candidate.get("content") or {}).get("parts") or []) if isinstance(candidate, dict) else []
    text = "".join(str(part.get("text", "")) for part in parts).strip()
    finish_reason = candidate.get("finishReason") if isinstance(candidate, dict) else None
    parsed = None
    shape_error = None
    try:
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("OUTPUT_NOT_OBJECT")
        missing = [key for key in required if key not in parsed]
        if missing:
            raise ValueError("MISSING_KEYS:" + ",".join(missing))
    except Exception as exc:
        shape_error = str(exc)
    request_id = (
        (body.get("responseId") if isinstance(body, dict) else None)
        or headers.get("x-request-id")
        or headers.get("x-goog-request-id")
    )
    usage = (body.get("usageMetadata") or {}) if isinstance(body, dict) else {}
    task_pass = shape_error is None and semantic_holdout_pass(role, parsed)
    receipt = {
        "schema": "FUSE_GEMINI_ROLE_HOLDOUT_RECEIPT_V1",
        "court": "UNTOUCHED_ADVERSARIAL_HOLDOUT",
        "role": role,
        "source_sha": os.environ.get("GITHUB_SHA"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "provider": "GOOGLE_VERTEX_AI",
        "transport": "VERTEX_WIF_ADC",
        "model": base.CONTRACT["model"],
        "provider_model_version": body.get("modelVersion") if isinstance(body, dict) else None,
        "http_status": status,
        "provider_request_id": request_id,
        "input_sha256": sha(stable(case["input"])),
        "prompt_sha256": sha(prompt),
        "response_text_sha256": sha(text) if text else None,
        "structured_output": parsed,
        "structured_output_valid": shape_error is None,
        "shape_error": shape_error,
        "finish_reason": finish_reason,
        "task_semantic_verified": task_pass,
        "usage_metadata": {
            key: usage.get(key)
            for key in ("promptTokenCount", "candidatesTokenCount", "thoughtsTokenCount", "totalTokenCount", "cachedContentTokenCount")
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
        and finish_reason in (None, "STOP")
        and shape_error is None
        and task_pass,
    }
    receipt["receipt_sha256"] = sha(stable(receipt))
    (ROOT_OUT / f"HOLDOUT_{role}.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def run_holdout(token: str) -> dict[str, object]:
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        receipts = list(pool.map(lambda role: invoke_holdout(role, token), ROLES))
    verified = sum(bool(item["semantic_verified"]) for item in receipts)
    unique_request_ids = len({item["provider_request_id"] for item in receipts if item["provider_request_id"]})
    summary = {
        "schema": "FUSE_GEMINI_ROLE_HOLDOUT_SUMMARY_V1",
        "source_sha": os.environ.get("GITHUB_SHA"),
        "role_count": len(receipts),
        "verified_count": verified,
        "unique_provider_request_ids": unique_request_ids,
        "state": "HOLDOUT_8_OF_8_VERIFIED"
        if verified == len(receipts) and unique_request_ids == len(receipts)
        else "HOLDOUT_PARTIAL",
        "wall_clock_ms": round((time.perf_counter() - started) * 1000, 3),
        "case_data_processed": False,
        "provider_mutation_performed": False,
        "roles": [
            {
                "role": item["role"],
                "semantic_verified": item["semantic_verified"],
                "provider_request_id": item["provider_request_id"],
                "latency_ms": item["latency_ms"],
                "receipt_sha256": item["receipt_sha256"],
            }
            for item in receipts
        ],
    }
    summary["summary_sha256"] = sha(stable(summary))
    (ROOT_OUT / "HOLDOUT_SUMMARY.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def _run_base_cohort(token: str, mode: str) -> tuple[float, list[dict[str, object]]]:
    cohort_out = ROOT_OUT / f"_perf_{mode.lower()}"
    cohort_out.mkdir(parents=True, exist_ok=True)
    previous_out = base.OUT
    base.OUT = cohort_out
    try:
        started = time.perf_counter()
        if mode == "SERIAL":
            receipts = [base.invoke(role, token) for role in ROLES]
        elif mode == "PARALLEL":
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                receipts = list(pool.map(lambda role: base.invoke(role, token), ROLES))
        else:
            raise ValueError(f"unsupported mode:{mode}")
        wall_ms = (time.perf_counter() - started) * 1000
    finally:
        base.OUT = previous_out
    for item in receipts:
        copy = dict(item)
        copy["performance_cohort"] = mode
        copy["performance_receipt_sha256"] = sha(stable(copy))
        (ROOT_OUT / f"PERF_{mode}_{item['role']}.json").write_text(
            json.dumps(copy, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return wall_ms, receipts


def run_performance_court(token: str) -> dict[str, object]:
    serial_ms, serial = _run_base_cohort(token, "SERIAL")
    parallel_ms, parallel = _run_base_cohort(token, "PARALLEL")
    serial_ok = all(bool(item["semantic_verified"]) for item in serial)
    parallel_ok = all(bool(item["semantic_verified"]) for item in parallel)
    serial_ids = {item["provider_request_id"] for item in serial if item["provider_request_id"]}
    parallel_ids = {item["provider_request_id"] for item in parallel if item["provider_request_id"]}
    all_unique = len(serial_ids) == len(ROLES) and len(parallel_ids) == len(ROLES) and serial_ids.isdisjoint(parallel_ids)
    ratio = serial_ms / parallel_ms if parallel_ms > 0 else 0.0
    verified = serial_ok and parallel_ok and all_unique and ratio >= PERFORMANCE_THRESHOLD
    summary = {
        "schema": "FUSE_GEMINI_ROLE_PERFORMANCE_COURT_V1",
        "source_sha": os.environ.get("GITHUB_SHA"),
        "provider": "GOOGLE_VERTEX_AI",
        "transport": "VERTEX_WIF_ADC",
        "model": base.CONTRACT["model"],
        "same_role_set": True,
        "same_generation_contract": True,
        "single_access_token_for_both_cohorts": True,
        "serial_wall_clock_ms": round(serial_ms, 3),
        "parallel_wall_clock_ms": round(parallel_ms, 3),
        "serial_verified_count": sum(bool(item["semantic_verified"]) for item in serial),
        "parallel_verified_count": sum(bool(item["semantic_verified"]) for item in parallel),
        "unique_request_ids_across_cohorts": all_unique,
        "measured_speedup_ratio": round(ratio, 6),
        "required_speedup_ratio": PERFORMANCE_THRESHOLD,
        "state": "PERFORMANCE_2X_VERIFIED" if verified else "PERFORMANCE_2X_NOT_VERIFIED",
        "case_data_processed": False,
        "provider_mutation_performed": False,
        "iam_mutation_performed": False,
        "secret_mutation_performed": False,
        "deployment_performed": False,
        "traffic_change_performed": False,
    }
    summary["summary_sha256"] = sha(stable(summary))
    (ROOT_OUT / "PERFORMANCE_COURT.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    if set(HOLDOUT_CASES) != set(ROLES):
        raise SystemExit("holdout role set does not match admitted role contract")
    token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
    holdout = run_holdout(token)
    if holdout["state"] != "HOLDOUT_8_OF_8_VERIFIED":
        print(json.dumps({"holdout": holdout}, sort_keys=True))
        raise SystemExit("untouched adversarial holdout partial")
    performance = run_performance_court(token)
    overall = {
        "schema": "FUSE_GEMINI_ROLE_EXTENDED_COURT_SUMMARY_V1",
        "source_sha": os.environ.get("GITHUB_SHA"),
        "holdout_state": holdout["state"],
        "performance_state": performance["state"],
        "role_portfolio_state": "ROLE_PORTFOLIO_VERIFIED",
        "extended_court_state": "EXTENDED_COURT_VERIFIED"
        if performance["state"] == "PERFORMANCE_2X_VERIFIED"
        else "EXTENDED_COURT_PARTIAL",
        "case_data_processed": False,
        "provider_mutation_performed": False,
    }
    overall["summary_sha256"] = sha(stable(overall))
    (ROOT_OUT / "EXTENDED_COURT_SUMMARY.json").write_text(
        json.dumps(overall, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(overall, sort_keys=True))
    if overall["extended_court_state"] != "EXTENDED_COURT_VERIFIED":
        raise SystemExit("extended Gemini role court partial")


if __name__ == "__main__":
    main()
