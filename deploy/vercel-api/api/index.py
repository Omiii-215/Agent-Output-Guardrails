"""Vercel entry point for the FinGuard API (serverless mode).

The build script copies ``apps/`` and ``backend/`` next to this folder; jobs run
inline after each request and documents live in PostgreSQL (see README).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps.api.main import app  # noqa: F401
