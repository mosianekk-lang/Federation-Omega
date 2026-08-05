from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import Signal


@dataclass(frozen=True)
class AudioV4Snapshot:
    processed_units: int
    emitted_segment_units: int
    zero_segment_units: int
    failed_units: int
    transcript_state: str
    exact_quote_requested: bool = False
    human_listened_to_exact_window: bool = False
    translated_quote_requested: bool = False
    bilingual_human_verified: bool = False
    signed_attestation_sha256: str | None = None

    def __post_init__(self) -> None:
        counts = (
            self.processed_units,
            self.emitted_segment_units,
            self.zero_segment_units,
            self.failed_units,
        )
        if any(value < 0 for value in counts):
            raise ValueError("audio unit counts cannot be negative")


def assess_audio_v4_snapshot(
    snapshot: AudioV4Snapshot,
    *,
    observed_at: str,
    source: str = "EVIDENCEOPS_AUDIO_V4_SUMMARY",
) -> dict[str, Any]:
    accounting_passed = snapshot.processed_units == (
        snapshot.emitted_segment_units
        + snapshot.zero_segment_units
        + snapshot.failed_units
    )
    signals: list[Signal] = []

    if not accounting_passed:
        signals.append(
            Signal(
                signal_id="AUDIO-V4-UNIT-ACCOUNTING-MISMATCH",
                observed_at=observed_at,
                kind="READBACK_MISMATCH",
                source=source,
                payload={
                    "contract": "EVIDENCEOPS_AUDIO_V4_UNIT_ACCOUNTING",
                    "processed_units": snapshot.processed_units,
                    "emitted_segment_units": snapshot.emitted_segment_units,
                    "zero_segment_units": snapshot.zero_segment_units,
                    "failed_units": snapshot.failed_units,
                },
            )
        )

    human_gate_reasons: list[str] = []
    if snapshot.exact_quote_requested and not snapshot.human_listened_to_exact_window:
        human_gate_reasons.append("EXACT_WINDOW_HUMAN_LISTENING_REQUIRED")
    if snapshot.translated_quote_requested and not snapshot.bilingual_human_verified:
        human_gate_reasons.append("BILINGUAL_HUMAN_VERIFICATION_REQUIRED")
    if snapshot.transcript_state == "EXTERNALLY_CERTIFIED" and not snapshot.signed_attestation_sha256:
        signals.append(
            Signal(
                signal_id="AUDIO-V4-CERTIFICATION-CLAIM-GAP",
                observed_at=observed_at,
                kind="CLAIM_EXCEEDS_PROOF",
                source=source,
                payload={"claim": snapshot.transcript_state, "proof": "NO_SIGNED_ATTESTATION_HASH"},
            )
        )
    if human_gate_reasons:
        signals.append(
            Signal(
                signal_id="AUDIO-V4-HUMAN-GATE",
                observed_at=observed_at,
                kind="HUMAN_GATE_REQUIRED",
                source=source,
                payload={"reasons": human_gate_reasons, "transcript_state": snapshot.transcript_state},
            )
        )

    return {
        "contract": "OMEGA_CYBERNETIC_AUDIO_V4_BINDING_V11",
        "unit_accounting_passed": accounting_passed,
        "signals": tuple(signals),
        "truth_boundary": (
            "This adapter evaluates control invariants and preserves human gates. "
            "It does not alter Audio v4 evidence, verify exact wording, identify a speaker, "
            "or certify a transcript."
        ),
    }
