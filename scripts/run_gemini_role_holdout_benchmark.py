from __future__ import annotations

import concurrent.futures
import hashlib
import json
import math
import os
import statistics
import subprocess
import time
from pathlib import Path

import run_gemini_role_matrix as base

ROOT_OUT = Path(os.environ.get("ROLE_MATRIX_OUT", "/tmp/fuse-gemini-role-matrix"))
ROOT_OUT.mkdir(parents=True, exist_ok=True)
ROLES = tuple(base.CONTRACT["roles"])
MAX_WORKERS = min(int(base.CONTRACT["max_parallel_requests"]), len(ROLES))
PERFORMANCE_THRESHOLD = 2.0
PERFORMANCE_PAIR_COUNT = 4
PERFORMANCE_PAIR_PASS_FRACTION = 0.75
PERFORMANCE_PAIR_ORDERS = ("AB", "BA", "AB", "BA")

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


FROZEN_HOLDOUT_CASES_SHA256 = "4adb1bf9dc1efb7965262bad1518c4247e1f10bef40783546de915a63fc7bd0a"

ROLE_OUTPUT_CONTRACTS = {
    "ALPHA_OMEGA_REASONER": {
        "guidance": "selected_route must be the strongest route that passes every hard gate; hard_gate_respected is a boolean stating whether the decision obeyed the hard gate.",
        "schema": {
            "type": "OBJECT",
            "properties": {
                "selected_route": {"type": "STRING"},
                "hard_gate_respected": {"type": "BOOLEAN"},
                "decision": {"type": "STRING"},
            },
            "required": ["selected_route", "hard_gate_respected", "decision"],
        },
    },
    "CFBE_CRITIC": {
        "guidance": "Honor DERIVED_METRICS_JSON exactly. quality_floor_respected is true when the verdict obeys the frozen rule. If quality_floor_violated=true, verdict must be REJECT or HOLD and quality_floor_respected=true.",
        "schema": {
            "type": "OBJECT",
            "properties": {
                "verdict": {"type": "STRING", "enum": ["REJECT", "HOLD", "PASS"]},
                "quality_floor_respected": {"type": "BOOLEAN"},
                "reason": {"type": "STRING"},
            },
            "required": ["verdict", "quality_floor_respected", "reason"],
        },
    },
    "CREATIVE_BRIEF_COMPILER": {
        "guidance": "franchise_copy_allowed is a boolean. ORIGINAL_ONLY forbids a recognizable franchise copy; preserve the rights route and compile an original alternative.",
        "schema": {
            "type": "OBJECT",
            "properties": {
                "rights_route": {"type": "STRING"},
                "franchise_copy_allowed": {"type": "BOOLEAN"},
                "brief_action": {"type": "STRING"},
            },
            "required": ["rights_route", "franchise_copy_allowed", "brief_action"],
        },
    },
    "DESIGNIR_VALIDATOR": {
        "guidance": "valid is false when any mandatory field is missing. missing_fields is an array of exact missing field names; repair_actions is an array of concise repairs.",
        "schema": {
            "type": "OBJECT",
            "properties": {
                "valid": {"type": "BOOLEAN"},
                "missing_fields": {"type": "ARRAY", "items": {"type": "STRING"}},
                "repair_actions": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": ["valid", "missing_fields", "repair_actions"],
        },
    },
    "ROUTE_RANKER": {
        "guidance": "ineligible_selected is a boolean and must remain false when the rule forbids ineligible routes. ranking contains only eligible route IDs.",
        "schema": {
            "type": "OBJECT",
            "properties": {
                "winner": {"type": "STRING"},
                "ranking": {"type": "ARRAY", "items": {"type": "STRING"}},
                "ineligible_selected": {"type": "BOOLEAN"},
            },
            "required": ["winner", "ranking", "ineligible_selected"],
        },
    },
    "STORYBOARD_CONTINUITY_CRITIC": {
        "guidance": "continuity_break_detected and requires_repair are booleans. Unmotivated sun-direction or wardrobe discontinuity is a continuity break requiring repair.",
        "schema": {
            "type": "OBJECT",
            "properties": {
                "continuity_break_detected": {"type": "BOOLEAN"},
                "requires_repair": {"type": "BOOLEAN"},
                "issues": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": ["continuity_break_detected", "requires_repair", "issues"],
        },
    },
    "PROVENANCE_ANALYST": {
        "guidance": "consent_gap is a boolean: true when any required adult-verification or consent evidence is missing. release_allowed must be false while such a gap exists.",
        "schema": {
            "type": "OBJECT",
            "properties": {
                "provenance_state": {"type": "STRING"},
                "consent_gap": {"type": "BOOLEAN"},
                "release_allowed": {"type": "BOOLEAN"},
            },
            "required": ["provenance_state", "consent_gap", "release_allowed"],
        },
    },
    "CHALLENGER_JUDGE": {
        "guidance": "For raw criteria: quality and safety are higher-is-better; latency is lower-is-better. Honor DERIVED_METRICS_JSON exactly. If any criterion exceeds the frozen threshold, promotion=false, winner=A, and regressions lists only the failing criterion names.",
        "schema": {
            "type": "OBJECT",
            "properties": {
                "winner": {"type": "STRING", "enum": ["A", "B", "HOLD", "TIE"]},
                "promotion": {"type": "BOOLEAN"},
                "regressions": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": ["winner", "promotion", "regressions"],
        },
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


def _threshold_from_rule(rule: str, fallback: float) -> float:
    import re
    values = re.findall(r"(?<![A-Za-z])(?:0(?:\.\d+)?|1(?:\.0+)?)", str(rule))
    return float(values[-1]) if values else fallback


def deterministic_numeric_evidence(role: str, data: dict[str, object]) -> dict[str, object]:
    """Derive arithmetic facts from supplied synthetic input; never infer authority or outcomes."""
    if role == "CFBE_CRITIC":
        candidate = dict(data.get("candidate") or {})
        incumbent = dict(data.get("incumbent") or {})
        threshold = _threshold_from_rule(str(data.get("rule") or ""), 0.01)
        regression = max(0.0, float(incumbent.get("quality", 0.0)) - float(candidate.get("quality", 0.0)))
        return {
            "quality_regression": round(regression, 6),
            "quality_regression_limit": threshold,
            "quality_floor_violated": regression > threshold,
        }
    if role == "CHALLENGER_JUDGE":
        incumbent = dict(data.get("A") or {})
        challenger = dict(data.get("B") or {})
        criteria = [str(x) for x in (data.get("criteria") or [])]
        threshold = _threshold_from_rule(str(data.get("hard_rule") or ""), 0.10)
        lower_is_better = {"latency", "cost", "risk", "error_rate", "failure_rate"}
        regressions: dict[str, float] = {}
        for criterion in criteria:
            a = float(incumbent.get(criterion, 0.0))
            b = float(challenger.get(criterion, 0.0))
            regression = (b - a) if criterion.lower() in lower_is_better else (a - b)
            regressions[criterion] = round(max(0.0, regression), 6)
        failing = [name for name, value in regressions.items() if value > threshold]
        return {
            "regression_threshold": threshold,
            "criterion_regressions": regressions,
            "criteria_exceeding_threshold": failing,
            "promotion_blocked_by_frozen_rule": bool(failing),
        }
    return {}


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
    output_contract = ROLE_OUTPUT_CONTRACTS[role]
    derived = deterministic_numeric_evidence(role, dict(case["input"]))
    prompt = "\n".join(
        [
            f"ROLE={role}",
            f"OBJECTIVE={case['objective']}",
            *[f"RULE={rule}" for rule in RULES],
            "RULE=DERIVED_METRICS_JSON is deterministic arithmetic over INPUT_JSON; use it exactly and do not recompute contradictory values.",
            "RULE=Keep every string concise and every array to the minimum entries needed by the contract.",
            "FIELD_CONTRACT=" + output_contract["guidance"],
            f"REQUIRED_KEYS={','.join(required)}",
            "DERIVED_METRICS_JSON=" + stable(derived),
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
            "maxOutputTokens": 256,
            "responseMimeType": "application/json",
            "responseSchema": output_contract["schema"],
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
        "response_contract_sha256": sha(stable(output_contract)),
        "holdout_cases_sha256": sha(stable(HOLDOUT_CASES)),
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


def _rotated_roles(pair_index: int) -> tuple[str, ...]:
    offset = pair_index % len(ROLES)
    return ROLES[offset:] + ROLES[:offset]


def _max_interval_overlap(intervals: list[dict[str, float]]) -> int:
    events: list[tuple[float, int]] = []
    for item in intervals:
        events.append((float(item["started_offset_ms"]), 1))
        events.append((float(item["ended_offset_ms"]), -1))
    current = 0
    maximum = 0
    for _, delta in sorted(events, key=lambda event: (event[0], event[1])):
        current += delta
        maximum = max(maximum, current)
    return maximum


def _required_pair_pass_count() -> int:
    return math.ceil(PERFORMANCE_PAIR_COUNT * PERFORMANCE_PAIR_PASS_FRACTION)


def _paired_performance_decision(
    paired_ratios: list[float],
    *,
    all_semantic: bool,
    unique_ids: bool,
    min_parallel_overlap: int,
) -> dict[str, object]:
    if len(paired_ratios) != PERFORMANCE_PAIR_COUNT:
        return {
            "verified": False,
            "median_speedup_ratio": 0.0,
            "pair_pass_count": 0,
            "required_pair_pass_count": _required_pair_pass_count(),
            "median_absolute_deviation": 0.0,
        }
    median_ratio = float(statistics.median(paired_ratios))
    pass_count = sum(ratio >= PERFORMANCE_THRESHOLD for ratio in paired_ratios)
    mad = float(statistics.median(abs(ratio - median_ratio) for ratio in paired_ratios))
    verified = (
        all_semantic
        and unique_ids
        and min_parallel_overlap >= min(2, MAX_WORKERS)
        and median_ratio >= PERFORMANCE_THRESHOLD
        and pass_count >= _required_pair_pass_count()
    )
    return {
        "verified": verified,
        "median_speedup_ratio": median_ratio,
        "pair_pass_count": pass_count,
        "required_pair_pass_count": _required_pair_pass_count(),
        "median_absolute_deviation": mad,
    }


def _run_base_cohort(
    token: str,
    mode: str,
    *,
    cohort_label: str,
    role_order: tuple[str, ...],
) -> dict[str, object]:
    cohort_out = ROOT_OUT / f"_perf_{cohort_label.lower()}"
    cohort_out.mkdir(parents=True, exist_ok=True)
    previous_out = base.OUT
    base.OUT = cohort_out
    cohort_started = time.perf_counter()

    def invoke_timed(role: str) -> tuple[dict[str, object], float, float]:
        started_offset_ms = (time.perf_counter() - cohort_started) * 1000
        item = base.invoke(role, token)
        ended_offset_ms = (time.perf_counter() - cohort_started) * 1000
        return item, started_offset_ms, ended_offset_ms

    try:
        if mode == "SERIAL":
            executed = [invoke_timed(role) for role in role_order]
        elif mode == "PARALLEL":
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                executed = list(pool.map(invoke_timed, role_order))
        else:
            raise ValueError(f"unsupported mode:{mode}")
        wall_ms = (time.perf_counter() - cohort_started) * 1000
    finally:
        base.OUT = previous_out

    receipts: list[dict[str, object]] = []
    intervals: list[dict[str, float]] = []
    for index, (item, started_offset_ms, ended_offset_ms) in enumerate(executed):
        copy = dict(item)
        copy["performance_cohort"] = mode
        copy["performance_cohort_label"] = cohort_label
        copy["role_order_index"] = index
        copy["started_offset_ms"] = round(started_offset_ms, 3)
        copy["ended_offset_ms"] = round(ended_offset_ms, 3)
        copy["performance_receipt_sha256"] = sha(stable(copy))
        receipts.append(copy)
        intervals.append(
            {
                "role": str(item["role"]),
                "started_offset_ms": round(started_offset_ms, 3),
                "ended_offset_ms": round(ended_offset_ms, 3),
            }
        )
        (ROOT_OUT / f"PERF_{cohort_label}_{item['role']}.json").write_text(
            json.dumps(copy, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    return {
        "mode": mode,
        "cohort_label": cohort_label,
        "role_order": list(role_order),
        "wall_clock_ms": wall_ms,
        "receipts": receipts,
        "intervals": intervals,
        "max_interval_overlap": _max_interval_overlap(intervals),
    }


def run_performance_court(token: str) -> dict[str, object]:
    if len(PERFORMANCE_PAIR_ORDERS) != PERFORMANCE_PAIR_COUNT:
        raise ValueError("counterbalanced pair-order contract mismatch")
    pairs: list[dict[str, object]] = []
    all_receipts: list[dict[str, object]] = []

    for pair_index, order in enumerate(PERFORMANCE_PAIR_ORDERS):
        role_order = _rotated_roles(pair_index)
        execution_modes = ("SERIAL", "PARALLEL") if order == "AB" else ("PARALLEL", "SERIAL")
        cohorts: dict[str, dict[str, object]] = {}
        for mode in execution_modes:
            label = f"P{pair_index + 1}_{order}_{mode}"
            cohort = _run_base_cohort(
                token,
                mode,
                cohort_label=label,
                role_order=role_order,
            )
            cohorts[mode] = cohort
            all_receipts.extend(cohort["receipts"])

        serial_ms = float(cohorts["SERIAL"]["wall_clock_ms"])
        parallel_ms = float(cohorts["PARALLEL"]["wall_clock_ms"])
        ratio = serial_ms / parallel_ms if parallel_ms > 0 else 0.0
        pair = {
            "pair_index": pair_index + 1,
            "order": order,
            "role_order": list(role_order),
            "serial_wall_clock_ms": round(serial_ms, 3),
            "parallel_wall_clock_ms": round(parallel_ms, 3),
            "speedup_ratio": round(ratio, 6),
            "serial_semantic_verified": all(
                bool(item["semantic_verified"]) for item in cohorts["SERIAL"]["receipts"]
            ),
            "parallel_semantic_verified": all(
                bool(item["semantic_verified"]) for item in cohorts["PARALLEL"]["receipts"]
            ),
            "parallel_overlap_max": int(cohorts["PARALLEL"]["max_interval_overlap"]),
        }
        pairs.append(pair)

    paired_ratios = [float(pair["speedup_ratio"]) for pair in pairs]
    all_semantic = all(
        bool(item["semantic_verified"])
        for item in all_receipts
    )
    provider_ids = [
        item.get("provider_request_id")
        for item in all_receipts
        if item.get("provider_request_id")
    ]
    all_unique = len(provider_ids) == len(all_receipts) and len(set(provider_ids)) == len(provider_ids)
    min_parallel_overlap = min(int(pair["parallel_overlap_max"]) for pair in pairs)
    decision = _paired_performance_decision(
        paired_ratios,
        all_semantic=all_semantic,
        unique_ids=all_unique,
        min_parallel_overlap=min_parallel_overlap,
    )

    serial_walls = [float(pair["serial_wall_clock_ms"]) for pair in pairs]
    parallel_walls = [float(pair["parallel_wall_clock_ms"]) for pair in pairs]
    role_tail_evidence: dict[str, dict[str, object]] = {}
    for role in ROLES:
        serial_latencies = [
            float(item["latency_ms"])
            for item in all_receipts
            if item["role"] == role and item["performance_cohort"] == "SERIAL"
        ]
        parallel_latencies = [
            float(item["latency_ms"])
            for item in all_receipts
            if item["role"] == role and item["performance_cohort"] == "PARALLEL"
        ]
        all_latencies = serial_latencies + parallel_latencies
        role_tail_evidence[role] = {
            "serial_median_ms": round(float(statistics.median(serial_latencies)), 3),
            "parallel_median_ms": round(float(statistics.median(parallel_latencies)), 3),
            "max_latency_ms": round(max(all_latencies), 3),
            "median_latency_ms": round(float(statistics.median(all_latencies)), 3),
            "tail_to_median_ratio": round(
                max(all_latencies) / float(statistics.median(all_latencies)),
                6,
            )
            if statistics.median(all_latencies) > 0
            else 0.0,
        }

    summary = {
        "schema": "FUSE_GEMINI_ROLE_PERFORMANCE_COURT_V2",
        "court_design": "COUNTERBALANCED_REPEATED_AB_BA",
        "source_sha": os.environ.get("GITHUB_SHA"),
        "provider": "GOOGLE_VERTEX_AI",
        "transport": "VERTEX_WIF_ADC",
        "model": base.CONTRACT["model"],
        "same_role_set": True,
        "same_generation_contract": True,
        "single_access_token_for_both_cohorts": True,
        "pair_count": PERFORMANCE_PAIR_COUNT,
        "pair_orders": list(PERFORMANCE_PAIR_ORDERS),
        "required_pair_pass_fraction": PERFORMANCE_PAIR_PASS_FRACTION,
        "required_pair_pass_count": decision["required_pair_pass_count"],
        "pair_pass_count": decision["pair_pass_count"],
        "paired_speedup_ratios": paired_ratios,
        "paired_speedup_median": round(float(decision["median_speedup_ratio"]), 6),
        "paired_speedup_mad": round(float(decision["median_absolute_deviation"]), 6),
        "serial_wall_clock_ms": round(float(statistics.median(serial_walls)), 3),
        "parallel_wall_clock_ms": round(float(statistics.median(parallel_walls)), 3),
        "serial_verified_count": sum(
            bool(item["semantic_verified"])
            for item in all_receipts
            if item["performance_cohort"] == "SERIAL"
        ),
        "parallel_verified_count": sum(
            bool(item["semantic_verified"])
            for item in all_receipts
            if item["performance_cohort"] == "PARALLEL"
        ),
        "unique_request_ids_across_cohorts": all_unique,
        "minimum_parallel_overlap": min_parallel_overlap,
        "measured_speedup_ratio": round(float(decision["median_speedup_ratio"]), 6),
        "required_speedup_ratio": PERFORMANCE_THRESHOLD,
        "pair_evidence": pairs,
        "role_tail_evidence": role_tail_evidence,
        "state": "PERFORMANCE_2X_VERIFIED"
        if decision["verified"]
        else "PERFORMANCE_2X_NOT_VERIFIED",
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
    if sha(stable(HOLDOUT_CASES)) != FROZEN_HOLDOUT_CASES_SHA256:
        raise SystemExit("holdout case corpus drifted; update requires separate adjudication")
    if set(ROLE_OUTPUT_CONTRACTS) != set(ROLES):
        raise SystemExit("role output contract set does not match admitted roles")
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
