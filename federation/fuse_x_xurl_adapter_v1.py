"""Read-only credential-isolation adapter for official X xurl CLI."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha256
import json, os, subprocess
from typing import Any, Callable

SCHEMA="FUSE-X-XURL-ADAPTER-V1"; VERSION="1.0.0"
READ_COMMANDS={"whoami","user","posts","timeline","mentions","bookmarks","likes","following","followers","search","read","lists","communities","spaces"}
MUTATING_COMMANDS={"post","reply","quote","delete","like","unlike","repost","unrepost","bookmark","unbookmark","follow","unfollow","mute","unmute","block","unblock","dm","chat","media","webhook"}
SECRET_FLAGS={"--bearer-token","--consumer-key","--consumer-secret","--access-token","--token-secret","--client-id","--client-secret","--verbose","-v"}
class PolicyError(RuntimeError): pass
class XurlAdapterError(RuntimeError):
    def __init__(self,category:str,code:int|None=None): super().__init__(category); self.category=category; self.code=code
@dataclass(frozen=True)
class AuthStatus:
    xurl_present:bool; app_count:int; oauth2_user_count:int; oauth1_present:bool; app_only_present:bool; redirect_uri_configured:bool
    def to_dict(self)->dict[str,Any]: return asdict(self)
Runner=Callable[[list[str],dict[str,str]],tuple[int,str,str]]
def _default_runner(argv,env):
    cp=subprocess.run(argv,text=True,capture_output=True,timeout=60,env=env); return cp.returncode,cp.stdout,cp.stderr
def _safe_env():
    env=dict(os.environ); env["NO_COLOR"]="1"; return env
def validate_args(args:list[str])->None:
    if not args: raise PolicyError("empty xurl invocation")
    lowered=[x.lower() for x in args]
    if any(flag in lowered for flag in SECRET_FLAGS): raise PolicyError("secret-bearing/verbose xurl flag prohibited")
    if any(x in {"-x","--request"} for x in lowered): raise PolicyError("HTTP method override prohibited")
    if any(x in MUTATING_COMMANDS for x in lowered): raise PolicyError("X account mutation prohibited")
    first=next((x for x in args if not x.startswith("-")),"")
    if first=="token": raise PolicyError("token material prohibited")
    if first=="auth":
        joined=" ".join(lowered)
        if not any(x in joined for x in ("auth status","auth apps list","auth apps redirect-uri get")): raise PolicyError("auth mutation/login prohibited inside agent adapter")
        return
    if first.startswith("/"):
        if not first.startswith("/2/"): raise PolicyError("only X API v2 raw GET paths allowed")
        return
    if first not in READ_COMMANDS: raise PolicyError(f"unsupported read-only xurl command: {first}")
def _safe_error_category(stderr,stdout,code):
    text=f"{stderr}\n{stdout}".lower()
    if "no apps registered" in text or "no credentials" in text: return "XURL_APP_NOT_CONFIGURED"
    if "oauth2" in text and ("none" in text or "token not found" in text): return "XURL_OAUTH_NOT_AUTHORIZED"
    if "client-not-enrolled" in text or "client-forbidden" in text: return "XURL_APP_NOT_ENROLLED"
    if "429" in text or "rate limit" in text: return "XURL_RATE_LIMITED"
    if "403" in text: return "XURL_FORBIDDEN"
    if "401" in text or "unauthorized" in text: return "XURL_UNAUTHORIZED"
    return f"XURL_EXIT_{code}"
class XurlReadOnlyAdapter:
    def __init__(self,binary="xurl",runner:Runner|None=None): self.binary=binary; self.runner=runner or _default_runner
    def _run(self,args):
        validate_args(args); code,out,err=self.runner([self.binary,*args],_safe_env())
        if code!=0: raise XurlAdapterError(_safe_error_category(err,out,code),code)
        return out,err
    def _json(self,args):
        out,_=self._run(args)
        try: value=json.loads(out.strip() or "{}")
        except json.JSONDecodeError as exc: raise XurlAdapterError("XURL_NON_JSON") from exc
        if not isinstance(value,dict): raise XurlAdapterError("XURL_JSON_OBJECT_REQUIRED")
        return value
    def auth_status(self):
        try: out,_=self._run(["auth","status"])
        except FileNotFoundError: return AuthStatus(False,0,0,False,False,False)
        lines=out.splitlines()
        return AuthStatus(True,
            sum(1 for line in lines if "client_id:" in line.lower() or "(no credentials)" in line.lower()),
            sum(1 for line in lines if "oauth2:" in line.lower() and "(none)" not in line.lower()),
            any("oauth1:" in line.lower() and "✓" in line for line in lines),
            any(("bearer:" in line.lower() or "app-only:" in line.lower()) and "✓" in line for line in lines),
            any("redirect_uri:" in line.lower() for line in lines))
    def whoami(self): return self._json(["whoami"])
    def timeline(self,max_results=100): return self._json(["timeline","-n",str(max(1,min(int(max_results),100)))])
    def search_recent(self,query,max_results=100): return self._json(["search",query,"-n",str(max(10,min(int(max_results),100)))])
    def bookmarks(self,max_results=100): return self._json(["bookmarks","-n",str(max(1,min(int(max_results),100)))])
    def mentions(self,max_results=100): return self._json(["mentions","-n",str(max(1,min(int(max_results),100)))])
    def raw_get(self,path):
        if not path.startswith("/2/"): raise PolicyError("only /2/ raw GET paths allowed")
        return self._json([path])
    def probe(self):
        status=self.auth_status(); result={"schema":SCHEMA,"version":VERSION,"auth":status.to_dict(),"authorized":False}
        if not status.xurl_present or not status.oauth2_user_count: return result
        try:
            me=self.whoami(); result["authorized"]=bool((me.get("data") or {}).get("id")); result["provider_user_id_present"]=result["authorized"]
        except XurlAdapterError as exc: result["provider_error"]=exc.category
        return result
def fingerprint_probe(probe): return sha256(json.dumps(probe,sort_keys=True,separators=(",",":")).encode()).hexdigest()
