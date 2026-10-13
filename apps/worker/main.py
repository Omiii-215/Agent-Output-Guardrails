"""Worker entry point.

Runs the durable job loop from the same codebase as the API. Job handlers are
registered by backend modules; see ``backend/persistence/jobs.py``.
"""

from __future__ import annotations

import argparse
import logging

from backend.config import get_settings
from backend.telemetry.tracing import configure_logging

log = logging.getLogger("finguard.worker")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FinGuard durable job worker")
    parser.add_argument("--once", action="store_true", help="process available jobs and exit")
    parser.parse_args(argv)
    configure_logging()
    settings = get_settings()
    log.info("worker starting in %s", settings.env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
