from __future__ import annotations
import base64,binascii,hashlib,hmac,json,os,platform,time,urllib.error,urllib.request
from dataclasses import asdict,dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from . import __version__
try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except ImportError:
    InvalidSignature = Exception
    Ed25519PublicKey = None

APP_NAME="FUSE Toka"
DEFAULT_CONTROL_PLANE=os.environ.get("FUSE_TOKA_CONTROL_PLANE","").rstrip("/")
STATE_DIR=Path(os.environ.get("FUSE_TOKA_STATE_DIR",Path.home()/".fuse_toka"))
MAX_MANIFEST_LIFETIME_SECONDS=7*24*60*60
CLOCK_SKEW_SECONDS=300
SIGNED_UPDATE_FIELDS=("channel","expires_at_epoch","issued_at_epoch","root_id","sha256","url","version")

@dataclass(frozen=True)
class RuntimeStatus:
    app:str; version:str; os:str; machine:str; control_plane_configured:bool; update_channel:str; state_dir:str

def status()->RuntimeStatus:
    return RuntimeStatus(APP_NAME,__version__,platform.system(),platform.machine(),bool(DEFAULT_CONTROL_PLANE),os.environ.get("FUSE_TOKA_CHANNEL","stable"),str(STATE_DIR))

def _json_request(url:str,payload:dict[str,Any]|None=None,timeout:float=4.0)->dict[str,Any]:
    data=None if payload is None else json.dumps(payload,sort_keys=True).encode()
    req=urllib.request.Request(url,data=data,method="GET" if data is None else "POST",headers={"Content-Type":"application/json","User-Agent":f"FUSE-Toka/{__version__}"})
    with urllib.request.urlopen(req,timeout=timeout) as resp:
        return json.loads(resp.read(1_000_000).decode())

def heartbeat()->dict[str,Any]:
    st=status()
    if not DEFAULT_CONTROL_PLANE:
        return {"state":"CONTROL_PLANE_NOT_CONFIGURED","runtime":asdict(st)}
    payload={"client_version":st.version,"platform":st.os,"machine_arch":st.machine,"channel":st.update_channel,"sent_at_epoch":int(time.time())}
    try:
        return {"state":"CONNECTED","runtime":asdict(st),"server":_json_request(f"{DEFAULT_CONTROL_PLANE}/v1/heartbeat",payload)}
    except (urllib.error.URLError,TimeoutError,ValueError,json.JSONDecodeError) as exc:
        return {"state":"CONTROL_PLANE_UNREACHABLE","error":type(exc).__name__,"runtime":asdict(st)}

def verify_download(path:Path,expected_sha256:str)->bool:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return hmac.compare_digest(h.hexdigest().lower(),expected_sha256.strip().lower())

def canonical_update_payload(update:dict[str,Any])->bytes:
    return json.dumps({key:update[key] for key in SIGNED_UPDATE_FIELDS},sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("utf-8")

def _strict_b64(value:str,expected_length:int)->bytes:
    try:
        raw=base64.b64decode(value,validate=True)
    except (binascii.Error,ValueError,TypeError) as exc:
        raise ValueError("invalid_base64") from exc
    if len(raw)!=expected_length:
        raise ValueError("invalid_length")
    return raw

def _validate_manifest(update:dict[str,Any],runtime:RuntimeStatus,now:int)->str|None:
    required=set(SIGNED_UPDATE_FIELDS)|{"signature"}
    missing=sorted(required-set(update))
    if missing:
        return "UPDATE_REJECTED_BAD_MANIFEST:"+",".join(missing)
    if not all(isinstance(update[k],str) and update[k] for k in ("version","url","sha256","signature","root_id","channel")):
        return "UPDATE_REJECTED_BAD_MANIFEST:invalid_string"
    if len(update["version"])>64 or len(update["root_id"])!=64:
        return "UPDATE_REJECTED_BAD_MANIFEST:invalid_identity"
    if len(update["sha256"])!=64 or any(c not in "0123456789abcdefABCDEF" for c in update["sha256"]):
        return "UPDATE_REJECTED_BAD_MANIFEST:invalid_sha256"
    parsed=urlsplit(update["url"])
    if parsed.scheme!="https" or not parsed.netloc or parsed.username or parsed.password or parsed.fragment:
        return "UPDATE_REJECTED_UNSAFE_URL"
    if update["channel"]!=runtime.update_channel:
        return "UPDATE_HELD_CHANNEL_MISMATCH"
    try:
        issued=int(update["issued_at_epoch"]); expires=int(update["expires_at_epoch"])
    except (TypeError,ValueError):
        return "UPDATE_REJECTED_BAD_MANIFEST:invalid_time"
    if issued>now+CLOCK_SKEW_SECONDS or expires<=now:
        return "UPDATE_REJECTED_EXPIRED_OR_FUTURE_MANIFEST"
    if expires-issued>MAX_MANIFEST_LIFETIME_SECONDS or expires<=issued:
        return "UPDATE_REJECTED_BAD_MANIFEST:invalid_lifetime"
    return None

def verify_update_manifest(update:dict[str,Any],runtime:RuntimeStatus|None=None,now:int|None=None)->tuple[bool,str]:
    st=runtime or status(); current=int(time.time()) if now is None else int(now)
    invalid=_validate_manifest(update,st,current)
    if invalid:
        return False,invalid
    public_key_b64=os.environ.get("FUSE_TOKA_TRUST_ROOT_ED25519_PUBLIC_KEY_B64","")
    configured_root=os.environ.get("FUSE_TOKA_TRUST_ROOT_ID","")
    if not public_key_b64 or not configured_root:
        return False,"UPDATE_HELD_TRUST_ROOT_KEY_UNAVAILABLE"
    if Ed25519PublicKey is None:
        return False,"UPDATE_HELD_SIGNATURE_VERIFIER_UNAVAILABLE"
    try:
        public_key=_strict_b64(public_key_b64,32)
        signature=_strict_b64(update["signature"],64)
    except ValueError:
        return False,"UPDATE_REJECTED_BAD_SIGNATURE_ENCODING"
    derived_root=hashlib.sha256(public_key).hexdigest()
    if not hmac.compare_digest(configured_root.lower(),derived_root) or not hmac.compare_digest(update["root_id"].lower(),derived_root):
        return False,"UPDATE_HELD_UNTRUSTED_ROOT"
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature,canonical_update_payload(update))
    except (InvalidSignature,ValueError):
        return False,"UPDATE_REJECTED_INVALID_SIGNATURE"
    return True,"UPDATE_MANIFEST_SIGNATURE_VERIFIED"

def signed_update_state()->dict[str,Any]:
    hb=heartbeat()
    if hb.get("state")!="CONNECTED":
        return {"state":"NO_UPDATE_SESSION","heartbeat":hb}
    update=hb.get("server",{}).get("update")
    if not update:
        return {"state":"CURRENT","heartbeat":hb}
    ok,reason=verify_update_manifest(update)
    if not ok:
        return {"state":reason,"candidate":str(update.get("version",""))[:64],"heartbeat":hb}
    candidate={key:update[key] for key in SIGNED_UPDATE_FIELDS}
    return {"state":"UPDATE_MANIFEST_SIGNATURE_VERIFIED_DOWNLOAD_NOT_AUTO_APPLIED","candidate":candidate,"heartbeat":hb}
