"""Write the API contract to contracts/openapi.json (the web client is generated from it).

PYTHONPATH=. uv run python scripts/export_openapi.py
"""

from __future__ import annotations

import json
from pathlib import Path

from apps.api.main import create_app
from backend.config import Settings

TARGET = Path(__file__).resolve().parents[1] / "contracts" / "openapi.json"


def render() -> str:
    app = create_app(Settings(env="test", database_url="sqlite:///:memory:"))
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    TARGET.write_text(render())
    print(f"wrote {TARGET}")
