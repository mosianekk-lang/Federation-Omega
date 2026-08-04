from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class AccuracyOpportunity:
    opportunity_id: str
    title: str
    expected_value: str
    evidence_risk: str
    implementation_state: str
    next_gate: str

    def to_dict(self):
        return asdict(self)


def default_opportunities() -> list[AccuracyOpportunity]:
    return [
        AccuracyOpportunity("OPP-ASR-001", "Architectural-family enforcement", "Prevents two Whisper checkpoints from being misrepresented as independent consensus.", "Low", "IMPLEMENTED", "Run with Whisper plus Parakeet/OpenAI/Chirp."),
        AccuracyOpportunity("OPP-ASR-002", "Critical-passage escalation", "Runs expensive high-accuracy models only on jurisdiction, lockout, reply and ruling windows.", "Low", "IMPLEMENTED_AS_REVIEW_PRIORITY", "Execute independent recogniser on priority windows."),
        AccuracyOpportunity("OPP-ASR-003", "Hearing-specific gold-sample calibration", "Replaces assumed model weights with measured WER on the actual room, microphones and accents.", "Low", "IMPLEMENTED", "Human-verify 10-15 minutes of representative audio."),
        AccuracyOpportunity("OPP-ASR-004", "Stereo-channel audit and channel-specific ASR", "May isolate room microphones or speakers before diarisation if left/right channels differ.", "Medium; derivatives only", "STAGED", "Acquire original source bytes and measure channel correlation."),
        AccuracyOpportunity("OPP-ASR-005", "Original-versus-enhanced audio ensemble", "Uses denoised audio as an additional hypothesis without replacing the original evidence.", "Medium; enhancement can distort", "STAGED", "Generate hashed enhancement derivatives and compare."),
        AccuracyOpportunity("OPP-ASR-006", "Document-grounded case lexicon", "Improves names, case numbers and legal terms while prohibiting unsupported semantic correction.", "Low if exact aliases only", "IMPLEMENTED", "Populate only from verified case documents."),
        AccuracyOpportunity("OPP-ASR-007", "Quotation release gate", "Stops uncertain machine wording from entering CCMA or court papers as a direct quote.", "Low", "IMPLEMENTED", "Human listening and audio-window hash required."),
    ]
