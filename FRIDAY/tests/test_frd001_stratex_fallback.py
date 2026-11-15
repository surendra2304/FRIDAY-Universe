"""TASK-FRD-001: the portfolio tool must not serve retired engines' state.

Production evidence (live conversation audit, 2026-11-15): on live-query
timeouts the fallback rendered ``Stratex/testnet_heartbeat.json`` — the
classic-testnet engine retired in TASK-STR-RETIRE-001, frozen at
2026-11-14T21:31:34Z — as the "last known engine state": balance
4,978.19, engine STOPPED, active strategies bb_reversion +
factory_winner_1..5 (deleted), while the live demo-fapi daemon was
trading. 3 of 9 portfolio questions in the audit hit this fallback.
The honest behaviour on failure is: no snapshot, say so plainly.
"""
import json
from pathlib import Path

from friday.tools.builtin.stratex_portfolio import (
    _read_local_snapshot,
    _unavailable_content,
)

_RETIRED_HEARTBEAT = {
    "timestamp": "2026-11-14T21:31:34.747351Z",
    "status": "STOPPED",
    "mode": "TESTNET",
    "current_equity": 4978.19,
    "open_positions": 0,
    "binance_connected": True,
    "strategies": ["bb_reversion", "factory_winner_1", "factory_winner_2"],
}


def _seed_state_dir(tmp_path: Path) -> None:
    (tmp_path / "testnet_heartbeat.json").write_text(
        json.dumps(_RETIRED_HEARTBEAT), encoding="utf-8"
    )
    (tmp_path / "heartbeat.json").write_text(
        json.dumps(_RETIRED_HEARTBEAT), encoding="utf-8"
    )


def test_retired_heartbeats_are_not_a_snapshot(tmp_path, monkeypatch):
    _seed_state_dir(tmp_path)
    monkeypatch.setenv("FRIDAY_STRATEX_STATE_DIR", str(tmp_path))
    assert _read_local_snapshot() is None


def test_unavailable_content_reports_no_recorded_state(tmp_path, monkeypatch):
    _seed_state_dir(tmp_path)
    monkeypatch.setenv("FRIDAY_STRATEX_STATE_DIR", str(tmp_path))
    content, fields = _unavailable_content(
        "Stratex could not answer that: ReadTimeout", "portfolio"
    )
    assert fields is None
    assert "bb_reversion" not in content
    assert "4,978" not in content
    assert "nothing was invented" in content
