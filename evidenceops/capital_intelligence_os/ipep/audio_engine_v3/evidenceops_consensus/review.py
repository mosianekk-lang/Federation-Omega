from __future__ import annotations

from .models import ConsensusWord
from .normalize import normalize_token

DEFAULT_CRITICAL_TERMS = {
    "jurisdiction", "limine", "functus", "officio", "agreement", "promotion",
    "benefits", "suspension", "bundle", "disclosure", "ruling", "costs",
    "ccma", "labour", "arbitration", "grievance", "implementation",
}


def review_priority(word: ConsensusWord, critical_terms: set[str] | None = None) -> tuple[float, list[str]]:
    critical_terms = critical_terms or DEFAULT_CRITICAL_TERMS
    score = (1.0 - word.agreement) * 60.0
    reasons: list[str] = []
    if word.needs_review:
        score += 20.0
        reasons.append("LOW_OR_SINGLE_FAMILY_SUPPORT")
    if len(word.architecture_families) < 2:
        score += 20.0
        reasons.append("INSUFFICIENT_ARCHITECTURE_DIVERSITY")
    if normalize_token(word.text) in critical_terms:
        score += 25.0
        reasons.append("LEGAL_OR_PROCEDURAL_TERM")
    if word.start is None or word.end is None:
        score += 10.0
        reasons.append("MISSING_WORD_ALIGNMENT")
    if len(word.alternatives) > 1:
        score += min(15.0, (len(word.alternatives) - 1) * 5.0)
        reasons.append("COMPETING_ALTERNATIVES")
    if word.speaker is None:
        score += 5.0
        reasons.append("SPEAKER_UNRESOLVED")
    return round(score, 3), reasons


def prioritize_review(words: list[ConsensusWord], critical_terms: set[str] | None = None) -> list[dict]:
    rows = []
    for index, word in enumerate(words):
        if not word.needs_review:
            continue
        score, reasons = review_priority(word, critical_terms)
        rows.append({"index": index, "priority": score, "reasons": reasons, **word.to_dict()})
    return sorted(rows, key=lambda item: (-item["priority"], item["index"]))
