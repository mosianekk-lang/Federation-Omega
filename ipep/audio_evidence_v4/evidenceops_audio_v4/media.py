from __future__ import annotations

import json
import math
import shutil
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from .hashing import sha256_file


class MediaToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class AudioProbe:
    duration_seconds: float
    sample_rate: int | None
    channels: int | None
    codec_name: str | None
    format_name: str | None
    size_bytes: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def require_executable(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise MediaToolError(f"required executable not found: {name}")
    return resolved


def probe_audio(path: str | Path) -> AudioProbe:
    source = Path(path)
    ffprobe = require_executable("ffprobe")
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration,format_name,size:stream=codec_type,codec_name,sample_rate,channels",
            "-of",
            "json",
            str(source),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise MediaToolError(completed.stderr.strip() or "ffprobe failed")
    payload = json.loads(completed.stdout)
    audio_stream = next((row for row in payload.get("streams", []) if row.get("codec_type") == "audio"), {})
    fmt = payload.get("format", {})
    return AudioProbe(
        duration_seconds=float(fmt.get("duration") or 0.0),
        sample_rate=int(audio_stream["sample_rate"]) if audio_stream.get("sample_rate") else None,
        channels=int(audio_stream["channels"]) if audio_stream.get("channels") else None,
        codec_name=audio_stream.get("codec_name"),
        format_name=fmt.get("format_name"),
        size_bytes=source.stat().st_size,
        sha256=sha256_file(source),
    )


def normalize_audio(
    source: str | Path,
    output: str | Path,
    *,
    sample_rate: int = 16000,
    channels: int = 1,
) -> dict[str, Any]:
    ffmpeg = require_executable("ffmpeg")
    source_path = Path(source)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-i",
        str(source_path),
        "-vn",
        "-ac",
        str(channels),
        "-ar",
        str(sample_rate),
        "-c:a",
        "flac",
        str(output_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise MediaToolError(completed.stderr[-4000:])
    return {
        "command": ["ffmpeg", "-i", source_path.name, "-ac", channels, "-ar", sample_rate, "-c:a", "flac"],
        "output": str(output_path),
        "output_sha256": sha256_file(output_path),
        "output_size_bytes": output_path.stat().st_size,
        "probe": probe_audio(output_path).to_dict(),
    }


def split_audio(
    source: str | Path,
    output_dir: str | Path,
    *,
    unit_seconds: float = 60.0,
    prefix: str = "unit",
) -> list[dict[str, Any]]:
    if unit_seconds <= 0:
        raise ValueError("unit_seconds must be positive")
    ffmpeg = require_executable("ffmpeg")
    source_path = Path(source)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    duration = probe_audio(source_path).duration_seconds
    units = []
    count = math.ceil(duration / unit_seconds)
    for index in range(count):
        start = index * unit_seconds
        end = min(duration, start + unit_seconds)
        output_path = destination / f"{prefix}-{index + 1:04d}.flac"
        command = [
            ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-y",
            "-ss",
            f"{start:.6f}",
            "-t",
            f"{end - start:.6f}",
            "-i",
            str(source_path),
            "-vn",
            "-c:a",
            "flac",
            str(output_path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise MediaToolError(f"unit {index + 1} split failed: {completed.stderr[-3000:]}")
        units.append(
            {
                "sequence": index + 1,
                "path": str(output_path),
                "start_seconds": round(start, 6),
                "end_seconds": round(end, 6),
                "duration_seconds": round(end - start, 6),
                "sha256": sha256_file(output_path),
                "size_bytes": output_path.stat().st_size,
            }
        )
    return units


def extract_audio_window(
    source: str | Path,
    output: str | Path,
    *,
    start_seconds: float,
    end_seconds: float,
) -> dict[str, Any]:
    if end_seconds <= start_seconds:
        raise ValueError("end_seconds must exceed start_seconds")
    ffmpeg = require_executable("ffmpeg")
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-y",
            "-ss",
            f"{start_seconds:.6f}",
            "-t",
            f"{end_seconds - start_seconds:.6f}",
            "-i",
            str(source),
            "-vn",
            "-c:a",
            "flac",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise MediaToolError(completed.stderr[-3000:])
    return {
        "path": str(output_path),
        "start_seconds": start_seconds,
        "end_seconds": end_seconds,
        "sha256": sha256_file(output_path),
        "size_bytes": output_path.stat().st_size,
    }
