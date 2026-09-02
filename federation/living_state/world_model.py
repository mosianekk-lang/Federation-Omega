from __future__ import annotations

"""Compatibility facade for Federation Living State & Evolution Fabric v1."""

from .types import *  # noqa: F401,F403
from .transition_model import TransitionAwareLivingWorldModel as LivingWorldModel  # noqa: F401
from .canary import learning_event, run_living_fabric_canary  # noqa: F401
