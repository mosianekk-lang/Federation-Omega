from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping


KERNEL_V2 = "2.0.0"


@dataclass(frozen=True)
class ManifestAnomaly:
    code: str
    detail: str
    receiver_id: str = ""


@dataclass(frozen=True)
class ReceiverManifestEntry:
    receiver_id: str
    canonical_control: str
    primary_id: str
    registry_status: str
    latest_event_id: str = ""
    latest_event_timestamp: str = ""
    latest_event_kernel_version: str = ""
    kernel_invoked: bool = False
    behavior_proven: bool = False
    independent_readback: bool = False
    current: bool = False
    evidence_refs: tuple[str, ...] = ()
    receiver_state: str = "REGISTERED_V2_BEHAVIOR_PENDING"


@dataclass(frozen=True)
class ReceiverManifestSnapshot:
    schema_version: str
    generated_from: str
    generated_at: str
    source_complete: bool
    complete: bool
    behavior_complete: bool
    receiver_count: int
    v2_behavior_proven_count: int
    v2_invoked_open_count: int
    v1_behavior_proven_v2_pending_count: int
    snapshot_sha256: str
    anomalies: tuple[ManifestAnomaly, ...]
    receivers: tuple[ReceiverManifestEntry, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).upper() in {"TRUE", "YES", "1", "VERIFIED"}


def _evidence_refs(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set)):
        return tuple(sorted({_text(item) for item in value if _text(item)}))
    text = _text(value)
    if not text:
        return ()
    # Semicolon is the canonical multi-reference delimiter. A legacy single
    # free-text receipt remains one reference rather than being guessed apart.
    return tuple(sorted({item.strip() for item in text.split(";") if item.strip()}))


def _canonical_hash(entries: Iterable[ReceiverManifestEntry]) -> str:
    payload = [
        {
            "receiver_id": item.receiver_id,
            "canonical_control": item.canonical_control,
            "primary_id": item.primary_id,
            "registry_status": item.registry_status,
            "latest_event_id": item.latest_event_id,
            "latest_event_timestamp": item.latest_event_timestamp,
            "latest_event_kernel_version": item.latest_event_kernel_version,
            "kernel_invoked": item.kernel_invoked,
            "behavior_proven": item.behavior_proven,
            "independent_readback": item.independent_readback,
            "current": item.current,
            "evidence_refs": list(item.evidence_refs),
            "receiver_state": item.receiver_state,
        }
        for item in sorted(entries, key=lambda value: value.receiver_id)
    ]
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _event_sort_key(event: Mapping[str, Any]) -> tuple[str, str]:
    return (_text(event.get("timestamp")), _text(event.get("event_id")))


def compile_receiver_manifest(
    registry_rows: Iterable[Mapping[str, Any]],
    event_rows: Iterable[Mapping[str, Any]],
    *,
    generated_from: str,
    generated_at: str,
    source_complete: bool,
) -> ReceiverManifestSnapshot:
    """Compile a fail-closed receiver manifest from provider-neutral tabular rows.

    Registry completeness and behavioral completeness are deliberately separate.
    A structurally complete 25-receiver universe may still have zero v2 behavior
    proofs. Historical v1 events remain visible but cannot promote v2 state.
    """

    anomalies: list[ManifestAnomaly] = []
    registry: dict[str, dict[str, str]] = {}

    for index, raw in enumerate(registry_rows, start=1):
        active = _truthy(raw.get("active", True))
        if not active:
            continue
        receiver_id = _text(raw.get("receiver_id"))
        canonical_control = _text(raw.get("canonical_control"))
        primary_id = _text(raw.get("primary_id"))
        if not receiver_id:
            anomalies.append(ManifestAnomaly("BLANK_RECEIVER_ID", f"registry row {index}"))
            continue
        if not primary_id:
            anomalies.append(ManifestAnomaly("BLANK_PRIMARY_ID", f"registry row {index}", receiver_id))
            continue
        if receiver_id in registry:
            anomalies.append(ManifestAnomaly("DUPLICATE_RECEIVER_ID", f"registry row {index}", receiver_id))
            continue
        registry[receiver_id] = {
            "canonical_control": canonical_control,
            "primary_id": primary_id,
        }

    latest: dict[str, Mapping[str, Any]] = {}
    for index, raw in enumerate(event_rows, start=1):
        event_id = _text(raw.get("event_id"))
        receiver_id = _text(raw.get("receiver_id"))
        if not event_id:
            anomalies.append(ManifestAnomaly("BLANK_EVENT_ID", f"event row {index}", receiver_id))
            continue
        if not receiver_id:
            anomalies.append(ManifestAnomaly("EVENT_WITHOUT_RECEIVER", f"event {event_id}"))
            continue
        if receiver_id not in registry:
            anomalies.append(ManifestAnomaly("UNKNOWN_EVENT_RECEIVER", f"event {event_id}", receiver_id))
            continue
        prior = latest.get(receiver_id)
        if prior is None or _event_sort_key(raw) >= _event_sort_key(prior):
            latest[receiver_id] = raw

    entries: list[ReceiverManifestEntry] = []
    for receiver_id in sorted(registry):
        base = registry[receiver_id]
        event = latest.get(receiver_id)
        if event is None:
            entries.append(
                ReceiverManifestEntry(
                    receiver_id=receiver_id,
                    canonical_control=base["canonical_control"],
                    primary_id=base["primary_id"],
                    registry_status="REGISTERED_V2",
                )
            )
            continue

        version = _text(event.get("kernel_version"))
        invoked = _truthy(event.get("kernel_invoked"))
        behavior = _truthy(event.get("behavior_proven"))
        readback = _truthy(event.get("independent_readback"))
        current = _truthy(event.get("current"))
        refs = _evidence_refs(event.get("evidence_refs"))

        if version == KERNEL_V2:
            if invoked and behavior and readback and current and refs:
                state = "V2_BEHAVIOR_PROVEN"
            elif invoked:
                state = "V2_INVOKED_PROOF_OPEN"
            else:
                state = "V2_EVENT_PRESENT_INVOCATION_OPEN"
        elif version == "1.0.0" and behavior:
            state = "V1_BEHAVIOR_PROVEN_V2_PENDING"
        else:
            state = "HISTORICAL_EVENT_V2_PENDING"

        entries.append(
            ReceiverManifestEntry(
                receiver_id=receiver_id,
                canonical_control=base["canonical_control"],
                primary_id=base["primary_id"],
                registry_status="REGISTERED_V2",
                latest_event_id=_text(event.get("event_id")),
                latest_event_timestamp=_text(event.get("timestamp")),
                latest_event_kernel_version=version,
                kernel_invoked=invoked if version == KERNEL_V2 else False,
                behavior_proven=behavior if version == KERNEL_V2 else False,
                independent_readback=readback if version == KERNEL_V2 else False,
                current=current if version == KERNEL_V2 else False,
                evidence_refs=refs,
                receiver_state=state,
            )
        )

    structural_codes = {
        "BLANK_RECEIVER_ID",
        "BLANK_PRIMARY_ID",
        "DUPLICATE_RECEIVER_ID",
        "BLANK_EVENT_ID",
        "EVENT_WITHOUT_RECEIVER",
        "UNKNOWN_EVENT_RECEIVER",
    }
    complete = bool(source_complete and entries) and not any(item.code in structural_codes for item in anomalies)
    behavior_complete = complete and all(item.receiver_state == "V2_BEHAVIOR_PROVEN" for item in entries)
    v2_behavior = sum(item.receiver_state == "V2_BEHAVIOR_PROVEN" for item in entries)
    v2_invoked_open = sum(item.receiver_state == "V2_INVOKED_PROOF_OPEN" for item in entries)
    v1_pending = sum(item.receiver_state == "V1_BEHAVIOR_PROVEN_V2_PENDING" for item in entries)

    return ReceiverManifestSnapshot(
        schema_version="failure-win.receiver-manifest.v2",
        generated_from=_text(generated_from),
        generated_at=_text(generated_at),
        source_complete=source_complete,
        complete=complete,
        behavior_complete=behavior_complete,
        receiver_count=len(entries),
        v2_behavior_proven_count=v2_behavior,
        v2_invoked_open_count=v2_invoked_open,
        v1_behavior_proven_v2_pending_count=v1_pending,
        snapshot_sha256=_canonical_hash(entries),
        anomalies=tuple(anomalies),
        receivers=tuple(entries),
    )
