from __future__ import annotations
import asyncio
from dataclasses import asdict
import os
from typing import Any,Mapping,Protocol
import httpx
from fastapi import APIRouter,Header,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from aegis_edge_bridge import EdgeBridgeError,submit_posture
class SessionIdentity(Protocol):
    subject:str; claims:Mapping[str,Any]
class SessionRuntime(Protocol):
    async def verify_session(self,token:str)->SessionIdentity: ...
class EdgePostureBody(BaseModel):
    model_config=ConfigDict(extra='forbid',populate_by_name=True); schema_name:str=Field(alias='schema',pattern='^AEGIS_EDGE_POSTURE_V1$'); sample_id:str=Field(min_length=8,max_length=96); collected_at:str=Field(min_length=10,max_length=64); consent:bool; platform:str=Field(min_length=2,max_length=16); os_major:str=Field(min_length=1,max_length=16); security_patch_month:str|None=Field(default=None,max_length=7); app_version_major_minor:str|None=Field(default=None,max_length=32); screen_lock_configured:bool|None=None; developer_mode:bool|None=None; adb_enabled:bool|None=None; app_debuggable:bool|None=None; secure_store_available:bool|None=None; gateway_https:bool|None=None; session_present:bool|None=None
class AegisSink(Protocol):
    async def __call__(self,request_id:str,events:list[dict[str,Any]])->Mapping[str,Any]: ...
class DisabledAegisSink:
    async def __call__(self,request_id,events): raise RuntimeError('AEGIS_EDGE_SINK_UNBOUND')
class CloudRunAegisSink:
    def __init__(self,base_url:str,*,timeout_seconds:float=20.0):
        self.base_url=base_url.rstrip('/');
        if not self.base_url.startswith('https://'): raise ValueError('AEGIS_EDGE_PRIVATE_HTTPS_REQUIRED')
        self.timeout_seconds=timeout_seconds
    async def __call__(self,request_id,events):
        try:
            from google.auth.transport.requests import Request as GoogleAuthRequest
            from google.oauth2 import id_token as google_id_token
        except ImportError as exc: raise RuntimeError('AEGIS_EDGE_GOOGLE_AUTH_DEPENDENCY_MISSING') from exc
        token=await asyncio.to_thread(google_id_token.fetch_id_token,GoogleAuthRequest(),self.base_url)
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client: response=await client.post(f'{self.base_url}/v1/assess',headers={'Authorization':f'Bearer {token}'},json={'request_id':request_id,'events':events})
        if response.status_code==409: raise RuntimeError('AEGIS_EDGE_IDEMPOTENCY_COLLISION')
        response.raise_for_status(); body=response.json(); case_id=str(body.get('case_id') or '').strip()
        if not case_id: raise RuntimeError('AEGIS_EDGE_CASE_ID_MISSING')
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client: readback=await client.get(f'{self.base_url}/v1/cases/{case_id}',headers={'Authorization':f'Bearer {token}'})
        readback.raise_for_status(); case=readback.json(); state_verified=bool(case.get('evidence_chain_valid') is True and case.get('assessment',{}).get('case_id')==case_id)
        if not state_verified: raise RuntimeError('AEGIS_EDGE_PROVIDER_STATE_UNVERIFIED')
        return {'request_id':request_id,'status':str(body.get('disposition') or 'ACCEPTED'),'case_id':case_id,'provider_state_verified':True,'provider_effect_performed':False}
def sink_from_environment():
    url=os.getenv('FUSE_AEGIS_PRIVATE_URL','').strip(); return CloudRunAegisSink(url) if url else DisabledAegisSink()
def _bearer(value):
    if not value: raise HTTPException(status_code=401,detail={'status':'HELD','reason':'AUTHORIZATION_REQUIRED'})
    scheme,_,token=value.partition(' ')
    if scheme.lower()!='bearer' or not token.strip(): raise HTTPException(status_code=401,detail={'status':'HELD','reason':'BEARER_TOKEN_REQUIRED'})
    return token.strip()
def build_aegis_edge_router(runtime,sink=None):
    active_sink=sink or DisabledAegisSink(); router=APIRouter()
    @router.post('/v1/aegis/posture')
    async def submit_edge_posture(body:EdgePostureBody,authorization:str|None=Header(default=None),x_fuse_authorization:str|None=Header(default=None,alias='X-Fuse-Authorization')):
        token=_bearer(x_fuse_authorization or authorization)
        try: identity=await runtime.verify_session(token)
        except Exception as exc: raise HTTPException(status_code=401,detail={'status':'HELD','reason':'SESSION_INVALID'}) from exc
        device_hash=str(identity.claims.get('device_hash') or '')
        if not device_hash: raise HTTPException(status_code=401,detail={'status':'HELD','reason':'SESSION_DEVICE_BINDING_REQUIRED'})
        try: receipt=await submit_posture(subject=identity.subject,device_hash=device_hash,posture=body.model_dump(mode='json',by_alias=True),sink=active_sink,allow_provider_effect=not isinstance(active_sink,DisabledAegisSink))
        except EdgeBridgeError as exc: raise HTTPException(status_code=400,detail={'status':'HELD','reason':str(exc)}) from exc
        except RuntimeError as exc:
            code=str(exc); status=503 if code=='AEGIS_EDGE_SINK_UNBOUND' else 502; raise HTTPException(status_code=status,detail={'status':'HELD','reason':code}) from exc
        return asdict(receipt)
    return router
