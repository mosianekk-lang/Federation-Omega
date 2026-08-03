from .development import Mnemosyne, Morphos
from .epistemic import Lucid, Noesis
from .learning import Janus, Symbiosis
from .simulation import Chimera, Polis
from .strategy import Argonaut, Polylogue

FRONTIER_SYSTEMS = [Noesis, Lucid, Mnemosyne, Morphos, Polis, Chimera, Argonaut, Polylogue, Janus, Symbiosis]

__all__ = [x.__name__ for x in FRONTIER_SYSTEMS] + ["FRONTIER_SYSTEMS"]
