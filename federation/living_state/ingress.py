from __future__ import annotations

"""Normalized durable ingress for the Federation Living State graph.

The ingress is event-driven, not a scheduler. A host/sensor supplies an envelope;
this module validates, normalizes, applies and atomically commits the journal
Delta + snapshot + idempotency receipt with a compare-and-swap head check.

EDPF prediction/outcome support is deliberately an ingress binding only. A host
must supply an explicit forecast probability or later observed outcome. This
module never derives forecast probabilities from policy-market scores and never
calls a model/provider itself.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json, re
from typing import Any, Mapping

from benchmarking.cfbe_omega.epistemic_decision_prediction_fabric_v1 import (
    Prediction,
    PredictionOutcome,
)
from .canary import learning_event
from .edpf_prediction_adapter import (
    OPEN_STATE as EDPF_OPEN_STATE,
    RESOLVED_FALSE_STATE as EDPF_RESOLVED_FALSE_STATE,
    RESOLVED_TRUE_STATE as EDPF_RESOLVED_TRUE_STATE,
    ProspectiveOutcomeRecord,
    ProspectivePredictionRecord,
    record_prospective_prediction,
    resolve_prospective_prediction,
)
from .store import LivingStateStore
from .types import (
    AUTHORITY_CEILING, ContextState, FabricError, LearningClass, NodeKind,
    ProofMaturity, Provenance, RouteTelemetry, WorldNode, _authority_ok, _id,
    _parse_time, digest,
)

INGRESS_SCHEMA="FEDERATION-LIVING-STATE-INGRESS-V1"
EDPF_PREDICTION_EVENT="EDPF_PREDICTION"
EDPF_OUTCOME_EVENT="EDPF_OUTCOME"
_EVENT_CLASSES={"NODE_STATE","ROUTE_TELEMETRY","CONTEXT_STATE","LEARNING","BENCHMARK",EDPF_PREDICTION_EVENT,EDPF_OUTCOME_EVENT}
_SECRET_KEYS={"password","passwd","secret","token","api_key","apikey","private_key","authorization","cookie","access_key","client_secret"}
_SECRET_VALUE_PATTERNS=(re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),re.compile(r"\bAIza[0-9A-Za-z_-]{20,}"),re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),re.compile(r"\bBearer\s+[A-Za-z0-9._~-]{16,}",re.I))


def _now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _contains_secret(value:Any)->bool:
    if isinstance(value,Mapping):
        for k,v in value.items():
            key=str(k).lower().replace("-","_")
            if key in _SECRET_KEYS or any(x in key for x in ("password","private_key","client_secret")): return True
            if _contains_secret(v): return True
        return False
    if isinstance(value,(list,tuple,set)): return any(_contains_secret(x) for x in value)
    text=str(value)
    return any(p.search(text) for p in _SECRET_VALUE_PATTERNS)


def _require_payload(payload:Mapping[str,Any], keys:tuple[str,...], code:str)->None:
    missing=[key for key in keys if key not in payload]
    if missing: raise ValueError(code+":"+",".join(sorted(missing)))


@dataclass(frozen=True)
class IngressEnvelope:
    event_id:str
    event_class:str
    source_ref:str
    observed_at:str
    proof_ref:str
    proof_maturity:ProofMaturity
    object_id:str
    object_kind:str
    state:str
    payload:Mapping[str,Any]
    ttl_seconds:int=3600
    confidence:float=.7
    matter_scope:str="GLOBAL"
    sensitivity:str="PUBLIC_SAFE"
    authority_ceiling:str=AUTHORITY_CEILING

    def validate(self, *, allow_private_local:bool=False):
        _id(self.event_id,"event_id"); _id(self.object_id,"object_id"); _parse_time(self.observed_at)
        if self.event_class not in _EVENT_CLASSES: raise ValueError("unsupported event_class")
        if not self.source_ref or not self.proof_ref or not self.state: raise ValueError("source/proof/state required")
        if self.ttl_seconds<=0 or not 0<=self.confidence<=1: raise ValueError("invalid ttl/confidence")
        if not _authority_ok(self.authority_ceiling): raise ValueError("ingress authority exceeds A1")
        if self.sensitivity not in {"PUBLIC_SAFE","PRIVATE_LOCAL"}: raise ValueError("invalid sensitivity")
        if self.sensitivity=="PRIVATE_LOCAL" and not allow_private_local: raise FabricError("private local ingress requires explicit private-store admission")
        if self.sensitivity=="PUBLIC_SAFE" and _contains_secret(self.payload): raise FabricError("secret-shaped material rejected from public-safe ingress")
        if self.event_class in {EDPF_PREDICTION_EVENT,EDPF_OUTCOME_EVENT}:
            if self.object_kind!=NodeKind.EXPERIMENT.value: raise ValueError("EDPF ingress requires EXPERIMENT object_kind")
            p=dict(self.payload)
            if self.event_class==EDPF_PREDICTION_EVENT:
                if self.proof_maturity in {ProofMaturity.UNKNOWN,ProofMaturity.DECLARED}: raise ValueError("EDPF prediction ingress proof maturity too weak")
                if self.state!=EDPF_OPEN_STATE: raise ValueError("EDPF prediction ingress state mismatch")
                _require_payload(p,("mission_id","system_source_head_sha","mission_snapshot_digest","predictor_source_fingerprint","predictor_version","predictor_id","domain","event","probability","expected_value","expected_latency","expected_owner_burden"),"EDPF_PREDICTION_PAYLOAD_REQUIRED")
            else:
                if self.proof_maturity in {ProofMaturity.UNKNOWN,ProofMaturity.DECLARED}: raise ValueError("EDPF outcome ingress proof maturity too weak")
                _require_payload(p,("occurred","realised_value","realised_latency","realised_owner_burden","proof_refs"),"EDPF_OUTCOME_PAYLOAD_REQUIRED")
                if not isinstance(p["occurred"],bool): raise ValueError("EDPF outcome occurred must be boolean")
                expected=EDPF_RESOLVED_TRUE_STATE if p["occurred"] else EDPF_RESOLVED_FALSE_STATE
                if self.state!=expected: raise ValueError("EDPF outcome ingress state mismatch")
        return self

    @property
    def envelope_sha256(self):
        d=asdict(self); d["proof_maturity"]=self.proof_maturity.value
        return digest(d)


@dataclass(frozen=True)
class IngressReceipt:
    event_id:str
    envelope_sha256:str
    disposition:str
    base_event_head:str
    new_event_head:str
    snapshot_sha256:str
    readback_verified:bool
    private_payload_returned:bool=False
    external_effects:int=0
    @property
    def receipt_sha256(self): return digest(asdict(self))


class LivingStateIngress:
    def __init__(self, store:LivingStateStore, *, fabric_id:str="FEDERATION", allow_private_local:bool=False):
        self.store=store; self.fabric_id=fabric_id; self.allow_private_local=allow_private_local
        self.store.connection.execute("""CREATE TABLE IF NOT EXISTS living_state_ingress_receipts(
          fabric_id TEXT NOT NULL,event_id TEXT NOT NULL,envelope_sha256 TEXT NOT NULL,
          disposition TEXT NOT NULL,base_event_head TEXT NOT NULL,new_event_head TEXT NOT NULL,
          snapshot_sha256 TEXT NOT NULL,source_ref TEXT NOT NULL,observed_at TEXT NOT NULL,created_at TEXT NOT NULL,
          PRIMARY KEY(fabric_id,event_id))""")
        self.store.connection.commit()

    def _existing(self,event_id:str):
        return self.store.connection.execute("SELECT * FROM living_state_ingress_receipts WHERE fabric_id=? AND event_id=?",(self.fabric_id,event_id)).fetchone()

    def _apply(self,model,envelope:IngressEnvelope):
        prov=Provenance(envelope.source_ref,envelope.proof_ref,envelope.observed_at,envelope.proof_maturity,envelope.ttl_seconds,envelope.confidence,envelope.authority_ceiling,envelope.matter_scope,envelope.sensitivity,"INGRESS").validate()
        p=dict(envelope.payload)
        if envelope.event_class=="NODE_STATE":
            model.observe_node(WorldNode(envelope.object_id,NodeKind(envelope.object_kind),str(p.pop("label",envelope.object_id)),envelope.state,p,prov))
        elif envelope.event_class=="ROUTE_TELEMETRY":
            model.observe_route_telemetry(RouteTelemetry(envelope.object_id,str(p["mission_id"]),envelope.observed_at,bool(p["success"]),float(p.get("latency_ms",0)),float(p.get("cost_units",0)),float(p.get("owner_burden",0)),float(p.get("proof_freshness",.5)),float(p.get("proof_strength",.5)),float(p.get("risk",0)),tuple(p.get("failure_domains",())),envelope.proof_ref,envelope.matter_scope,False))
        elif envelope.event_class=="CONTEXT_STATE":
            model.observe_context(ContextState(envelope.object_id,int(p["used_units"]),int(p["capacity_units"]),float(p.get("duplicate_ratio",0)),int(p.get("stale_items",0)),tuple(p.get("verified_facts",())),tuple(p.get("adverse_evidence",())),tuple(p.get("contradictions",())),tuple(p.get("gaps",())),tuple(p.get("blockers",())),tuple(p.get("decisions",())),tuple(p.get("source_refs",()))))
        elif envelope.event_class=="LEARNING":
            model.observe_learning(learning_event(learning_class=LearningClass(str(p["learning_class"])),fingerprint=str(p["fingerprint"]),observed_at=envelope.observed_at,matter_scope=envelope.matter_scope,route_id=str(p.get("route_id","NONE")),signal=str(p["signal"]),diagnosis=str(p["diagnosis"]),hypothesis=str(p.get("hypothesis","UNKNOWN")),test_ref=str(p.get("test_ref",envelope.proof_ref)),result_ref=str(p.get("result_ref",envelope.proof_ref)),proof_refs=tuple(p.get("proof_refs",(envelope.proof_ref,))),recurrence=int(p.get("recurrence",1)),independent_evidence=bool(p.get("independent_evidence",False)),privacy_sensitive=envelope.sensitivity=="PRIVATE_LOCAL"))
        elif envelope.event_class==EDPF_PREDICTION_EVENT:
            prediction=Prediction(prediction_id=envelope.object_id,predictor_id=str(p["predictor_id"]),domain=str(p["domain"]),event=str(p["event"]),probability=float(p["probability"]),expected_value=float(p["expected_value"]),expected_latency=float(p["expected_latency"]),expected_owner_burden=float(p["expected_owner_burden"]),evidence_refs=tuple(p.get("evidence_refs",())))
            record_prospective_prediction(model,ProspectivePredictionRecord(mission_id=str(p["mission_id"]),system_source_head_sha=str(p["system_source_head_sha"]),mission_snapshot_digest=str(p["mission_snapshot_digest"]),predictor_source_fingerprint=str(p["predictor_source_fingerprint"]),predictor_version=str(p["predictor_version"]),observed_at=envelope.observed_at,prediction_proof_ref=envelope.proof_ref,prediction=prediction,matter_scope=envelope.matter_scope,sensitivity=envelope.sensitivity,ttl_seconds=envelope.ttl_seconds))
        elif envelope.event_class==EDPF_OUTCOME_EVENT:
            outcome=PredictionOutcome(prediction_id=envelope.object_id,occurred=bool(p["occurred"]),realised_value=float(p["realised_value"]),realised_latency=float(p["realised_latency"]),realised_owner_burden=float(p["realised_owner_burden"]),proof_refs=tuple(p["proof_refs"]))
            resolve_prospective_prediction(model,ProspectiveOutcomeRecord(prediction_id=envelope.object_id,observed_at=envelope.observed_at,outcome_source_ref=envelope.source_ref,proof_maturity=envelope.proof_maturity,outcome=outcome,matter_scope=envelope.matter_scope,sensitivity=envelope.sensitivity,ttl_seconds=envelope.ttl_seconds))
        else:
            model.observe_benchmark(envelope.object_id,envelope.observed_at,envelope.proof_ref)

    @staticmethod
    def _head(connection,fabric_id):
        row=connection.execute("SELECT sequence,event_digest FROM living_state_events WHERE fabric_id=? ORDER BY sequence DESC LIMIT 1",(fabric_id,)).fetchone()
        return (0,"GENESIS") if row is None else (int(row["sequence"]),str(row["event_digest"]))

    def ingest(self,envelope:IngressEnvelope):
        envelope.validate(allow_private_local=self.allow_private_local); h=envelope.envelope_sha256
        existing=self._existing(envelope.event_id)
        if existing:
            if str(existing["envelope_sha256"])!=h: raise FabricError("event_id reused with different payload")
            return IngressReceipt(envelope.event_id,h,"DUPLICATE_IDEMPOTENT",str(existing["base_event_head"]),str(existing["new_event_head"]),str(existing["snapshot_sha256"]),True)

        model=self.store.restore(fabric_id=self.fabric_id); base_count=model.event_count; base_head=model.event_head_digest
        self._apply(model,envelope)
        if model.external_effects: raise FabricError("ingress unexpectedly created external effect")
        delta=model.export_event_log()[base_count:]; snapshot=model.snapshot(now=envelope.observed_at); created=_now(); c=self.store.connection.cursor(); c.execute("BEGIN IMMEDIATE")
        try:
            if self._existing(envelope.event_id): raise FabricError("concurrent ingress event collision")
            db_count,db_head=self._head(self.store.connection,self.fabric_id)
            if db_count!=base_count or db_head!=base_head: raise FabricError("INGRESS_CAS_HEAD_DRIFT")
            for e in delta:
                c.execute("INSERT INTO living_state_events(fabric_id,sequence,event_digest,prior_digest,event_type,object_id,payload_json,created_at) VALUES(?,?,?,?,?,?,?,?)",(self.fabric_id,int(e["sequence"]),str(e["event_digest"]),str(e["prior_digest"]),str(e["event_type"]),str(e["object_id"]),json.dumps(e["payload"],sort_keys=True,separators=(",",":"),ensure_ascii=False,default=str),created))
            c.execute("INSERT OR IGNORE INTO living_state_snapshots(fabric_id,snapshot_sha256,event_head_digest,event_count,observed_at,payload_json,created_at) VALUES(?,?,?,?,?,?,?)",(self.fabric_id,snapshot["snapshot_sha256"],snapshot["event_head_digest"],snapshot["event_count"],envelope.observed_at,json.dumps(snapshot,sort_keys=True,separators=(",",":"),ensure_ascii=False,default=str),created))
            c.execute("INSERT INTO living_state_ingress_receipts VALUES(?,?,?,?,?,?,?,?,?,?)",(self.fabric_id,envelope.event_id,h,"APPLIED",base_head,model.event_head_digest,snapshot["snapshot_sha256"],envelope.source_ref,envelope.observed_at,created))
            self.store.connection.commit()
        except Exception:
            self.store.connection.rollback(); raise
        restored=self.store.restore(fabric_id=self.fabric_id); readback=restored.snapshot(now=envelope.observed_at)["snapshot_sha256"]==snapshot["snapshot_sha256"]
        if not readback: raise FabricError("ingress semantic readback mismatch")
        return IngressReceipt(envelope.event_id,h,"APPLIED",base_head,model.event_head_digest,snapshot["snapshot_sha256"],True)


def run_ingress_canary():
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        with LivingStateStore(Path(td)/"living.sqlite3") as store:
            ingress=LivingStateIngress(store)
            e=IngressEnvelope("evt:1","NODE_STATE","provider-sensor","2026-08-28T06:00:00+00:00","provider-proof",ProofMaturity.PROVIDER_READBACK,"provider:GITHUB",NodeKind.PROVIDER.value,"READY",{"label":"GitHub","latency_ms":20})
            r1=ingress.ingest(e); r2=ingress.ingest(e); model=store.restore(); estimate=model.state_estimate("provider:GITHUB",now=e.observed_at)
            conflict=False
            try: ingress.ingest(IngressEnvelope(**{**e.__dict__,"state":"DOWN"}))
            except FabricError: conflict=True
            secret=False
            try:
                fake_token="sk-"+("fixture"*4)
                ingress.ingest(IngressEnvelope("evt:secret","NODE_STATE","s",e.observed_at,"p",ProofMaturity.SOURCE_READBACK,"surface:X",NodeKind.SURFACE.value,"READY",{"api_key":fake_token}))
            except FabricError: secret=True
            checks={"provider_event_applied":r1.disposition=="APPLIED" and estimate.state=="READY","duplicate_is_idempotent":r2.disposition=="DUPLICATE_IDEMPOTENT" and model.event_count==1,"conflicting_event_id_fails_closed":conflict,"public_secret_shape_rejected":secret,"receipt_has_no_private_payload":not r1.private_payload_returned,"journal_readback_verified":r1.readback_verified,"zero_external_effects":model.external_effects==0}
            return {"schema":"FEDERATION-LIVING-STATE-INGRESS-CANARY-V1","status":"PASS" if all(checks.values()) else "FAIL","count":len(checks),"checks":checks,"external_effects":model.external_effects,"receipt_sha256":digest({"checks":checks,"head":model.event_head_digest}),"truth_boundary":{"host_invoked_not_background_daemon":True,"exactly_once_is_store_scoped_transactional":True,"provider_liveness_not_inferred_from_ingress_code":True,"private_payload_not_returned_in_receipt":True,"external_effect_authority_created":False}}

__all__=["INGRESS_SCHEMA","EDPF_PREDICTION_EVENT","EDPF_OUTCOME_EVENT","IngressEnvelope","IngressReceipt","LivingStateIngress","run_ingress_canary"]