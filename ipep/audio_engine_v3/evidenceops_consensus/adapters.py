from __future__ import annotations

"""Optional adapters for public transcription systems.

Heavy dependencies are imported lazily. Each adapter fails closed and reports
its missing dependency or credential instead of silently falling back.
"""

from dataclasses import dataclass, asdict
import os


@dataclass(frozen=True)
class AdapterPreflight:
    adapter: str
    ready: bool
    state: str
    requirements: tuple[str, ...]
    configuration: dict

    def to_dict(self):
        return asdict(self)


class FasterWhisperAdapter:
    name = "faster_whisper_large_v3"

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("EO_FW_MODEL", "large-v3-turbo")

    def preflight(self) -> AdapterPreflight:
        try:
            import faster_whisper  # noqa: F401
            ready = True
        except Exception:
            ready = False
        return AdapterPreflight(
            self.name,
            ready,
            "READY" if ready else "BLOCKED_DEPENDENCY",
            (() if ready else ("pip install faster-whisper",)),
            {
                "model": self.model,
                "beam_size": 5,
                "vad_filter": True,
                "condition_on_previous_text": False,
                "hotwords": True,
            },
        )


class WhisperXAdapter:
    name = "whisperx_alignment"

    def preflight(self) -> AdapterPreflight:
        try:
            import whisperx  # noqa: F401
            ready = True
        except Exception:
            ready = False
        return AdapterPreflight(
            self.name,
            ready,
            "READY" if ready else "BLOCKED_DEPENDENCY",
            (() if ready else ("pip install whisperx",)),
            {"word_alignment": True, "vad": True},
        )


class NeMoParakeetAdapter:
    name = "nemo_parakeet_tdt"

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("EO_PARAKEET_MODEL", "nvidia/parakeet-tdt-0.6b-v2")

    def preflight(self) -> AdapterPreflight:
        try:
            import nemo.collections.asr  # noqa: F401
            ready = True
        except Exception:
            ready = False
        return AdapterPreflight(
            self.name,
            ready,
            "READY" if ready else "BLOCKED_DEPENDENCY",
            (() if ready else ("install NVIDIA NeMo ASR",)),
            {"model": self.model, "timestamps": True},
        )


class PyannoteDiarizationAdapter:
    name = "pyannote_community_1"

    def preflight(self) -> AdapterPreflight:
        token = bool(os.getenv("HF_TOKEN"))
        try:
            import pyannote.audio  # noqa: F401
            dependency = True
        except Exception:
            dependency = False
        requirements = []
        if not dependency:
            requirements.append("pip install pyannote.audio")
        if not token:
            requirements.append("HF_TOKEN after accepting community-1 terms")
        ready = not requirements
        return AdapterPreflight(
            self.name,
            ready,
            "READY" if ready else "BLOCKED_DEPENDENCY_OR_TOKEN",
            tuple(requirements),
            {
                "pipeline": "pyannote/speaker-diarization-community-1",
                "exclusive_diarization": True,
            },
        )


class OpenAIDiarizedAdapter:
    name = "openai_gpt_4o_transcribe_diarize"

    def preflight(self) -> AdapterPreflight:
        ready = bool(os.getenv("OPENAI_API_KEY"))
        return AdapterPreflight(
            self.name,
            ready,
            "READY" if ready else "BLOCKED_CREDENTIAL",
            (() if ready else ("OPENAI_API_KEY",)),
            {
                "model": "gpt-4o-transcribe-diarize",
                "response_format": "diarized_json",
            },
        )
