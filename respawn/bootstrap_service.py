from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "federation_manifest.json"
CONFIG_ROOT = ROOT.parent / "config"
BOOTSTRAP_MEMORY_PATH = CONFIG_ROOT / "fuse-bootstrap-memory-snapshot-v1.json"
BOOTSTRAP_IMPROVEMENT_PATH = CONFIG_ROOT / "fuse-bootstrap-self-improvement-v1.json"
AUTONOMY_PATH = CONFIG_ROOT / "fuse-24x7-autonomy-v1.json"
AUTONOMOUS_WORKER_PATH = ROOT.parent / "fuse_runtime" / "autonomous_improvement_loop_v1.mjs"
OUTPUT_MIRROR_V3_PATH = ROOT.parent / "fuse_runtime" / "output_mirror_v3.mjs"
HIPB_MODULE_PATH = ROOT.parent / "fuse_runtime" / "hyper_intelligence_performance_v1.mjs"
HIPB_COURT_PATH = ROOT.parent / "benchmarks" / "hyper_intelligence_performance_court_v1.mjs"
STATE_PATH = Path(os.getenv("FEDERATION_RESPAWN_STATE", ROOT / "runtime_state.json"))

app = FastAPI(title="Federation Respawn Bootstrap", version="1.5.0")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
    tmp.replace(path)


def resolve_runtime_alias(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("env:"):
        return os.getenv(value[4:], "")
    if isinstance(value, dict):
        return {key: resolve_runtime_alias(item) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_runtime_alias(item) for item in value]
    return value


def manifest() -> Dict[str, Any]:
    return load_json(MANIFEST_PATH, {})


def resolved_control_plane() -> Dict[str, Any]:
    return resolve_runtime_alias(manifest().get("control_plane", {}))


def bootstrap_memory_bundle() -> Dict[str, Any]:
    snapshot = load_json(BOOTSTRAP_MEMORY_PATH, {})
    improvement = load_json(BOOTSTRAP_IMPROVEMENT_PATH, {})
    autonomy = load_json(AUTONOMY_PATH, {})
    issues: List[str] = []
    if snapshot.get("schema") != "FUSE_BOOTSTRAP_MEMORY_SNAPSHOT_V1":
        issues.append("BOOTSTRAP_MEMORY_SNAPSHOT_MISSING_OR_INVALID")
    if improvement.get("schema") != "FUSE_BOOTSTRAP_SELF_IMPROVEMENT_V1":
        issues.append("BOOTSTRAP_SELF_IMPROVEMENT_MISSING_OR_INVALID")
    policy = improvement.get("iteration_policy", {})
    if improvement.get("version") != "2.0.0":
        issues.append("BOOTSTRAP_SELF_IMPROVEMENT_VERSION_MISMATCH")
    if policy.get("exact_iterations_per_cycle") != 10:
        issues.append("AUTONOMOUS_IMPROVEMENT_ITERATION_COUNT_MISMATCH")
    if policy.get("inhouse_default") is not True:
        issues.append("AUTONOMOUS_IMPROVEMENT_INHOUSE_DISABLED")
    if policy.get("build_to_completion") is not True:
        issues.append("AUTONOMOUS_IMPROVEMENT_COMPLETION_DISABLED")
    if not AUTONOMOUS_WORKER_PATH.exists():
        issues.append("AUTONOMOUS_IMPROVEMENT_WORKER_MISSING")
        worker_sha256 = None
    else:
        worker_sha256 = hashlib.sha256(AUTONOMOUS_WORKER_PATH.read_bytes()).hexdigest()
        if worker_sha256 != improvement.get("live_proof", {}).get("worker_sha256"):
            issues.append("AUTONOMOUS_IMPROVEMENT_WORKER_HASH_MISMATCH")
    if autonomy.get("schema") != "FUSE_24X7_AUTONOMY_V1":
        issues.append("AUTONOMY_CONTRACT_MISSING_OR_INVALID")
    backfill = autonomy.get("historical_chat_backfill", {})
    if autonomy.get("auto_repeat", {}).get("iterations") != 10:
        issues.append("AUTONOMY_REPEAT_COUNT_MISMATCH")
    if backfill.get("iterations_per_recovered_chat") != 10:
        issues.append("HISTORICAL_CHAT_ITERATION_COUNT_MISMATCH")
    if backfill.get("current_exact_recoverable_chat_records") != 37:
        issues.append("HISTORICAL_CHAT_RECORD_COUNT_MISMATCH")
    if backfill.get("current_completed_chat_iterations") != 370:
        issues.append("HISTORICAL_CHAT_COMPLETED_ITERATIONS_MISMATCH")
    if backfill.get("native_totality") != "UNVERIFIED":
        issues.append("NATIVE_CHAT_TOTALITY_FALSE_CLAIM")
    if backfill.get("no_false_totality_claim") is not True:
        issues.append("NATIVE_CHAT_TOTALITY_GUARD_MISSING")
    return {
        "ok": not issues,
        "issues": issues,
        "snapshot": snapshot,
        "self_improvement": improvement,
        "autonomy": autonomy,
        "worker_sha256": worker_sha256,
    }

def autonomous_improvement_bootstrap_guard(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    source = payload if payload is not None else manifest()
    contract = source.get("bootstrap_self_improvement", {})
    history = source.get("historical_chat_backfill", {})
    issues: List[str] = []
    if contract.get("contract_id") != "FUSE-BOOTSTRAP-SELF-IMPROVEMENT-V2":
        issues.append("AUTONOMOUS_IMPROVEMENT_CONTRACT_ID_MISMATCH")
    if contract.get("iterations_per_cycle") != 10 or contract.get("exact_iteration_count") is not True:
        issues.append("AUTONOMOUS_IMPROVEMENT_MANIFEST_ITERATION_MISMATCH")
    measured_worker_sha256 = hashlib.sha256(AUTONOMOUS_WORKER_PATH.read_bytes()).hexdigest() if AUTONOMOUS_WORKER_PATH.exists() else None
    if contract.get("worker_sha256") != measured_worker_sha256:
        issues.append("AUTONOMOUS_IMPROVEMENT_MANIFEST_WORKER_MISMATCH")
    if history.get("iterations_per_recovered_chat") != 10:
        issues.append("HISTORICAL_BACKFILL_MANIFEST_ITERATION_MISMATCH")
    if history.get("current_exact_recovered_chat_records") != 37:
        issues.append("HISTORICAL_BACKFILL_MANIFEST_RECORD_MISMATCH")
    if history.get("current_completed_iterations") != 370:
        issues.append("HISTORICAL_BACKFILL_MANIFEST_COMPLETION_MISMATCH")
    if int(history.get("recoverable_record_instances", 0)) < 129:
        issues.append("HISTORICAL_BACKFILL_RECOVERABLE_BASELINE_REGRESSED")
    if int(history.get("completed_record_iterations", 0)) < 1290:
        issues.append("HISTORICAL_BACKFILL_ITERATION_BASELINE_REGRESSED")
    if history.get("native_account_totality") != "UNVERIFIED":
        issues.append("HISTORICAL_BACKFILL_NATIVE_TOTALITY_FALSE_CLAIM")
    return {
        "schema": "FUSE_AUTONOMOUS_IMPROVEMENT_BOOTSTRAP_GUARD_V1",
        "ok": not issues,
        "issues": issues,
        "iterations": contract.get("iterations_per_cycle"),
        "worker_sha256": contract.get("worker_sha256"),
        "historical_chat_records": history.get("current_exact_recovered_chat_records"),
        "historical_chat_iterations": history.get("current_completed_iterations"),
        "native_account_totality": history.get("native_account_totality"),
    }



def hyper_intelligence_performance_bootstrap_guard(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    source = payload if payload is not None else manifest()
    contract = source.get("hyper_intelligence_performance", {})
    order = source.get("bootstrap_order", [])
    issues: List[str] = []
    if contract.get("enabled") is not True:
        issues.append("HIPB_DISABLED_OR_MISSING")
    if contract.get("contract_id") != "FUSE-HIPB-001":
        issues.append("HIPB_CONTRACT_ID_MISMATCH")
    if contract.get("schema") != "FUSE_HYPER_INTELLIGENCE_PERFORMANCE_BINDING_V1":
        issues.append("HIPB_SCHEMA_MISMATCH")
    if "load_hyper_intelligence_performance_contract" not in order:
        issues.append("HIPB_LOAD_STEP_MISSING")
    if "compile_hyper_intelligence_plan" not in order:
        issues.append("HIPB_COMPILE_STEP_MISSING")
    if "execute" in order and "compile_hyper_intelligence_plan" in order:
        if order.index("compile_hyper_intelligence_plan") > order.index("execute"):
            issues.append("HIPB_COMPILE_AFTER_EXECUTE")
    measured_module_sha256 = hashlib.sha256(HIPB_MODULE_PATH.read_bytes()).hexdigest() if HIPB_MODULE_PATH.exists() else None
    measured_court_sha256 = hashlib.sha256(HIPB_COURT_PATH.read_bytes()).hexdigest() if HIPB_COURT_PATH.exists() else None
    if measured_module_sha256 is None:
        issues.append("HIPB_MODULE_MISSING")
    elif contract.get("module_sha256") != measured_module_sha256:
        issues.append("HIPB_MODULE_HASH_MISMATCH")
    if measured_court_sha256 is None:
        issues.append("HIPB_COURT_MISSING")
    elif contract.get("court_sha256") != measured_court_sha256:
        issues.append("HIPB_COURT_HASH_MISMATCH")
    if "HYPER_PERFORMANCE_CLAIMS_REQUIRE_MATCHED_EMPIRICAL_PROOF" not in source.get("bootstrap_invariants", []):
        issues.append("HIPB_MATCHED_PERFORMANCE_INVARIANT_MISSING")
    return {
        "schema": "FUSE_HIPB_BOOTSTRAP_GUARD_V1",
        "ok": not issues,
        "issues": issues,
        "contract_id": contract.get("contract_id"),
        "version": contract.get("version"),
        "module_sha256": contract.get("module_sha256"),
        "court_sha256": contract.get("court_sha256"),
        "runtime_promotion_proven": False,
        "truth_boundary": contract.get("truth_boundary"),
    }


def output_mirror_bootstrap_guard(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    source = payload if payload is not None else manifest()
    contract = source.get("output_mirror_bootstrap", {})
    fidelity = source.get("directive_fidelity_bootstrap", {})
    issues: List[str] = []
    if fidelity.get("enabled") is not True:
        issues.append("DIRECTIVE_FIDELITY_DISABLED_OR_MISSING")
    if fidelity.get("contract_id") != "FUSE-DIRECTIVE-FIDELITY-V1":
        issues.append("DIRECTIVE_FIDELITY_CONTRACT_ID_MISMATCH")
    if contract.get("enabled") is not True:
        issues.append("OUTPUT_MIRROR_BOOTSTRAP_DISABLED_OR_MISSING")
    if contract.get("contract_id") != "FUSE-OUTPUT-MIRROR-BOOTSTRAP-V3":
        issues.append("OUTPUT_MIRROR_BOOTSTRAP_CONTRACT_ID_MISMATCH")
    if contract.get("release_policy") != "ZERO_FAIL_ACROSS_ALL_REQUIRED_DIMENSIONS":
        issues.append("OUTPUT_MIRROR_RELEASE_POLICY_MISMATCH")
    required = set(contract.get("required_dimensions", []))
    expected = {
        "intent_fidelity", "execution_finality", "proof_evidence", "design_code_health",
        "testing", "security_privacy", "reliability_recovery", "performance_cost",
        "currentness_reproducibility", "owner_value",
    }
    missing = sorted(expected - required)
    issues.extend(f"MISSING_OUTPUT_MIRROR_DIMENSION:{name}" for name in missing)
    if contract.get("developer1000", {}).get("sha256") != "f7277e2244f1d59849f64f5d4f48af7c20de14ecb8573dba763353bf6084cb7e":
        issues.append("DEVELOPER1000_CORPUS_MISMATCH")
    if contract.get("benchmark_court", {}).get("dataset_sha256") != "d69644412e285ef3a5baeab0b0ef4683ae42280ddca0bdb4a0ea2ce3a5fd6510":
        issues.append("OUTPUT_MIRROR_BENCHMARK_COURT_MISMATCH")
    diary = contract.get("power_diary", {})
    if diary.get("source_sha256") != "3d95834ff0070e06c8de385b9240c65490d9b71ceb63fa5e3364f407261c0495":
        issues.append("POWER_DIARY_SOURCE_MISMATCH")
    if diary.get("chapter_count") != 40:
        issues.append("POWER_DIARY_CHAPTER_COUNT_MISMATCH")
    if diary.get("required_family_count") != 17:
        issues.append("POWER_DIARY_FAMILY_COUNT_MISMATCH")
    measured_mirror_sha256 = None
    if not OUTPUT_MIRROR_V3_PATH.exists():
        issues.append("OUTPUT_MIRROR_MODULE_MISSING")
    else:
        measured_mirror_sha256 = hashlib.sha256(OUTPUT_MIRROR_V3_PATH.read_bytes()).hexdigest()
        if diary.get("module_sha256") != measured_mirror_sha256:
            issues.append("POWER_DIARY_MODULE_HASH_MISMATCH")
    return {
        "schema": "FUSE_OUTPUT_MIRROR_BOOTSTRAP_GUARD_V3",
        "ok": not issues,
        "issues": issues,
        "contract_id": contract.get("contract_id"),
        "boot_kernel_min_version": contract.get("boot_kernel_min_version"),
        "mirror_min_version": contract.get("mirror_min_version"),
        "required_dimension_count": len(required),
        "power_diary_sha256": contract.get("power_diary", {}).get("source_sha256"),
        "power_diary_chapter_count": contract.get("power_diary", {}).get("chapter_count"),
        "power_diary_family_count": contract.get("power_diary", {}).get("required_family_count"),
        "directive_fidelity_contract_id": fidelity.get("contract_id"),
        "directive_fidelity_enabled": fidelity.get("enabled"),
    }


def state() -> Dict[str, Any]:
    return load_json(
        STATE_PATH,
        {"deltas": [], "patterns": [], "conflicts": [], "bibliography": []},
    )


def fingerprint(*parts: str) -> str:
    payload = "\n".join(p.strip().lower() for p in parts if p).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


class SpawnRequest(BaseModel):
    system: str
    matter: Optional[str] = None
    chat_ref: Optional[str] = None
    objective: Optional[str] = None
    terms: List[str] = Field(default_factory=list)


class SolvedRequest(BaseModel):
    system: Optional[str] = None
    matter: Optional[str] = None
    problem: str
    terms: List[str] = Field(default_factory=list)


class DeltaRequest(BaseModel):
    source_system: str
    matter: Optional[str] = None
    chat_ref: Optional[str] = None
    summary: str
    problem_signature: Optional[str] = None
    reusable_pattern: Optional[str] = None
    affected_systems: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    status: str = "VERIFIED"
    supersedes: List[str] = Field(default_factory=list)
    idempotency_key: Optional[str] = None


def validate_system(name: str) -> None:
    systems = set(manifest().get("registered_systems", []))
    if name not in systems:
        raise HTTPException(status_code=400, detail=f"Unregistered system: {name}")


def search_state(req: SolvedRequest) -> List[Dict[str, Any]]:
    s = state()
    needles = {x.lower() for x in [req.problem, req.matter or "", *req.terms] if x}
    out: List[Dict[str, Any]] = []
    for item in [*s.get("patterns", []), *s.get("bibliography", []), *s.get("deltas", [])]:
        hay = json.dumps(item, ensure_ascii=False).lower()
        score = sum(1 for n in needles if n and n in hay)
        if score:
            enriched = dict(item)
            enriched["match_score"] = score
            out.append(enriched)
    return sorted(out, key=lambda x: x.get("match_score", 0), reverse=True)[:20]


def provider_adapter() -> Any:
    try:
        from google_workspace_adapter import GoogleWorkspaceBibleAdapter
    except Exception as exc:
        return {"available": False, "reason": f"adapter_import_failed:{type(exc).__name__}"}
    if not GoogleWorkspaceBibleAdapter.configured():
        return {"available": False, "reason": "provider_not_configured"}
    try:
        return GoogleWorkspaceBibleAdapter()
    except Exception as exc:
        return {"available": False, "reason": f"provider_initialization_failed:{type(exc).__name__}"}


@app.get("/health")
def health() -> Dict[str, Any]:
    m = manifest()
    adapter = provider_adapter()
    provider_state = (
        {"available": True, "provider": "google-workspace"}
        if not isinstance(adapter, dict)
        else adapter
    )
    return {
        "ok": True,
        "service": "federation-respawn-bootstrap",
        "schema_version": m.get("schema_version"),
        "registered_system_count": len(m.get("registered_systems", [])),
        "state_path": str(STATE_PATH),
        "provider": provider_state,
        "time": utcnow(),
    }


@app.post("/already-solved")
def already_solved(req: SolvedRequest) -> Dict[str, Any]:
    matches = search_state(req)
    return {
        "problem_fingerprint": fingerprint(req.system or "", req.matter or "", req.problem, *req.terms),
        "already_solved": bool(matches),
        "matches": matches,
    }


@app.post("/bootstrap")
def bootstrap(req: SpawnRequest) -> Dict[str, Any]:
    validate_system(req.system)
    source_manifest = manifest()
    mirror_guard = output_mirror_bootstrap_guard(source_manifest)
    memory_bundle = bootstrap_memory_bundle()
    autonomy_guard = autonomous_improvement_bootstrap_guard(source_manifest)
    hipb_guard = hyper_intelligence_performance_bootstrap_guard(source_manifest)
    if not mirror_guard["ok"] or not memory_bundle["ok"] or not autonomy_guard["ok"] or not hipb_guard["ok"]:
        raise HTTPException(
            status_code=503,
            detail={"error": "BOOTSTRAP_INVARIANT_FAILED", "output_mirror_bootstrap_guard": mirror_guard, "bootstrap_memory_guard": {"ok": memory_bundle["ok"], "issues": memory_bundle["issues"]}, "autonomous_improvement_guard": autonomy_guard, "hyper_intelligence_performance_guard": hipb_guard},
        )
    s = state()
    solved = search_state(
        SolvedRequest(system=req.system, matter=req.matter, problem=req.objective or "", terms=req.terms)
    )
    recent = [d for d in s.get("deltas", []) if not req.matter or d.get("matter") == req.matter][-20:]
    conflicts = [c for c in s.get("conflicts", []) if not req.matter or c.get("matter") == req.matter]

    adapter = provider_adapter()
    provider_context: Dict[str, Any]
    if isinstance(adapter, dict):
        provider_context = adapter
    else:
        try:
            provider_context = adapter.bootstrap(req.system, req.matter)
        except Exception as exc:
            provider_context = {
                "available": False,
                "reason": f"provider_bootstrap_failed:{type(exc).__name__}",
            }

    return {
        "spawn_id": fingerprint(req.system, req.matter or "", req.chat_ref or "", utcnow()),
        "system": req.system,
        "matter": req.matter,
        "chat_ref": req.chat_ref,
        "bootstrap_order": manifest().get("bootstrap_order", []),
        "bootstrap_invariants": manifest().get("bootstrap_invariants", []),
        "runtime_sovereignty": source_manifest.get("runtime_sovereignty", {}),
        "bootstrap_memory_snapshot": memory_bundle["snapshot"],
        "bootstrap_self_improvement": memory_bundle["self_improvement"],
        "autonomy_contract": memory_bundle["autonomy"],
        "autonomous_improvement_guard": autonomy_guard,
        "hyper_intelligence_performance": source_manifest.get("hyper_intelligence_performance", {}),
        "hyper_intelligence_performance_guard": hipb_guard,
        "historical_chat_backfill": source_manifest.get("historical_chat_backfill", {}),
        "directive_fidelity_bootstrap": source_manifest.get("directive_fidelity_bootstrap", {}),
        "output_mirror_bootstrap": source_manifest.get("output_mirror_bootstrap", {}),
        "output_mirror_bootstrap_guard": mirror_guard,
        "delivery_rule": source_manifest.get("delivery_rule"),
        "control_plane": resolved_control_plane(),
        "already_solved_candidates": solved,
        "recent_deltas": recent,
        "open_conflicts": conflicts,
        "provider_context": provider_context,
        "proof_rule": manifest().get("proof_rule"),
        "generated_at": utcnow(),
    }


@app.post("/delta")
def publish_delta(req: DeltaRequest) -> Dict[str, Any]:
    validate_system(req.source_system)
    data = state()

    if req.idempotency_key:
        for existing in data.get("deltas", []):
            if existing.get("idempotency_key") == req.idempotency_key:
                return {
                    "accepted": True,
                    "duplicate": True,
                    "delta_id": existing.get("delta_id"),
                    "proof_state": existing.get("provider_proof_state", "LOCAL_RUNTIME_ONLY"),
                }

    delta_id = fingerprint(
        req.source_system,
        req.matter or "",
        req.idempotency_key or req.summary,
        "stable" if req.idempotency_key else utcnow(),
    )
    record = req.model_dump()
    record.update({"delta_id": delta_id, "created_at": utcnow()})
    data.setdefault("deltas", []).append(record)

    if req.reusable_pattern:
        data.setdefault("patterns", []).append(
            {
                "pattern_id": fingerprint(req.reusable_pattern, req.problem_signature or ""),
                "source_delta_id": delta_id,
                "source_system": req.source_system,
                "matter": req.matter,
                "problem_signature": req.problem_signature,
                "pattern": req.reusable_pattern,
                "evidence_refs": req.evidence_refs,
                "created_at": utcnow(),
            }
        )

    data.setdefault("bibliography", []).append(
        {
            "entry_id": fingerprint(delta_id, req.chat_ref or ""),
            "source_system": req.source_system,
            "matter": req.matter,
            "chat_ref": req.chat_ref,
            "work_summary": req.summary,
            "affected_systems": req.affected_systems,
            "evidence_refs": req.evidence_refs,
            "status": req.status,
            "created_at": utcnow(),
        }
    )

    provider_result: Dict[str, Any] = {"written": False, "reason": "provider_not_configured_or_not_authorised"}
    adapter = provider_adapter()
    if not isinstance(adapter, dict) and adapter.provider_writes:
        try:
            provider_write = adapter.publish_delta(
                event_id=f"SYNC-{delta_id}",
                source_system=req.source_system,
                affected_systems=req.affected_systems,
                topic=req.problem_signature or req.matter or "Federation delta",
                summary=req.summary,
                evidence_refs=req.evidence_refs,
                chat_ref=req.chat_ref,
                status=req.status,
            )
            provider_result = {"written": True, "readback": provider_write}
            record["provider_proof_state"] = "PROVIDER_WRITE_ACKNOWLEDGED"
        except Exception as exc:
            provider_result = {"written": False, "reason": f"provider_write_failed:{type(exc).__name__}"}
            record["provider_proof_state"] = "PROVIDER_WRITE_FAILED"
    else:
        record["provider_proof_state"] = "LOCAL_RUNTIME_ONLY"

    save_json(STATE_PATH, data)
    return {
        "accepted": True,
        "duplicate": False,
        "delta_id": delta_id,
        "affected_systems": req.affected_systems,
        "provider": provider_result,
        "proof_state": record["provider_proof_state"],
        "note": "Provider-side completion is asserted only when the provider adapter returns a write acknowledgement.",
    }
