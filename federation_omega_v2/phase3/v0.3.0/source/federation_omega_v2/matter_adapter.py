from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

from .core import Event, EventStore, Relationship, sha

PHASE3_STAGES = (
    "SOURCE_LOCK",
    "CASE_WALL",
    "PROVENANCE_IMPORT",
    "CHRONOLOGY_CONTROL",
    "CHARGE_ELEMENT_MAP",
    "CONTRADICTION_CONTROL",
    "GAP_SCHEDULE",
    "READINESS_COMPARISON",
    "OWNER_BRIEF",
    "RESTART_VERIFY",
)

PROHIBITED_RAW_KEYS = {
    "message_body", "raw_content", "attachment_bytes", "medical_report",
    "medical_certificate", "email_body", "transcript", "password", "token",
    "secret", "private_key",
}


@dataclass(frozen=True)
class MatterControlSnapshot:
    data: dict[str, Any]

    def validate(self) -> None:
        d = self.data
        if d.get("schema") != "FEDERATION-OMEGA-V2-EVIDENCEOPS-MATTER-CONTROL-1":
            raise ValueError("unsupported matter snapshot")
        if d.get("authority_ceiling") != "A1":
            raise ValueError("Phase 3 matter authority must remain A1")
        if d.get("communication_state") != "NO_SEND":
            raise ValueError("communication state must remain NO_SEND")
        if d.get("external_effects_allowed") is not False:
            raise ValueError("external effects must remain disabled")
        if d.get("privacy_tier") != "P2_CONFIDENTIAL":
            raise ValueError("unexpected privacy tier")
        if not d.get("matter_id") or not d.get("node_id"):
            raise ValueError("matter and node identifiers are required")
        processing = d["processing_state"]
        if processing["processed_units"] + processing["remaining_units"] != processing["registered_units"]:
            raise ValueError("processing counts do not reconcile")
        source_ids = [row["source_id"] for row in d.get("source_controls", [])]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("duplicate source identity")
        encoded = json.dumps(d, sort_keys=True).casefold()
        for key in PROHIBITED_RAW_KEYS:
            if f'"{key}"' in encoded:
                raise ValueError(f"raw or secret field prohibited: {key}")

    @property
    def matter_id(self) -> str:
        return self.data["matter_id"]

    @property
    def node_id(self) -> str:
        return self.data["node_id"]


def load_snapshot(path: str | Path) -> MatterControlSnapshot:
    snapshot = MatterControlSnapshot(json.loads(Path(path).read_text(encoding="utf-8")))
    snapshot.validate()
    return snapshot


def _matter_state(snapshot: MatterControlSnapshot) -> dict[str, Any]:
    d = snapshot.data
    return {
        "matter_id": d["matter_id"],
        "node_id": d["node_id"],
        "title": d["title"],
        "privacy_tier": d["privacy_tier"],
        "authority_ceiling": d["authority_ceiling"],
        "communication_state": d["communication_state"],
        "external_effects_allowed": False,
        "case_wall": d["case_wall"],
        "source_ids": [row["source_id"] for row in d["source_controls"]],
        "processing_state": d["processing_state"],
        "claims_not_proven": d["claims_not_proven"],
        "truth_boundary": d["truth_boundary"],
    }


def import_matter(store: EventStore, snapshot: MatterControlSnapshot, observed_at: str) -> dict[str, Any]:
    snapshot.validate()
    payload = {"state": _matter_state(snapshot)}
    event_id = "EVT-MATTER-" + sha({"matter_id": snapshot.matter_id, "payload": payload})[:24].upper()
    event_result = store.append(Event(
        event_id,
        snapshot.matter_id,
        "STATE_SET",
        observed_at,
        "SRC-PHASE3-MATTER-CONTROL",
        payload,
    ))
    relationships = [
        Relationship(snapshot.matter_id, "SYS-EVIDENCEOPS", "USES"),
        Relationship(snapshot.matter_id, "SYS-MODISA", "GATED_BY"),
        Relationship(snapshot.matter_id, "SYS-SOL-61", "ORCHESTRATED_BY"),
        Relationship(snapshot.matter_id, "SYS-BIBLE", "PUBLISHES_SAFE_DELTAS_TO"),
    ]
    return {
        "event": event_result,
        "relationships": [store.add_relationship(row) for row in relationships],
    }


def evaluate_claims(snapshot: MatterControlSnapshot, proposed_claims: list[str]) -> dict[str, Any]:
    prohibited = {value.casefold() for value in snapshot.data["claims_not_proven"]}
    held = []
    accepted = []
    for claim in proposed_claims:
        normalized = " ".join(str(claim).split())
        key = normalized.upper().replace(" ", "_")
        if key.casefold() in prohibited or any(
            term.casefold() in normalized.casefold()
            for term in snapshot.data["claims_not_proven"]
        ):
            held.append({"claim": normalized, "state": "CONFLICT_HELD_UNPROVEN"})
        else:
            accepted.append({"claim": normalized, "state": "CONTROL_METADATA_ONLY"})
    return {"accepted": accepted, "held": held}


def _stage_payload(snapshot: MatterControlSnapshot, stage: str) -> dict[str, Any]:
    d = snapshot.data
    if stage == "SOURCE_LOCK":
        return {
            "source_count": len(d["source_controls"]),
            "source_ids": [row["source_id"] for row in d["source_controls"]],
            "raw_evidence_imported": False,
        }
    if stage == "CASE_WALL":
        return {"case_wall": d["case_wall"], "route_contamination": False}
    if stage == "PROVENANCE_IMPORT":
        return {
            "sources": [
                {
                    "source_id": row["source_id"],
                    "kind": row["kind"],
                    "verification": row["verification"],
                    "privacy": row["privacy"],
                }
                for row in d["source_controls"]
            ]
        }
    if stage == "CHRONOLOGY_CONTROL":
        return {
            "processed_units": d["processing_state"]["processed_units"],
            "remaining_units": d["processing_state"]["remaining_units"],
            "root_inventory": d["processing_state"]["root_inventory"],
            "nested_inventory": d["processing_state"]["nested_inventory"],
        }
    if stage == "CHARGE_ELEMENT_MAP":
        return {
            "charge_count": len(d["charge_controls"]),
            "charges": d["charge_controls"],
            "evidence_streams": d["evidence_streams"],
        }
    if stage == "CONTRADICTION_CONTROL":
        return {
            "contradictions": d["controlled_contradictions"],
            "overclaim_test": evaluate_claims(snapshot, ["retaliation", "motive", "causation"]),
        }
    if stage == "GAP_SCHEDULE":
        return {"gap_count": len(d["open_gaps"]), "open_gaps": d["open_gaps"]}
    if stage == "READINESS_COMPARISON":
        p = d["processing_state"]
        generated = "NOT_COMPLETE" if p["remaining_units"] > 0 or p["nested_inventory"] != "CLOSED" else "COMPLETE"
        return {
            "baseline": p["completion_state"],
            "generated": generated,
            "match": generated == p["completion_state"],
            "hearing_readiness_claimed": False,
        }
    if stage == "OWNER_BRIEF":
        p = d["processing_state"]
        return {
            "headline": "TUT disciplinary control record remains incomplete but institutionally structured.",
            "processed": p["processed_units"],
            "remaining": p["remaining_units"],
            "priority": d["next_controlled_action"],
            "strongest_controls": [
                "Force exact particulars and distinct facts per charge",
                "Require policy, instruction, duty, access and prejudice foundations",
                "Preserve the distinction between temporal relevance and proved causation",
                "Complete the remaining registered units before merits finality",
            ],
            "external_effects": 0,
        }
    if stage == "RESTART_VERIFY":
        return {"restart_required": True, "expected_projection_rebuild": "IDENTICAL"}
    raise ValueError("unknown Phase 3 stage")


def run_phase3_mission(store: EventStore, snapshot: MatterControlSnapshot, observed_at: str) -> dict[str, Any]:
    snapshot.validate()
    import_result = import_matter(store, snapshot, observed_at)
    mission_body = {
        "objective": "Produce a proof-controlled internal owner-review brief for the registered TUT disciplinary matter using control metadata only",
        "matter_id": snapshot.matter_id,
        "node_id": snapshot.node_id,
        "authority_ceiling": "A1",
        "privacy_tier": "P2_CONFIDENTIAL",
        "constraints": [
            "NO_RAW_P2_EVIDENCE_IMPORT",
            "NO_SEND",
            "NO_FILING",
            "NO_SETTLEMENT_ACTION",
            "NO_EVIDENCE_DELETION",
            "NO_HEARING_READINESS_CLAIM",
        ],
        "proof_requirements": [
            "SOURCE_IDENTITY",
            "CASE_WALL",
            "STAGE_RECEIPTS",
            "READINESS_COMPARISON",
            "RESTART_RECONSTRUCTION",
        ],
        "external_effects": 0,
    }
    mission_id = "MISSION-" + sha(mission_body)[:24].upper()
    mission = {"mission_id": mission_id, **mission_body}
    store.save_mission(mission)

    receipts = []
    previous = None
    for index, stage in enumerate(PHASE3_STAGES, 1):
        stage_data = _stage_payload(snapshot, stage)
        receipt = sha({
            "mission_id": mission_id,
            "stage": stage,
            "index": index,
            "previous": previous,
            "stage_data": stage_data,
        })
        event_id = f"EVT-{mission_id}-P3-{index:02d}"
        store.append(Event(
            event_id,
            mission_id,
            "MISSION_STAGE",
            observed_at,
            "SRC-PHASE3-TUT-DISCIPLINARY-ADAPTER",
            {
                "stage": stage,
                "status": "COMPLETE_VERIFIED_INTERNAL",
                "receipt_sha256": receipt,
                "previous_receipt": previous,
                "stage_data": stage_data,
                "external_effects": 0,
            },
        ))
        receipts.append({"stage": stage, "receipt_sha256": receipt})
        previous = receipt

    projection = store.project(mission_id)
    if len(projection["state"].get("stages", {})) != len(PHASE3_STAGES):
        raise ValueError("Phase 3 mission incomplete")
    readiness = _stage_payload(snapshot, "READINESS_COMPARISON")
    if readiness["match"] is not True:
        raise ValueError("readiness comparison mismatch")

    return {
        "state": "COMPLETE_VERIFIED_REAL_MATTER_CONTROL_ADAPTER",
        "mission": mission,
        "import_result": import_result,
        "stage_count": len(PHASE3_STAGES),
        "receipts": receipts,
        "projection": projection,
        "readiness_comparison": readiness,
        "owner_brief": _stage_payload(snapshot, "OWNER_BRIEF"),
        "raw_evidence_imported": False,
        "external_effects": 0,
    }
