from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class QuotationEvidence:
    independent_architectures: int
    word_timestamps_present: bool
    speaker_role_supported: bool
    legal_entities_verified: bool
    human_listened: bool
    audio_window_hash: str | None = None


def quotation_release_gate(evidence: QuotationEvidence) -> dict:
    checks = {
        "two_independent_architectures": evidence.independent_architectures >= 2,
        "word_timestamps_present": evidence.word_timestamps_present,
        "speaker_role_supported": evidence.speaker_role_supported,
        "legal_entities_verified": evidence.legal_entities_verified,
        "human_listened": evidence.human_listened,
        "audio_window_hash_present": bool(evidence.audio_window_hash),
    }
    passed = all(checks.values())
    return {
        "contract": "EVIDENCEOPS_QUOTATION_RELEASE_GATE_V1",
        "state": "VERIFIED_FOR_QUOTATION" if passed else "BLOCKED_NOT_VERIFIED_FOR_QUOTATION",
        "checks": checks,
        "evidence": asdict(evidence),
        "truth_boundary": "No automated transcript may be quoted in a filing until every gate passes.",
    }
