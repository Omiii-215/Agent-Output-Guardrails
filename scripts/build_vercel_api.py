"""Assemble deploy/vercel-api for `vercel deploy`.

Copies the API and backend code next to the Vercel entry point and pins the
runtime dependencies from uv.lock (no dev tools).

    PYTHONPATH=. uv run python scripts/build_vercel_api.py
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "deploy" / "vercel-api"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "tests")


def main() -> int:
    for name in ("apps", "backend"):
        shutil.rmtree(OUT / name, ignore_errors=True)
    (OUT / "apps").mkdir(parents=True)
    shutil.copy2(ROOT / "apps" / "__init__.py", OUT / "apps" / "__init__.py")
    shutil.copytree(ROOT / "apps" / "api", OUT / "apps" / "api", ignore=IGNORE)
    shutil.copytree(ROOT / "backend", OUT / "backend", ignore=IGNORE)
    subprocess.run(
        [
            "uv",
            "export",
            "--frozen",
            "--no-dev",
            "--no-hashes",
            "--no-emit-project",
            "--output-file",
            str(OUT / "requirements.txt"),
        ],
        check=True,
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
    )
    print(f"built {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
