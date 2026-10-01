from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

_ALLOWED = {
    "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
    "image/webp": (b"RIFF", ".webp"),
}


@dataclass(frozen=True, slots=True)
class ObservationSignal:
    category: str
    severity: str
    recommended_action: str
    normalized_message: str


def classify_ui_signal(text: str) -> ObservationSignal:
    clean = " ".join(text.strip().split())[:4000]
    lowered = clean.lower()
    if any(x in lowered for x in ("maximum length for this conversation", "max weighted tokens", "context limit", "conversation is too long")):
        return ObservationSignal("CONTEXT_LIMIT", "HIGH", "CHECKPOINT_DETACH_REJOIN", clean)
    if any(x in lowered for x in ("rate limit", "too many requests", "quota")):
        return ObservationSignal("RATE_LIMIT", "MEDIUM", "REELECT_CARRIER_WITH_CHANGED_ROUTE", clean)
    if any(x in lowered for x in ("failed to upload", "upload failed", "attachment failed")):
        return ObservationSignal("UPLOAD_FAILURE", "MEDIUM", "RETRY_CHANGED_ROUTE", clean)
    if any(x in lowered for x in ("permission denied", "access denied", "not authorized")):
        return ObservationSignal("AUTHORITY_BOUNDARY", "HIGH", "REFRESH_AUTHORITY_CURRENTNESS_AND_REROUTE", clean)
    return ObservationSignal("OTHER", "LOW", "OBSERVE_ONLY", clean)


class ObservationCache:
    """Ephemeral owner-view cache; never a mission/state/authority root."""

    def __init__(self, root: Path, *, ttl_seconds: int = 15, max_bytes: int = 8 * 1024 * 1024):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = max(1, ttl_seconds)
        self.max_bytes = max(1024, max_bytes)
        self.meta_path = self.root / "latest.json"

    @classmethod
    def from_environment(cls) -> "ObservationCache":
        root = Path(os.getenv("FUSE_OBSERVATION_CACHE_DIR", ".fuse-observation"))
        ttl = int(os.getenv("FUSE_OBSERVATION_TTL_SECONDS", "15"))
        max_bytes = int(os.getenv("FUSE_OBSERVATION_MAX_BYTES", str(8 * 1024 * 1024)))
        return cls(root, ttl_seconds=ttl, max_bytes=max_bytes)

    def _meta(self) -> dict | None:
        if not self.meta_path.exists():
            return None
        try:
            return json.loads(self.meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def ingest_frame(self, data: bytes, *, content_type: str, source: str, mission_id: str | None = None) -> dict:
        if not data:
            raise ValueError("VISION_FRAME_EMPTY")
        if len(data) > self.max_bytes:
            raise ValueError("VISION_FRAME_TOO_LARGE")
        media = content_type.split(";", 1)[0].strip().lower()
        if media not in _ALLOWED:
            raise ValueError("VISION_CONTENT_TYPE_NOT_ALLOWED")
        signature, suffix = _ALLOWED[media]
        if media == "image/webp":
            valid = data.startswith(signature) and len(data) >= 12 and data[8:12] == b"WEBP"
        else:
            valid = data.startswith(signature)
        if not valid:
            raise ValueError("VISION_IMAGE_SIGNATURE_INVALID")

        digest = hashlib.sha256(data).hexdigest()
        image = self.root / f"latest{suffix}"
        tmp = self.root / f".latest{suffix}.tmp"
        tmp.write_bytes(data)
        tmp.replace(image)
        observed = time.time()
        meta = {
            "schema": "FUSE-OBSERVATION-FRAME-V1",
            "sha256": digest,
            "bytes": len(data),
            "content_type": media,
            "source": source[:256],
            "mission_id": mission_id,
            "observed_at_epoch": observed,
            "image_name": image.name,
            "truth_boundary": "EPHEMERAL_OWNER_VIEW_ONLY__NO_MISSION_STATE_OR_EFFECT_AUTHORITY",
        }
        meta_tmp = self.root / ".latest.json.tmp"
        meta_tmp.write_text(json.dumps(meta, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        meta_tmp.replace(self.meta_path)
        for other in self.root.glob("latest.*"):
            if other not in {image, self.meta_path}:
                other.unlink(missing_ok=True)
        return self.status()

    def status(self) -> dict:
        meta = self._meta()
        if not meta:
            return {"available": False, "fresh": False, "truth_boundary": "EPHEMERAL_OWNER_VIEW_ONLY__NO_MISSION_STATE_OR_EFFECT_AUTHORITY"}
        image = self.root / str(meta.get("image_name", ""))
        age = max(0.0, time.time() - float(meta.get("observed_at_epoch", 0)))
        return {**meta, "available": image.is_file(), "fresh": image.is_file() and age <= self.ttl_seconds, "age_seconds": round(age, 3)}

    def image_path(self) -> Path | None:
        meta = self._meta()
        if not meta:
            return None
        path = self.root / str(meta.get("image_name", ""))
        return path if path.is_file() else None

    def clear(self) -> dict:
        for path in self.root.glob("latest.*"):
            path.unlink(missing_ok=True)
        return {"status": "CLEARED", "mission_state_changed": False}
