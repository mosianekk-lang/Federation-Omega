from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from .common import redact, sha256_file, utc_now
from .manifest import AudioManifest, ChunkRecord, ManifestError
from .providers import GeminiFilesProvider, GoogleSpeechV2Provider, LocalWhisperCppProvider


class EvidenceOpsAudioEngine:
    """Alpha→Omega orchestration with Formation proof gates and IPEP in-place outputs."""

    def __init__(self, workspace: str | Path, manifest: AudioManifest):
        self.workspace = Path(workspace)
        self.manifest = manifest
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.receipts_dir = self.workspace / "receipts"
        self.outputs_dir = self.workspace / "outputs"
        self.chunk_output_dir = self.outputs_dir / "chunks"
        self.receipts_dir.mkdir(exist_ok=True)
        self.chunk_output_dir.mkdir(parents=True, exist_ok=True)

    def providers(self):
        return [LocalWhisperCppProvider(), GoogleSpeechV2Provider(), GeminiFilesProvider()]

    def preflight(self):
        provider_results = [dataclasses.asdict(provider.preflight()) for provider in self.providers()]
        receipt = {
            "contract": "EVIDENCEOPS_AUDIO_PREFLIGHT_V2",
            "state": "READY_PROVIDER" if any(item["ready"] for item in provider_results) else "BLOCKED_PROVIDER_AUTH_OR_MODEL",
            "manifest": self.manifest.validate(),
            "providers": provider_results,
            "truth_boundary": {
                "manifest_valid": True,
                "transcript_created": False,
                "provider_execution_verified": False,
            },
            "recorded_at": utc_now(),
        }
        self._write_receipt("preflight", receipt)
        return receipt

    def verify_chunk(self, chunk: ChunkRecord, audio_path: str | Path):
        path = Path(audio_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        observed = {"size_bytes": path.stat().st_size, "sha256": sha256_file(path)}
        passed = observed["size_bytes"] == chunk.size_bytes and observed["sha256"] == chunk.sha256
        receipt = {
            "contract": "EVIDENCEOPS_AUDIO_CHUNK_INTEGRITY_V2",
            "sequence": chunk.sequence,
            "file": chunk.file,
            "expected": {"size_bytes": chunk.size_bytes, "sha256": chunk.sha256},
            "observed": observed,
            "state": "INTEGRITY_VERIFIED" if passed else "INTEGRITY_FAILED",
            "recorded_at": utc_now(),
        }
        self._write_receipt(f"chunk-{chunk.sequence:03d}-integrity", receipt)
        if not passed:
            raise ManifestError(f"chunk integrity failed: {chunk.file}")
        return receipt

    def transcribe_chunk(self, sequence, audio_path, provider_name=None):
        chunk = next((item for item in self.manifest.chunks if item.sequence == sequence), None)
        if not chunk:
            raise KeyError(f"chunk sequence not found: {sequence}")
        integrity = self.verify_chunk(chunk, audio_path)
        candidates = self.providers()
        if provider_name:
            candidates = [provider for provider in candidates if provider.name == provider_name]
            if not candidates:
                raise KeyError(f"unknown provider: {provider_name}")
        attempted = []
        selected = None
        for provider in candidates:
            preflight = provider.preflight()
            attempted.append(dataclasses.asdict(preflight))
            if preflight.ready:
                selected = provider
                break
        if not selected:
            receipt = {
                "contract": "EVIDENCEOPS_AUDIO_TRANSCRIPTION_V2",
                "state": "BLOCKED_PROVIDER_AUTH_OR_MODEL",
                "sequence": sequence,
                "integrity": integrity,
                "provider_attempts": attempted,
                "truth_boundary": "No transcript was created.",
                "recorded_at": utc_now(),
            }
            self._write_receipt(f"chunk-{sequence:03d}-transcription", receipt)
            return receipt
        provider_result = selected.transcribe(Path(audio_path), chunk, self.chunk_output_dir)
        transcript_path = self.chunk_output_dir / f"chunk-{sequence:03d}.txt"
        if provider_result.transcript_text.strip():
            transcript_path.write_text(provider_result.transcript_text, encoding="utf-8")
        receipt = {
            "contract": "EVIDENCEOPS_AUDIO_TRANSCRIPTION_V2",
            "state": provider_result.state,
            "sequence": sequence,
            "chunk": dataclasses.asdict(chunk),
            "integrity": integrity,
            "provider": selected.name,
            "provider_result": redact(dataclasses.asdict(provider_result)),
            "transcript_path": str(transcript_path) if transcript_path.exists() else None,
            "transcript_sha256": sha256_file(transcript_path) if transcript_path.exists() else None,
            "truth_boundary": "Transcript claimed only when state is TRANSCRIBED and transcript SHA-256 exists.",
            "recorded_at": utc_now(),
        }
        self._write_receipt(f"chunk-{sequence:03d}-transcription", receipt)
        return receipt

    def build_resume_plan(self):
        rows = []
        for chunk in self.manifest.chunks:
            path = self.chunk_output_dir / f"chunk-{chunk.sequence:03d}.txt"
            rows.append({
                "sequence": chunk.sequence,
                "file": chunk.file,
                "state": "TRANSCRIBED" if path.exists() and path.stat().st_size else "PENDING",
                "transcript_path": str(path) if path.exists() else None,
            })
        completed = sum(row["state"] == "TRANSCRIBED" for row in rows)
        return {
            "contract": "EVIDENCEOPS_AUDIO_RESUME_PLAN_V2",
            "completed_chunks": completed,
            "total_chunks": len(rows),
            "completion_pct": round(completed / len(rows) * 100, 2) if rows else 0,
            "chunks": rows,
            "recorded_at": utc_now(),
        }

    def assemble_transcript(self):
        missing = []
        sections = []
        for chunk in self.manifest.chunks:
            path = self.chunk_output_dir / f"chunk-{chunk.sequence:03d}.txt"
            if not path.exists() or not path.stat().st_size:
                missing.append(chunk.sequence)
                continue
            sections.append(
                f"\n\n=== CHUNK {chunk.sequence:03d} | {chunk.start_seconds:.3f}s-"
                f"{chunk.end_seconds:.3f}s | {chunk.sha256} ===\n\n"
                + path.read_text(encoding="utf-8", errors="replace")
            )
        output = self.outputs_dir / "master-verbatim-transcript.txt"
        if not missing:
            output.write_text("".join(sections).lstrip(), encoding="utf-8")
        receipt = {
            "contract": "EVIDENCEOPS_AUDIO_ASSEMBLY_V2",
            "state": "ASSEMBLED" if not missing else "BLOCKED_MISSING_CHUNKS",
            "missing_chunks": missing,
            "output": str(output) if output.exists() else None,
            "output_sha256": sha256_file(output) if output.exists() else None,
            "recorded_at": utc_now(),
        }
        self._write_receipt("master-assembly", receipt)
        return receipt

    def _write_receipt(self, name, payload):
        path = self.receipts_dir / f"{name}.json"
        path.write_text(
            json.dumps(redact(payload), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path
