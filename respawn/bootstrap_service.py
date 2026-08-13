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
STATE_PATH = Path(os.getenv("FEDERATION_RESPAWN_STATE", ROOT / "runtime_state.json"))

app = FastAPI(title="Federation Respawn Bootstrap", version="1.1.0")


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
