from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Protocol

from .common import ProviderPreflight, ProviderResult, redact, stable_json
from .manifest import ChunkRecord


class TranscriptionProvider(Protocol):
    name: str

    def preflight(self) -> ProviderPreflight: ...
    def transcribe(self, audio_path: Path, chunk: ChunkRecord, output_dir: Path) -> ProviderResult: ...


class LocalWhisperCppProvider:
    name = "local_whisper_cpp"

    def __init__(self, binary: str | None = None, model: str | None = None):
        self.binary = binary or os.getenv("IPEP_WHISPER_BIN", "whisper-cli")
        self.model = model or os.getenv("IPEP_WHISPER_MODEL", "")

    def preflight(self) -> ProviderPreflight:
        binary_path = shutil.which(self.binary) if not Path(self.binary).exists() else self.binary
        requirements = []
        if not binary_path:
            requirements.append("IPEP_WHISPER_BIN or whisper-cli executable")
        if not self.model or not Path(self.model).is_file():
            requirements.append("IPEP_WHISPER_MODEL pointing to a local ggml/gguf model")
        return ProviderPreflight(
            self.name,
            not requirements,
            "READY" if not requirements else "BLOCKED_MODEL_OR_BINARY",
            tuple(requirements),
            {"binary": str(binary_path or self.binary), "model_configured": bool(self.model)},
        )

    def transcribe(self, audio_path: Path, chunk: ChunkRecord, output_dir: Path) -> ProviderResult:
        preflight = self.preflight()
        if not preflight.ready:
            return ProviderResult(self.name, preflight.state, error="; ".join(preflight.requirements))
        output_dir.mkdir(parents=True, exist_ok=True)
        prefix = output_dir / f"chunk-{chunk.sequence:03d}"
        command = [
            str(self.binary), "-m", str(self.model), "-f", str(audio_path),
            "-of", str(prefix), "-otxt", "-osrt", "-oj", "-l", "auto",
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=7200)
        if completed.returncode != 0:
            return ProviderResult(self.name, "FAILED", error=completed.stderr[-3000:])
        text_path = prefix.with_suffix(".txt")
        transcript = text_path.read_text(encoding="utf-8", errors="replace") if text_path.exists() else ""
        return ProviderResult(
            self.name,
            "TRANSCRIBED" if transcript.strip() else "FAILED_EMPTY_TRANSCRIPT",
            transcript_text=transcript,
            raw={
                "command": [command[0], "-m", "[MODEL]", "-f", audio_path.name],
                "stdout_tail": completed.stdout[-1500:],
            },
        )


class GeminiFilesProvider:
    name = "gemini_files_api"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
        self.model = model or os.getenv("IPEP_GEMINI_MODEL", "gemini-3.6-flash")

    def preflight(self) -> ProviderPreflight:
        missing = () if self.api_key else ("GEMINI_API_KEY or GOOGLE_API_KEY",)
        return ProviderPreflight(
            self.name,
            bool(self.api_key),
            "READY" if self.api_key else "BLOCKED_CREDENTIAL",
            missing,
            {"model": self.model, "api_key_present": bool(self.api_key)},
        )

    def _request_json(self, url, payload, timeout=180):
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", "replace"))

    def _upload(self, audio_path: Path):
        start_url = "https://generativelanguage.googleapis.com/upload/v1beta/files"
        headers = {
            "x-goog-api-key": self.api_key,
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(audio_path.stat().st_size),
            "X-Goog-Upload-Header-Content-Type": "audio/flac",
            "Content-Type": "application/json",
        }
        request = urllib.request.Request(
            start_url,
            data=json.dumps({"file": {"display_name": audio_path.name}}).encode(),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            upload_url = response.headers.get("X-Goog-Upload-URL")
        if not upload_url:
            raise RuntimeError("Gemini Files API did not return an upload URL")
        data = audio_path.read_bytes()
        upload_request = urllib.request.Request(
            upload_url,
            data=data,
            headers={
                "Content-Length": str(len(data)),
                "X-Goog-Upload-Offset": "0",
                "X-Goog-Upload-Command": "upload, finalize",
            },
            method="POST",
        )
        with urllib.request.urlopen(upload_request, timeout=600) as response:
            return json.loads(response.read().decode("utf-8", "replace"))

    def transcribe(self, audio_path: Path, chunk: ChunkRecord, output_dir: Path) -> ProviderResult:
        preflight = self.preflight()
        if not preflight.ready:
            return ProviderResult(self.name, preflight.state, error="; ".join(preflight.requirements))
        try:
            uploaded = self._upload(audio_path)
            file_data = uploaded.get("file") or uploaded
            file_uri = file_data.get("uri")
            mime_type = file_data.get("mimeType") or file_data.get("mime_type") or "audio/flac"
            if not file_uri:
                raise RuntimeError("Gemini upload response did not contain file URI")
            prompt = (
                "Produce a forensic verbatim transcript of this legal hearing audio. "
                "Return plain text with [HH:MM:SS] timestamps at every speaker change. "
                "Use neutral speaker labels such as SPEAKER_1. Mark [INAUDIBLE], "
                "[OVERLAPPING SPEECH], and [UNCERTAIN: ...]. Do not invent speech. "
                "Preserve repetitions and interruptions."
            )
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            response = self._request_json(
                endpoint,
                {
                    "contents": [{
                        "parts": [
                            {"text": prompt},
                            {"file_data": {"mime_type": mime_type, "file_uri": file_uri}},
                        ]
                    }],
                    "generationConfig": {"temperature": 0.0},
                },
                timeout=1200,
            )
            parts = (((response.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [])
            transcript = "\n".join(str(part.get("text", "")) for part in parts if part.get("text"))
            return ProviderResult(
                self.name,
                "TRANSCRIBED" if transcript.strip() else "FAILED_EMPTY_TRANSCRIPT",
                transcript_text=transcript,
                raw=redact({"file": file_data, "response": response}),
            )
        except Exception as exc:
            return ProviderResult(self.name, "FAILED", error=f"{type(exc).__name__}: {exc}")


class GoogleSpeechV2Provider:
    name = "google_speech_v2"

    def __init__(self):
        self.project = os.getenv("GOOGLE_CLOUD_PROJECT", "") or os.getenv("IPEP_GCP_PROJECT", "")
        self.location = os.getenv("IPEP_SPEECH_LOCATION", "global")
        self.language = os.getenv("IPEP_LANGUAGE_CODE", "en-ZA")
        self.model = os.getenv("IPEP_SPEECH_MODEL", "chirp_3")
        self.gcs_prefix = os.getenv("IPEP_GCS_URI_PREFIX", "").rstrip("/")
        self.token = os.getenv("GOOGLE_OAUTH_ACCESS_TOKEN", "")

    def _access_token(self):
        if self.token:
            return self.token
        if shutil.which("gcloud"):
            completed = subprocess.run(
                ["gcloud", "auth", "application-default", "print-access-token"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if completed.returncode == 0:
                return completed.stdout.strip()
        return ""

    def preflight(self) -> ProviderPreflight:
        missing = []
        if not self.project:
            missing.append("GOOGLE_CLOUD_PROJECT or IPEP_GCP_PROJECT")
        if not self.gcs_prefix:
            missing.append("IPEP_GCS_URI_PREFIX")
        if not self._access_token():
            missing.append("Google ADC or GOOGLE_OAUTH_ACCESS_TOKEN")
        return ProviderPreflight(
            self.name,
            not missing,
            "READY" if not missing else "BLOCKED_GOOGLE_AUTH_OR_GCS",
            tuple(missing),
            {
                "project": self.project,
                "location": self.location,
                "language": self.language,
                "model": self.model,
            },
        )

    def transcribe(self, audio_path: Path, chunk: ChunkRecord, output_dir: Path) -> ProviderResult:
        preflight = self.preflight()
        if not preflight.ready:
            return ProviderResult(self.name, preflight.state, error="; ".join(preflight.requirements))
        if not shutil.which("gcloud"):
            return ProviderResult(self.name, "BLOCKED_GCLOUD", error="gcloud is required to stage audio in Cloud Storage")
        gcs_uri = f"{self.gcs_prefix}/{audio_path.name}"
        cp = subprocess.run(
            ["gcloud", "storage", "cp", str(audio_path), gcs_uri],
            capture_output=True,
            text=True,
            timeout=1800,
        )
        if cp.returncode != 0:
            return ProviderResult(self.name, "FAILED_GCS_UPLOAD", error=cp.stderr[-3000:])
        token = self._access_token()
        endpoint = (
            f"https://speech.googleapis.com/v2/projects/{self.project}/locations/"
            f"{self.location}/recognizers/_:batchRecognize"
        )
        payload = {
            "config": {
                "autoDecodingConfig": {},
                "languageCodes": [self.language],
                "model": self.model,
                "features": {"enableWordTimeOffsets": True, "enableWordConfidence": True},
            },
            "files": [{"uri": gcs_uri}],
            "recognitionOutputConfig": {"inlineResponseConfig": {}},
        }
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                operation = json.loads(response.read().decode("utf-8", "replace"))
            operation_name = operation.get("name")
            if not operation_name:
                raise RuntimeError("Speech API did not return operation name")
            operation_url = f"https://speech.googleapis.com/v2/{operation_name}"
            deadline = time.time() + 7200
            result = operation
            while time.time() < deadline:
                poll = urllib.request.Request(
                    operation_url,
                    headers={"Authorization": f"Bearer {token}"},
                )
                with urllib.request.urlopen(poll, timeout=120) as response:
                    result = json.loads(response.read().decode("utf-8", "replace"))
                if result.get("done"):
                    break
                time.sleep(15)
            if not result.get("done"):
                return ProviderResult(self.name, "TIMEOUT", raw=redact(result))
            if result.get("error"):
                return ProviderResult(
                    self.name,
                    "FAILED",
                    raw=redact(result),
                    error=stable_json(result["error"]),
                )
            transcript_parts = []
            response_map = ((result.get("response") or {}).get("results") or {})
            for file_result in response_map.values():
                inline = ((file_result.get("inlineResult") or {}).get("transcript") or {})
                for item in inline.get("results", []):
                    alternatives = item.get("alternatives") or []
                    if alternatives:
                        transcript_parts.append(str(alternatives[0].get("transcript", "")))
            transcript = "\n".join(part for part in transcript_parts if part.strip())
            return ProviderResult(
                self.name,
                "TRANSCRIBED" if transcript else "FAILED_EMPTY_TRANSCRIPT",
                transcript_text=transcript,
                raw=redact(result),
            )
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            return ProviderResult(self.name, "FAILED", error=f"HTTP {exc.code}: {body[:3000]}")
        except Exception as exc:
            return ProviderResult(self.name, "FAILED", error=f"{type(exc).__name__}: {exc}")
