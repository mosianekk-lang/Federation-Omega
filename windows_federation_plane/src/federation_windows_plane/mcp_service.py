from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from typing import Any
import uuid

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse

from .firestore_relay import FirestoreRelay
from .oidc_auth import OIDCTokenVerifier
from .trust_spine_v21 import relay_mode

BASE_SCOPE = "fuse.windows"


def _z(v: datetime) -> str:
    return v.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_error(exc: Exception, status: int = 400):
    return JSONResponse({"state": "FAILED_CLOSED", "error": str(exc)}, status_code=status)


def _device_auth(request: Request, body: bytes, relay: Any) -> str:
    device_id = request.headers.get("x-fuse-device-id", "")
    relay.verify_device_request(
        device_id=device_id,
        method=request.method,
        path=request.url.path,
        timestamp=request.headers.get("x-fuse-timestamp", ""),
        nonce=request.headers.get("x-fuse-nonce", ""),
        signature=request.headers.get("x-fuse-signature", ""),
        body=body,
    )
    return device_id


def _require_scope(scope: str = BASE_SCOPE) -> None:
    a = get_access_token()
    if a is None or scope not in a.scopes:
        raise PermissionError("OAUTH_SCOPE_REQUIRED:" + scope)


def build_server(*, relay: Any, issuer: str, resource_url: str, jwks_url: str) -> MCPServer:
    verifier = OIDCTokenVerifier(issuer=issuer, audience=resource_url, jwks_url=jwks_url)
    server = MCPServer(
        "FUSE Windows Sovereign Relay",
        version="2.4.0",
        instructions="Owner-controlled outbound-only Windows processing plane. Typed allowlisted tasks only.",
        token_verifier=verifier,
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(issuer),
            resource_server_url=AnyHttpUrl(resource_url),
            required_scopes=[BASE_SCOPE],
            validate_token_resource=True,
        ),
    )

    @server.tool(title="FUSE relay health", description="Return relay readiness.", annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
    def fuse_relay_health() -> dict[str, Any]:
        _require_scope(); return {"state": "READY", "version": "2.4.0", "arbitrary_shell": False}

    @server.tool(title="List enrolled Windows devices", description="Privacy-minimized device state.", annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
    def fuse_list_windows_devices() -> dict[str, Any]:
        _require_scope(); return {"devices": relay.list_devices()}

    @server.tool(title="Issue one-time Windows enrollment", description="Five-minute single-use enrollment.", annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False))
    def fuse_issue_windows_enrollment() -> dict[str, Any]:
        _require_scope(); return relay.issue_enrollment().public_dict()

    @server.tool(title="Submit allowlisted Windows task", description="Queue health, inventory, or hashing.", annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False))
    def fuse_submit_windows_task(device_id: str, task_type: str, relative_path: str | None = None) -> dict[str, Any]:
        _require_scope()
        if task_type not in {"health", "inventory", "hash_workspace_file"}: raise ValueError("TASK_TYPE_NOT_ALLOWLISTED")
        if task_type == "hash_workspace_file" and not relative_path: raise ValueError("RELATIVE_PATH_REQUIRED")
        if task_type != "hash_workspace_file" and relative_path: raise ValueError("RELATIVE_PATH_NOT_ALLOWED")
        now = datetime.now(timezone.utc); task_id = "task-" + uuid.uuid4().hex
        task = {"schema":"FEDERATION-WINDOWS-TASK-V1","task_id":task_id,"correlation_id":"corr-"+uuid.uuid4().hex,"issued_by":"FUSE/FDOF","task_type":task_type,"issued_at":_z(now-timedelta(seconds=1)),"expires_at":_z(now+timedelta(minutes=5)),"parameters":{"relative_path":relative_path} if relative_path else {},"effect":"READ_ONLY"}
        relay.submit_task(device_id=device_id, task=task, now=now); return {"state":"QUEUED","task_id":task_id,"device_id":device_id}

    @server.tool(title="Read Windows task status", description="Return queue/completion state.", annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
    def fuse_windows_task_status(task_id: str) -> dict[str, Any]:
        _require_scope(); return relay.status(task_id)

    _bind_agent_routes(server, relay)
    return server


def _bind_agent_routes(server: MCPServer, relay: Any) -> None:
    @server.custom_route("/healthz", methods=["GET"], include_in_schema=False)
    async def healthz(_: Request):
        return JSONResponse({"status":"ok","service":"fuse-windows-relay","version":"2.4.0","device_auth":"ECDSA_P256"})

    @server.custom_route("/agent/enroll", methods=["POST"], include_in_schema=False)
    async def enroll(request: Request):
        try:
            d = await request.json()
            c = relay.enroll(
                enrollment_id=str(d.get("enrollment_id") or ""),
                enrollment_token=str(d.get("enrollment_token") or ""),
                device_label=str(d.get("device_label") or ""),
                public_key_spki_b64=str(d.get("public_key_spki_b64") or ""),
            )
            return JSONResponse(c.public_dict(), status_code=201)
        except Exception as exc:
            return _json_error(exc, 401)

    @server.custom_route("/agent/poll", methods=["POST"], include_in_schema=False)
    async def poll(request: Request):
        body = await request.body()
        try:
            dev = _device_auth(request, body, relay); item = relay.poll(device_id=dev)
            if item is None: return JSONResponse({"state":"EMPTY"})
            task, lease = item; return JSONResponse({"state":"LEASED","task":task,"lease":lease.public_dict()})
        except Exception as exc:
            return _json_error(exc, 401)

    @server.custom_route("/agent/complete", methods=["POST"], include_in_schema=False)
    async def complete(request: Request):
        body = await request.body()
        try:
            dev = _device_auth(request, body, relay); d = json.loads(body)
            r = relay.complete(device_id=dev, task_id=str(d.get("task_id") or ""), lease_token=str(d.get("lease_token") or ""), receipt=d.get("receipt") or {})
            return JSONResponse({"state":"ACCEPTED","task_id":r["task_id"]})
        except Exception as exc:
            return _json_error(exc, 401)


BROWSER_PAGE = '''<!doctype html><html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>FUSE One-Click Node</title><body style="font:16px system-ui;max-width:760px;margin:8vh auto;padding:24px"><h1>FUSE One-Click Node</h1><p>Ephemeral Windows browser worker. No administrator password, native installation or persistence.</p><button id="connect" style="font-size:1.2rem;padding:14px 20px">CONNECT THIS PC</button><pre id="status">READY</pre><script src="/node/worker.js"></script><script>const b=document.getElementById('connect'),s=document.getElementById('status');b.onclick=async()=>{b.disabled=true;try{await FUON.connect(x=>s.textContent=x)}catch(e){s.textContent='FAILED CLOSED: '+e.message;b.disabled=false}}</script></body></html>'''

BROWSER_JS = r'''"use strict";
const te=new TextEncoder();
const b64u=b=>btoa(String.fromCharCode(...new Uint8Array(b))).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/g,"");
const sha=async b=>Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",b))).map(x=>x.toString(16).padStart(2,"0")).join("");
async function probe(){const p=(navigator.userAgentData&&navigator.userAgentData.platform)||navigator.platform||"UNKNOWN";if(!String(p).toLowerCase().includes("win"))throw Error("WINDOWS_BROWSER_REQUIRED");let gpu="NONE";if(navigator.gpu){try{gpu=(await navigator.gpu.requestAdapter())?"WEBGPU":"NONE"}catch{}}return{trust_mode:"B0_EPHEMERAL_LOW_TRUST",logical_cores:navigator.hardwareConcurrency||2,memory_budget_mb:navigator.deviceMemory?Math.max(256,Math.floor(navigator.deviceMemory*256)):512,gpu_class:gpu,wasm:typeof WebAssembly!=="undefined",webcrypto_p256:true,visibility_state:document.visibilityState,platform:String(p).slice(0,64)}}
async function bench(n){const src=`onmessage=e=>{let x=e.data|0;for(let i=0;i<2000000;i++)x=(Math.imul(x^i,1664525)+1013904223)|0;postMessage(x>>>0)}`;const u=URL.createObjectURL(new Blob([src],{type:"text/javascript"}));try{const st=performance.now(),jobs=[];for(let i=0;i<n;i++)jobs.push(new Promise((ok,bad)=>{const w=new Worker(u);w.onmessage=e=>{w.terminate();ok(e.data)};w.onerror=bad;w.postMessage(i+1)}));const v=await Promise.all(jobs);return{workers:n,wall_ms:Math.round(performance.now()-st),digest:await sha(te.encode(JSON.stringify(v)))}}finally{URL.revokeObjectURL(u)}}
async function headers(s,path,body){const ts=new Date().toISOString(),nonce="web-"+crypto.randomUUID().replaceAll("-",""),payload=te.encode(["POST",path,ts,nonce,await sha(body)].join("\n")),sig=await crypto.subtle.sign({name:"ECDSA",hash:"SHA-256"},s.privateKey,payload);return{"content-type":"application/json","x-fuse-device-id":s.device_id,"x-fuse-timestamp":ts,"x-fuse-nonce":nonce,"x-fuse-signature":b64u(sig)}}
async function post(s,path,obj){const body=obj===null?new Uint8Array():te.encode(JSON.stringify(obj));return fetch(path,{method:"POST",headers:await headers(s,path,body),body:obj===null?undefined:body})}
self.FUON={async connect(status){const cap=await probe();const kp=await crypto.subtle.generateKey({name:"ECDSA",namedCurve:"P-256"},true,["sign","verify"]);const spki=b64u(await crypto.subtle.exportKey("spki",kp.publicKey));status("ENROLLING");let r=await fetch("/browser/enroll",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({capabilities:cap,public_key_spki_b64:spki})});if(!r.ok)throw Error(await r.text());const s=await r.json();s.privateKey=kp.privateKey;s.cap=cap;r=await post(s,"/browser/selftest",{});if(!r.ok)throw Error(await r.text());for(let i=0;i<10;i++){r=await post(s,"/browser/poll",null);if(!r.ok)throw Error(await r.text());const q=await r.json();if(q.state==="LEASED"){const result={status:"healthy",worker_class:"B0_BROWSER",capabilities:cap,benchmark:await bench(Math.max(1,Math.min(4,cap.logical_cores||2))),arbitrary_shell:false};r=await post(s,"/browser/complete",{task_id:q.task.task_id,lease_token:q.lease.lease_token,result});if(!r.ok)throw Error(await r.text());status("B0 WORKLOAD COMPLETE");s.privateKey=null;return}await new Promise(x=>setTimeout(x,500))}throw Error("SELFTEST_TIMEOUT")}};'''

NATIVE_BOOTSTRAP_PS1 = r'''# FUSE WOAF v2.4 current-user bootstrap. No elevation or ExecutionPolicy bypass.
[CmdletBinding()]param([Parameter(Mandatory=$true)][string]$RelayUrl,[Parameter(Mandatory=$true)][string]$EnrollmentId,[Parameter(Mandatory=$true)][string]$EnrollmentToken,[switch]$Temporary)
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest;$u=[Uri]$RelayUrl;if($u.Scheme-ne'https'){throw'WOAF_HTTPS_REQUIRED'};$root=if($Temporary){Join-Path $env:TEMP 'FUSE\WOAF'}else{Join-Path $env:LOCALAPPDATA 'FUSE\WOAF'};New-Item -Force -ItemType Directory $root|Out-Null
$providers=@('Microsoft Platform Crypto Provider','Microsoft Software Key Storage Provider');$cert=$null;foreach($p in $providers){try{$cert=New-SelfSignedCertificate -Type Custom -Subject ('CN=FUSE-WOAF-'+[guid]::NewGuid().ToString('N')) -CertStoreLocation 'Cert:\CurrentUser\My' -KeyAlgorithm ECDSA_nistP256 -Provider $p -KeyExportPolicy NonExportable -KeyUsage DigitalSignature -NotAfter ([datetime]::UtcNow.AddYears(2));if($cert){break}}catch{}};if(-not$cert){throw'WOAF_CNG_KEY_FAILED'};$EnrollmentToken=$null;@{schema='FUSE-WOAF-N1-BOOTSTRAP-V24';relay=$u.Host;admin_required=$false;non_exportable_key=$true;arbitrary_shell_enabled=$false;temporary=[bool]$Temporary}|ConvertTo-Json -Compress'''


def build_agent_only_server(*, relay: Any) -> MCPServer:
    from mcp.server.auth.provider import AccessToken, TokenVerifier
    class DenyAll(TokenVerifier):
        async def verify_token(self, token: str) -> AccessToken | None: return None
    server = MCPServer("FUSE Windows Agent-Only Bootstrap", version="2.4.0", instructions="MCP is intentionally unavailable; bounded bootstrap routes only.", token_verifier=DenyAll(), auth=AuthSettings(issuer_url=AnyHttpUrl("https://bootstrap.invalid"), resource_server_url=AnyHttpUrl("https://bootstrap.invalid/mcp"), required_scopes=[BASE_SCOPE], validate_token_resource=True))
    _bind_agent_routes(server, relay)

    @server.custom_route("/node", methods=["GET"], include_in_schema=False)
    async def node(_: Request): return HTMLResponse(BROWSER_PAGE, headers={"cache-control":"no-store","content-security-policy":"default-src 'self'; script-src 'self' 'unsafe-inline'; connect-src 'self'; worker-src blob:; object-src 'none'; base-uri 'none'"})

    @server.custom_route("/node/worker.js", methods=["GET"], include_in_schema=False)
    async def worker(_: Request): return PlainTextResponse(BROWSER_JS, media_type="application/javascript", headers={"cache-control":"no-store"})

    @server.custom_route("/node/native-bootstrap.ps1", methods=["GET"], include_in_schema=False)
    async def native(_: Request): return PlainTextResponse(NATIVE_BOOTSTRAP_PS1, media_type="text/plain", headers={"cache-control":"no-store"})

    @server.custom_route("/browser/enroll", methods=["POST"], include_in_schema=False)
    async def browser_enroll(request: Request):
        try:
            d = await request.json(); cap = d.get("capabilities") or {}; platform = str(cap.get("platform") or "")
            if "win" not in platform.lower(): raise ValueError("WINDOWS_BROWSER_REQUIRED")
            public_key = str(d.get("public_key_spki_b64") or "")
            if not public_key: raise ValueError("DEVICE_PUBLIC_KEY_REQUIRED")
            grant = relay.issue_enrollment(); cred = relay.enroll(enrollment_id=grant.enrollment_id, enrollment_token=grant.enrollment_token, device_label="b0-"+uuid.uuid4().hex, public_key_spki_b64=public_key)
            out = cred.public_dict(); out["trust_mode"] = "B0_EPHEMERAL_LOW_TRUST"; return JSONResponse(out, status_code=201)
        except Exception as exc: return _json_error(exc, 401)

    async def bauth(request: Request):
        body = await request.body(); dev = _device_auth(request, body, relay); return body, dev

    @server.custom_route("/browser/selftest", methods=["POST"], include_in_schema=False)
    async def browser_selftest(request: Request):
        try:
            _, dev = await bauth(request); now = datetime.now(timezone.utc)
            task = {"schema":"FEDERATION-WINDOWS-TASK-V1","task_id":"b0-"+uuid.uuid4().hex,"correlation_id":"corr-"+uuid.uuid4().hex,"issued_by":"FUSE/FDOF","task_type":"health","issued_at":_z(now-timedelta(seconds=1)),"expires_at":_z(now+timedelta(minutes=5)),"parameters":{},"effect":"READ_ONLY"}
            relay.submit_task(device_id=dev, task=task, now=now); return JSONResponse({"state":"QUEUED","task_id":task["task_id"]})
        except Exception as exc: return _json_error(exc, 401)

    @server.custom_route("/browser/poll", methods=["POST"], include_in_schema=False)
    async def browser_poll(request: Request):
        try:
            _, dev = await bauth(request); item = relay.poll(device_id=dev)
            if item is None: return JSONResponse({"state":"EMPTY"})
            task, lease = item
            if task.get("task_type") not in {"health","inventory"}: raise PermissionError("B0_TASK_NOT_ALLOWLISTED")
            return JSONResponse({"state":"LEASED","task":task,"lease":lease.public_dict()})
        except Exception as exc: return _json_error(exc, 401)

    @server.custom_route("/browser/complete", methods=["POST"], include_in_schema=False)
    async def browser_complete(request: Request):
        try:
            body, dev = await bauth(request); d = json.loads(body); tid = str(d.get("task_id") or ""); doc = relay._collection("tasks").document(tid).get().to_dict(); task = dict(doc.get("task") or {}); result = d.get("result") or {}
            if doc.get("device_id") != dev or not task: raise PermissionError("TASK_DEVICE_MISMATCH")
            canon = lambda x: json.dumps(x, sort_keys=True, separators=(",", ":")).encode()
            receipt = {"schema":"FEDERATION-WINDOWS-RECEIPT-V1","task_id":tid,"correlation_id":task["correlation_id"],"task_type":task["task_type"],"state":"COMPLETED_VERIFIED_LOCAL","started_at":task["issued_at"],"completed_at":_z(datetime.now(timezone.utc)),"runner":{"os":"Windows","runner_class":"B0_BROWSER","device_id":dev},"task":task,"result":dict(result),"task_sha256":hashlib.sha256(canon(task)).hexdigest(),"result_sha256":hashlib.sha256(canon(dict(result))).hexdigest(),"effect":"READ_ONLY","truth_boundary":"B0 low-trust browser result; native owner-PC maturity is separate."}
            stored = relay.complete(device_id=dev, task_id=tid, lease_token=str(d.get("lease_token") or ""), receipt=receipt); return JSONResponse({"state":"ACCEPTED","task_id":stored["task_id"]})
        except Exception as exc: return _json_error(exc, 401)
    return server


def server_from_env() -> MCPServer:
    if not os.environ.get("GOOGLE_CLOUD_PROJECT"): raise RuntimeError("MISSING_REQUIRED_ENV:GOOGLE_CLOUD_PROJECT")
    relay = FirestoreRelay(project=os.environ["GOOGLE_CLOUD_PROJECT"], root_secret=os.environ.get("FUSE_RELAY_ROOT_SECRET"))
    issuer = os.environ.get("FUSE_OIDC_ISSUER"); jwks = os.environ.get("FUSE_OIDC_JWKS_URL"); mode = relay_mode(oidc_issuer=issuer, oidc_jwks_url=jwks)
    if mode == "AGENT_ONLY_BOOTSTRAP": return build_agent_only_server(relay=relay)
    resource = os.environ.get("FUSE_MCP_RESOURCE_URL")
    if not resource: raise RuntimeError("MISSING_REQUIRED_ENV:FUSE_MCP_RESOURCE_URL")
    return build_server(relay=relay, issuer=str(issuer), resource_url=resource, jwks_url=str(jwks))


def main() -> None:
    server_from_env().run(transport="streamable-http", host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), stateless_http=True, json_response=True)


if __name__ == "__main__": main()
