from pathlib import Path

from modisa_v2.schemas import EvidenceIngestRequest, ProofAppendRequest, ProofType


def test_backup_and_restore_canary(services, settings, tmp_path: Path):
    matter_id, mission_id = "MAT-B", "MIS-B"
    services.repo.ensure_matter(matter_id)
    source = settings.data_root / "backup-evidence.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("backup evidence", encoding="utf-8")
    services.vault.ingest(
        EvidenceIngestRequest(matter_id=matter_id, mission_id=mission_id, path=str(source)),
        "owner",
    )
    services.ledger.append(
        ProofAppendRequest(
            matter_id=matter_id,
            mission_id=mission_id,
            proof_type=ProofType.MISSION_SCOPE,
            subject_id=mission_id,
            actor_id="owner",
            payload={"scope": "backup test"},
        )
    )
    destination = tmp_path / "snapshot"
    manifest = services.backup.create_snapshot(
        matter_id=matter_id,
        mission_id=mission_id,
        actor_id="owner",
        destination=destination,
    )
    assert manifest["evidence"]
    proof_id = services.backup.restore_canary(
        matter_id=matter_id,
        mission_id=mission_id,
        actor_id="owner",
        snapshot_dir=destination,
    )
    assert services.ledger.get(proof_id).proof_type == ProofType.RESTORE_CANARY
