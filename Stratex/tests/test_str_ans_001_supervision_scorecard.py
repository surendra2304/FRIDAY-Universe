"""TASK-STR-ANS-001 (Stratex side): the supervision payload carries the ledger.

FRIDAY's portfolio answers could only ever be as substantive as the
payload Stratex hands her. The supervision status carried balances and
positions but no recorded P&L, so "how is my portfolio doing" had no
ledger numbers to render. ``_get_engine_status_summary`` now includes a
compact ``ledger_scorecard`` block computed from the phase-2 fill ledger
(measurement.scorecard.build_scorecard — the same generator behind
state/scorecard.json), failing soft: a broken ledger read omits the
block (None) instead of breaking the status answer.

The fixture card mirrors the real post-phase-2 ledger shape (LEGACY 3
owner-directed closes +195.71, one governed bb_reversion close +0.5437,
two RESET_BOUNDARY rows).
"""

from __future__ import annotations

import pytest

from measurement import scorecard


_FIXTURE_CARD = {
    "generated_at": "2026-11-15T00:00:00Z",
    "source": "state/fill_ledger.jsonl",
    "total_fills": 9,
    "fill_rows": 7,
    "close_rows": 4,
    "totals": {
        "trades": 4,
        "wins": 3,
        "losses": 1,
        "win_rate": 0.75,
        "gross_profit": 229.99,
        "gross_loss": -33.74,
        "net_pnl": 196.25,
        "fees": 0.0,
        "expectancy_gross_per_trade": 49.06,
        "expectancy_net_per_trade": 49.06,
        "profit_factor": 6.82,
        "max_drawdown": 33.74,
    },
    "strategies": {
        "LEGACY-UNATTRIBUTED": {"trades": 3, "net_pnl": 195.71, "profit_factor": 6.77, "win_rate": 0.67},
        "bb_reversion": {"trades": 1, "net_pnl": 0.54, "profit_factor": None, "win_rate": 1.0},
    },
    "venues": {},
    "reset_boundaries": [{"kind": "RESET_BOUNDARY"}, {"kind": "RESET_BOUNDARY"}],
    "unattributed_closes": 3,
}


def test_ledger_block_shapes_the_scorecard_compactly(monkeypatch):
    from api import friday_supervision

    monkeypatch.setattr(scorecard, "build_scorecard", lambda *a, **k: dict(_FIXTURE_CARD))
    block = friday_supervision._ledger_scorecard_block()

    assert block is not None
    assert block["totals"]["trades"] == 4
    assert block["totals"]["net_pnl"] == 196.25
    assert block["totals"]["profit_factor"] == 6.82
    assert block["strategies"]["LEGACY-UNATTRIBUTED"]["net_pnl"] == 195.71
    assert block["strategies"]["bb_reversion"]["trades"] == 1
    assert block["reset_boundaries"] == 2
    assert block["total_fills"] == 9
    # The bulky raw rows must NOT ride along in a status payload.
    assert "fill_rows" not in block and "venues" not in block


def test_ledger_block_fails_soft_when_the_ledger_read_breaks(monkeypatch):
    from api import friday_supervision

    def _boom(*a, **k):
        raise RuntimeError("ledger unreadable")

    monkeypatch.setattr(scorecard, "build_scorecard", _boom)
    assert friday_supervision._ledger_scorecard_block() is None


def test_supervision_status_endpoint_carries_the_ledger_block(monkeypatch):
    """End to end through the real Flask route FRIDAY polls."""
    monkeypatch.setattr(scorecard, "build_scorecard", lambda *a, **k: dict(_FIXTURE_CARD))
    from dashboard import app

    app.config["TESTING"] = True
    with app.test_client() as client:
        res = client.get("/v1/friday/supervision/status")

    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["engine"] == "Stratex"
    block = data.get("ledger_scorecard")
    assert block is not None, "supervision payload must carry the ledger scorecard"
    assert block["totals"]["trades"] == 4
    assert block["totals"]["net_pnl"] == 196.25
