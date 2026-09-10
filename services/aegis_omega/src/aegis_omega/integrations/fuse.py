from __future__ import annotations
import hashlib, hmac, json
from urllib import request
from ..config import settings
from ..schemas import Assessment


def emit_defensive_finding(assessment: Assessment) -> bool:
    """Optional signed webhook into FUSE/Federation.

    Only the assessment summary is emitted. No raw personal content or covert collection is supported.
    """
    if not settings.fuse_webhook_url or not settings.fuse_shared_secret:
        return False
    payload = json.dumps({
        "type": "aegis.defensive_assessment",
        "case_id": assessment.case_id,
        "risk_score": assessment.risk_score,
        "confidence": assessment.confidence,
        "disposition": assessment.disposition,
    }, sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(settings.fuse_shared_secret.encode(), payload, hashlib.sha256).hexdigest()
    req = request.Request(settings.fuse_webhook_url, data=payload,
                          headers={"Content-Type": "application/json", "X-AEGIS-Signature": signature}, method="POST")
    with request.urlopen(req, timeout=10) as resp:
        return 200 <= resp.status < 300
