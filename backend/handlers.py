"""Import modules that register job handlers and event consumers."""

from backend.worker import registry

__all__ = ["registry"]
