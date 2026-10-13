"""Worker entry point.

Runs the durable job loop from the same codebase as the API. Job handlers are
registered by backend modules (see ``backend/handlers.py``).
"""

from __future__ import annotations

import argparse
import logging

from backend import handlers  # noqa: F401  (registers handlers)
from backend.config import get_settings
from backend.runtime import build_runtime
from backend.telemetry.tracing import configure_logging
from backend.worker import run_forever, run_once

log = logging.getLogger("finguard.worker")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FinGuard durable job worker")
    parser.add_argument("--once", action="store_true", help="process available jobs and exit")
    args = parser.parse_args(argv)
    configure_logging()
    settings = get_settings()
    runtime = build_runtime(settings)
    log.info("worker starting in %s", settings.env)
    if args.once:
        log.info("processed %d jobs", run_once(runtime))
        return 0
    run_forever(runtime)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
