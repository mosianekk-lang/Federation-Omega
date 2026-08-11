from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

_PUNCT = re.compile(r"[^\w'-]+", re.UNICODE)
_WS = re.compile(r"\s+")


def normalize_token(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).strip().lower()
    text = text.replace("–", "-").replace("—", "-")
    return _PUNCT.sub("", text)


def normalize_phrase(value: str) -> str:
    return _WS.sub(" ", " ".join(normalize_token(part) for part in value.split())).strip()


def similarity(a: str, b: str) -> float:
    na, nb = normalize_token(a), normalize_token(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()
