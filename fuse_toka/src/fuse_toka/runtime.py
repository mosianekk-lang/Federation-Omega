from __future__ import annotations
import hashlib,json,os,platform,time,urllib.error,urllib.request
from dataclasses import asdict,dataclass
from pathlib import Path
from typing import Any
from . import __version__
APP_NAME="FUSE Toka"; DEFAULT_CONTROL_PLANE=os.environ.get("FUSE_TOKA_CONTROL_PLANE","").rstrip("/"); STATE_DIR=Path(os.environ.get("FUSE_TOKA_STATE_DIR",Path.home()/".fuse_toka"))
@dataclass(frozen=True)
class RuntimeStatus:
    app:str; version:str; os:str; machine:str; control_plane_configured:bool; update_channel:str; state_dir:str
def status()->RuntimeStatus:
    return RuntimeStatus(APP_NAME,__version__,platform.system(),platform.machine(),bool(DEFAULT_CONTROL_PLANE),os.environ.get("FUSE_TOKA_CHANNEL","stable"),str(STATE_DIR))
def _json_request(url:str,payload:dict[str,Any]|None=None,timeout:float=4.0)->dict[str,Any]:
    data=None if payload is None else json.dumps(payload,sort_keys=True).encode(); req=urllib.request.Request(url,data=data,method="GET" if data is None else "POST",headers={"Content-Type":"application/json","User-Agent":f"FUSE-Toka/{__version__}"})
    with urllib.request.urlopen(req,timeout=timeout) as resp: return json.loads(resp.read(1_000_000).decode())
def heartbeat()->dict[str,Any]:
    st=status()
    if not DEFAULT_CONTROL_PLANE: return {"state":"CONTROL_PLANE_NOT_CONFIGURED","runtime":asdict(st)}
    payload={"client_version":st.version,"platform":st.os,"machine_arch":st.machine,"channel":st.update_channel,"sent_at_epoch":int(time.time())}
    try: return {"state":"CONNECTED","runtime":asdict(st),"server":_json_request(f"{DEFAULT_CONTROL_PLANE}/v1/heartbeat",payload)}
    except (urllib.error.URLError,TimeoutError,ValueError,json.JSONDecodeError) as exc: return {"state":"CONTROL_PLANE_UNREACHABLE","error":type(exc).__name__,"runtime":asdict(st)}
def verify_download(path:Path,expected_sha256:str)->bool:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest().lower()==expected_sha256.strip().lower()
def signed_update_state()->dict[str,Any]:
    hb=heartbeat()
    if hb.get("state")!="CONNECTED": return {"state":"NO_UPDATE_SESSION","heartbeat":hb}
    update=hb.get("server",{}).get("update")
    if not update: return {"state":"CURRENT","heartbeat":hb}
    required={"version","url","sha256","signature","root_id"}; missing=sorted(required-set(update))
    if missing: return {"state":"UPDATE_REJECTED_BAD_MANIFEST","missing":missing,"heartbeat":hb}
    trusted_root=os.environ.get("FUSE_TOKA_TRUST_ROOT_ID","")
    if not trusted_root or update.get("root_id")!=trusted_root: return {"state":"UPDATE_HELD_UNTRUSTED_ROOT","candidate":update.get("version"),"heartbeat":hb}
    return {"state":"UPDATE_MANIFEST_ACCEPTED_DOWNLOAD_NOT_AUTO_APPLIED","candidate":update,"heartbeat":hb}
