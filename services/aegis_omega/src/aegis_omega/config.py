from dataclasses import dataclass
import os

DEVELOPMENT_HMAC_SECRET="development-only-secret"
MIN_PRODUCTION_HMAC_SECRET_BYTES=32

def _float(name:str,default:float)->float:
    try:return float(os.getenv(name,str(default)))
    except ValueError:return default

@dataclass(frozen=True)
class Settings:
    env:str=os.getenv("AEGIS_ENV","development")
    hmac_secret:str=os.getenv("AEGIS_HMAC_SECRET",DEVELOPMENT_HMAC_SECRET)
    hmac_key_id:str=os.getenv("AEGIS_HMAC_KEY_ID","development-v1")
    manual_approval_threshold:float=_float("AEGIS_MANUAL_APPROVAL_THRESHOLD",0.70)
    high_risk_threshold:float=_float("AEGIS_HIGH_RISK_THRESHOLD",0.85)
    gemini_api_key:str=os.getenv("GEMINI_API_KEY","")
    gemini_model:str=os.getenv("GEMINI_MODEL","")
    gemini_api_base:str=os.getenv("GEMINI_API_BASE","https://generativelanguage.googleapis.com/v1beta")
    fuse_webhook_url:str=os.getenv("FUSE_WEBHOOK_URL","")
    fuse_shared_secret:str=os.getenv("FUSE_SHARED_SECRET","")
    case_store:str=os.getenv("AEGIS_CASE_STORE","firestore" if os.getenv("AEGIS_ENV")=="production" else "memory")
    gcp_project:str=os.getenv("AEGIS_GCP_PROJECT","")
    pubsub_topic:str=os.getenv("AEGIS_PUBSUB_TOPIC","")
    evidence_bucket:str=os.getenv("AEGIS_EVIDENCE_BUCKET","")
    def __post_init__(self)->None:
        if self.env.strip().lower()=="production":
            secret=self.hmac_secret.encode("utf-8")
            if self.hmac_secret==DEVELOPMENT_HMAC_SECRET or len(secret)<MIN_PRODUCTION_HMAC_SECRET_BYTES:
                raise RuntimeError("AEGIS production start refused: AEGIS_HMAC_SECRET must be injected from an approved secret source and contain at least 32 UTF-8 bytes; the development fallback is forbidden.")
settings=Settings()
