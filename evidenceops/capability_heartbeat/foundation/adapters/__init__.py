"""Read-only local adapters. They accept paths, never callbacks or executables."""

from .formation_state import read_formation_state
from .local_bible import read_local_bible
from .local_repo import read_local_repo

__all__ = ["read_formation_state", "read_local_bible", "read_local_repo"]
