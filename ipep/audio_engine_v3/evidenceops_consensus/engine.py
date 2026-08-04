from __future__ import annotations

from pathlib import Path
import json

from .cleanup import suppress_repetition
from .lexicon import LegalLexicon
from .models import TranscriptHypothesis
from .review import prioritize_review
from .rover import fuse


class ConsensusTranscriptionMode:
    """EvidenceOps v3.1 multi-architecture consensus mode.

    It accepts independently produced, word-timestamped hypotheses. Different
    checkpoints from the same architecture family do not satisfy the diversity
    gate. Provider execution is never claimed merely because an adapter exists.
    """

    def __init__(
        self,
        review_threshold: float = 0.67,
        lexicon: LegalLexicon | None = None,
        minimum_architectures: int = 2,
    ):
        self.review_threshold = review_threshold
        self.lexicon = lexicon or LegalLexicon()
        self.minimum_architectures = minimum_architectures

    def run(self, hypotheses: list[TranscriptHypothesis], output_dir: str | Path) -> dict:
        families = sorted({h.architecture_family for h in hypotheses if h.architecture_family != "unknown"})
        if len(families) < self.minimum_architectures:
            return {
                "contract": "EVIDENCEOPS_CONSENSUS_TRANSCRIPTION_V3_1",
                "state": "BLOCKED_INSUFFICIENT_INDEPENDENT_ARCHITECTURES",
                "required_architectures": self.minimum_architectures,
                "observed_architectures": families,
                "observed_models": [h.model for h in hypotheses],
                "truth_boundary": "Different checkpoints from one ASR family are not independent consensus evidence.",
            }
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        words = fuse(hypotheses, review_threshold=self.review_threshold)
        raw_tokens = [word.text for word in words]
        deduped, repetition_corrections = suppress_repetition(raw_tokens)
        corrected, lexicon_corrections = self.lexicon.apply(deduped)

        consensus_json = output / "consensus_words.json"
        consensus_json.write_text(
            json.dumps([word.to_dict() for word in words], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        transcript_path = output / "consensus_transcript.txt"
        transcript_path.write_text(" ".join(corrected).strip() + "\n", encoding="utf-8")
        corrections = [c.to_dict() for c in repetition_corrections + lexicon_corrections]
        correction_path = output / "consensus_corrections.json"
        correction_path.write_text(json.dumps(corrections, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        review = prioritize_review(words)
        review_path = output / "consensus_review_queue.json"
        review_path.write_text(json.dumps(review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        return {
            "contract": "EVIDENCEOPS_CONSENSUS_TRANSCRIPTION_V3_1",
            "state": "CONSENSUS_ASSEMBLED_WITH_REVIEW_QUEUE" if review else "CONSENSUS_ASSEMBLED",
            "models": [h.model for h in hypotheses],
            "architecture_families": families,
            "model_count": len(hypotheses),
            "architecture_count": len(families),
            "consensus_word_count": len(words),
            "review_word_count": len(review),
            "review_pct": round(len(review) / len(words) * 100, 2) if words else 0.0,
            "correction_count": len(corrections),
            "outputs": {
                "transcript": str(transcript_path),
                "words": str(consensus_json),
                "corrections": str(correction_path),
                "review_queue": str(review_path),
            },
            "truth_boundary": "Consensus reduces single-model errors but does not replace human verification of filing quotations.",
        }
