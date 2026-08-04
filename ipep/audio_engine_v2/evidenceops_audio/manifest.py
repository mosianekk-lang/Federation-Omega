from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .common import utc_now

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class ChunkRecord:
    sequence: int
    file: str
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    size_bytes: int
    sha256: str
    drive_id: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ChunkRecord":
        return cls(
            sequence=int(raw["sequence"]),
            file=str(raw["file"]),
            start_seconds=float(raw["start_seconds"]),
            end_seconds=float(raw["end_seconds"]),
            duration_seconds=float(raw["duration_seconds"]),
            size_bytes=int(raw["size_bytes"]),
            sha256=str(raw["sha256"]).lower(),
            drive_id=str(raw["drive_id"]) if raw.get("drive_id") else None,
        )


@dataclass(frozen=True)
class AudioManifest:
    source_file: str
    source_drive_id: str
    preservation_copy_drive_id: str
    source_sha256: str
    source_size_bytes: int
    source_duration_seconds: float
    processing_profile: dict[str, Any]
    chunks: tuple[ChunkRecord, ...]
    transcription_state: str
    truth_boundary: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AudioManifest":
        return cls(
            source_file=str(raw["source_file"]),
            source_drive_id=str(raw["source_drive_id"]),
            preservation_copy_drive_id=str(raw["preservation_copy_drive_id"]),
            source_sha256=str(raw["source_sha256"]).lower(),
            source_size_bytes=int(raw["source_size_bytes"]),
            source_duration_seconds=float(raw["source_duration_seconds"]),
            processing_profile=dict(raw["processing_profile"]),
            chunks=tuple(ChunkRecord.from_dict(item) for item in raw["chunks"]),
            transcription_state=str(raw.get("transcription_state", "UNKNOWN")),
            truth_boundary=str(raw.get("truth_boundary", "")),
        )

    def validate(self, tolerance_seconds: float = 0.05) -> dict[str, Any]:
        errors: list[str] = []
        if not SHA256_RE.fullmatch(self.source_sha256):
            errors.append("source_sha256 is not a lowercase 64-character SHA-256")
        if self.source_size_bytes <= 0 or self.source_duration_seconds <= 0:
            errors.append("source size and duration must be positive")
        if not self.chunks:
            errors.append("no chunks present")
        expected_start = 0.0
        expected_sequence = 1
        for chunk in self.chunks:
            if chunk.sequence != expected_sequence:
                errors.append(
                    f"sequence mismatch at {chunk.file}: expected {expected_sequence}, got {chunk.sequence}"
                )
            if not SHA256_RE.fullmatch(chunk.sha256):
                errors.append(f"invalid chunk SHA-256: {chunk.file}")
            if chunk.size_bytes <= 0 or chunk.duration_seconds <= 0:
                errors.append(f"non-positive size or duration: {chunk.file}")
            if abs(chunk.start_seconds - expected_start) > tolerance_seconds:
                errors.append(
                    f"coverage gap/overlap before {chunk.file}: expected {expected_start}, got {chunk.start_seconds}"
                )
            if abs((chunk.end_seconds - chunk.start_seconds) - chunk.duration_seconds) > tolerance_seconds:
                errors.append(f"duration mismatch: {chunk.file}")
            expected_start = chunk.end_seconds
            expected_sequence += 1
        if self.chunks and abs(self.chunks[-1].end_seconds - self.source_duration_seconds) > tolerance_seconds:
            errors.append(
                f"final coverage mismatch: chunks end {self.chunks[-1].end_seconds}, source {self.source_duration_seconds}"
            )
        if errors:
            raise ManifestError("; ".join(errors))
        return {
            "status": "MANIFEST_VALID",
            "chunk_count": len(self.chunks),
            "coverage_start": self.chunks[0].start_seconds,
            "coverage_end": self.chunks[-1].end_seconds,
            "source_duration_seconds": self.source_duration_seconds,
            "coverage_pct": round(
                (self.chunks[-1].end_seconds / self.source_duration_seconds) * 100,
                6,
            ),
            "validated_at": utc_now(),
        }


def load_manifest(path: str | Path) -> AudioManifest:
    raw = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    manifest = AudioManifest.from_dict(raw)
    manifest.validate()
    return manifest
