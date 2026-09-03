from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple

class Severity(str, Enum):
    LOW='LOW'; MEDIUM='MEDIUM'; HIGH='HIGH'; CRITICAL='CRITICAL'

class Disposition(str, Enum):
    HEALTHY='HEALTHY'
    AUTO_REPAIR_NOW='AUTO_REPAIR_NOW'
    AUTO_REPAIR_FENCED='AUTO_REPAIR_FENCED'
    AUTO_REPAIR_CANARY='AUTO_REPAIR_CANARY'
    WAITING_EXACT_CAPABILITY='WAITING_EXACT_CAPABILITY'
    OWNER_OR_PROVIDER_TRIGGER_REQUIRED='OWNER_OR_PROVIDER_TRIGGER_REQUIRED'
    QUARANTINE_AND_REROUTE='QUARANTINE_AND_REROUTE'

@dataclass(frozen=True)
class Observation:
    kind: str
    subject: str
    actual: Dict[str, Any]
    expected: Dict[str, Any]
    source_ref: str
    authority: str='READ_ONLY'
    reversible: bool=True
    cost_class: str='ZERO_OR_INCLUDED'

@dataclass(frozen=True)
class Finding:
    finding_id: str
    finding_type: str
    subject: str
    severity: Severity
    observed_state: Dict[str, Any]
    expected_state: Dict[str, Any]
    source_ref: str
    disposition: Disposition
    reason: str
    repair_route: str
    proof_floor: Tuple[str, ...]
    rollback: str
    resume_condition: str=''
    provider_effect_allowed: bool=False

    def arc_finding(self) -> Dict[str, Any]:
        return {
            'finding_id': self.finding_id,
            'source_ref': self.source_ref,
            'observed_state': self.observed_state,
            'expected_state': self.expected_state,
            'severity': self.severity.value,
            'affected_scope': self.subject,
            'proof_state': 'OBSERVED',
            'current_authority': 'READ_ONLY_SENSOR',
            'cost_class': 'ZERO_OR_INCLUDED',
            'reversibility': True,
            'confidence': 1.0,
            'sentinel_disposition': self.disposition.value,
            'provider_effect_allowed': False,
        }

class KioasSentinel:
    VERSION='1.0.0'
    PROVIDER_EFFECT=False
    HIGH_RISK_ACTIONS={'SEND_STATUS_EMAIL','SNAPSHOT_PROJECT','UPSERT_SCRIPT_FILE','INSTALL_MODULE','ROLLBACK_PROJECT'}

    def evaluate(self, observations: Iterable[Observation]) -> List[Finding]:
        return [f for o in observations for f in self._evaluate_one(o)]

    def _evaluate_one(self, o: Observation) -> List[Finding]:
        handlers={
            'apps_script_permission': self._permission,
            'generic_invocation': self._generic_invocation,
            'scheduler_liveness': self._scheduler,
            'backup_freshness': self._backup,
            'repeated_route_failure': self._repeated_route,
            'source_identity': self._source_identity,
        }
        fn=handlers.get(o.kind)
        return fn(o) if fn else []

    def _permission(self,o:Observation)->List[Finding]:
        public_writers=int(o.actual.get('public_writer_count',0) or 0)
        if public_writers<=int(o.expected.get('public_writer_count',0) or 0): return []
        return [Finding('SENT-PERM-'+o.subject,'PUBLIC_WRITER_EXPOSURE',o.subject,Severity.CRITICAL,o.actual,o.expected,o.source_ref,Disposition.OWNER_OR_PROVIDER_TRIGGER_REQUIRED,'Apps Script source has public/domain writer authority; sensor cannot revoke provider permissions.','PROVIDER_NATIVE_PERMISSION_REMOVAL',('PRIVATE_RECOVERY_COPY','PERMISSION_READBACK_PUBLIC_WRITER_COUNT_0'),'Retain private recovery copy; no readmission until exact permission readback.','permission_removal_capability_available_or_permission_metadata_changes')]

    def _generic_invocation(self,o:Observation)->List[Finding]:
        wrapper=str(o.actual.get('wrapper_risk','MEDIUM')).upper(); callee=str(o.actual.get('callee_risk','CRITICAL')).upper()
        order={'LOW':1,'MEDIUM':2,'HIGH':3,'CRITICAL':4}; effective=max((wrapper,callee),key=lambda x:order.get(x,4))
        if order.get(effective,4)<=order.get(str(o.expected.get('max_generic_risk','MEDIUM')).upper(),2): return []
        return [Finding('SENT-AUTH-'+o.subject,'GENERIC_INVOCATION_EFFECT_INHERITANCE',o.subject,Severity.CRITICAL,o.actual,o.expected,o.source_ref,Disposition.AUTO_REPAIR_FENCED,'Generic dispatcher risk must inherit target function intrinsic effect class.','PATCH_EXISTING_POLICY_AND_SOURCE_THEN_NEGATIVE_CANARY',('POLICY_READBACK','SOURCE_TEST','UNAUTHORIZED_CALL_REJECTED'),'Restore prior policy row/source if hardening regresses safe reads.')]

    def _scheduler(self,o:Observation)->List[Finding]:
        if bool(o.actual.get('heartbeat_fresh',False)): return []
        return [Finding('SENT-GNS3-'+o.subject,'SCHEDULER_LIVENESS_GAP',o.subject,Severity.HIGH,o.actual,o.expected,o.source_ref,Disposition.WAITING_EXACT_CAPABILITY,'Scheduler liveness cannot be repaired without exact Apps Script trigger/function authority.','READ_ONLY_CANARY_THEN_SAME_SINGLETON_RECOVERY',('TRIGGER_COUNT_READBACK','CANARY','UNATTENDED_HEARTBEAT','ADAPTER_SEMANTIC_PROOF'),'Never create a second scheduler fleet.','action_specific_apps_script_executor_available')]

    def _backup(self,o:Observation)->List[Finding]:
        age=float(o.actual.get('age_hours',1e9)); limit=float(o.expected.get('max_age_hours',24))
        if age<=limit:return []
        return [Finding('SENT-BACKUP-'+o.subject,'STALE_RECOVERY_ANCHOR',o.subject,Severity.HIGH,o.actual,o.expected,o.source_ref,Disposition.AUTO_REPAIR_CANARY,'Mutation must not proceed without a fresh complete recovery anchor.','CREATE_PRIVATE_PROVIDER_COPY_THEN_VERIFY',('OWNER_ONLY_PERMISSION_READBACK','COPY_ID','TIMESTAMP'),'Delete only the newly-created failed copy if readback fails.')]

    def _repeated_route(self,o:Observation)->List[Finding]:
        repeat=int(o.actual.get('unchanged_repeat_count',0));
        if repeat<1:return []
        return [Finding('SENT-ROUTE-'+o.subject,'UNCHANGED_FAILED_ROUTE',o.subject,Severity.MEDIUM,o.actual,o.expected,o.source_ref,Disposition.QUARANTINE_AND_REROUTE,'Unchanged failure fingerprint may not be retried.','SELECT_MATERIALLY_DIFFERENT_ROUTE',('FAILURE_FINGERPRINT','MATERIAL_DELTA_BEFORE_RETRY'),'No rollback; this is a route hold.','route_or_authority_or_source_epoch_materially_changes')]

    def _source_identity(self,o:Observation)->List[Finding]:
        if o.actual.get('provider_id')==o.expected.get('provider_id'):return []
        return [Finding('SENT-ID-'+o.subject,'SOURCE_IDENTITY_DRIFT',o.subject,Severity.HIGH,o.actual,o.expected,o.source_ref,Disposition.AUTO_REPAIR_FENCED,'Canonical control identity differs from provider-read current identity.','UPDATE_CONTROL_POINTER_WITH_EXACT_READBACK',('PROVIDER_IDENTITY','CONTROL_ROW_READBACK'),'Restore previous control pointer on mismatch.')]

def sentinel_receipt(findings: Iterable[Finding]) -> Dict[str, Any]:
    fs=list(findings)
    return {'schema':'kioas.sentinel.receipt.v1','version':KioasSentinel.VERSION,'provider_effect':False,'finding_count':len(fs),'findings':[asdict(f) for f in fs]}
