from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class AudioVariantPlan:
    variant_id: str
    purpose: str
    transformation: str
    evidence_rule: str
    may_vote: bool

    def to_dict(self):
        return asdict(self)


def recommended_audio_variants(source_channels: int = 1) -> list[AudioVariantPlan]:
    variants = [
        AudioVariantPlan("ORIGINAL_NORMALIZED", "Primary recognition input", "16 kHz mono PCM/FLAC with timestamps reset only", "Hash source and derivative; never overwrite source.", True),
        AudioVariantPlan("DENOISED_PARALLEL", "Improve low-SNR words", "Conservative stationary-noise reduction", "May contribute only as a secondary hypothesis; never replace original wording alone.", True),
    ]
    if source_channels >= 2:
        variants.extend([
            AudioVariantPlan("LEFT_CHANNEL", "Test whether one microphone isolates a participant", "Extract channel 0 without mixing", "Use only after channel-correlation and clipping audit.", True),
            AudioVariantPlan("RIGHT_CHANNEL", "Test whether one microphone isolates a participant", "Extract channel 1 without mixing", "Use only after channel-correlation and clipping audit.", True),
        ])
    return variants
