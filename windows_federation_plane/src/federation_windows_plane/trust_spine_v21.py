from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import base64, hashlib, json, os
from typing import Any, Mapping

def canonical_bytes(v: Any)->bytes:return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def sha256_hex(v:bytes)->str:return hashlib.sha256(v).hexdigest()
def parse_utc(v:str)->datetime:
    d=datetime.fromisoformat(v.replace("Z","+00:00"))
    if d.tzinfo is None: raise ValueError("TIMEZONE_REQUIRED")
    return d.astimezone(timezone.utc)
def _b64e(v:bytes)->str:return base64.urlsafe_b64encode(v).decode().rstrip("=")
def _b64d(v:str)->bytes:return base64.urlsafe_b64decode(v+"="*(-len(v)%4))

class ECDSASigner:
    def __init__(self,key:Any):self._key=key
    @classmethod
    def generate(cls):
        from cryptography.hazmat.primitives.asymmetric import ec
        return cls(ec.generate_private_key(ec.SECP256R1()))
    def public_spki_b64(self)->str:
        from cryptography.hazmat.primitives import serialization
        return _b64e(self._key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo))
    def sign_b64(self,payload:bytes)->str:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        return _b64e(self._key.sign(payload,ec.ECDSA(hashes.SHA256())))
    @staticmethod
    def verify_spki_b64(spki:str,payload:bytes,sig_b64:str)->bool:
        from cryptography.hazmat.primitives import hashes,serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
        try:
            key=serialization.load_der_public_key(_b64d(spki)); sig=_b64d(sig_b64)
            if not isinstance(key,ec.EllipticCurvePublicKey): return False
            if len(sig)==64:sig=encode_dss_signature(int.from_bytes(sig[:32],"big"),int.from_bytes(sig[32:],"big"))
            key.verify(sig,payload,ec.ECDSA(hashes.SHA256()));return True
        except Exception:return False

@dataclass(frozen=True)
class CapabilityEnvelope:
    schema:str;device_id:str;device_generation:int;mission_id:str;task_id:str;capability:str;args_sha256:str;source_epoch:str;policy_epoch:str;capability_manifest_digest:str;effect_class:str;posture_floor:int;nonce:str;issued_at:str;expires_at:str;execution_lease_id:str;prepare_digest:str|None=None
    def payload(self):return asdict(self)
    def digest(self):return sha256_hex(canonical_bytes(self.payload()))
@dataclass(frozen=True)
class SignedCapability:
    envelope:CapabilityEnvelope;signature_b64:str
    @classmethod
    def issue(cls,e:CapabilityEnvelope,s:ECDSASigner):return cls(e,s.sign_b64(canonical_bytes(e.payload())))
    def verify(self,*,authority_spki_b64:str,expected_device_id:str,expected_device_generation:int,expected_source_epoch:str,expected_policy_epoch:str,expected_manifest_digest:str,actual_args:Mapping[str,Any],allowed_capabilities:set[str],actual_posture_score:int,now:datetime,seen_nonces:set[str])->None:
        e=self.envelope
        if not ECDSASigner.verify_spki_b64(authority_spki_b64,canonical_bytes(e.payload()),self.signature_b64):raise PermissionError("CAPABILITY_SIGNATURE_INVALID")
        checks=[(e.device_id==expected_device_id,"DEVICE_ID_FENCE"),(e.device_generation==expected_device_generation,"DEVICE_GENERATION_FENCE"),(e.source_epoch==expected_source_epoch,"SOURCE_EPOCH_FENCE"),(e.policy_epoch==expected_policy_epoch,"POLICY_EPOCH_FENCE"),(e.capability_manifest_digest==expected_manifest_digest,"CAPABILITY_MANIFEST_FENCE"),(e.capability in allowed_capabilities,"CAPABILITY_NOT_ALLOWLISTED"),(sha256_hex(canonical_bytes(dict(actual_args)))==e.args_sha256,"ARGS_DIGEST_MISMATCH"),(actual_posture_score>=e.posture_floor,"POSTURE_FLOOR_NOT_MET"),(e.nonce not in seen_nonces,"NONCE_REPLAY")]
        for ok,code in checks:
            if not ok:raise PermissionError(code)
        cur=now.astimezone(timezone.utc)
        if cur<parse_utc(e.issued_at):raise PermissionError("CAPABILITY_NOT_YET_VALID")
        if cur>=parse_utc(e.expires_at):raise PermissionError("CAPABILITY_EXPIRED")
        seen_nonces.add(e.nonce)

@dataclass(frozen=True)
class PostureEnvelope:
    schema:str;device_id:str;device_generation:int;tpm_state:str;secure_boot:bool|None;bitlocker:bool|None;defender:bool|None;firewall:bool|None;os_build:str;patch_age_days:int|None;agent_version:str;agent_sha256:str;clock_skew_seconds:int;key_status:str;session_state:str;power_state:str;observed_at:str
    def score(self)->int:
        s=100
        if self.tpm_state!="TPM_PLATFORM":s-=25
        for v in(self.secure_boot,self.defender,self.firewall):s-=20 if v is False else 5 if v is None else 0
        s-=10 if self.bitlocker is False else 3 if self.bitlocker is None else 0
        if self.patch_age_days is not None and self.patch_age_days>45:s-=min(20,(self.patch_age_days-45)//5+1)
        if abs(self.clock_skew_seconds)>300:s-=20
        if self.key_status!="ACTIVE":s-=40
        return max(0,s)
@dataclass(frozen=True)
class ExecutionLease:
    lease_id:str;task_id:str;device_id:str;device_generation:int;source_epoch:str;policy_epoch:str;issued_at:str;expires_at:str
    def verify(self,*,task_id:str,device_id:str,device_generation:int,source_epoch:str,policy_epoch:str,now:datetime)->None:
        for ok,code in[(self.task_id==task_id,"LEASE_TASK_FENCE"),(self.device_id==device_id,"LEASE_DEVICE_FENCE"),(self.device_generation==device_generation,"LEASE_GENERATION_FENCE"),(self.source_epoch==source_epoch,"LEASE_SOURCE_FENCE"),(self.policy_epoch==policy_epoch,"LEASE_POLICY_FENCE")]:
            if not ok:raise PermissionError(code)
        if now.astimezone(timezone.utc)>=parse_utc(self.expires_at):raise PermissionError("LEASE_EXPIRED")
@dataclass(frozen=True)
class PreparedEffect:
    target:str;diff_sha256:str;input_sha256:str;source_epoch:str;policy_epoch:str
    def digest(self):return sha256_hex(canonical_bytes(asdict(self)))
@dataclass(frozen=True)
class CommitPermit:
    prepare_digest:str;issued_at:str;expires_at:str
    def verify(self,p:PreparedEffect,now:datetime)->None:
        if p.digest()!=self.prepare_digest:raise PermissionError("PREPARE_DIGEST_MISMATCH")
        if now.astimezone(timezone.utc)>=parse_utc(self.expires_at):raise PermissionError("COMMIT_PERMIT_EXPIRED")

class ReceiptChain:
    def __init__(self):self._r=[]
    @property
    def receipts(self):return [dict(x) for x in self._r]
    def append(self,body:Mapping[str,Any]):
        item={"sequence":len(self._r)+1,"previous_receipt_sha256":self._r[-1]["receipt_sha256"] if self._r else "0"*64,"body":dict(body)};item["receipt_sha256"]=sha256_hex(canonical_bytes(item));self._r.append(item);return dict(item)
    @staticmethod
    def verify(rs:list[Mapping[str,Any]])->None:
        prev="0"*64
        for i,raw in enumerate(rs,1):
            x=dict(raw);digest=x.pop("receipt_sha256",None)
            if x.get("sequence")!=i:raise ValueError("RECEIPT_SEQUENCE_INVALID")
            if x.get("previous_receipt_sha256")!=prev:raise ValueError("RECEIPT_PREDECESSOR_INVALID")
            if digest!=sha256_hex(canonical_bytes(x)):raise ValueError("RECEIPT_DIGEST_INVALID")
            prev=str(digest)
class EncryptedReceiptSpool:
    def __init__(self,key:bytes,aad:bytes=b"FUSE-WOAF-SPOOL-V2"):
        if len(key) not in{16,24,32}:raise ValueError("AES_KEY_LENGTH_INVALID")
        self.key,self.aad=key,aad
    def seal(self,rs:list[Mapping[str,Any]])->bytes:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        n=os.urandom(12);return n+AESGCM(self.key).encrypt(n,canonical_bytes([dict(x) for x in rs]),self.aad)
    def open(self,b:bytes):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        if len(b)<13:raise ValueError("SPOOL_BLOB_INVALID")
        v=json.loads(AESGCM(self.key).decrypt(b[:12],b[12:],self.aad));
        if not isinstance(v,list):raise ValueError("SPOOL_PAYLOAD_INVALID")
        return [dict(x) for x in v]

class DeviceState(str,Enum):ENROLLED="ENROLLED";ACTIVE="ACTIVE";DEGRADED="DEGRADED";QUARANTINED="QUARANTINED";ROTATED="ROTATED";RECOVERED="RECOVERED";RETIRED="RETIRED"
_T={DeviceState.ENROLLED:{DeviceState.ACTIVE,DeviceState.QUARANTINED,DeviceState.RETIRED},DeviceState.ACTIVE:{DeviceState.DEGRADED,DeviceState.QUARANTINED,DeviceState.ROTATED,DeviceState.RETIRED},DeviceState.DEGRADED:{DeviceState.ACTIVE,DeviceState.QUARANTINED,DeviceState.ROTATED,DeviceState.RETIRED},DeviceState.QUARANTINED:{DeviceState.ROTATED,DeviceState.RETIRED},DeviceState.ROTATED:{DeviceState.RECOVERED,DeviceState.QUARANTINED,DeviceState.RETIRED},DeviceState.RECOVERED:{DeviceState.ACTIVE,DeviceState.QUARANTINED,DeviceState.RETIRED},DeviceState.RETIRED:set()}
@dataclass
class DeviceLifecycle:
    state:DeviceState=DeviceState.ENROLLED;generation:int=1
    def transition(self,target:DeviceState):
        if target not in _T[self.state]:raise ValueError(f"DEVICE_STATE_TRANSITION_INVALID:{self.state}->{target}")
        if target==DeviceState.ROTATED:self.generation+=1
        self.state=target
@dataclass(frozen=True)
class UpdateManifest:
    version:int;binary_sha256:str;issued_at:str;expires_at:str;previous_version:int
    def payload(self):return asdict(self)
@dataclass
class UpdateState:
    current_version:int;last_known_good_version:int;current_sha256:str
    def stage(self,m:UpdateManifest,sig:str,spki:str,*,now:datetime,observed_binary_sha256:str):
        if not ECDSASigner.verify_spki_b64(spki,canonical_bytes(m.payload()),sig):raise PermissionError("UPDATE_SIGNATURE_INVALID")
        if now.astimezone(timezone.utc)>=parse_utc(m.expires_at):raise PermissionError("UPDATE_METADATA_EXPIRED")
        if m.version<=self.current_version:raise PermissionError("UPDATE_ROLLBACK_REJECTED")
        if m.previous_version!=self.current_version:raise PermissionError("UPDATE_PREDECESSOR_MISMATCH")
        if m.binary_sha256!=observed_binary_sha256:raise PermissionError("UPDATE_BINARY_DIGEST_MISMATCH")
    def promote(self,m:UpdateManifest):self.last_known_good_version,self.current_version,self.current_sha256=self.current_version,m.version,m.binary_sha256
    def rollback(self,sha:str):self.current_version,self.current_sha256=self.last_known_good_version,sha

class CanaryPhase(str,Enum):UNLOCKED="UNLOCKED";LOCK_TRANSITION="LOCK_TRANSITION";LOCKED_BACKGROUND="LOCKED_BACKGROUND";WAITING_UNLOCK="WAITING_UNLOCK";RECOVERY="RECOVERY";COMPLETE="COMPLETE"
_REQUIRED_CANARY_EVIDENCE={CanaryPhase.UNLOCKED:{"filesystem","sqlite","queue","worker","python","git","hashing","checkpoint","dns","capability_passport","resource_governor","receipt_validation","identity_possession","identity_renewal","fence_rejection","nonce_replay_rejection","posture_rejection","lease_expiry","prepare_commit_mismatch","receipt_tamper","spool_roundtrip","update_lkg","quarantine_rotation"},CanaryPhase.LOCK_TRANSITION:{"lock_transition"},CanaryPhase.LOCKED_BACKGROUND:{"background_continuity"},CanaryPhase.WAITING_UNLOCK:{"waiting_unlock"},CanaryPhase.RECOVERY:{"reconnect_cursor","crash_recovery"},CanaryPhase.COMPLETE:{"real_allowlisted_task","device_signed_receipt"}}
class Canary001V3:
    def __init__(self):self.i=0;self.phases=list(CanaryPhase)
    @property
    def phase(self):return self.phases[self.i]
    def advance(self,e:set[str]):
        m=_REQUIRED_CANARY_EVIDENCE[self.phase]-e
        if m:raise ValueError("CANARY_EVIDENCE_MISSING:"+",".join(sorted(m)))
        if self.phase!=CanaryPhase.COMPLETE:self.i+=1
        return self.phase

DENIED_COMMAND_FAMILY=frozenset({"shell","powershell","cmd","exec","command","script"})
@dataclass(frozen=True)
class ArtifactCapsuleManifest:
    capsule_id:str;version:str;platform:str;arch:str;runtime:str;entrypoint:str;artifact_uri:str;byte_size:int;sha256:str;signature_ref:str;source_epoch:str;policy_epoch:str;capabilities:tuple[str,...];effect_ceiling:str;resource_requirements:Mapping[str,Any];expires_at:str;rollback_ref:str|None=None
    def validate(self,*,now:datetime):
        if not self.artifact_uri.startswith("https://"):raise ValueError("CAPSULE_HTTPS_REQUIRED")
        if self.byte_size<=0:raise ValueError("CAPSULE_SIZE_INVALID")
        if len(self.sha256)!=64:raise ValueError("CAPSULE_SHA256_INVALID")
        if now.astimezone(timezone.utc)>=parse_utc(self.expires_at):raise ValueError("CAPSULE_EXPIRED")
        if any(c in DENIED_COMMAND_FAMILY for c in self.capabilities):raise ValueError("CAPSULE_CAPABILITY_DENIED")
    def verify_bytes(self,payload:bytes,*,now:datetime):
        self.validate(now=now)
        if len(payload)!=self.byte_size:raise ValueError("CAPSULE_SIZE_MISMATCH")
        if sha256_hex(payload)!=self.sha256:raise ValueError("CAPSULE_DIGEST_MISMATCH")
@dataclass(frozen=True)
class NodeCapabilities:
    trust_mode:str;logical_cores:int;memory_budget_mb:int;gpu_class:str;wasm_simd:bool;wasm_threads:bool;disk_cache_mb:int;network_rtt_ms:int;power_state:str;visibility_state:str
@dataclass(frozen=True)
class ResourceGrant:cpu_workers:int;memory_mb:int;gpu_allowed:bool;max_seconds:int
class ResourceSovereigntyGovernor:
    def grant(self,n:NodeCapabilities,*,requested_workers:int,requested_memory_mb:int,requested_gpu:bool,max_seconds:int)->ResourceGrant:
        if n.trust_mode not in{"B0_EPHEMERAL_LOW_TRUST","N1_PORTABLE_USER","P2_TRUSTED_OWNER"}:raise ValueError("NODE_TRUST_MODE_INVALID")
        c=max(1,min(n.logical_cores-1 if n.logical_cores>2 else 1,16));c=min(c,max(1,n.logical_cores//2)) if n.visibility_state=="visible" else c
        return ResourceGrant(max(1,min(requested_workers,c)),max(64,min(requested_memory_mb,max(64,n.memory_budget_mb))),bool(requested_gpu and n.gpu_class!="NONE"),max(1,min(max_seconds,900 if n.trust_mode=="B0_EPHEMERAL_LOW_TRUST" else 3600)))
def placement_score(n:NodeCapabilities,*,needs_gpu:bool,min_memory_mb:int)->float:
    if min_memory_mb>n.memory_budget_mb or(needs_gpu and n.gpu_class=="NONE"):return float("-inf")
    return {"B0_EPHEMERAL_LOW_TRUST":1,"N1_PORTABLE_USER":1.5,"P2_TRUSTED_OWNER":2}.get(n.trust_mode,0)+min(n.logical_cores,32)/8+min(n.memory_budget_mb,32768)/8192-min(max(n.network_rtt_ms,0),1000)/1000

def relay_mode(*,oidc_issuer:str|None,oidc_jwks_url:str|None)->str:
    i,j=bool(oidc_issuer),bool(oidc_jwks_url)
    if i and j:
        if not str(oidc_issuer).startswith("https://") or not str(oidc_jwks_url).startswith("https://"):raise ValueError("OIDC_HTTPS_REQUIRED")
        return "FULL_MCP_AGENT"
    if not i and not j:return "AGENT_ONLY_BOOTSTRAP"
    raise ValueError("OIDC_CONFIG_MIXED_FAIL_CLOSED")
AGENT_ONLY_ALLOWED_ROUTES=frozenset({"/healthz","/agent/enroll","/agent/poll","/agent/complete","/node","/node/worker.js","/node/native-bootstrap.ps1"})
ALLOWLISTED_CAPABILITIES=frozenset({"health","inventory","hash_workspace_file","woaf_canary_v3"})
B0_ALLOWLISTED_CAPABILITIES=frozenset({"health","inventory"})
def agent_only_route_allowed(path:str)->bool:return path in AGENT_ONLY_ALLOWED_ROUTES
