"""SOVARA sovereign backup pipeline.

This module is deliberately provider-neutral. It builds deterministic full or
incremental backup archives, verifies provider readback and privacy, and emits
hash-linked receipts. Exact private Drive folders, Gmail addresses, credentials,
and provider object IDs are resolved by an authorised private adapter at runtime;
they must never be embedded in public source.

Source presence does not prove scheduling, provider upload, email delivery, or
restoration. Those states require adapter-specific readback receipts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
import hashlib
import io
import json
import re
from typing import Any, Iterable, Mapping, Protocol, Sequence
import zipfile


SCHEMA = "SOVARA-SOVEREIGN-BACKUP-PIPELINE-1"
MANIFEST_VERSION = "1.0.0"
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/+ -]{0,239}$")
_SAFE_ALIAS = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")

_SECRET_KEY = re.compile(
    r"(?:^|_)(?:access_?token|refresh_?token|id_?token|api_?key|password|passwd|"
    r"client_?secret|private_?key|credential|authorization|cookie|secret)(?:$|_)",
    re.IGNORECASE,
)
_SAFE_SECRET_SUFFIXES = (
    "_ref",
    "_reference",
    "_alias",
    "_handle",
    "_fingerprint",
    "_sha256",
)
_SECRET_VALUES = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{16,}=*", re.IGNORECASE),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    re.compile(r"\bya29\.[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)


class BackupError(RuntimeError):
    """Fail-closed backup construction, verification, or provider error."""


class BackupEventType(StrEnum):
    ADMITTED_SOURCE_RELEASE = "ADMITTED_SOURCE_RELEASE"
    LIVE_BIBLE_REVISION = "LIVE_BIBLE_REVISION"
    PROVIDER_CANARY = "PROVIDER_CANARY"
    DEPLOYMENT = "DEPLOYMENT"
    ROLLBACK = "ROLLBACK"
    MATERIAL_CONFIG_CHANGE = "MATERIAL_CONFIG_CHANGE"
    MANUAL_CHECKPOINT = "MANUAL_CHECKPOINT"


class BackupMode(StrEnum):
    FULL = "FULL"
    DELTA = "DELTA"
    NO_CHANGE = "NO_CHANGE"


class ArtifactClass(StrEnum):
    PUBLIC_SAFE = "PUBLIC_SAFE"
    PRIVATE_CONTROL = "PRIVATE_CONTROL"
    PRIVATE_SENSITIVE = "PRIVATE_SENSITIVE"
    SECRET_REFERENCE_ONLY = "SECRET_REFERENCE_ONLY"


@dataclass(frozen=True)
class ArtifactInput:
    logical_name: str
    content: bytes
    media_type: str = "application/octet-stream"
    classification: ArtifactClass = ArtifactClass.PRIVATE_CONTROL
    source_ref: str = ""
    email_eligible: bool = False


@dataclass(frozen=True)
class ArtifactRecord:
    logical_name: str
    sha256: str
    size_bytes: int
    media_type: str
    classification: str
    source_ref: str
    email_eligible: bool


@dataclass(frozen=True)
class BackupPlan:
    manifest: Mapping[str, Any]
    manifest_bytes: bytes
    manifest_sha256: str
    selected_artifacts: tuple[ArtifactInput, ...]
    archive_name: str | None
    archive_bytes: bytes | None
    archive_sha256: str | None
    checksums_bytes: bytes
    idempotency_key: str

    @property
    def mode(self) -> BackupMode:
        return BackupMode(str(self.manifest["backup_mode"]))


@dataclass(frozen=True)
class ProviderFile:
    file_id: str
    name: str
    size_bytes: int
    url: str = ""


@dataclass(frozen=True)
class PermissionReadback:
    shared: bool
    owner_identities: tuple[str, ...]
    non_owner_identities: tuple[str, ...] = ()


class BackupProvider(Protocol):
    """Minimal private adapter contract.

    Implementations may use Google Drive/Gmail, another provider, or a local
    sovereign store. The public core accepts aliases only; exact provider IDs
    remain in the private adapter or private canonical registry.
    """

    def resolve_destination(self, alias: str) -> str: ...

    def create_snapshot_container(self, destination: str, name: str) -> str: ...

    def upload_bytes(
        self, container: str, name: str, content: bytes, media_type: str
    ) -> ProviderFile: ...

    def download_bytes(self, file_id: str) -> bytes: ...

    def read_permissions(self, container: str) -> PermissionReadback: ...

    def send_continuity_email(
        self,
        *,
        subject: str,
        body: str,
        attachments: Sequence[tuple[str, bytes, str]],
    ) -> str: ...


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_canonical_json(value))


def _normalise_time(value: datetime | str) -> str:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise BackupError("created_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise BackupError("created_at must include a timezone")
    return parsed.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_logical_name(value: str) -> str:
    name = " ".join(str(value).strip().split())
    if name.startswith(("/", "\\")) or ".." in name.split("/") or "\\" in name:
        raise BackupError(f"artifact name may not traverse paths: {name}")
    if not _SAFE_NAME.fullmatch(name):
        raise BackupError(f"unsafe or empty artifact name: {value!r}")
    return name


def _safe_event_id(value: str) -> str:
    event_id = str(value).strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{2,191}", event_id):
        raise BackupError("event_id must be a stable public-safe identifier")
    return event_id


def _safe_alias(value: str) -> str:
    alias = str(value).strip()
    if not _SAFE_ALIAS.fullmatch(alias):
        raise BackupError("destination must be a private canonical alias, not a raw provider ID")
    return alias


def reject_secret_metadata(value: Any, path: str = "payload") -> None:
    """Reject raw credential material from manifests, receipts, and routing data."""

    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key)
            lowered = key.lower()
            if _SECRET_KEY.search(lowered) and not lowered.endswith(_SAFE_SECRET_SUFFIXES):
                raise BackupError(f"secret-bearing metadata field rejected at {path}.{key}")
            reject_secret_metadata(item, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for index, item in enumerate(value):
            reject_secret_metadata(item, f"{path}[{index}]")
        return
    if isinstance(value, str):
        for pattern in _SECRET_VALUES:
            if pattern.search(value):
                raise BackupError(f"raw credential-like metadata rejected at {path}")


def _scan_email_or_public_content(artifact: ArtifactInput) -> None:
    if not (
        artifact.email_eligible or artifact.classification is ArtifactClass.PUBLIC_SAFE
    ):
        return
    if artifact.media_type.startswith("text/") or artifact.media_type in {
        "application/json",
        "application/yaml",
        "application/xml",
        "application/javascript",
    }:
        text = artifact.content.decode("utf-8", errors="replace")
        for pattern in _SECRET_VALUES:
            if pattern.search(text):
                raise BackupError(
                    f"email/public artifact contains credential-shaped material: {artifact.logical_name}"
                )


def _record(artifact: ArtifactInput) -> ArtifactRecord:
    name = _safe_logical_name(artifact.logical_name)
    reject_secret_metadata(
        {
            "logical_name": name,
            "media_type": artifact.media_type,
            "classification": artifact.classification.value,
            "source_ref": artifact.source_ref,
        },
        "artifact_metadata",
    )
    _scan_email_or_public_content(artifact)
    return ArtifactRecord(
        logical_name=name,
        sha256=_sha256_bytes(artifact.content),
        size_bytes=len(artifact.content),
        media_type=str(artifact.media_type),
        classification=artifact.classification.value,
        source_ref=str(artifact.source_ref),
        email_eligible=bool(artifact.email_eligible),
    )


def _prior_index(prior_manifest: Mapping[str, Any] | None) -> dict[str, Mapping[str, Any]]:
    if prior_manifest is None:
        return {}
    if prior_manifest.get("schema") != SCHEMA:
        raise BackupError("prior manifest schema is not supported")
    artifacts = prior_manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise BackupError("prior manifest artifacts must be a list")
    index: dict[str, Mapping[str, Any]] = {}
    for item in artifacts:
        if not isinstance(item, Mapping):
            raise BackupError("prior artifact record must be an object")
        name = _safe_logical_name(str(item.get("logical_name") or ""))
        digest = str(item.get("sha256") or "").lower()
        if not _HEX64.fullmatch(digest):
            raise BackupError(f"prior artifact digest is invalid: {name}")
        if name in index:
            raise BackupError(f"duplicate prior artifact: {name}")
        index[name] = item
    return index


def _deterministic_archive(
    *,
    manifest_bytes: bytes,
    checksums_bytes: bytes,
    selected: Sequence[ArtifactInput],
) -> bytes:
    output = io.BytesIO()
    entries: list[tuple[str, bytes]] = [
        ("BACKUP_MANIFEST.json", manifest_bytes),
        ("CHECKSUMS.sha256", checksums_bytes),
    ]
    entries.extend((f"artifacts/{_safe_logical_name(item.logical_name)}", item.content) for item in selected)
    with zipfile.ZipFile(
        output, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for name, content in sorted(entries, key=lambda item: item[0]):
            info = zipfile.ZipInfo(name, _FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            archive.writestr(info, content)
    return output.getvalue()


def build_backup_plan(
    *,
    event_type: BackupEventType | str,
    event_id: str,
    created_at: datetime | str,
    source_identity: str,
    source_version: str,
    artifacts: Iterable[ArtifactInput],
    prior_manifest: Mapping[str, Any] | None = None,
    prior_manifest_sha256: str | None = None,
    prior_receipt_sha256: str | None = None,
    sequence: int | None = None,
    checkpoint_every: int = 7,
    force_full: bool = False,
) -> BackupPlan:
    """Build a deterministic full, delta, or no-change backup plan."""

    try:
        event = BackupEventType(str(event_type))
    except ValueError as exc:
        raise BackupError(f"unsupported backup event type: {event_type}") from exc
    stable_event_id = _safe_event_id(event_id)
    timestamp = _normalise_time(created_at)
    if checkpoint_every < 1:
        raise BackupError("checkpoint_every must be at least 1")

    items = tuple(artifacts)
    if not items:
        raise BackupError("at least one artifact is required")
    records = tuple(_record(item) for item in items)
    names = [item.logical_name for item in records]
    if len(names) != len(set(names)):
        raise BackupError("artifact logical names must be unique")

    reject_secret_metadata(
        {
            "event_id": stable_event_id,
            "source_identity": source_identity,
            "source_version": source_version,
            "prior_manifest_sha256": prior_manifest_sha256 or "",
            "prior_receipt_sha256": prior_receipt_sha256 or "",
        },
        "backup_control",
    )
    if not str(source_identity).strip() or not str(source_version).strip():
        raise BackupError("source_identity and source_version are required")

    prior_index = _prior_index(prior_manifest)
    if prior_manifest is not None:
        computed_prior = _sha256_json(prior_manifest)
        if prior_manifest_sha256 and computed_prior != prior_manifest_sha256:
            raise BackupError("prior manifest SHA-256 does not match its content")
        prior_manifest_sha256 = computed_prior
        prior_sequence = int(prior_manifest.get("sequence") or 0)
    else:
        prior_sequence = 0
        prior_manifest_sha256 = None

    next_sequence = sequence if sequence is not None else prior_sequence + 1
    if next_sequence < 1 or next_sequence <= prior_sequence:
        raise BackupError("sequence must advance beyond the prior manifest")

    current_index = {record.logical_name: asdict(record) for record in records}
    changed = tuple(
        sorted(
            name
            for name, record in current_index.items()
            if name not in prior_index
            or str(prior_index[name].get("sha256")) != record["sha256"]
        )
    )
    removed = tuple(sorted(set(prior_index) - set(current_index)))
    periodic_full = next_sequence % checkpoint_every == 0

    if prior_manifest is None or force_full or periodic_full:
        mode = BackupMode.FULL
        selected_names = tuple(sorted(current_index))
    elif not changed and not removed:
        mode = BackupMode.NO_CHANGE
        selected_names = ()
    else:
        mode = BackupMode.DELTA
        selected_names = changed

    selected_by_name = {_safe_logical_name(item.logical_name): item for item in items}
    selected = tuple(selected_by_name[name] for name in selected_names)
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "version": MANIFEST_VERSION,
        "event_type": event.value,
        "event_id": stable_event_id,
        "created_at": timestamp,
        "source_identity": str(source_identity),
        "source_version": str(source_version),
        "sequence": next_sequence,
        "checkpoint_every": checkpoint_every,
        "backup_mode": mode.value,
        "previous_manifest_sha256": prior_manifest_sha256,
        "previous_receipt_sha256": prior_receipt_sha256,
        "artifacts": [current_index[name] for name in sorted(current_index)],
        "selected_artifacts": list(selected_names),
        "changed_artifacts": list(changed),
        "removed_artifacts": list(removed),
        "unchanged_artifact_count": len(current_index) - len(changed),
        "truth_boundary": {
            "archive_built": mode is not BackupMode.NO_CHANGE,
            "provider_upload_performed": False,
            "provider_download_readback_performed": False,
            "permission_readback_performed": False,
            "gmail_receipt_sent": False,
            "provider_runtime_proven": False,
            "external_effect": False,
        },
    }
    reject_secret_metadata(manifest, "manifest")
    manifest_bytes = _canonical_json(manifest)
    manifest_sha256 = _sha256_bytes(manifest_bytes)
    idempotency_key = "sovbak-" + _sha256_bytes(
        (
            event.value
            + "|"
            + stable_event_id
            + "|"
            + str(source_identity)
            + "|"
            + str(source_version)
            + "|"
            + manifest_sha256
        ).encode("utf-8")
    )

    checksum_lines = [f"{record.sha256}  artifacts/{record.logical_name}" for record in records]
    checksum_lines.append(f"{manifest_sha256}  BACKUP_MANIFEST.json")
    checksums_bytes = ("\n".join(sorted(checksum_lines)) + "\n").encode("utf-8")

    if mode is BackupMode.NO_CHANGE:
        archive_name = None
        archive_bytes = None
        archive_sha256 = None
    else:
        archive_name = f"SOVARA_{stable_event_id}_{mode.value}.zip"
        archive_bytes = _deterministic_archive(
            manifest_bytes=manifest_bytes,
            checksums_bytes=checksums_bytes,
            selected=selected,
        )
        archive_sha256 = _sha256_bytes(archive_bytes)

    return BackupPlan(
        manifest=manifest,
        manifest_bytes=manifest_bytes,
        manifest_sha256=manifest_sha256,
        selected_artifacts=selected,
        archive_name=archive_name,
        archive_bytes=archive_bytes,
        archive_sha256=archive_sha256,
        checksums_bytes=checksums_bytes,
        idempotency_key=idempotency_key,
    )


def verify_archive(plan: BackupPlan, archive_bytes: bytes | None = None) -> bool:
    if plan.mode is BackupMode.NO_CHANGE:
        if archive_bytes not in (None, b""):
            raise BackupError("no-change plan must not carry an archive")
        return True
    payload = plan.archive_bytes if archive_bytes is None else archive_bytes
    if payload is None:
        raise BackupError("archive bytes are missing")
    if _sha256_bytes(payload) != plan.archive_sha256:
        raise BackupError("archive SHA-256 mismatch")
    try:
        with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
            if archive.testzip() is not None:
                raise BackupError("archive CRC verification failed")
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise BackupError("archive contains duplicate names")
            for name in names:
                if name.startswith(("/", "\\")) or ".." in name.split("/") or "\\" in name:
                    raise BackupError("archive contains an unsafe path")
            stored_manifest = archive.read("BACKUP_MANIFEST.json")
            if stored_manifest != plan.manifest_bytes:
                raise BackupError("archive manifest differs from the plan")
            for artifact in plan.selected_artifacts:
                name = f"artifacts/{_safe_logical_name(artifact.logical_name)}"
                content = archive.read(name)
                if _sha256_bytes(content) != _sha256_bytes(artifact.content):
                    raise BackupError(f"artifact readback mismatch: {artifact.logical_name}")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise BackupError("archive is invalid or incomplete") from exc
    return True


class IdempotencyLedger:
    """Compact payload-bound idempotency and receipt-chain ledger."""

    def __init__(self, events: Iterable[Mapping[str, Any]] = ()) -> None:
        self._events: list[dict[str, Any]] = [dict(item) for item in events]
        if not self.verify_chain():
            raise BackupError("existing idempotency ledger hash chain is invalid")

    @property
    def events(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(dict(item) for item in self._events)

    @property
    def head_hash(self) -> str:
        return self._events[-1]["event_hash"] if self._events else "GENESIS"

    def admit(self, *, key: str, payload_sha256: str, receipt: Mapping[str, Any]) -> str:
        if not _HEX64.fullmatch(str(payload_sha256)):
            raise BackupError("payload_sha256 must be a lowercase SHA-256")
        matches = [event for event in self._events if event["key"] == key]
        if matches:
            if any(event["payload_sha256"] != payload_sha256 for event in matches):
                raise BackupError("idempotency key collision with changed payload")
            return "ALREADY_ADMITTED_EXACT"
        reject_secret_metadata(receipt, "receipt")
        body = {
            "sequence": len(self._events) + 1,
            "key": str(key),
            "payload_sha256": payload_sha256,
            "previous_hash": self.head_hash,
            "receipt": dict(receipt),
        }
        event = body | {"event_hash": _sha256_json(body)}
        self._events.append(event)
        return "ADMITTED"

    def verify_chain(self) -> bool:
        previous = "GENESIS"
        for sequence, event in enumerate(self._events, 1):
            body = {
                "sequence": event.get("sequence"),
                "key": event.get("key"),
                "payload_sha256": event.get("payload_sha256"),
                "previous_hash": event.get("previous_hash"),
                "receipt": event.get("receipt"),
            }
            if body["sequence"] != sequence or body["previous_hash"] != previous:
                return False
            expected = _sha256_json(body)
            if event.get("event_hash") != expected:
                return False
            previous = expected
        return True


def execute_private_backup(
    *,
    plan: BackupPlan,
    provider: BackupProvider,
    destination_alias: str,
    expected_owner_identity: str,
    ledger: IdempotencyLedger,
    email_subject_prefix: str = "SOVARA Ω backup",
    attach_archive_limit_bytes: int = 20_000_000,
    send_email: bool = True,
) -> Mapping[str, Any]:
    """Execute one provider backup with exact readback and permission proof."""

    alias = _safe_alias(destination_alias)
    owner = str(expected_owner_identity).strip().lower()
    if not owner:
        raise BackupError("expected_owner_identity is required")

    payload_sha256 = plan.archive_sha256 or plan.manifest_sha256
    prior = [event for event in ledger.events if event["key"] == plan.idempotency_key]
    if prior:
        if any(event["payload_sha256"] != payload_sha256 for event in prior):
            raise BackupError("idempotency key collision with changed payload")
        return prior[-1]["receipt"] | {"idempotency_state": "ALREADY_ADMITTED_EXACT"}

    destination = provider.resolve_destination(alias)
    if not destination:
        raise BackupError("private destination alias did not resolve")
    container = provider.create_snapshot_container(
        destination,
        f"{plan.manifest['created_at'][:10]} — {plan.manifest['event_type']} — {plan.manifest['event_id']}",
    )
    permissions = provider.read_permissions(container)
    owners = {identity.strip().lower() for identity in permissions.owner_identities}
    non_owners = {identity.strip().lower() for identity in permissions.non_owner_identities}
    if permissions.shared or owners != {owner} or non_owners:
        raise BackupError("backup container is not owner-only private")

    manifest_file = provider.upload_bytes(
        container,
        "BACKUP_MANIFEST.json",
        plan.manifest_bytes,
        "application/json",
    )
    checksum_file = provider.upload_bytes(
        container,
        "CHECKSUMS.sha256",
        plan.checksums_bytes,
        "text/plain",
    )
    uploaded_archive: ProviderFile | None = None
    readback_sha256: str | None = None
    if plan.archive_bytes is not None and plan.archive_name is not None:
        uploaded_archive = provider.upload_bytes(
            container,
            plan.archive_name,
            plan.archive_bytes,
            "application/zip",
        )
        downloaded = provider.download_bytes(uploaded_archive.file_id)
        readback_sha256 = _sha256_bytes(downloaded)
        if readback_sha256 != plan.archive_sha256:
            raise BackupError("provider-download archive SHA-256 mismatch")
        verify_archive(plan, downloaded)

    receipt: dict[str, Any] = {
        "schema": "SOVARA-SOVEREIGN-BACKUP-RECEIPT-1",
        "event_id": plan.manifest["event_id"],
        "event_type": plan.manifest["event_type"],
        "backup_mode": plan.manifest["backup_mode"],
        "idempotency_key": plan.idempotency_key,
        "destination_alias": alias,
        "container_ref": container,
        "manifest": asdict(manifest_file),
        "checksums": asdict(checksum_file),
        "archive": asdict(uploaded_archive) if uploaded_archive else None,
        "manifest_sha256": plan.manifest_sha256,
        "archive_sha256": plan.archive_sha256,
        "provider_download_sha256": readback_sha256,
        "permission_readback": {
            "shared": permissions.shared,
            "owner_identity_count": len(owners),
            "non_owner_identity_count": len(non_owners),
            "owner_only_private": True,
        },
        "email_message_ref": None,
        "truth_boundary": {
            "provider_upload_performed": True,
            "provider_download_readback_performed": uploaded_archive is not None,
            "permission_readback_performed": True,
            "gmail_receipt_sent": False,
            "provider_runtime_proven": True,
            "external_effect": True,
        },
    }
    reject_secret_metadata(receipt, "provider_receipt")

    if send_email:
        all_email_eligible = all(item.email_eligible for item in plan.selected_artifacts)
        attachments: list[tuple[str, bytes, str]] = [
            ("BACKUP_MANIFEST.json", plan.manifest_bytes, "application/json"),
            ("CHECKSUMS.sha256", plan.checksums_bytes, "text/plain"),
        ]
        if (
            plan.archive_bytes is not None
            and len(plan.archive_bytes) <= attach_archive_limit_bytes
            and all_email_eligible
        ):
            attachments.append((plan.archive_name or "backup.zip", plan.archive_bytes, "application/zip"))
        subject = f"{email_subject_prefix} — {plan.manifest['event_type']} — {plan.manifest['event_id']}"
        body = (
            "The private backup completed with provider download and permission readback.\n\n"
            f"Mode: {plan.manifest['backup_mode']}\n"
            f"Manifest SHA-256: {plan.manifest_sha256}\n"
            f"Archive SHA-256: {plan.archive_sha256 or 'NO_CHANGE'}\n"
            f"Destination alias: {alias}\n"
            "The exact provider pointer remains in the private canonical registry."
        )
        receipt["email_message_ref"] = provider.send_continuity_email(
            subject=subject,
            body=body,
            attachments=tuple(attachments),
        )
        receipt["truth_boundary"]["gmail_receipt_sent"] = True

    receipt["receipt_sha256"] = _sha256_json(receipt)
    ledger_state = ledger.admit(
        key=plan.idempotency_key,
        payload_sha256=payload_sha256,
        receipt=receipt,
    )
    receipt["idempotency_state"] = ledger_state
    receipt["ledger_head_sha256"] = ledger.head_hash
    return receipt


def restore_snapshot_chain(
    archives: Sequence[bytes],
) -> Mapping[str, bytes]:
    """Verify and restore an ordered FULL→DELTA archive chain in memory."""

    restored: dict[str, bytes] = {}
    previous_manifest_sha256: str | None = None
    previous_sequence = 0
    for position, payload in enumerate(archives):
        try:
            with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
                if archive.testzip() is not None:
                    raise BackupError("archive CRC verification failed during restore")
                manifest_bytes = archive.read("BACKUP_MANIFEST.json")
                manifest = json.loads(manifest_bytes)
                if manifest.get("schema") != SCHEMA:
                    raise BackupError("restore manifest schema is not supported")
                current_hash = _sha256_bytes(manifest_bytes)
                sequence = int(manifest.get("sequence") or 0)
                if sequence <= previous_sequence:
                    raise BackupError("restore chain sequence is not strictly increasing")
                if position == 0 and manifest.get("backup_mode") != BackupMode.FULL.value:
                    raise BackupError("restore chain must begin with a full backup")
                if position > 0 and manifest.get("previous_manifest_sha256") != previous_manifest_sha256:
                    raise BackupError("restore chain previous-manifest binding failed")
                if manifest.get("backup_mode") == BackupMode.FULL.value:
                    restored.clear()
                for name in manifest.get("removed_artifacts") or []:
                    restored.pop(_safe_logical_name(str(name)), None)
                for name in manifest.get("selected_artifacts") or []:
                    safe_name = _safe_logical_name(str(name))
                    restored[safe_name] = archive.read(f"artifacts/{safe_name}")
                expected_records = {
                    str(item["logical_name"]): item
                    for item in manifest.get("artifacts") or []
                }
                for name, content in restored.items():
                    if name not in expected_records:
                        raise BackupError(f"restored artifact not present in manifest: {name}")
                    if _sha256_bytes(content) != expected_records[name]["sha256"]:
                        raise BackupError(f"restored artifact digest mismatch: {name}")
                if set(restored) != set(expected_records):
                    raise BackupError("restored artifact set differs from current manifest")
                previous_manifest_sha256 = current_hash
                previous_sequence = sequence
        except (KeyError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
            raise BackupError("restore archive is invalid or incomplete") from exc
    return dict(sorted(restored.items()))
