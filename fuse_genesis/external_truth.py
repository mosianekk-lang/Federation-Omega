from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

HEX64=re.compile(r"^[0-9a-f]{64}$")

class ExternalTruthError(ValueError): pass

class TruthState(str,Enum):
    VERIFIED_TRUE="VERIFIED_TRUE"
    VERIFIED_FALSE="VERIFIED_FALSE"
    UNKNOWN="UNKNOWN"
    DISPUTED="DISPUTED"
    STALE="STALE"
    INVALID="INVALID"

def canon(value:Any)->str:
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)

def digest(value:Any)->str:
    return sha256(canon(value).encode("utf-8")).hexdigest()

def _required(value:Any,label:str)->str:
    v=str(value).strip()
    if not v: raise ExternalTruthError(f"{label}_REQUIRED")
    return v

def _hex64(value:Any,label:str)->str:
    v=str(value).lower()
    if not HEX64.fullmatch(v): raise ExternalTruthError(f"{label}_INVALID")
    return v

def parse_aware_time(value:str)->datetime:
    raw=_required(value,"OBSERVED_AT")
    if raw.endswith("Z"): raw=raw[:-1]+"+00:00"
    try:
        dt=datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ExternalTruthError("OBSERVED_AT_INVALID") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ExternalTruthError("OBSERVED_AT_TIMEZONE_REQUIRED")
    return dt.astimezone(timezone.utc)

@dataclass(frozen=True,slots=True)
class BooleanSchema:
    true_values:tuple[Any,...]=()
    false_values:tuple[Any,...]=()

    def parse(self,value:Any)->TruthState:
        if type(value) is bool:
            return TruthState.VERIFIED_TRUE if value else TruthState.VERIFIED_FALSE
        if any(type(value) is type(v) and value==v for v in self.true_values):
            return TruthState.VERIFIED_TRUE
        if any(type(value) is type(v) and value==v for v in self.false_values):
            return TruthState.VERIFIED_FALSE
        return TruthState.INVALID

STRICT_BOOLEAN=BooleanSchema()

@dataclass(frozen=True,slots=True)
class StatusContract:
    true_statuses:frozenset[str]
    false_statuses:frozenset[str]
    unknown_statuses:frozenset[str]=frozenset()

    def normalize(self,value:Any)->TruthState:
        if type(value) is not str:
            return TruthState.INVALID
        if value in self.true_statuses: return TruthState.VERIFIED_TRUE
        if value in self.false_statuses: return TruthState.VERIFIED_FALSE
        if value in self.unknown_statuses: return TruthState.UNKNOWN
        return TruthState.INVALID

@dataclass(frozen=True,slots=True)
class TruthReceipt:
    provider_id:str
    operation_id:str
    subject_id:str
    source_epoch_digest:str
    observed_at:str
    truth_state:TruthState
    semantic_code:str
    evidence_sha256:str
    transport_ok:bool
    raw_schema_id:str

    def __post_init__(self):
        _required(self.provider_id,"PROVIDER_ID")
        _required(self.operation_id,"OPERATION_ID")
        _required(self.subject_id,"SUBJECT_ID")
        _hex64(self.source_epoch_digest,"SOURCE_EPOCH_DIGEST")
        parse_aware_time(self.observed_at)
        if not isinstance(self.truth_state,TruthState):
            raise ExternalTruthError("TRUTH_STATE_INVALID")
        _required(self.semantic_code,"SEMANTIC_CODE")
        _hex64(self.evidence_sha256,"EVIDENCE_SHA256")
        if type(self.transport_ok) is not bool:
            raise ExternalTruthError("TRANSPORT_OK_MUST_BE_BOOLEAN")
        _required(self.raw_schema_id,"RAW_SCHEMA_ID")

    @property
    def receipt_sha256(self)->str:
        return digest({
            "provider_id":self.provider_id,
            "operation_id":self.operation_id,
            "subject_id":self.subject_id,
            "source_epoch_digest":self.source_epoch_digest,
            "observed_at":parse_aware_time(self.observed_at).isoformat(),
            "truth_state":self.truth_state.value,
            "semantic_code":self.semantic_code,
            "evidence_sha256":self.evidence_sha256,
            "transport_ok":self.transport_ok,
            "raw_schema_id":self.raw_schema_id,
        })

@dataclass(frozen=True,slots=True)
class ReconciledTruth:
    subject_id:str
    state:TruthState
    receipt_sha256s:tuple[str,...]
    reasons:tuple[str,...]

class ExternalTruthNormalizer:
    def normalize_boolean(self,value:Any,*,schema:BooleanSchema=STRICT_BOOLEAN)->TruthState:
        if not isinstance(schema,BooleanSchema):
            raise ExternalTruthError("BOOLEAN_SCHEMA_REQUIRED")
        return schema.parse(value)

    def normalize_status(self,value:Any,*,contract:StatusContract)->TruthState:
        if not isinstance(contract,StatusContract):
            raise ExternalTruthError("STATUS_CONTRACT_REQUIRED")
        return contract.normalize(value)

    def normalize_semantic_result(
        self,
        *,
        transport_ok:Any,
        semantic:Mapping[str,Any],
        applied_field:str="applied",
        boolean_schema:BooleanSchema=STRICT_BOOLEAN,
    )->TruthState:
        if type(transport_ok) is not bool:
            return TruthState.INVALID
        if transport_ok is False:
            return TruthState.UNKNOWN
        if not isinstance(semantic,Mapping) or applied_field not in semantic:
            return TruthState.INVALID
        return self.normalize_boolean(semantic[applied_field],schema=boolean_schema)

    def make_receipt(
        self,
        *,
        provider_id:str,
        operation_id:str,
        subject_id:str,
        source_epoch_digest:str,
        observed_at:str,
        truth_state:TruthState,
        semantic_code:str,
        raw_evidence:Any,
        transport_ok:bool,
        raw_schema_id:str,
    )->TruthReceipt:
        return TruthReceipt(
            provider_id=provider_id,
            operation_id=operation_id,
            subject_id=subject_id,
            source_epoch_digest=source_epoch_digest,
            observed_at=observed_at,
            truth_state=truth_state,
            semantic_code=semantic_code,
            evidence_sha256=digest(raw_evidence),
            transport_ok=transport_ok,
            raw_schema_id=raw_schema_id,
        )

    def classify_currentness(
        self,
        receipt:TruthReceipt,
        *,
        current_source_epoch:str,
        now:str,
        max_age_seconds:float,
    )->TruthState:
        _hex64(current_source_epoch,"CURRENT_SOURCE_EPOCH")
        if max_age_seconds<=0: raise ExternalTruthError("MAX_AGE_INVALID")
        if receipt.source_epoch_digest!=current_source_epoch:
            return TruthState.STALE
        n=parse_aware_time(now)
        observed=parse_aware_time(receipt.observed_at)
        age=(n-observed).total_seconds()
        if age<0:
            return TruthState.INVALID
        if age>max_age_seconds:
            return TruthState.STALE
        return receipt.truth_state

    def reconcile(
        self,
        receipts:Sequence[TruthReceipt],
        *,
        subject_id:str,
        current_source_epoch:str,
        now:str,
        max_age_seconds:float,
    )->ReconciledTruth:
        subject=_required(subject_id,"SUBJECT_ID")
        relevant=[r for r in receipts if r.subject_id==subject]
        if not relevant:
            return ReconciledTruth(subject,TruthState.UNKNOWN,(),("NO_RECEIPTS",))

        classified=[]
        stale=[]
        invalid=[]
        for r in relevant:
            state=self.classify_currentness(
                r,current_source_epoch=current_source_epoch,now=now,max_age_seconds=max_age_seconds)
            if state is TruthState.STALE: stale.append(r)
            elif state is TruthState.INVALID: invalid.append(r)
            else: classified.append((r,state))

        decisive={state for _,state in classified if state in {TruthState.VERIFIED_TRUE,TruthState.VERIFIED_FALSE}}
        receipts_sha=tuple(sorted(r.receipt_sha256 for r in relevant))
        if len(decisive)>1:
            return ReconciledTruth(subject,TruthState.DISPUTED,receipts_sha,("CONTRADICTORY_FRESH_RECEIPTS",))
        if TruthState.VERIFIED_TRUE in decisive:
            return ReconciledTruth(subject,TruthState.VERIFIED_TRUE,receipts_sha,())
        if TruthState.VERIFIED_FALSE in decisive:
            return ReconciledTruth(subject,TruthState.VERIFIED_FALSE,receipts_sha,())
        if any(state is TruthState.DISPUTED for _,state in classified):
            return ReconciledTruth(subject,TruthState.DISPUTED,receipts_sha,("UPSTREAM_DISPUTED",))
        if any(state is TruthState.INVALID for _,state in classified) or invalid:
            return ReconciledTruth(subject,TruthState.INVALID,receipts_sha,("INVALID_FRESH_RECEIPT",))
        if classified:
            return ReconciledTruth(subject,TruthState.UNKNOWN,receipts_sha,("FRESH_BUT_NONDECISIVE",))
        if stale:
            return ReconciledTruth(subject,TruthState.STALE,receipts_sha,("ONLY_STALE_RECEIPTS",))
        return ReconciledTruth(subject,TruthState.UNKNOWN,receipts_sha,("NO_DECISIVE_RECEIPT",))

def require_verified_true(result:ReconciledTruth)->bool:
    if not isinstance(result,ReconciledTruth):
        raise ExternalTruthError("RECONCILED_TRUTH_REQUIRED")
    if result.state is not TruthState.VERIFIED_TRUE:
        raise ExternalTruthError(f"VERIFIED_TRUE_REQUIRED:{result.state.value}")
    return True
