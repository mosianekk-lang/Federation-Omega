from __future__ import annotations

"""Provider-neutral Work Plane durable-bundle adapter for private Cloud Run hosts.

The core WorkPlaneRuntime stays unchanged in its local proof semantics.  This adapter
maps one complete runtime bundle (state JSON + append-only JSONL events) onto a single
generation-fenced object.  Each logical operation is therefore committed with an
object-generation compare-and-swap: concurrent instances may compute, but only one
can commit a given generation.

The production Google client is lazy-loaded and uses Application Default Credentials.
Tests use the in-memory generation client; no provider is required for source courts.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Protocol
from urllib.parse import quote

from federation.fuse_work_plane_runtime_v1 import JsonlEventStore, WorkPlaneRuntime

BUNDLE_SCHEMA = "FUSE-WORK-PLANE-GCS-BUNDLE-V1"
ADAPTER_VERSION = "1.1.0"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def _digest(value: Any) -> str:
    return sha256(_canonical(value)).hexdigest()


class CasConflict(RuntimeError):
    pass


class GenerationClient(Protocol):
    def read(self, bucket: str, object_name: str) -> tuple[int, bytes | None]: ...
    def put(self, bucket: str, object_name: str, payload: bytes, *, if_generation_match: int) -> int: ...


@dataclass(frozen=True, slots=True)
class BundleCommitReceipt:
    schema: str
    adapter_version: str
    operation: str
    mission_id: str
    prior_generation: int
    committed_generation: int
    bundle_sha256: str
    result: dict[str, Any]
    provider_effect_authorized: bool
    receipt_sha256: str


class GoogleStorageGenerationClient:
    """GCS JSON API client with exact object-generation preconditions.

    Uses google-auth AuthorizedSession plus raw JSON API calls.  This avoids a
    google-api-python-client runtime dependency and reuses the google-auth stack
    already present through the repository's existing Google provider libraries.
    """

    API_ROOT = "https://storage.googleapis.com/storage/v1"
    UPLOAD_ROOT = "https://storage.googleapis.com/upload/storage/v1"

    def __init__(self, session: Any | None = None) -> None:
        if session is not None:
            self.session = session
            return
        import google.auth
        from google.auth.transport.requests import AuthorizedSession

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/devstorage.read_write"]
        )
        self.session = AuthorizedSession(credentials)

    @staticmethod
    def _object_path(bucket: str, object_name: str) -> str:
        return (
            f"/b/{quote(bucket, safe='')}/o/"
            f"{quote(object_name, safe='')}"
        )

    @staticmethod
    def _raise(response: Any) -> None:
        response.raise_for_status()

    def read(self, bucket: str, object_name: str) -> tuple[int, bytes | None]:
        path = self._object_path(bucket, object_name)
        meta = self.session.get(
            self.API_ROOT + path,
            params={"fields": "generation"},
            timeout=30,
        )
        if int(getattr(meta, "status_code", 0)) == 404:
            return 0, None
        self._raise(meta)
        payload = meta.json()
        generation = int(payload["generation"])
        media = self.session.get(
            self.API_ROOT + path,
            params={"alt": "media", "generation": str(generation)},
            timeout=30,
        )
        self._raise(media)
        return generation, bytes(media.content)

    def put(self, bucket: str, object_name: str, payload: bytes, *, if_generation_match: int) -> int:
        url = self.UPLOAD_ROOT + f"/b/{quote(bucket, safe='')}/o"
        response = self.session.post(
            url,
            params={
                "uploadType": "media",
                "name": object_name,
                "ifGenerationMatch": str(int(if_generation_match)),
            },
            headers={"content-type": "application/json"},
            data=payload,
            timeout=30,
        )
        if int(getattr(response, "status_code", 0)) == 412:
            raise CasConflict("GENERATION_CONFLICT")
        self._raise(response)
        return int(response.json()["generation"])


class InMemoryGenerationClient:
    """Deterministic source-court backend with GCS generation semantics."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[int, bytes]] = {}

    def read(self, bucket: str, object_name: str) -> tuple[int, bytes | None]:
        item = self.objects.get((bucket, object_name))
        return (0, None) if item is None else item

    def put(self, bucket: str, object_name: str, payload: bytes, *, if_generation_match: int) -> int:
        key = (bucket, object_name)
        current = self.objects.get(key)
        observed = 0 if current is None else current[0]
        if int(if_generation_match) != observed:
            raise CasConflict("GENERATION_CONFLICT")
        new_generation = observed + 1
        self.objects[key] = (new_generation, bytes(payload))
        return new_generation


class DurableBundleRuntime:
    """Execute one bounded Work Plane operation under generation CAS."""

    def __init__(self, *, bucket: str, object_name: str, client: GenerationClient) -> None:
        if not bucket.strip() or not object_name.strip():
            raise ValueError("BUCKET_AND_OBJECT_REQUIRED")
        self.bucket = bucket
        self.object_name = object_name
        self.client = client

    @classmethod
    def from_environment(cls) -> "DurableBundleRuntime":
        bucket = os.getenv("FUSE_WORK_PLANE_BUCKET", "").strip()
        object_name = os.getenv("FUSE_WORK_PLANE_OBJECT", "work-plane/runtime-v1.json").strip()
        return cls(bucket=bucket, object_name=object_name, client=GoogleStorageGenerationClient())

    @staticmethod
    def _empty_bundle() -> dict[str, Any]:
        return {
            "schema": BUNDLE_SCHEMA,
            "adapter_version": ADAPTER_VERSION,
            "core_schema": "FUSE-WORK-PLANE-RUNTIME-V1",
            "state_json": "",
            "events_jsonl": "",
            "commit_count": 0,
        }

    def _load(self) -> tuple[int, dict[str, Any]]:
        generation, raw = self.client.read(self.bucket, self.object_name)
        if raw is None:
            return generation, self._empty_bundle()
        bundle = json.loads(raw.decode("utf-8"))
        if bundle.get("schema") != BUNDLE_SCHEMA:
            raise RuntimeError("BUNDLE_SCHEMA_MISMATCH")
        return generation, bundle

    @staticmethod
    def _materialize(bundle: dict[str, Any], root: Path) -> WorkPlaneRuntime:
        state = root / "state.json"
        events = root / "events.jsonl"
        state_text = str(bundle.get("state_json") or "")
        events_text = str(bundle.get("events_jsonl") or "")
        if state_text:
            state.write_text(state_text, encoding="utf-8")
        events.write_text(events_text, encoding="utf-8")
        return WorkPlaneRuntime(JsonlEventStore(events), state)

    @staticmethod
    def _pack(runtime: WorkPlaneRuntime, root: Path, prior: dict[str, Any]) -> dict[str, Any]:
        state = root / "state.json"
        events = root / "events.jsonl"
        return {
            "schema": BUNDLE_SCHEMA,
            "adapter_version": ADAPTER_VERSION,
            "core_schema": runtime.state.get("schema"),
            "core_version": runtime.state.get("version"),
            "state_json": state.read_text(encoding="utf-8") if state.exists() else "",
            "events_jsonl": events.read_text(encoding="utf-8") if events.exists() else "",
            "commit_count": int(prior.get("commit_count", 0)) + 1,
        }

    def execute(self, *, operation: str, mission_id: str, actor: str = "FUSE_WORK_PLANE",
                fence: int | None = None, payload: Any = None, effect_id: str | None = None,
                readback: str | None = None, proof_ref: str | None = None,
                verifier: str | None = None, ttl_seconds: int = 120) -> BundleCommitReceipt:
        generation, bundle = self._load()
        with tempfile.TemporaryDirectory(prefix="fuse-work-plane-") as td:
            root = Path(td)
            runtime = self._materialize(bundle, root)
            op = operation.upper()
            result: dict[str, Any]

            if op == "PUBLISH":
                event = runtime.publish(mission_id, actor=actor)
                result = {"event": asdict(event)}
            elif op == "CLAIM":
                new_fence, event = runtime.claim(mission_id, actor=actor, ttl_seconds=ttl_seconds)
                result = {"fence": new_fence, "event": asdict(event)}
            elif op == "HEARTBEAT":
                if fence is None: raise ValueError("FENCE_REQUIRED")
                result = {"event": asdict(runtime.heartbeat(mission_id, actor, fence, ttl_seconds=ttl_seconds))}
            elif op == "RUNNING":
                if fence is None: raise ValueError("FENCE_REQUIRED")
                result = {"event": asdict(runtime.running(mission_id, actor, fence))}
            elif op == "CHECKPOINT":
                if fence is None: raise ValueError("FENCE_REQUIRED")
                result = {"event": asdict(runtime.checkpoint(mission_id, actor, fence, payload))}
            elif op == "EFFECT_UNKNOWN":
                if fence is None or not effect_id: raise ValueError("FENCE_AND_EFFECT_REQUIRED")
                result = {"event": asdict(runtime.mark_effect_uncertain(mission_id, actor, fence, effect_id))}
            elif op == "RESULT_READY":
                if fence is None: raise ValueError("FENCE_REQUIRED")
                result = {"event": asdict(runtime.result_ready(mission_id, actor, fence, payload))}
            elif op == "RECOVER_ORPHAN":
                new_fence, event = runtime.recover_orphan(
                    mission_id, actor, readback=readback, ttl_seconds=ttl_seconds
                )
                result = {"fence": new_fence, "event": asdict(event)}
            elif op == "CONFIRM_EFFECT_READBACK":
                if fence is None or not effect_id or not readback or not proof_ref:
                    raise ValueError("FENCE_EFFECT_READBACK_PROOF_REQUIRED")
                result = {"event": asdict(runtime.confirm_effect_readback(
                    mission_id, actor, fence, effect_id=effect_id, readback=readback, proof_ref=proof_ref
                ))}
            elif op == "IMPORT_EXTERNAL_RESULT":
                if not effect_id or not proof_ref or not verifier:
                    raise ValueError("EFFECT_PROOF_VERIFIER_REQUIRED")
                result = {"event": asdict(runtime.import_external_result(
                    mission_id, verifier=verifier, effect_id=effect_id, result=payload, proof_ref=proof_ref
                ))}
            elif op == "PROJECTION":
                # Read-only projection intentionally has no CAS write.
                projection = asdict(runtime.projection(mission_id))
                body = {
                    "schema": "FUSE-WORK-PLANE-GCS-READ-RECEIPT-V1",
                    "mission_id": mission_id,
                    "generation": generation,
                    "projection": projection,
                }
                return BundleCommitReceipt(
                    schema="FUSE-WORK-PLANE-GCS-READ-RECEIPT-V1",
                    adapter_version=ADAPTER_VERSION,
                    operation=op,
                    mission_id=mission_id,
                    prior_generation=generation,
                    committed_generation=generation,
                    bundle_sha256=_digest(bundle),
                    result=projection,
                    provider_effect_authorized=False,
                    receipt_sha256=_digest(body),
                )
            else:
                raise ValueError("OPERATION_NOT_ALLOWED")

            updated = self._pack(runtime, root, bundle)
            raw = _canonical(updated)
            committed = self.client.put(
                self.bucket, self.object_name, raw, if_generation_match=generation
            )
            body = {
                "schema": "FUSE-WORK-PLANE-GCS-COMMIT-RECEIPT-V1",
                "adapter_version": ADAPTER_VERSION,
                "operation": op,
                "mission_id": mission_id,
                "prior_generation": generation,
                "committed_generation": committed,
                "bundle_sha256": sha256(raw).hexdigest(),
                "result": result,
                "provider_effect_authorized": False,
            }
            return BundleCommitReceipt(
                receipt_sha256=_digest(body),
                **body,
            )
