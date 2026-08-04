from __future__ import annotations

"""Optional adapters for public or documented transcription systems.

Heavy dependencies are imported lazily. Each adapter fails closed and reports
configuration only; a ready preflight is not proof that transcription ran.
"""

from dataclasses import dataclass, asdict
import os
import shutil


@dataclass(frozen=True)
class AdapterPreflight:
    adapter: str
    architecture_family: str
    ready: bool
    state: str
    requirements: tuple[str, ...]
    configuration: dict

    def to_dict(self):
        return asdict(self)


class FasterWhisperAdapter:
    name = "faster_whisper_large_v3"
    architecture_family = "whisper_encoder_decoder"

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("EO_FW_MODEL", "large-v3-turbo")

    def preflight(self) -> AdapterPreflight:
        try:
            import faster_whisper  # noqa: F401
            ready = True
        except Exception:
            ready = False
        hotwords = [x.strip() for x in os.getenv("EO_HOTWORDS", "").split(",") if x.strip()]
        return AdapterPreflight(
            self.name, self.architecture_family, ready,
            "READY" if ready else "BLOCKED_DEPENDENCY",
            (() if ready else ("pip install faster-whisper",)),
            {
                "model": self.model,
                "beam_size": 5,
                "vad_filter": True,
                "condition_on_previous_text": False,
                "language": "en",
                "hotwords": hotwords,
            },
        )


class WhisperXAdapter:
    name = "whisperx_alignment"
    architecture_family = "alignment_not_asr"

    def preflight(self) -> AdapterPreflight:
        try:
            import whisperx  # noqa: F401
            ready = True
        except Exception:
            ready = False
        return AdapterPreflight(
            self.name, self.architecture_family, ready,
            "READY" if ready else "BLOCKED_DEPENDENCY",
            (() if ready else ("pip install whisperx>=3.8.6",)),
            {
                "word_alignment": True,
                "vad": True,
                "condition_on_previous_text": False,
                "required_release_floor": "3.8.6",
                "avg_logprob_capture": True,
            },
        )


class NeMoParakeetAdapter:
    name = "nemo_parakeet_tdt"
    architecture_family = "nvidia_parakeet_tdt"

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("EO_PARAKEET_MODEL", "nvidia/parakeet-tdt-0.6b-v2")

    def preflight(self) -> AdapterPreflight:
        try:
            import nemo.collections.asr  # noqa: F401
            ready = True
        except Exception:
            ready = False
        boost_words = [x.strip() for x in os.getenv("EO_PARAKEET_BOOST_WORDS", "").split(",") if x.strip()]
        return AdapterPreflight(
            self.name, self.architecture_family, ready,
            "READY" if ready else "BLOCKED_DEPENDENCY",
            (() if ready else ("install NVIDIA NeMo ASR",)),
            {
                "model": self.model,
                "timestamps": ["word", "segment"],
                "preserve_alignments": True,
                "compute_timestamps": True,
                "word_boosting_candidates": boost_words,
            },
        )


class GoogleChirp3Adapter:
    name = "google_chirp_3"
    architecture_family = "google_chirp"

    def preflight(self) -> AdapterPreflight:
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "") or os.getenv("IPEP_GCP_PROJECT", "")
        token = bool(os.getenv("GOOGLE_OAUTH_ACCESS_TOKEN")) or bool(shutil.which("gcloud"))
        requirements = []
        if not project:
            requirements.append("GOOGLE_CLOUD_PROJECT or IPEP_GCP_PROJECT")
        if not token:
            requirements.append("Google ADC, gcloud, or GOOGLE_OAUTH_ACCESS_TOKEN")
        phrases = [x.strip() for x in os.getenv("EO_CHIRP_INLINE_PHRASES", "").split(",") if x.strip()]
        return AdapterPreflight(
            self.name, self.architecture_family, not requirements,
            "READY" if not requirements else "BLOCKED_GOOGLE_AUTH",
            tuple(requirements),
            {
                "model": "chirp_3",
                "language_codes": ["en-ZA", "en-US"],
                "word_time_offsets": True,
                "word_confidence": True,
                "inline_phrase_candidates": phrases,
            },
        )


class PyannoteDiarizationAdapter:
    name = "pyannote_community_1"
    architecture_family = "diarization_not_asr"

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
            self.name, self.architecture_family, ready,
            "READY" if ready else "BLOCKED_DEPENDENCY_OR_TOKEN",
            tuple(requirements),
            {
                "pipeline": "pyannote/speaker-diarization-community-1",
                "exclusive_diarization": True,
                "known_speaker_count_range": [2, 5],
            },
        )


class OpenAIDiarizedAdapter:
    name = "openai_gpt_4o_transcribe_diarize"
    architecture_family = "openai_gpt4o_asr"

    def preflight(self) -> AdapterPreflight:
        ready = bool(os.getenv("OPENAI_API_KEY"))
        return AdapterPreflight(
            self.name, self.architecture_family, ready,
            "READY" if ready else "BLOCKED_CREDENTIAL",
            (() if ready else ("OPENAI_API_KEY",)),
            {
                "diarization_model": "gpt-4o-transcribe-diarize",
                "lexical_model": "gpt-4o-transcribe",
                "response_format": "diarized_json",
                "chunking_strategy": "auto",
                "language": "en",
                "known_speaker_reference_support": True,
                "lexical_logprobs": True,
                "truth_boundary": "Diarized and lexical calls are one architecture family, not two independent votes.",
            },
        )
