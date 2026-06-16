from __future__ import annotations


class WorkflowError(ValueError):
    """Raised when GCW event history cannot be reduced into a valid projection."""

