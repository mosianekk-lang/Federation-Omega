"""Minimum-cost live provider court for FUSE-X finality."""
from __future__ import annotations
from dataclasses import dataclass,asdict
from hashlib import sha256
import json,urllib.parse,urllib.request
from typing import Any,Callable
SCHEMA="FUSE-X-MINIMAL-LIVE-CANARY-V1"; PRICING_EPOCH="2026-09-19"; PUBLISHED_USER_READ_USD=0.010; PUBLISHED_POST_READ_USD=0.005; DEFAULT_VARIABLE_COST_CAP_USD=0.020
class CanaryError(RuntimeError): pass
def _canonical(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def _hash(v): return sha256(_canonical(v)).hexdigest()
@dataclass(frozen=True)
class CanaryReceipt:
    schema:str; pricing_epoch:str; authorized_user_present:bool; home_post_count:int; user_response_hash:str; home_response_hash:str; estimated_resource_cost_usd:float; write_effects:int; content_disclosed_in_receipt:bool
    def to_dict(self): return asdict(self)
class MinimalXApiClient:
    def __init__(self,token_provider:Callable[[],str],timeout=30): self.token_provider=token_provider; self.timeout=timeout
    def _get(self,path,params=None):
        token=(self.token_provider() or "").strip()
        if not token: raise CanaryError("AUTHORIZED_TOKEN_UNAVAILABLE")
        if not path.startswith("/2/"): raise CanaryError("ONLY_X_API_V2_ALLOWED")
        url="https://api.x.com"+path
        if params: url+="?"+urllib.parse.urlencode({k:v for k,v in params.items() if v is not None},doseq=True)
        req=urllib.request.Request(url,method="GET",headers={"Accept":"application/json","Authorization":f"Bearer {token}","User-Agent":"FUSE-X-Minimal-Canary/1.0"})
        try:
            with urllib.request.urlopen(req,timeout=self.timeout) as resp: out=json.loads(resp.read().decode())
        except Exception as exc: raise CanaryError("X_API_READ_FAILED") from exc
        if not isinstance(out,dict): raise CanaryError("X_API_JSON_OBJECT_REQUIRED")
        return out
    def whoami(self): return self._get("/2/users/me",{"user.fields":"id"})
    def home_one(self,user_id): return self._get(f"/2/users/{user_id}/timelines/reverse_chronological",{"max_results":1,"tweet.fields":"id,created_at"})
def estimated_variable_cost(user_reads=1,post_reads=1): return round(user_reads*PUBLISHED_USER_READ_USD+post_reads*PUBLISHED_POST_READ_USD,6)
def run_minimal_live_canary(client,cost_cap_usd=DEFAULT_VARIABLE_COST_CAP_USD):
    if cost_cap_usd<estimated_variable_cost(1,1): raise CanaryError("COST_CAP_TOO_LOW_FOR_CANARY")
    me=client.whoami(); data=me.get("data") or {}; uid=str(data.get("id") or "")
    if not uid: raise CanaryError("AUTHORIZED_USER_ID_MISSING")
    home=client.home_one(uid); posts=home.get("data") or []; posts=[posts] if isinstance(posts,dict) else posts; valid=[p for p in posts if isinstance(p,dict) and p.get("id")]
    if not valid: raise CanaryError("HOME_TIMELINE_EMPTY_OR_UNAVAILABLE")
    est=estimated_variable_cost(1,len(valid))
    if est>cost_cap_usd: raise CanaryError("CANARY_COST_CAP_EXCEEDED")
    return CanaryReceipt(SCHEMA,PRICING_EPOCH,True,len(valid),_hash({"data":{"id_present":True}}),_hash({"ids":[str(p["id"]) for p in valid]}),est,0,False)
