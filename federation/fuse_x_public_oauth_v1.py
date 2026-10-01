"""FUSE-owned X OAuth 2.0 PKCE public-client binder."""
from __future__ import annotations
from dataclasses import dataclass,asdict
import base64,ctypes,ctypes.wintypes,hashlib,http.server,json,os,secrets,socketserver,threading,time,urllib.parse,urllib.request,webbrowser
from pathlib import Path
from typing import Any,Callable,Protocol
SCHEMA="FUSE-X-PUBLIC-OAUTH-V1"; VERSION="1.0.0"
AUTH_URL="https://x.com/i/oauth2/authorize"; TOKEN_URL="https://api.x.com/2/oauth2/token"; DEFAULT_REDIRECT="http://localhost:8080/callback"; DEFAULT_SCOPES=("tweet.read","users.read","offline.access")
class OAuthError(RuntimeError): pass
class VaultError(RuntimeError): pass
class Vault(Protocol):
    def save(self,name:str,value:dict[str,Any])->None: ...
    def load(self,name:str)->dict[str,Any]|None: ...
class MemoryVault:
    def __init__(self): self.data={}
    def save(self,name,value): self.data[name]=json.loads(json.dumps(value))
    def load(self,name):
        value=self.data.get(name); return json.loads(json.dumps(value)) if value is not None else None
class _DATA_BLOB(ctypes.Structure):
    _fields_=[("cbData",ctypes.wintypes.DWORD),("pbData",ctypes.POINTER(ctypes.c_char))]
def _blob(data):
    buf=ctypes.create_string_buffer(data); return _DATA_BLOB(len(data),ctypes.cast(buf,ctypes.POINTER(ctypes.c_char))),buf
def _dpapi_protect(data):
    if os.name!="nt": raise VaultError("DPAPI_WINDOWS_ONLY")
    crypt32=ctypes.windll.crypt32; kernel32=ctypes.windll.kernel32; inp,keep=_blob(data); out=_DATA_BLOB()
    if not crypt32.CryptProtectData(ctypes.byref(inp),"FUSE-X",None,None,None,0,ctypes.byref(out)): raise VaultError("DPAPI_PROTECT_FAILED")
    try: return ctypes.string_at(out.pbData,out.cbData)
    finally: kernel32.LocalFree(out.pbData)
def _dpapi_unprotect(data):
    if os.name!="nt": raise VaultError("DPAPI_WINDOWS_ONLY")
    crypt32=ctypes.windll.crypt32; kernel32=ctypes.windll.kernel32; inp,keep=_blob(data); out=_DATA_BLOB()
    if not crypt32.CryptUnprotectData(ctypes.byref(inp),None,None,None,None,0,ctypes.byref(out)): raise VaultError("DPAPI_UNPROTECT_FAILED")
    try: return ctypes.string_at(out.pbData,out.cbData)
    finally: kernel32.LocalFree(out.pbData)
class WindowsDPAPIVault:
    def __init__(self,root=None):
        if os.name!="nt": raise VaultError("DPAPI_WINDOWS_ONLY")
        base=Path(os.environ.get("LOCALAPPDATA") or Path.home())/"FUSE"/"X"/"auth" if root is None else Path(root); base.mkdir(parents=True,exist_ok=True); self.root=base
    def _path(self,name):
        safe="".join(c for c in name if c.isalnum() or c in "-_.")
        if not safe: raise VaultError("VAULT_NAME_INVALID")
        return self.root/(safe+".dpapi")
    def save(self,name,value):
        raw=json.dumps(value,sort_keys=True,separators=(",",":")).encode(); enc=_dpapi_protect(raw); p=self._path(name); tmp=p.with_suffix(p.suffix+".tmp"); tmp.write_bytes(enc); os.replace(tmp,p)
    def load(self,name):
        p=self._path(name)
        if not p.exists(): return None
        return json.loads(_dpapi_unprotect(p.read_bytes()).decode())
@dataclass(frozen=True)
class OAuthAttempt:
    state:str; verifier:str; challenge:str; authorization_url:str; redirect_uri:str
@dataclass(frozen=True)
class TokenState:
    access_token:str; refresh_token:str|None; token_type:str; expires_at:int; scope:str
    def public_status(self): return {"has_access_token":bool(self.access_token),"has_refresh_token":bool(self.refresh_token),"token_type":self.token_type,"expires_at":self.expires_at,"scope":self.scope}
def _b64url(data): return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
def generate_verifier(): return _b64url(secrets.token_bytes(64))
def challenge_for(verifier): return _b64url(hashlib.sha256(verifier.encode()).digest())
def utc_epoch(): return int(time.time())
def build_attempt(client_id,redirect_uri=DEFAULT_REDIRECT,scopes=DEFAULT_SCOPES):
    client_id=client_id.strip()
    if not client_id: raise OAuthError("CLIENT_ID_REQUIRED")
    parsed=urllib.parse.urlsplit(redirect_uri)
    if parsed.scheme!="http" or parsed.hostname not in {"localhost","127.0.0.1","::1"}: raise OAuthError("LOOPBACK_REDIRECT_REQUIRED")
    state=_b64url(secrets.token_bytes(32)); verifier=generate_verifier(); challenge=challenge_for(verifier)
    params={"response_type":"code","client_id":client_id,"redirect_uri":redirect_uri,"scope":" ".join(scopes),"state":state,"code_challenge":challenge,"code_challenge_method":"S256"}
    return OAuthAttempt(state,verifier,challenge,AUTH_URL+"?"+urllib.parse.urlencode(params),redirect_uri)
def default_exchange(url,form):
    body=urllib.parse.urlencode(form).encode(); req=urllib.request.Request(url,data=body,method="POST",headers={"Content-Type":"application/x-www-form-urlencoded","Accept":"application/json","User-Agent":"FUSE-X-Public-OAuth/1.0"})
    try:
        with urllib.request.urlopen(req,timeout=30) as resp: payload=json.loads(resp.read().decode())
    except Exception as exc: raise OAuthError("TOKEN_EXCHANGE_FAILED") from exc
    if not isinstance(payload,dict) or not payload.get("access_token"): raise OAuthError("TOKEN_RESPONSE_INVALID")
    return payload
def token_state(payload,now=None):
    if not payload.get("access_token"): raise OAuthError("ACCESS_TOKEN_MISSING")
    now=utc_epoch() if now is None else now
    return TokenState(str(payload["access_token"]),str(payload.get("refresh_token")) if payload.get("refresh_token") else None,str(payload.get("token_type") or "bearer"),now+int(payload.get("expires_in") or 7200),str(payload.get("scope") or ""))
class PublicClientOAuth:
    def __init__(self,client_id,vault,name="owner",redirect_uri=DEFAULT_REDIRECT,exchange=None):
        if not client_id.strip(): raise OAuthError("CLIENT_ID_REQUIRED")
        self.client_id=client_id.strip(); self.vault=vault; self.name=name; self.redirect_uri=redirect_uri; self.exchange=exchange or default_exchange
    def start(self): return build_attempt(self.client_id,self.redirect_uri)
    def complete(self,attempt,callback_url_or_query):
        q=urllib.parse.urlsplit(callback_url_or_query).query if "://" in callback_url_or_query else callback_url_or_query.lstrip("?"); params=urllib.parse.parse_qs(q); state=(params.get("state") or [""])[0]; code=(params.get("code") or [""])[0]
        if state!=attempt.state: raise OAuthError("STATE_MISMATCH")
        if not code: raise OAuthError("AUTHORIZATION_CODE_MISSING")
        payload=self.exchange(TOKEN_URL,{"grant_type":"authorization_code","code":code,"redirect_uri":attempt.redirect_uri,"code_verifier":attempt.verifier,"client_id":self.client_id})
        st=token_state(payload); self.vault.save(self.name,asdict(st)); return st.public_status()
    def _load(self):
        raw=self.vault.load(self.name); return TokenState(**raw) if raw else None
    def status(self):
        st=self._load(); return {"configured":st is not None,**(st.public_status() if st else {"has_access_token":False,"has_refresh_token":False})}
    def access_token(self):
        st=self._load()
        if st is None: raise OAuthError("OAUTH_NOT_AUTHORIZED")
        if st.expires_at>utc_epoch()+60: return st.access_token
        if not st.refresh_token: raise OAuthError("REFRESH_TOKEN_MISSING")
        payload=self.exchange(TOKEN_URL,{"grant_type":"refresh_token","refresh_token":st.refresh_token,"client_id":self.client_id}); new=token_state(payload)
        if not new.refresh_token: new=TokenState(new.access_token,st.refresh_token,new.token_type,new.expires_at,new.scope or st.scope)
        self.vault.save(self.name,asdict(new)); return new.access_token
def local_browser_authorize(oauth,timeout_seconds=300,open_browser=None):
    attempt=oauth.start(); parsed=urllib.parse.urlsplit(attempt.redirect_uri); callback_path=parsed.path or "/callback"; holder={}; event=threading.Event()
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if urllib.parse.urlsplit(self.path).path!=callback_path: self.send_response(404); self.end_headers(); return
            holder["value"]=self.path; self.send_response(200); self.send_header("Content-Type","text/plain"); self.end_headers(); self.wfile.write(b"FUSE-X authorization received. You may close this window."); event.set()
        def log_message(self,format,*args): pass
    class Server(socketserver.TCPServer): allow_reuse_address=True
    with Server(("127.0.0.1",parsed.port or 8080),Handler) as server:
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start(); (open_browser or webbrowser.open)(attempt.authorization_url)
        if not event.wait(timeout_seconds): raise OAuthError("OAUTH_CONSENT_TIMEOUT")
        server.shutdown()
    return oauth.complete(attempt,holder["value"])
