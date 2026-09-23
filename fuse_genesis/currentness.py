from __future__ import annotations
from dataclasses import dataclass
import hashlib, json, os, re
from typing import Mapping

_SHA40 = re.compile(r"^[0-9a-f]{40}$")

class SourceCurrentnessError(ValueError):
    pass

def _canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

@dataclass(frozen=True, slots=True)
class SourceEpoch:
    main_sha: str
    writer: str
    fence: int
    mission_id: str = "GENESIS"

    def __post_init__(self):
        if not _SHA40.fullmatch(str(self.main_sha).lower()):
            raise SourceCurrentnessError("SOURCE_MAIN_INVALID")
        if not str(self.writer).strip():
            raise SourceCurrentnessError("SOURCE_WRITER_REQUIRED")
        if isinstance(self.fence, bool) or not isinstance(self.fence, int) or self.fence < 1:
            raise SourceCurrentnessError("SOURCE_FENCE_INVALID")
        if not str(self.mission_id).strip():
            raise SourceCurrentnessError("MISSION_ID_REQUIRED")

    def as_dict(self):
        return {
            "main_sha": self.main_sha.lower(),
            "writer": self.writer,
            "fence": self.fence,
            "mission_id": self.mission_id,
        }

    @property
    def digest(self):
        return hashlib.sha256(_canon(self.as_dict()).encode()).hexdigest()

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None):
        env = os.environ if environ is None else environ
        missing = [
            key for key in (
                "FUSE_GENESIS_SOURCE_MAIN",
                "FUSE_GENESIS_SOURCE_WRITER",
                "FUSE_GENESIS_SOURCE_FENCE",
            )
            if not str(env.get(key, "")).strip()
        ]
        if missing:
            raise SourceCurrentnessError("SOURCE_EPOCH_REQUIRED:" + ",".join(missing))
        try:
            fence = int(env["FUSE_GENESIS_SOURCE_FENCE"])
        except Exception as exc:
            raise SourceCurrentnessError("SOURCE_FENCE_INVALID") from exc
        return cls(
            main_sha=str(env["FUSE_GENESIS_SOURCE_MAIN"]).lower(),
            writer=str(env["FUSE_GENESIS_SOURCE_WRITER"]),
            fence=fence,
            mission_id=str(env.get("FUSE_GENESIS_MISSION_ID", "GENESIS")),
        )

def resolve_source_epoch(epoch: SourceEpoch | None = None, environ: Mapping[str, str] | None = None) -> SourceEpoch:
    if epoch is not None:
        if not isinstance(epoch, SourceEpoch):
            raise SourceCurrentnessError("SOURCE_EPOCH_TYPE_INVALID")
        return epoch
    return SourceEpoch.from_env(environ)
