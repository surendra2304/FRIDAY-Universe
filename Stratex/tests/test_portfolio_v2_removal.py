"""
tests/test_portfolio_v2_removal.py — TASK-STR-FWD-033 regression coverage.

Stratex/portfolio_v2 (oanda_client plus its dead-only callers engine /
backtest / risk and sole-support files config / strategy / indicators /
__init__) was proven dead (issue #35 comment 7058854400: only references
were siblings inside the same package, no live path, no test, no runner
since 2026-11-13) and removed as a unit. This test pins the removal: the
package directory must not exist, and no Python file anywhere in the repo
may reference portfolio_v2 or oanda_client again.

Dated history logs (docs/collaboration/qa_loop/STATE.md, ACTIVITY_LOG.md)
still name the package and are intentionally untouched, so the scan covers
*.py files only. This file itself contains the forbidden strings, so it is
excluded from the scan.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STRATEX_ROOT = REPO_ROOT / "Stratex"

FORBIDDEN = ("portfolio_v2", "oanda_client")


def _python_files():
    for path in REPO_ROOT.rglob("*.py"):
        if ".git" in path.parts:
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        yield path


def test_portfolio_v2_directory_is_gone():
    assert not (STRATEX_ROOT / "portfolio_v2").exists()


def test_no_python_file_references_portfolio_v2_or_oanda_client():
    offenders = []
    for path in _python_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        hits = [token for token in FORBIDDEN if token in text]
        if hits:
            offenders.append(f"{path.relative_to(REPO_ROOT)}: {', '.join(hits)}")
    assert not offenders, (
        "dead portfolio_v2 references resurrected:\n" + "\n".join(offenders)
    )
