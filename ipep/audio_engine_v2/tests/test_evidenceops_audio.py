import hashlib
import tempfile
import unittest
from pathlib import Path

from evidenceops_audio.core import AudioManifest, EvidenceOpsAudioEngine, ManifestError, redact


def manifest_dict(tmp_path: Path):
    payload = b"test-audio"
    path = tmp_path / "part.flac"
    path.write_bytes(payload)
    sha = hashlib.sha256(payload).hexdigest()
    raw = {
        "source_file": "source.m4a",
        "source_drive_id": "source-id",
        "preservation_copy_drive_id": "copy-id",
        "source_sha256": "a" * 64,
        "source_size_bytes": 100,
        "source_duration_seconds": 10.0,
        "processing_profile": {"channels": 1, "sample_rate_hz": 16000, "codec": "FLAC", "segment_seconds": 10},
        "chunks": [{
            "sequence": 1,
            "file": "part.flac",
            "start_seconds": 0,
            "end_seconds": 10,
            "duration_seconds": 10,
            "size_bytes": len(payload),
            "sha256": sha,
        }],
        "transcription_state": "STAGED_NOT_TRANSCRIBED",
        "truth_boundary": "No transcript",
    }
    return raw, path


class EvidenceOpsAudioTests(unittest.TestCase):
    def test_valid_manifest_and_integrity(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            raw, path = manifest_dict(root)
            manifest = AudioManifest.from_dict(raw)
            self.assertEqual(manifest.validate()["coverage_pct"], 100.0)
            engine = EvidenceOpsAudioEngine(root / "work", manifest)
            self.assertEqual(engine.verify_chunk(manifest.chunks[0], path)["state"], "INTEGRITY_VERIFIED")

    def test_gap_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            raw, _ = manifest_dict(Path(d))
            raw["chunks"][0]["start_seconds"] = 1
            with self.assertRaises(ManifestError):
                AudioManifest.from_dict(raw).validate()

    def test_bad_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            raw, _ = manifest_dict(Path(d))
            raw["chunks"][0]["sha256"] = "bad"
            with self.assertRaises(ManifestError):
                AudioManifest.from_dict(raw).validate()

    def test_redaction_is_recursive(self):
        value = {"api_key": "abc", "nested": {"approvalKey": "def", "safe": 1}}
        self.assertEqual(redact(value), {"api_key": "[REDACTED]", "nested": {"approvalKey": "[REDACTED]", "safe": 1}})

    def test_preflight_truth_boundary(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            raw, _ = manifest_dict(root)
            engine = EvidenceOpsAudioEngine(root / "work", AudioManifest.from_dict(raw))
            receipt = engine.preflight()
            self.assertFalse(receipt["truth_boundary"]["transcript_created"])
            self.assertEqual(
                {p["provider"] for p in receipt["providers"]},
                {
                    "local_whisper_cpp",
                    "google_speech_v2",
                    "openai_audio_transcriptions",
                    "gemini_files_api",
                },
            )

    def test_resume_plan(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            raw, _ = manifest_dict(root)
            engine = EvidenceOpsAudioEngine(root / "work", AudioManifest.from_dict(raw))
            self.assertEqual(engine.build_resume_plan()["completion_pct"], 0)
            out = engine.chunk_output_dir / "chunk-001.txt"
            out.write_text("hello", encoding="utf-8")
            self.assertEqual(engine.build_resume_plan()["completion_pct"], 100)

    def test_assembly_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            raw, _ = manifest_dict(root)
            engine = EvidenceOpsAudioEngine(root / "work", AudioManifest.from_dict(raw))
            result = engine.assemble_transcript()
            self.assertEqual(result["state"], "BLOCKED_MISSING_CHUNKS")
            self.assertEqual(result["missing_chunks"], [1])


if __name__ == "__main__":
    unittest.main()
