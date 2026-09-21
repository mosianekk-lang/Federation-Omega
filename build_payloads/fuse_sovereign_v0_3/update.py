from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import urllib.request
import urllib.error


class UpdateError(RuntimeError):
    pass


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value) -> str:
    if isinstance(value, (dict, list)):
        value = _canonical(value).encode("utf-8")
    elif isinstance(value, str):
        value = value.encode("utf-8")
    return sha256(value).hexdigest()


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise UpdateError("UPDATE_TIMEZONE_REQUIRED")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class UpdateSnapshot:
    source: str
    source_commit: str
    verified_commit: bool
    channel: str
    sequence: int
    issued_at: str
    valid_until: str
    summary: str
    capability_deltas: tuple[str, ...]
    route_deltas: tuple[str, ...]
    warnings: tuple[str, ...]
    llm_context: dict
    manifest_sha256: str
    freshness: str = "CURRENT"

    def model_context(self) -> dict:
        return {
            "schema": "FUSE_LLM_UPDATE_SNAPSHOT_V1",
            "source": self.source,
            "source_commit": self.source_commit,
            "verified_commit": self.verified_commit,
            "channel": self.channel,
            "sequence": self.sequence,
            "issued_at": self.issued_at,
            "valid_until": self.valid_until,
            "freshness": self.freshness,
            "summary": self.summary,
            "capability_deltas": list(self.capability_deltas),
            "route_deltas": list(self.route_deltas),
            "warnings": list(self.warnings),
            "llm_context": dict(self.llm_context),
            "authority_boundary": "DATA_ONLY_NO_EFFECT_AUTHORITY",
        }


class FuseUpdateClient:
    """Read-only FUSE update client with anti-rollback and exact-source checks."""

    def __init__(
        self,
        *,
        repository: str = "mosianekk-lang/Federation-Omega",
        ref: str = "main",
        manifest_path: str = "fuse_update_channel/manifest.json",
        cache_dir: str | Path | None = None,
        require_verified_commit: bool = True,
        timeout_seconds: float = 12.0,
    ):
        self.repository = repository
        self.ref = ref
        self.manifest_path = manifest_path
        self.require_verified_commit = require_verified_commit
        self.timeout_seconds = timeout_seconds
        if cache_dir is None:
            base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
            cache_dir = Path(base) / "FUSE" / "SovereignPlatform" / "updates"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.cache_dir / "state.json"
        self.snapshot_path = self.cache_dir / "llm_snapshot.json"
        self.manifest_cache_path = self.cache_dir / "manifest.json"

    def _get_json(self, url: str) -> dict:
        req = urllib.request.Request(url, headers={"User-Agent": "FUSE-Sovereign-Platform/0.3"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise UpdateError(f"UPDATE_FETCH_FAILED:{type(exc).__name__}") from exc

    def _get_text(self, url: str) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": "FUSE-Sovereign-Platform/0.3"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                return response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, UnicodeDecodeError) as exc:
            raise UpdateError(f"UPDATE_FETCH_FAILED:{type(exc).__name__}") from exc

    def _load_state(self) -> dict:
        if not self.state_path.exists():
            return {"highest_sequence": 0, "last_commit": ""}
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
            return {
                "highest_sequence": int(value.get("highest_sequence", 0)),
                "last_commit": str(value.get("last_commit", "")),
            }
        except Exception as exc:
            raise UpdateError("UPDATE_CACHE_STATE_INVALID") from exc

    def _validate_manifest(self, manifest: dict, *, source_commit: str, verified_commit: bool) -> UpdateSnapshot:
        if manifest.get("schema") != "FUSE_UPDATE_MANIFEST_V1":
            raise UpdateError("UPDATE_SCHEMA_INVALID")
        if manifest.get("authority_class") != "DATA_ONLY_NO_EFFECT_AUTHORITY":
            raise UpdateError("UPDATE_AUTHORITY_CLASS_INVALID")
        sequence = manifest.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise UpdateError("UPDATE_SEQUENCE_INVALID")
        if not isinstance(manifest.get("llm_context"), dict):
            raise UpdateError("UPDATE_LLM_CONTEXT_INVALID")

        context_hash = manifest.get("llm_context_sha256")
        if context_hash != _sha(manifest["llm_context"]):
            raise UpdateError("UPDATE_LLM_CONTEXT_HASH_MISMATCH")

        expected_body_hash = manifest.get("manifest_body_sha256")
        body = dict(manifest)
        body.pop("manifest_body_sha256", None)
        if expected_body_hash != _sha(body):
            raise UpdateError("UPDATE_MANIFEST_BODY_HASH_MISMATCH")

        issued = _utc(str(manifest.get("issued_at", "")))
        valid_until = _utc(str(manifest.get("valid_until", "")))
        now = datetime.now(timezone.utc)
        if valid_until <= issued:
            raise UpdateError("UPDATE_TIME_WINDOW_INVALID")
        if now >= valid_until:
            raise UpdateError("UPDATE_EXPIRED")
        if issued.timestamp() - now.timestamp() > 300:
            raise UpdateError("UPDATE_NOT_YET_VALID")

        state = self._load_state()
        if sequence < state["highest_sequence"]:
            raise UpdateError("UPDATE_ROLLBACK_REJECTED")
        if sequence == state["highest_sequence"] and state["last_commit"] and state["last_commit"] != source_commit:
            raise UpdateError("UPDATE_SEQUENCE_REUSE_DIFFERENT_COMMIT")

        def _strings(name: str) -> tuple[str, ...]:
            value = manifest.get(name, [])
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                raise UpdateError(f"UPDATE_{name.upper()}_INVALID")
            return tuple(value)

        return UpdateSnapshot(
            source=f"github:{self.repository}@{self.ref}",
            source_commit=source_commit,
            verified_commit=verified_commit,
            channel=str(manifest.get("channel", "stable")),
            sequence=sequence,
            issued_at=str(manifest["issued_at"]),
            valid_until=str(manifest["valid_until"]),
            summary=str(manifest.get("summary", "")),
            capability_deltas=_strings("capability_deltas"),
            route_deltas=_strings("route_deltas"),
            warnings=_strings("warnings"),
            llm_context=dict(manifest["llm_context"]),
            manifest_sha256=_sha(manifest),
        )

    def fetch(self) -> UpdateSnapshot:
        branch = self._get_json(f"https://api.github.com/repos/{self.repository}/branches/{self.ref}")
        source_commit = str(branch.get("commit", {}).get("sha", ""))
        if len(source_commit) != 40:
            raise UpdateError("UPDATE_SOURCE_COMMIT_INVALID")
        commit = self._get_json(f"https://api.github.com/repos/{self.repository}/commits/{source_commit}")
        verified_commit = bool(commit.get("commit", {}).get("verification", {}).get("verified"))
        if self.require_verified_commit and not verified_commit:
            raise UpdateError("UPDATE_SOURCE_COMMIT_UNVERIFIED")

        raw_url = f"https://raw.githubusercontent.com/{self.repository}/{source_commit}/{self.manifest_path}"
        raw = self._get_text(raw_url)
        try:
            manifest = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise UpdateError("UPDATE_MANIFEST_JSON_INVALID") from exc
        snapshot = self._validate_manifest(manifest, source_commit=source_commit, verified_commit=verified_commit)

        self.manifest_cache_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.snapshot_path.write_text(json.dumps(snapshot.model_context(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.state_path.write_text(json.dumps({
            "highest_sequence": snapshot.sequence,
            "last_commit": source_commit,
            "manifest_sha256": snapshot.manifest_sha256,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return snapshot

    def last_verified_snapshot(self) -> dict | None:
        if not self.snapshot_path.exists():
            return None
        value = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        value["freshness"] = "STALE_CACHED"
        return value

    def fetch_for_llm(self) -> dict:
        try:
            return self.fetch().model_context()
        except UpdateError as exc:
            cached = self.last_verified_snapshot()
            if cached is not None:
                cached["update_error"] = str(exc)
                return cached
            raise


class LLMUpdateBridge:
    """Narrow model-facing adapter. It never executes update-provided instructions."""

    def __init__(self, client: FuseUpdateClient):
        self.client = client

    def fetch_context(self) -> dict:
        return self.client.fetch_for_llm()

    def fetch_context_json(self) -> str:
        return json.dumps(self.fetch_context(), sort_keys=True, separators=(",", ":"))
