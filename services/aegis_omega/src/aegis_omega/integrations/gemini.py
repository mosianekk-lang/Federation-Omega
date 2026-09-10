from __future__ import annotations
import json
from urllib import request, parse
from ..config import settings
from ..schemas import Assessment

_ALLOWED_FIELDS = ("case_id", "risk_score", "confidence", "disposition", "rationale")


def explain_assessment(assessment: Assessment) -> str:
    """Request a concise defensive explanation from Gemini.

    The adapter sends no raw messages, files, credentials, contacts, or private device content.
    It is advisory only and has no response authority.
    """
    if not settings.gemini_api_key or not settings.gemini_model:
        return "Gemini explanation disabled: configure GEMINI_API_KEY and GEMINI_MODEL via Secret Manager/environment."
    minimized = {k: getattr(assessment, k) for k in _ALLOWED_FIELDS}
    prompt = (
        "You are a defensive mobile-security analyst. Explain this already-computed assessment, "
        "identify uncertainty, and suggest additional non-invasive evidence to collect. Do not assert compromise "
        "without corroboration and do not suggest offensive actions. Assessment: " + json.dumps(minimized)
    )
    url = f"{settings.gemini_api_base}/models/{parse.quote(settings.gemini_model, safe='')}:generateContent?key={parse.quote(settings.gemini_api_key, safe='')}"
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    req = request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=20) as resp:
        data = json.load(resp)
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return "Gemini returned no usable explanation."
