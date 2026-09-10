from __future__ import annotations
import hashlib,json,re
from dataclasses import dataclass
from datetime import datetime
from typing import Any,Awaitable,Callable,Mapping
EDGE_SCHEMA='AEGIS_EDGE_POSTURE_V1'; MAX_PAYLOAD_BYTES=4096; _SAMPLE_ID=re.compile(r'^[A-Za-z0-9._:-]{8,96}$')
_ALLOWED={'schema','sample_id','collected_at','consent','platform','os_major','security_patch_month','app_version_major_minor','screen_lock_configured','developer_mode','adb_enabled','app_debuggable','secure_store_available','gateway_https','session_present'}
_FORBIDDEN={'imei','meid','serial','serial_number','android_id','advertising_id','phone_number','email','contacts','messages','location','latitude','longitude','ssid','bssid','ip','ip_address','mac_address','device_name','app_list','installed_apps','file_paths','files','photos','clipboard'}
class EdgeBridgeError(ValueError): pass
def _canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('utf-8')
def _sha(value): return hashlib.sha256(value).hexdigest()
def validate_posture(payload):
    raw=_canonical(payload)
    if len(raw)>MAX_PAYLOAD_BYTES: raise EdgeBridgeError('EDGE_PAYLOAD_TOO_LARGE')
    unknown=set(payload)-_ALLOWED
    if unknown: raise EdgeBridgeError('EDGE_UNKNOWN_FIELDS:'+','.join(sorted(unknown)))
    if _FORBIDDEN.intersection({str(k).lower() for k in payload}): raise EdgeBridgeError('EDGE_FORBIDDEN_FIELD')
    if payload.get('schema')!=EDGE_SCHEMA: raise EdgeBridgeError('EDGE_SCHEMA_INVALID')
    if payload.get('consent') is not True: raise EdgeBridgeError('EDGE_CONSENT_REQUIRED')
    sample_id=str(payload.get('sample_id') or '')
    if not _SAMPLE_ID.fullmatch(sample_id): raise EdgeBridgeError('EDGE_SAMPLE_ID_INVALID')
    try: datetime.fromisoformat(str(payload.get('collected_at') or '').replace('Z','+00:00'))
    except Exception as exc: raise EdgeBridgeError('EDGE_TIMESTAMP_INVALID') from exc
    return dict(payload)
def pseudonymous_device_id(device_hash):
    if not re.fullmatch(r'[0-9a-fA-F]{64}',device_hash): raise EdgeBridgeError('EDGE_DEVICE_HASH_INVALID')
    return _sha(('fuse-device:'+device_hash.lower()).encode())[:32]
def request_identity(*,subject,device_hash,posture):
    if not subject.strip(): raise EdgeBridgeError('EDGE_SUBJECT_REQUIRED')
    clean=validate_posture(posture); payload_hash=_sha(_canonical(clean)); return _sha((subject+'|'+device_hash.lower()+'|'+payload_hash).encode()),payload_hash
def posture_events(*,device_hash,posture):
    p=validate_posture(posture); device_id=pseudonymous_device_id(device_hash); events=[]
    flags={'screen_lock_missing':p.get('screen_lock_configured') is False,'developer_mode':p.get('developer_mode') is True,'adb_enabled':p.get('adb_enabled') is True,'app_debuggable':p.get('app_debuggable') is True,'secure_store_missing':p.get('secure_store_available') is False}; count=sum(bool(v) for v in flags.values())
    if count: events.append({'device_id':device_id,'event_id':f"edge-{_sha((device_id+'|'+str(p['sample_id'])+'|device_integrity').encode())[:24]}",'event_class':'device_integrity','severity':min(.95,.25+.13*count),'confidence':.90,'source':'FUSE_AEGIS_EDGE','consent':True,'attributes':flags})
    if p.get('gateway_https') is False: events.append({'device_id':device_id,'event_id':f"edge-{_sha((device_id+'|'+str(p['sample_id'])+'|network_risk').encode())[:24]}",'event_class':'network_risk','severity':.85,'confidence':.98,'source':'FUSE_AEGIS_EDGE','consent':True,'attributes':{'gateway_https':False}})
    if p.get('session_present') is False: events.append({'device_id':device_id,'event_id':f"edge-{_sha((device_id+'|'+str(p['sample_id'])+'|identity_risk').encode())[:24]}",'event_class':'identity_risk','severity':.35,'confidence':.85,'source':'FUSE_AEGIS_EDGE','consent':True,'attributes':{'session_present':False}})
    return events
@dataclass(frozen=True)
class EdgeBridgeReceipt:
    request_id:str; payload_sha256:str; pseudonymous_device_id:str; event_count:int; case_id:str|None; provider_state_verified:bool; provider_effect_performed:bool; status:str
async def submit_posture(*,subject,device_hash,posture,sink,allow_provider_effect=False):
    request_id,payload_hash=request_identity(subject=subject,device_hash=device_hash,posture=posture); events=posture_events(device_hash=device_hash,posture=posture); device_id=pseudonymous_device_id(device_hash)
    if not events:
        return EdgeBridgeReceipt(request_id,payload_hash,device_id,0,None,False,False,'NO_CHANGE')
    result=dict(await sink(request_id,events)); effect=result.get('provider_effect_performed') is True
    if effect and not allow_provider_effect: raise EdgeBridgeError('EDGE_SINK_UNEXPECTED_PROVIDER_EFFECT')
    if result.get('request_id') not in {None,request_id}: raise EdgeBridgeError('EDGE_SINK_REQUEST_ID_MISMATCH')
    case_id=str(result.get('case_id') or '').strip() or None; provider_state_verified=result.get('provider_state_verified') is True
    return EdgeBridgeReceipt(request_id,payload_hash,device_id,len(events),case_id,provider_state_verified,effect,str(result.get('status') or 'ACCEPTED'))
