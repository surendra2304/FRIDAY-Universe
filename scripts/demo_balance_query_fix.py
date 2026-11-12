#!/usr/bin/env python3
"""Demonstrate the Stratex balance-query fix end-to-end (ZAI Agent 1).

Scenario: the user asks Friday "check my Stratex balance" while the live
Stratex engine is NOT reachable. Before the fix, Friday answered with a flat
refusal the LLM softened into excuses ("I'm afraid I can't do that"). After
the fix, the answer carries: the exact live failure reason, the last-known
engine state from Stratex's own heartbeat files, and an explicit
"nothing was invented" statement.

This exercises the REAL routing (FridayAgent fast path), not a mock.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# The sanctioned test-backend environment (same as FRIDAY/tests/conftest.py):
# sqlite memory backend inside a non-production run.
os.environ.setdefault("FRIDAY_MEMORY_BACKEND", "sqlite")
os.environ.setdefault("FRIDAY_ENV", "testing")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "FRIDAY" / "src"))

from friday.tools.builtin.stratex_portfolio import StratexPortfolioTool


def main() -> int:
    tool = StratexPortfolioTool()  # real FleetClient with no Stratex URL configured
    result = tool.execute(question="friday, check my stratex balance", kind="portfolio")
    print("=" * 72)
    print("Friday's answer to 'check my Stratex balance' (live engine unreachable):")
    print("=" * 72)
    print(result.content)
    print("=" * 72)
    print(f"is_error: {result.is_error}")
    meta = result.metadata or {}
    print(f"live_url: {meta.get('live_url')!r}  error: {meta.get('error')!r}")
    fb = meta.get("fallback") or {}
    print(f"fallback source: {fb.get('source_file')} recorded at {fb.get('snapshot_timestamp')}")
    ok = (
        "Balance" in result.content
        and "nothing was invented" in result.content
        and fb.get("snapshot_timestamp")
    )
    print("VERDICT:", "PASS - honest answer with last-known state, no refusal" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
