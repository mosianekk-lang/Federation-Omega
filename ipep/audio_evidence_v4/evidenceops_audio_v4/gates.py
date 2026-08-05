from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .models import QuoteRequest


def quotation_release_gate(request: QuoteRequest, *, source_language: str) -> dict[str, Any]:
    families = sorted({family for family in request.supporting_architecture_families if family and family != "unknown"})
    translated_quote = request.quote_language != source_language
    checks = {
        "two_independent_asr_architectures": len(families) >= 2,
        "word_timestamps_present": request.word_timestamps_present,
        "speaker_role_supported": request.speaker_role_supported,
        "legal_entities_verified": request.legal_entities_verified,
        "human_listened_to_exact_window": request.human_listened,
        "source_text_human_verified": request.source_text_human_verified,
        "audio_window_hash_present": bool(request.audio_window_sha256),
        "translation_human_verified_when_quote_is_translated": (
            request.translation_human_verified if translated_quote else True
        ),
    }
    passed = all(checks.values())
    return {
        "contract": "EVIDENCEOPS_AUDIO_QUOTATION_RELEASE_GATE_V4",
        "segment_id": request.segment_id,
        "state": "VERIFIED_FOR_QUOTATION" if passed else "BLOCKED_NOT_VERIFIED_FOR_QUOTATION",
        "checks": checks,
        "source_language": source_language,
        "quote_language": request.quote_language,
        "translated_quote": translated_quote,
        "supporting_architecture_families": families,
        "evidence": asdict(request),
        "truth_boundary": (
            "Passing this gate supports quotation use for the identified excerpt and language only. "
            "It does not certify the entire transcript, authenticate a speaker biometrically, or decide admissibility."
        ),
    }


def transcript_certification_gate(
    *,
    total_segments: int,
    human_verified_segments: int,
    custody_chain_passed: bool,
    unit_accounting_passed: bool,
    signed_attestation_sha256: str | None,
    attesting_person: str | None,
    attesting_role: str | None,
) -> dict[str, Any]:
    checks = {
        "all_segments_human_verified": total_segments > 0 and human_verified_segments == total_segments,
        "custody_chain_passed": custody_chain_passed,
        "unit_accounting_passed": unit_accounting_passed,
        "signed_attestation_hash_present": bool(signed_attestation_sha256),
        "attesting_person_present": bool(attesting_person),
        "attesting_role_present": bool(attesting_role),
    }
    passed = all(checks.values())
    return {
        "contract": "EVIDENCEOPS_TRANSCRIPT_CERTIFICATION_GATE_V1",
        "state": "ELIGIBLE_FOR_EXTERNAL_CERTIFICATION_RECORD" if passed else "NOT_CERTIFIED",
        "checks": checks,
        "counts": {
            "total_segments": total_segments,
            "human_verified_segments": human_verified_segments,
        },
        "attestation": {
            "sha256": signed_attestation_sha256,
            "person": attesting_person,
            "role": attesting_role,
        },
        "truth_boundary": (
            "The software never self-certifies a transcript. Even a passing result only records that the stated "
            "inputs satisfy this technical gate; the legal effect of an attestation is external to the system."
        ),
    }
