from __future__ import annotations

import json
import os
import secrets
import urllib.error
import urllib.request
from pathlib import Path

from .common import ProviderPreflight, ProviderResult, redact
from .manifest import ChunkRecord


class OpenAITranscriptionProvider:
    name = "openai_audio_transcriptions"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model or os.getenv(
            "IPEP_OPENAI_TRANSCRIBE_MODEL", "gpt-4o-transcribe-diarize"
        )
        self.endpoint = os.getenv(
            "IPEP_OPENAI_TRANSCRIBE_ENDPOINT",
            "https://api.openai.com/v1/audio/transcriptions",
        )

    def preflight(self) -> ProviderPreflight:
        missing = () if self.api_key else ("OPENAI_API_KEY",)
        return ProviderPreflight(
            self.name,
            bool(self.api_key),
            "READY" if self.api_key else "BLOCKED_CREDENTIAL",
            missing,
            {"model": self.model, "api_key_present": bool(self.api_key)},
        )

    @staticmethod
    def _multipart(fields: dict[str, str], audio_path: Path) -> tuple[bytes, str]:
        boundary = "----evidenceops-" + secrets.token_hex(16)
        chunks: list[bytes] = []
        for key, value in fields.items():
            chunks.extend([
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode(),
                str(value).encode(),
                b"\r\n",
            ])
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            (
                'Content-Disposition: form-data; name="file"; '
                f'filename="{audio_path.name}"\r\n'
            ).encode(),
            b"Content-Type: audio/flac\r\n\r\n",
            audio_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ])
        return b"".join(chunks), boundary

    @staticmethod
    def _timestamp(seconds: float) -> str:
        total = max(0, int(round(seconds)))
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def transcribe(self, audio_path: Path, chunk: ChunkRecord, output_dir: Path) -> ProviderResult:
        preflight = self.preflight()
        if not preflight.ready:
            return ProviderResult(
                self.name, preflight.state, error="; ".join(preflight.requirements)
            )
        fields = {
            "model": self.model,
            "response_format": "diarized_json",
            "chunking_strategy": "auto",
            "language": os.getenv("IPEP_OPENAI_LANGUAGE", "en"),
        }
        body, boundary = self._multipart(fields, audio_path)
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=3600) as response:
                payload = json.loads(response.read().decode("utf-8", "replace"))
            segments = payload.get("segments") or []
            lines: list[str] = []
            normalized_segments: list[dict[str, object]] = []
            for segment in segments:
                relative_start = float(segment.get("start", 0.0) or 0.0)
                relative_end = float(segment.get("end", relative_start) or relative_start)
                absolute_start = chunk.start_seconds + relative_start
                absolute_end = chunk.start_seconds + relative_end
                speaker = str(
                    segment.get("speaker")
                    or segment.get("speaker_label")
                    or "SPEAKER_UNKNOWN"
                )
                spoken = str(segment.get("text", "")).strip()
                if spoken:
                    lines.append(
                        f"[{self._timestamp(absolute_start)}] {speaker}: {spoken}"
                    )
                normalized_segments.append({
                    "speaker": speaker,
                    "relative_start": relative_start,
                    "relative_end": relative_end,
                    "absolute_start": absolute_start,
                    "absolute_end": absolute_end,
                    "text": spoken,
                })
            transcript = "\n".join(lines).strip() or str(payload.get("text", "")).strip()
            return ProviderResult(
                self.name,
                "TRANSCRIBED" if transcript else "FAILED_EMPTY_TRANSCRIPT",
                transcript_text=transcript,
                segments=tuple(normalized_segments),
                raw=redact(payload),
            )
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", "replace")
            return ProviderResult(
                self.name, "FAILED", error=f"HTTP {exc.code}: {error_body[:3000]}"
            )
        except Exception as exc:
            return ProviderResult(
                self.name, "FAILED", error=f"{type(exc).__name__}: {exc}"
            )
