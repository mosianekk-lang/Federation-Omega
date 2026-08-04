"""Backward-compatible import surface for EvidenceOps Audio Processing v2."""
from .common import ProviderPreflight, ProviderResult, redact, sha256_file, stable_json, utc_now
from .engine import EvidenceOpsAudioEngine
from .manifest import AudioManifest, ChunkRecord, ManifestError, load_manifest
from .providers import GeminiFilesProvider, GoogleSpeechV2Provider, LocalWhisperCppProvider

__all__ = [
    "AudioManifest", "ChunkRecord", "EvidenceOpsAudioEngine", "ManifestError",
    "ProviderPreflight", "ProviderResult", "GeminiFilesProvider",
    "GoogleSpeechV2Provider", "LocalWhisperCppProvider", "load_manifest",
    "redact", "sha256_file", "stable_json", "utc_now",
]
