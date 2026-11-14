"""TASK-REL-007: Futuris must declare its hard pyarrow dependency.

Production failure (2026-11-14, found while verifying the Futuris 500 fix):
after the Oracle JSON crash was repaired, ``POST /v1/friday/forecast`` still
500'd — ``futuris/evidence/snapshots.py`` freezes every forecast evidence
snapshot with ``df.to_parquet(..., engine="pyarrow")``, but pyarrow was
declared in neither ``Futuris/requirements.txt`` nor
``Futuris/pyproject.toml``. Any environment built from Futuris' own
dependency declarations therefore cannot complete a forecast. These tests
pin the declaration so the dependency cannot silently disappear again.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FUTURIS = REPO_ROOT / "Futuris"


def test_pyarrow_declared_in_requirements():
    text = (FUTURIS / "requirements.txt").read_text(encoding="utf-8")
    declared = {
        line.strip().split("=")[0].split(">")[0].split("<")[0].strip().lower()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    assert "pyarrow" in declared


def test_pyarrow_declared_in_pyproject():
    text = (FUTURIS / "pyproject.toml").read_text(encoding="utf-8")
    assert '"pyarrow' in text


def test_snapshot_writer_really_requires_pyarrow():
    """Guard against the declaration becoming vestigial in the other
    direction: if the parquet engine ever changes, update this test and the
    declarations together."""
    source = (FUTURIS / "futuris" / "evidence" / "snapshots.py").read_text(encoding="utf-8")
    assert 'engine="pyarrow"' in source
