from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import hashlib
import json

from .config import settings
from .schemas import SecurityEvent, Assessment, CandidateMetrics, CertificationResult, SealedEvent
from .normalize import normalize_event
from .provenance import seal_event
from .fusion import assess_events
from .storage import build_case_store, IdempotencyCollision
from .evidence_store import build_evidence_store
from .event_bus import build_event_bus
from .policy import plan_response
from .evolution.certifier import certify
from .orchestration import aegis_current_mission_plan, mission_plan_public_dict
from .evidence_chain import verify_evidence_chain
from .adversarial.court import run_adversarial_court

app = FastAPI(title="AEGIS-Ω", version="0.3.0", description="Defensive adversarial mobile threat-defense control plane")
store = build_case_store(settings.case_store, settings.gcp_project)
evidence_store = build_evidence_store(settings.evidence_bucket)
event_bus = build_event_bus(settings.gcp_project, settings.pubsub_topic)

class AssessmentRequest(BaseModel):
    request_id: str = Field(min_length=8, max_length=128)
    events: list[SecurityEvent] = Field(min_length=1, max_length=256)

def _request_hash(events: list[SecurityEvent]) -> str:
    body = []
    for event in events:
        row = event.model_dump(mode="json")
        if "timestamp" not in event.model_fields_set:
            row["timestamp"] = "SERVER_ASSIGNED"
        body.append(row)
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def _assessment_from_case(case: dict) -> Assessment:
    return Assessment.model_validate(case["assessment"])

def _ensure_outbox_delivery(case: dict) -> None:
    assessment = _assessment_from_case(case)
    state = store.outbox_state(assessment.case_id)
    if state and state.get("delivered") is True:
        return
    try:
        provider_ref = event_bus.publish_assessment(assessment)
        store.mark_outbox_delivered(assessment.case_id, str(provider_ref or ""))
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"error":"AEGIS_OUTBOX_DELIVERY_PENDING","case_id":assessment.case_id,"retry_safe":True}) from exc

@app.get("/healthz")
def healthz():
    return {"status":"ok","service":"aegis-omega","version":"0.3.0","env":settings.env,"mode":"defensive-only","adversarial_mode":"synthetic-defensive-only"}

@app.post("/v1/events", response_model=Assessment)
def ingest_event(event: SecurityEvent):
    request_hash = _request_hash([event])
    try: normalized = normalize_event(event)
    except ValueError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc
    request_id=f"event:{normalized.event_id}"
    try: existing=store.resolve_request(request_id,request_hash)
    except IdempotencyCollision as exc: raise HTTPException(status_code=409,detail=str(exc)) from exc
    if existing:
        _ensure_outbox_delivery(existing); return _assessment_from_case(existing)
    sealed=seal_event(normalized,settings.hmac_secret,settings.hmac_key_id)
    assessment=assess_events([normalized],settings.manual_approval_threshold,settings.high_risk_threshold)
    evidence_store.persist(sealed)
    try: stored=store.put(assessment,[sealed],request_id=request_id,request_hash=request_hash)
    except IdempotencyCollision as exc: raise HTTPException(status_code=409,detail=str(exc)) from exc
    _ensure_outbox_delivery(stored); return _assessment_from_case(stored)

@app.post("/v1/assess", response_model=Assessment)
def assess(req: AssessmentRequest):
    request_hash=_request_hash(req.events)
    try: normalized=[normalize_event(e) for e in req.events]
    except ValueError as exc: raise HTTPException(status_code=403,detail=str(exc)) from exc
    try: existing=store.resolve_request(req.request_id,request_hash)
    except IdempotencyCollision as exc: raise HTTPException(status_code=409,detail=str(exc)) from exc
    if existing:
        _ensure_outbox_delivery(existing); return _assessment_from_case(existing)
    sealed=[seal_event(e,settings.hmac_secret,settings.hmac_key_id) for e in normalized]
    assessment=assess_events(normalized,settings.manual_approval_threshold,settings.high_risk_threshold)
    for item in sealed: evidence_store.persist(item)
    try: stored=store.put(assessment,sealed,request_id=req.request_id,request_hash=request_hash)
    except IdempotencyCollision as exc: raise HTTPException(status_code=409,detail=str(exc)) from exc
    _ensure_outbox_delivery(stored); return _assessment_from_case(stored)

@app.get("/v1/cases/{case_id}")
def get_case(case_id: str):
    case=store.get(case_id)
    if not case: raise HTTPException(status_code=404,detail="case not found")
    try:
        sealed=[SealedEvent.model_validate(item) for item in case.get("events",[])]
        chain_valid=verify_evidence_chain(sealed,case.get("evidence_chain",[]))
    except Exception as exc: raise HTTPException(status_code=500,detail="case evidence chain unreadable") from exc
    if not chain_valid: raise HTTPException(status_code=500,detail="case evidence chain verification failed")
    plan=plan_response(Assessment.model_validate(case["assessment"]))
    return {**case,"evidence_chain_valid":True,"outbox_delivery":store.outbox_state(case_id),"response_plan":{"automated":plan.automated,"approval_required":plan.approval_required}}

@app.post("/v1/evolution/certify", response_model=CertificationResult)
def certify_candidate(metrics: CandidateMetrics): return certify(metrics)

@app.get("/v1/orchestration/profile")
def orchestration_profile(): return mission_plan_public_dict(aegis_current_mission_plan())

@app.get("/v1/adversarial/profile")
def adversarial_profile():
    return {"schema":"AEGIS_ADVERSARIAL_PROFILE_V1","defensive_only":True,"synthetic_scenarios_only":True,"components":["OMEGA_ADVERSARY_TWIN","OMEGA_EVIDENCE_IMMUNE_GRAPH","OMEGA_SHADOW_NEURAL_SENTINEL","OMEGA_EVOLUTION_TOURNAMENT","OMEGA_ADVERSARIAL_COURT"],"neural_decision_authority":False,"automatic_model_promotion":False,"provider_effect_authority":False,"high_impact_response_requires_human_approval":True}

@app.post("/v1/adversarial/court")
def adversarial_court():
    receipt=run_adversarial_court()
    return {"schema":receipt.schema,"scenario_count":receipt.scenario_count,"scenario_pass_count":receipt.scenario_pass_count,"threat_recall_synthetic":receipt.threat_recall,"benign_specificity_synthetic":receipt.benign_specificity,"neural_shadow_holdout_accuracy_synthetic":receipt.neural_receipt.holdout_accuracy,"auto_promotion_performed":receipt.auto_promotion_performed,"provider_effect_performed":receipt.provider_effect_performed,"stable_promotion_authorized":receipt.stable_promotion_authorized,"receipt_sha256":receipt.receipt_sha256}
