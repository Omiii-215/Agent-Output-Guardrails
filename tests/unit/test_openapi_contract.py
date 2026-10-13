from pathlib import Path

from scripts.export_openapi import TARGET, render


def test_committed_openapi_contract_is_current():
    """Regenerate with: PYTHONPATH=. uv run python scripts/export_openapi.py"""
    assert Path(TARGET).read_text() == render()
