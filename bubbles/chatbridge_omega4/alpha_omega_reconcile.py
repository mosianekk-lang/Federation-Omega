from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import threading
import uuid
from dataclasses import replace
from typing import Any, Dict, Iterable, List, Optional, Sequence

from ao_harmonic_v3.science_and_routes import FormationEngine
from .full_fidelity_ledger import (
    ConversationIdentityConflict, ConversationNotBound, EventExecutionState,
    FullFidelityConversationLedger, IncompleteTranscript,
    TerminalExecutionClaimError, TranscriptIntegrityState,
)
from .alpha_omega_models import (
    AlphaOmegaRestoreMode, CaptureObservation, CapturePath, CapturePathConflict,
    CapturePathKind, CapturePathNotRegistered, CapturePathState, ConversationStream,
    ObservationConflict, OrderingAuthority, ReconciliationState, ReplayChunk,
    StreamExpectation, StreamManifestError, _canonical_json, _digest, _key,
    _missing_ranges, _namespace, _now,
)

class AlphaOmegaReconcileMixin:
    def reconcile(
        self,
        conversation_key: str,
        namespace_key: str,
        *,
        allow_derived_ordering: bool = True,
        source_provider: str = "CHATGPT",
        title: str = "",
    ) -> Dict[str, Any]:
        key = _key(conversation_key, "conversation_key")
        namespace = _namespace(namespace_key)
        with self._capture_lock:
            self.ledger.bind(
                key,
                namespace,
                source_provider=source_provider,
                title=title,
            )
            status = self.ledger.status(key)
            ledger_status = status["verification"]
            next_sequence = (
                int(status["last_sequence"]) + 1
                if status.get("last_sequence") is not None
                else int(status["expected_first_sequence"])
            )
            groups = self._candidate_groups(key)
            receipts: List[Dict[str, Any]] = []
            pending_explicit: Dict[
                int, Tuple[CaptureObservation, List[str], List[str], str]
            ] = {}
            pending_derived: List[
                Tuple[CaptureObservation, List[str], List[str], str]
            ] = []
            conflicts: List[Dict[str, Any]] = []

            for identity_key, rows in groups.items():
                payload_hashes = {row["payload_hash"] for row in rows}
                if len(payload_hashes) > 1 or any(
                    row["reconciliation_state"] == ReconciliationState.CONFLICTED.value
                    for row in rows
                ):
                    conflicts.append(
                        {
                            "identity_key": identity_key,
                            "path_ids": sorted({row["path_id"] for row in rows}),
                            "payload_hashes": sorted(payload_hashes),
                        }
                    )
                    continue

                observations = [
                    CaptureObservation.from_dict(json.loads(row["observation_json"]))
                    for row in rows
                ]
                paths = [
                    self._registered_path(key, item.path_id, require_eligible=False)
                    for item in observations
                ]
                supporting_paths = sorted({item.path_id for item in observations})
                supporting_groups = sorted({item.normalized_group() for item in paths})
                canonical = self._canonical_row(key, identity_key)
                if canonical:
                    receipts.append(
                        self._update_corroboration(
                            key,
                            identity_key,
                            supporting_paths,
                            supporting_groups,
                        )
                    )
                    continue

                global_sequences = {
                    item.global_sequence
                    for item in observations
                    if item.global_sequence is not None
                }
                if len(global_sequences) > 1:
                    finding = self._finding(
                        key,
                        "MULTIPATH_SEQUENCE_CONFLICT",
                        severity="CRITICAL",
                        references=[identity_key] + supporting_paths,
                        detail={"global_sequences": sorted(global_sequences)},
                    )
                    conflicts.append(
                        {
                            "identity_key": identity_key,
                            "path_ids": supporting_paths,
                            "global_sequences": sorted(global_sequences),
                            "finding": finding,
                        }
                    )
                    continue

                selected_path = self._choose_path(key, supporting_paths)
                stream_sequences = {
                    item.stream_sequence
                    for item in observations
                    if item.stream_sequence is not None
                }
                if len(stream_sequences) > 1:
                    finding = self._finding(
                        key,
                        "MULTIPATH_STREAM_SEQUENCE_CONFLICT",
                        severity="CRITICAL",
                        references=[identity_key] + supporting_paths,
                        detail={"stream_sequences": sorted(stream_sequences)},
                    )
                    conflicts.append(
                        {
                            "identity_key": identity_key,
                            "path_ids": supporting_paths,
                            "stream_sequences": sorted(stream_sequences),
                            "finding": finding,
                        }
                    )
                    continue

                # The earliest staged observation is the stable canonical representative.
                # Route ranking decides the provenance winner but cannot rewrite FFCL
                # content when path health changes later. Explicit ordering recovered from
                # any agreeing path is projected onto that stable representative.
                selected = observations[0]
                projected_global = (
                    int(next(iter(global_sequences))) if global_sequences else None
                )
                projected_stream = (
                    int(next(iter(stream_sequences))) if stream_sequences else None
                )
                selected = replace(
                    selected,
                    global_sequence=projected_global,
                    stream_sequence=projected_stream,
                )
                if global_sequences:
                    target = int(next(iter(global_sequences)))
                    pending_explicit[target] = (
                        selected,
                        supporting_paths,
                        supporting_groups,
                        selected_path.path_id,
                    )
                else:
                    pending_derived.append(
                        (
                            selected,
                            supporting_paths,
                            supporting_groups,
                            selected_path.path_id,
                        )
                    )

            # Recover the narrow crash window where FFCL append succeeded but the
            # Alpha→Omega canonical mapping did not commit. The stable canonical event
            # is idempotently re-appended at the already-used sequence and then mapped.
            for stale_sequence in sorted(
                sequence for sequence in pending_explicit if sequence < next_sequence
            ):
                (
                    observation,
                    paths,
                    groups_for_event,
                    chosen_path_id,
                ) = pending_explicit.pop(stale_sequence)
                try:
                    receipts.append(
                        self._append_canonical(
                            observation,
                            canonical_sequence=stale_sequence,
                            supporting_paths=paths,
                            supporting_groups=groups_for_event,
                            ordering_authority=OrderingAuthority.EXPLICIT_GLOBAL_SEQUENCE,
                            chosen_path_id=chosen_path_id,
                        )
                    )
                except Exception as exc:
                    finding = self._finding(
                        key,
                        "CANONICAL_SEQUENCE_COLLISION",
                        severity="CRITICAL",
                        references=[str(stale_sequence), observation.identity_key()],
                        detail={"error": str(exc)},
                    )
                    conflicts.append(
                        {
                            "identity_key": observation.identity_key(),
                            "canonical_sequence": stale_sequence,
                            "finding": finding,
                        }
                    )

            progress = True
            while progress:
                progress = False
                if next_sequence in pending_explicit:
                    (
                        observation,
                        paths,
                        groups_for_event,
                        chosen_path_id,
                    ) = pending_explicit.pop(next_sequence)
                    receipts.append(
                        self._append_canonical(
                            observation,
                            canonical_sequence=next_sequence,
                            supporting_paths=paths,
                            supporting_groups=groups_for_event,
                            ordering_authority=OrderingAuthority.EXPLICIT_GLOBAL_SEQUENCE,
                            chosen_path_id=chosen_path_id,
                        )
                    )
                    next_sequence += 1
                    progress = True
                    continue
                if pending_derived and allow_derived_ordering:
                    pending_derived.sort(
                        key=lambda item: (
                            item[0].occurred_at,
                            item[0].stream.value,
                            item[0].identity_key(),
                        )
                    )
                    (
                        observation,
                        paths,
                        groups_for_event,
                        chosen_path_id,
                    ) = pending_derived.pop(0)
                    receipts.append(
                        self._append_canonical(
                            observation,
                            canonical_sequence=next_sequence,
                            supporting_paths=paths,
                            supporting_groups=groups_for_event,
                            ordering_authority=OrderingAuthority.DERIVED_DETERMINISTIC_ORDER,
                            chosen_path_id=chosen_path_id,
                        )
                    )
                    next_sequence += 1
                    progress = True

            gap_pending = sorted(sequence for sequence in pending_explicit if sequence > next_sequence)
            if gap_pending:
                conn = self._conn()
                conn.execute("BEGIN IMMEDIATE")
                try:
                    for sequence, (observation, _, _, _) in pending_explicit.items():
                        conn.execute(
                            """
                            UPDATE ao_capture_candidates
                            SET reconciliation_state=?,updated_at=?
                            WHERE conversation_key=? AND identity_key=?
                            """,
                            (
                                ReconciliationState.GAP_PENDING.value,
                                _now(),
                                key,
                                observation.identity_key(),
                            ),
                        )
                    self._audit(
                        conn,
                        key,
                        "SOURCE_SEQUENCE_GAP_PENDING",
                        {
                            "next_expected_sequence": next_sequence,
                            "pending_explicit_sequences": gap_pending,
                        },
                    )
                    conn.execute("COMMIT")
                except Exception:
                    conn.execute("ROLLBACK")
                    raise
                self._finding(
                    key,
                    "SOURCE_SEQUENCE_GAP",
                    severity="HIGH",
                    references=[str(next_sequence)] + [str(item) for item in gap_pending],
                    detail={
                        "next_expected_sequence": next_sequence,
                        "pending_explicit_sequences": gap_pending,
                    },
                )

            if not gap_pending:
                self._resolve_open_findings_by_type(
                    key,
                    "SOURCE_SEQUENCE_GAP",
                    resolution="All previously pending explicit sequences are now canonicalised.",
                )

            result = {
                "state": (
                    "RECONCILIATION_CONFLICTED"
                    if conflicts
                    else "RECONCILIATION_VERIFIED"
                ),
                "conversation_key": key,
                "namespace_key": namespace,
                "receipts": receipts,
                "conflicts": conflicts,
                "next_expected_sequence": next_sequence,
                "pending_explicit_sequences": gap_pending,
                "pending_derived_count": len(pending_derived),
                "ledger_before": ledger_status,
                "ledger_after": self.ledger.verify(key),
                "failover_plan": self.rank_paths(key),
            }
            return result

    def capture(
        self,
        observations: Iterable[CaptureObservation],
        *,
        allow_derived_ordering: bool = True,
        source_provider: str = "CHATGPT",
        title: str = "",
    ) -> Dict[str, Any]:
        items = list(observations)
        if not items:
            return {"state": "NO_OBSERVATIONS", "staged": [], "reconciliation": {}}
        keys = {_key(item.conversation_key, "conversation_key") for item in items}
        namespaces = {_namespace(item.namespace_key) for item in items}
        if len(keys) != 1 or len(namespaces) != 1:
            raise ConversationIdentityConflict(
                "one capture batch must target one exact conversation and namespace"
            )
        staged = [self._stage(item) for item in items]
        reconciliation = self.reconcile(
            items[0].conversation_key,
            items[0].namespace_key,
            allow_derived_ordering=allow_derived_ordering,
            source_provider=source_provider,
            title=title,
        )
        return {
            "state": (
                "CAPTURE_CONFLICTED"
                if reconciliation["conflicts"]
                else "CAPTURE_RECONCILED_VERIFIED"
            ),
            "conversation_key": items[0].conversation_key,
            "namespace_key": _namespace(items[0].namespace_key),
            "staged": staged,
            "reconciliation": reconciliation,
            "assessment": self.assess(items[0].conversation_key),
        }

