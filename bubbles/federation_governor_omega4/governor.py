from __future__ import annotations

from .registry import FederationRegistry
from .dedup import FederationDeduplicator

VERSION = "4.0.0"

class FederationGovernor:
    def __init__(self, db_path: str = "bubbles_federation_governor_omega4.sqlite3") -> None:
        self.registry = FederationRegistry(db_path)
        self.dedup = FederationDeduplicator(self.registry)
