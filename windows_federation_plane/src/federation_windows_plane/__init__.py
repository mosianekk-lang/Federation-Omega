"""Federation Windows Execution Plane v1."""

from .executor import WindowsPlane
from .models import TaskEnvelope, TaskReceipt

__all__ = ["TaskEnvelope", "TaskReceipt", "WindowsPlane"]
__version__ = "1.0.0"
