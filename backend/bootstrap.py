"""Import modules that register rules, job handlers, event consumers and case
detail providers. The API and the worker both call ``load()`` at start-up."""

from __future__ import annotations

import importlib

_MODULES = ("backend.policies.rules_common",)


def load() -> None:
    for name in _MODULES:
        importlib.import_module(name)
