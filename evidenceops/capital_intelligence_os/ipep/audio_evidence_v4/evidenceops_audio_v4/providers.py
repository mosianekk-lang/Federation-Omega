from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .hashing import atomic_write_json, sha256_bytes, sha256_file
from .ledger import utc_now
from .models import TranscriptSegment, TranslationRecord, UnitReceipt


class ProviderError(RuntimeError):
    pass


class TranslationAdapter(Protocol):
    name: str

    def translate(
        self,
        *,
        segment_id: str,
        text: str,
        source_language: str,
        target_language: str,
        receipt_dir: str | Path,
    ) -> TranslationRecord: ...


@dataclass(frozen=True)
class WhisperCppConfig:
    binary: str
    model: str
    vad_model: str | None = None
    language: str = "auto"
    timeout_seconds: int = 1800


class WhisperCppUnitAdapter:
    """Local whisper.cpp adapter that preserves a raw receipt per unit.

    The adapter records zero-segment units explicitly. It does not silently turn
    an empty provider response into a missing unit.
    """

    name = "local_whisper_cpp"
    architecture_family = "whisper_encoder_decoder"

    def __init__(self, config: WhisperCppConfig):
        self.config = config

    def _resolve_binary(self) -> str:
        binary = self.config.binary
        resolved = shutil.which(binary) if not Path(binary).exists() else binary
        if not resolved:
            raise ProviderError(f"whisper.cpp binary not found: {binary}")
        if not Path(self.config.model).is_file():
            raise ProviderError(f"whisper.cpp model not found: {self.config.model}")
        if self.config.vad_model and not Path(self.config.vad_model).is_file():
            raise ProviderError(f"VAD model not found: {self.config.vad_model}")
        return str(resolved)

    @staticmethod
    def _offset_seconds(value: Any) -> float | None:
        if value is None:
            return None
        numeric = float(value)
        return numeric / 1000.0 if numeric > 1000 else numeric

    def _parse_segments(
        self,
        payload: dict[str, Any],
        *,
        unit_id: str,
        source_item_id: str,
        absolute_start: float,
        raw_response_sha256: str,
    ) -> tuple[list[TranscriptSegment], str]:
        rows = payload.get("transcription") or payload.get("segments") or []
        language = (
            payload.get("result", {}).get("language")
            or payload.get("language")
            or self.config.language
            or "und"
        )
        segments: list[TranscriptSegment] = []
        for index, row in enumerate(rows, start=1):
            text = str(row.get("text") or "").strip()
            if not text:
                continue
            offsets = row.get("offsets") or row.get("timestamps") or {}
            start = (float(offsets.get("from")) / 1000.0) if isinstance(offsets, dict) and offsets.get("from") is not None else None
            end = (float(offsets.get("to")) / 1000.0) if isinstance(offsets, dict) and offsets.get("to") is not None else None
            if start is None:
                start = self._offset_seconds(row.get("start")) or 0.0
            if end is None:
                end = self._offset_seconds(row.get("end"))
            if end is None:
                end = start
            probabilities = row.get("tokens") or []
            confidence_values = [float(token["p"]) for token in probabilities if isinstance(token, dict) and token.get("p") is not None]
            confidence = sum(confidence_values) / len(confidence_values) if confidence_values else row.get("confidence")
            segments.append(
                TranscriptSegment(
                    segment_id=f"{unit_id}-S{index:04d}",
                    unit_id=unit_id,
                    source_item_id=source_item_id,
                    start_seconds=round(absolute_start + start, 6),
                    end_seconds=round(absolute_start + end, 6),
                    original_text=text,
                    source_language=str(language),
                    provider=self.name,
                    architecture_family=self.architecture_family,
                    confidence=float(confidence) if confidence is not None else None,
                    speaker_label=None,
                    speaker_role=None,
                    word_timestamps_present=bool(row.get("tokens")),
                    raw_response_sha256=raw_response_sha256,
                    metadata={"provider_row": index},
                )
            )
        return segments, str(language)

    def transcribe_unit(
        self,
        *,
        unit_path: str | Path,
        source_item_id: str,
        source_sha256: str,
        unit_id: str,
        absolute_start: float,
        absolute_end: float,
        receipt_dir: str | Path,
    ) -> tuple[UnitReceipt, list[TranscriptSegment]]:
        binary = self._resolve_binary()
        audio = Path(unit_path)
        output = Path(receipt_dir)
        output.mkdir(parents=True, exist_ok=True)
        prefix = output / unit_id
        command = [
            binary,
            "-m",
            self.config.model,
            "-f",
            str(audio),
            "-of",
            str(prefix),
            "-oj",
            "-l",
            self.config.language,
        ]
        if self.config.vad_model:
            command.extend(["--vad", "--vad-model", self.config.vad_model])
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=self.config.timeout_seconds,
            check=False,
        )
        json_path = prefix.with_suffix(".json")
        stdout_path = output / f"{unit_id}.stdout.txt"
        stderr_path = output / f"{unit_id}.stderr.txt"
        stdout_path.write_text(completed.stdout, encoding="utf-8", errors="replace")
        stderr_path.write_text(completed.stderr, encoding="utf-8", errors="replace")
        raw_payload: dict[str, Any] = {}
        raw_sha = None
        if json_path.exists():
            raw_sha = sha256_file(json_path)
            raw_payload = json.loads(json_path.read_text(encoding="utf-8", errors="replace"))
        segments: list[TranscriptSegment] = []
        language = self.config.language
        error = None
        if completed.returncode == 0 and raw_payload:
            segments, language = self._parse_segments(
                raw_payload,
                unit_id=unit_id,
                source_item_id=source_item_id,
                absolute_start=absolute_start,
                raw_response_sha256=raw_sha or "",
            )
        elif completed.returncode != 0:
            error = completed.stderr[-3000:] or f"provider exit code {completed.returncode}"
        state = "FAILED" if completed.returncode != 0 else ("EMITTED_SEGMENTS" if segments else "ZERO_SEGMENT")
        redacted_command = [
            Path(binary).name,
            "-m",
            "[MODEL]",
            "-f",
            audio.name,
            "-of",
            unit_id,
            "-oj",
            "-l",
            self.config.language,
        ]
        command_receipt = {
            "contract": "EVIDENCEOPS_PROVIDER_UNIT_RECEIPT_V1",
            "unit_id": unit_id,
            "provider": self.name,
            "architecture_family": self.architecture_family,
            "command": redacted_command,
            "binary_sha256": sha256_file(binary) if Path(binary).is_file() else None,
            "model_sha256": sha256_file(self.config.model),
            "vad_model_sha256": sha256_file(self.config.vad_model) if self.config.vad_model else None,
            "input_file": audio.name,
            "input_sha256": sha256_file(audio),
            "exit_code": completed.returncode,
            "stdout_sha256": sha256_file(stdout_path),
            "stderr_sha256": sha256_file(stderr_path),
            "raw_response_sha256": raw_sha,
            "segment_count": len(segments),
            "state": state,
            "created_at": utc_now(),
        }
        receipt_path = output / f"{unit_id}.provider-receipt.json"
        atomic_write_json(receipt_path, command_receipt)
        receipt = UnitReceipt(
            unit_id=unit_id,
            source_item_id=source_item_id,
            source_sha256=source_sha256,
            provider=self.name,
            architecture_family=self.architecture_family,
            start_seconds=absolute_start,
            end_seconds=absolute_end,
            state=state,
            segment_count=len(segments),
            raw_response_sha256=raw_sha,
            command_receipt_sha256=sha256_file(receipt_path),
            provider_exit_code=completed.returncode,
            created_at=utc_now(),
            language=language,
            error=error,
            metadata={
                "provider_receipt": str(receipt_path),
                "stdout": str(stdout_path),
                "stderr": str(stderr_path),
            },
        )
        return receipt, segments


class CommandTranslationAdapter:
    """Provider-neutral automated translation adapter using a JSON command contract.

    The command receives JSON on stdin and must return JSON with
    ``translated_text`` and optional ``model``. This permits approved local,
    enterprise or cloud translation runtimes without hard-coding credentials.
    """

    name = "command_translation_adapter"

    def __init__(self, command: list[str] | str, *, timeout_seconds: int = 300):
        self.command = shlex.split(command) if isinstance(command, str) else list(command)
        self.timeout_seconds = timeout_seconds
        if not self.command:
            raise ValueError("translation command cannot be empty")

    def translate(
        self,
        *,
        segment_id: str,
        text: str,
        source_language: str,
        target_language: str,
        receipt_dir: str | Path,
    ) -> TranslationRecord:
        payload = {
            "segment_id": segment_id,
            "text": text,
            "source_language": source_language,
            "target_language": target_language,
        }
        completed = subprocess.run(
            self.command,
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            raise ProviderError(completed.stderr[-3000:] or f"translation exit code {completed.returncode}")
        try:
            response = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"translation adapter returned invalid JSON: {exc}") from exc
        translated_text = str(response.get("translated_text") or "").strip()
        if not translated_text:
            raise ProviderError("translation adapter returned empty translated_text")
        destination = Path(receipt_dir)
        destination.mkdir(parents=True, exist_ok=True)
        raw_path = destination / f"translation-{segment_id}-{target_language}-{uuid.uuid4().hex[:8]}.json"
        atomic_write_json(
            raw_path,
            {
                "request": payload,
                "response": response,
                "command": [Path(self.command[0]).name, *self.command[1:]],
                "exit_code": completed.returncode,
                "stderr_sha256": sha256_bytes(completed.stderr.encode("utf-8")),
                "created_at": utc_now(),
            },
        )
        return TranslationRecord(
            translation_id=f"TRN-{uuid.uuid4().hex[:16]}",
            segment_id=segment_id,
            source_language=source_language,
            target_language=target_language,
            source_text_sha256=sha256_bytes(text.encode("utf-8")),
            translated_text=translated_text,
            provider=self.name,
            model=response.get("model"),
            raw_response_sha256=sha256_file(raw_path),
            created_at=utc_now(),
            metadata={"raw_receipt": str(raw_path)},
        )
