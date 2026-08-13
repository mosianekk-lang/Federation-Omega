from __future__ import annotations

from .registry import FederationRegistry, ProjectRecord, EvidenceRecord
from .dedup import FederationDeduplicator, fingerprint
from .capabilities import install_defaults
from .bootstrap import build_chat_shim
from .inheritance import project_capsule

VERSION = "4.0.0"


class FederationGovernor:
    def __init__(self, db_path: str = "bubbles_federation_governor_omega4.sqlite3") -> None:
        self.registry = FederationRegistry(db_path)
        self.dedup = FederationDeduplicator(self.registry)
        install_defaults(self.registry)

    def register_project(self, project_id: str, name: str, matter_wall: str, profile: str = "DEFAULT") -> None:
        self.registry.register_project(ProjectRecord(project_id, name, matter_wall, profile))

    def register_mission(self, **kwargs) -> None:
        self.registry.register_mission(**kwargs)

    def bootstrap_chat(self, **kwargs):
        return build_chat_shim(self.registry, VERSION, **kwargs)

    def inheritance_capsule(self, project_id: str):
        return project_capsule(self.registry, VERSION, project_id)

    def select_capabilities(self, tags, max_results: int = 4):
        return self.registry.resolve_capabilities(tags, max_results=max_results)

    def preflight_work(self, **kwargs):
        return self.dedup.preflight(**kwargs)

    def put_evidence(self, record: EvidenceRecord) -> None:
        self.registry.put_evidence(record)

    def record_work(self, *, project_id: str, mission_id: str, objective: str,
                    proof_gap: str, action: str, target: str, state: str,
                    source_version: str = "", result_pointer: str = "", semantic_ok: bool = True) -> str:
        key = fingerprint(project_id=project_id, objective=objective, proof_gap=proof_gap,
                          action=action, target=target, source_version=source_version)
        self.registry.save_receipt(fingerprint=key, project_id=project_id, mission_id=mission_id,
                                   state=state, source_version=source_version,
                                   result_pointer=result_pointer, semantic_ok=semantic_ok)
        return key
