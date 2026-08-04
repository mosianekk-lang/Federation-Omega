from __future__ import annotations

from pathlib import Path
import json

from .cleanup import suppress_repetition
from .lexicon import LegalLexicon
from .models import TranscriptHypothesis
from .rover import fuse


class ConsensusTranscriptionMode:
    """EvidenceOps v3 multi-recogniser consensus mode.

    It accepts independently produced, word-timestamped hypotheses. It does not
    claim that a provider ran merely because an adapter is configured.
    """

    def __init__(self, review_threshold: float = 0.67, lexicon: LegalLexicon | None = None):
        self.review_threshold = review_threshold
        self.lexicon = lexicon or LegalLexicon()

    def run(self, hypotheses: list[TranscriptHypothesis], output_dir: str | Path) -> dict:
        if len(hypotheses) < 2:
            return {
                "contract": "EVIDENCEOPS_CONSENSUS_TRANSCRIPTION_V3",
                "state": "BLOCKED_INSUFFICIENT_INDEPENDENT_HYPOTHESES",
                "required": 2,
                "observed": len(hypotheses),
                "truth_boundary": "A consensus transcript is never claimed from one recogniser.",
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
        review = [word.to_dict() for word in words if word.needs_review]
        review_path = output / "consensus_review_queue.json"
        review_path.write_text(json.dumps(review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        return {
            "contract": "EVIDENCEOPS_CONSENSUS_TRANSCRIPTION_V3",
            "state": "CONSENSUS_ASSEMBLED_WITH_REVIEW_QUEUE" if review else "CONSENSUS_ASSEMBLED",
            "models": [h.model for h in hypotheses],
            "model_count": len(hypotheses),
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
