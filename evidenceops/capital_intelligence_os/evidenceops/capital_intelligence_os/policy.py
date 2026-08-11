from __future__ import annotations
from dataclasses import dataclass
import hashlib, hmac

@dataclass(frozen=True)
class RuntimePrincipal:
    tenant_id:str; user_id:str; roles:tuple[str,...]=('operator',)

class RuntimePolicy:
    SAFE_ROUTES={('GET','/health'),('GET','/ready'),('GET','/v1/verify'),('POST','/v1/events')}
    FORBIDDEN_PREFIXES=('/orders','/trade','/transfer','/withdraw','/payments','/sign','/regulatory-file')
    def __init__(self,bearer_token:str):
        if len(bearer_token)<24: raise ValueError('local canary bearer token must be at least 24 characters')
        self._token_hash=hashlib.sha256(bearer_token.encode()).digest()
    def authenticate(self,authorization:str|None,tenant_id:str|None,user_id:str|None)->RuntimePrincipal:
        if not authorization or not authorization.startswith('Bearer '): raise PermissionError('AUTH_REQUIRED')
        supplied=hashlib.sha256(authorization[7:].encode()).digest()
        if not hmac.compare_digest(supplied,self._token_hash): raise PermissionError('AUTH_INVALID')
        if not tenant_id or not user_id: raise PermissionError('TENANT_AND_USER_REQUIRED')
        return RuntimePrincipal(tenant_id,user_id)
    def authorize(self,method:str,path:str)->None:
        normalized=path.split('?',1)[0]
        if any(normalized.startswith(prefix) for prefix in self.FORBIDDEN_PREFIXES): raise PermissionError('CONSEQUENTIAL_ROUTE_NOT_EXPOSED')
        if (method.upper(),normalized) not in self.SAFE_ROUTES: raise PermissionError('ROUTE_DEFAULT_DENY')
