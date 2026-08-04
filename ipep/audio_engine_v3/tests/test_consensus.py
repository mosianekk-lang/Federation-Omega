import tempfile
import unittest
from pathlib import Path

from evidenceops_consensus import (
    ConsensusTranscriptionMode,
    LegalLexicon,
    LexiconEntry,
    TranscriptHypothesis,
    WordHypothesis,
    fuse,
)
from evidenceops_consensus.cleanup import suppress_repetition


def h(model, text, weight=1.0, confidence=0.9):
    words = []
    for i, token in enumerate(text.split()):
        words.append(WordHypothesis(token, i * 0.5, i * 0.5 + 0.4, confidence, "S1", model))
    return TranscriptHypothesis(model, tuple(words), weight)


class ConsensusTests(unittest.TestCase):
    def test_majority_corrects_single_model_error(self):
        out = fuse([
            h("whisper", "the commissioner reserved the ruling", 1.0),
            h("parakeet", "the commissioner reserved the ruling", 1.1),
            h("other", "the commission reserved the rolling", 0.8),
        ])
        self.assertEqual(" ".join(x.text.lower() for x in out), "the commissioner reserved the ruling")

    def test_low_agreement_enters_review_queue(self):
        out = fuse([h("a", "alpha"), h("b", "bravo")], review_threshold=0.67)
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

    def test_single_model_cannot_claim_consensus(self):
        with tempfile.TemporaryDirectory() as d:
            result = ConsensusTranscriptionMode().run([h("only", "hello")], d)
            self.assertEqual(result["state"], "BLOCKED_INSUFFICIENT_INDEPENDENT_HYPOTHESES")

    def test_engine_writes_consensus_and_review_receipts(self):
        lex = LegalLexicon((LexiconEntry("point in limine", ("pointing limine",), 1.0),))
        with tempfile.TemporaryDirectory() as d:
            result = ConsensusTranscriptionMode(lexicon=lex).run([
                h("whisper", "the point in limine was raised"),
                h("parakeet", "the point in limine was raised"),
                h("third", "the pointing limine was raised", 0.7),
            ], d)
            self.assertTrue(Path(result["outputs"]["transcript"]).exists())
            text = Path(result["outputs"]["transcript"]).read_text()
            self.assertIn("point in limine", text)
            self.assertTrue(Path(result["outputs"]["review_queue"]).exists())


if __name__ == "__main__":
    unittest.main()
