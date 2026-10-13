"""Helpers shared by test modules."""

from __future__ import annotations

import os

import pytest

BACKEND = os.environ.get("FINGUARD_TEST_BACKEND", "postgres")

pg_only = pytest.mark.skipif(BACKEND == "sqlite", reason="row-level security requires PostgreSQL")
