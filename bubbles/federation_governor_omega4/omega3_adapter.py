from __future__ import annotations

from bubbles.chat_governor_omega3 import DurableState, MissionCompiler


class Omega3ProjectAdapter:
    """Create mission-local Ω3 plans from an Ω4 project/mission record."""

    def __init__(self, db_path: str = "bubbles_chat_governor_omega3.sqlite3") -> None:
        self.state = DurableState(db_path)
        self.compiler = MissionCompiler(self.state)

    def compile(self, mission_record, specialists=(), connectors=()):
        return self.compiler.compile(
            mission_record["objective"],
            mission_id=mission_record["mission_id"],
            required_specialists=list(specialists) or None,
            required_connectors=list(connectors) or None,
        )
