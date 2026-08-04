import tempfile
import unittest
from pathlib import Path

from evidenceops_consensus import (
    ConsensusTranscriptionMode,
    LegalLexicon,
    LexiconEntry,
    QuotationEvidence,
    TranscriptHypothesis,
    WordHypothesis,
    calibrate_weights,
    fuse,
    prioritize_review,
    quotation_release_gate,
    word_error_rate,
)
from evidenceops_consensus.cleanup import suppress_repetition


def h(model, text, weight=1.0, confidence=0.9, family="whisper_encoder_decoder"):
    words = []
    for i, token in enumerate(text.split()):
        words.append(WordHypothesis(token, i * 0.5, i * 0.5 + 0.4, confidence, "S1", model))
    return TranscriptHypothesis(model, tuple(words), weight, {"architecture_family": family})


class ConsensusTests(unittest.TestCase):
    def test_majority_corrects_single_model_error(self):
        out = fuse([
            h("whisper", "the commissioner reserved the ruling", 1.0, family="whisper_encoder_decoder"),
            h("parakeet", "the commissioner reserved the ruling", 1.1, family="nvidia_parakeet_tdt"),
            h("openai", "the commission reserved the rolling", 0.8, family="openai_gpt4o_asr"),
        ])
        self.assertEqual(" ".join(x.text.lower() for x in out), "the commissioner reserved the ruling")

    def test_low_agreement_enters_review_queue(self):
        out = fuse([
            h("a", "alpha", family="whisper_encoder_decoder"),
            h("b", "bravo", family="nvidia_parakeet_tdt"),
        ], review_threshold=0.67)
        self.assertTrue(out[0].needs_review)

    def test_repetition_suppression_is_logged(self):
        tokens, log = suppress_repetition("thank you thank you thank you thank you next".split(), max_repeat=2)
        self.assertEqual(tokens, "thank you thank you next".split())
        self.assertEqual(log[0].kind, "REPETITION_SUPPRESSION")

    def test_legal_lexicon_correction_is_auditable(self):
        lex = LegalLexicon((LexiconEntry("functus officio", ("factors official", "functus official"), 1.0),))
        out, log = lex.apply("the ccma is factors official".split())
        self.assertIn("functus", out)
        self.assertEqual(log[0].after, "functus officio")

    def test_legal_lexicon_does_not_overcorrect_ordinary_language(self):
        lex = LegalLexicon((
            LexiconEntry("functus officio", ("factors official",), 1.0),
            LexiconEntry("point in limine", ("pointing limine",), 1.0),
        ))
        out, log = lex.apply("the factors that you have to consider include the reporting line".split())
        self.assertEqual(" ".join(out), "the factors that you have to consider include the reporting line")
        self.assertEqual(log, [])

    def test_two_whisper_models_do_not_satisfy_architecture_gate(self):
        with tempfile.TemporaryDirectory() as d:
            result = ConsensusTranscriptionMode().run([
                h("whisper-small", "hello"),
                h("whisper-large", "hello"),
            ], d)
            self.assertEqual(result["state"], "BLOCKED_INSUFFICIENT_INDEPENDENT_ARCHITECTURES")

    def test_independent_architectures_can_produce_consensus(self):
        with tempfile.TemporaryDirectory() as d:
            result = ConsensusTranscriptionMode().run([
                h("whisper-large", "the point in limine was raised", family="whisper_encoder_decoder"),
                h("parakeet", "the point in limine was raised", family="nvidia_parakeet_tdt"),
            ], d)
            self.assertTrue(Path(result["outputs"]["transcript"]).exists())
            self.assertEqual(result["architecture_count"], 2)

    def test_review_prioritizes_legal_disagreement(self):
        words = fuse([
            h("whisper", "jurisdiction ordinary", family="whisper_encoder_decoder"),
            h("parakeet", "juris diction ordinary", family="nvidia_parakeet_tdt"),
        ])
        queue = prioritize_review(words)
        self.assertGreaterEqual(queue[0]["priority"], queue[-1]["priority"])

    def test_word_error_rate_and_calibration(self):
        self.assertEqual(word_error_rate("the ruling", "the ruling"), 0.0)
        results = calibrate_weights("the commissioner reserved the ruling", {
            "good": ("nvidia_parakeet_tdt", "the commissioner reserved the ruling"),
            "bad": ("whisper_encoder_decoder", "the commission reversed a rolling"),
        })
        self.assertLess(results[0].wer, results[1].wer)
        self.assertGreater(results[0].weight, results[1].weight)

    def test_quotation_gate_requires_human_listening(self):
        blocked = quotation_release_gate(QuotationEvidence(2, True, True, True, False, "a" * 64))
        self.assertEqual(blocked["state"], "BLOCKED_NOT_VERIFIED_FOR_QUOTATION")
        passed = quotation_release_gate(QuotationEvidence(2, True, True, True, True, "a" * 64))
        self.assertEqual(passed["state"], "VERIFIED_FOR_QUOTATION")


if __name__ == "__main__":
    unittest.main()
